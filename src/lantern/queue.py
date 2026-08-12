"""Render queue — ONE background worker thread, one job at a time.

Sequential is the *feature*: slide 1 must finish before 2..N can attach it
as their style reference. Deck-level job = ordered list of pending slide
numbers. All deck mutations go through store (invariant 2).

Semantics (from the brief):
- enqueue_deck skips slides already done — that's resume for free.
- First failing slide halts the deck's remaining queue; deck.status=error;
  everything already done stays done; render again to resume.
- cancel drains the deck's remaining jobs; the in-flight slide finishes.
"""
import logging
import threading
from collections import deque

from . import gemini, render_service, store

logger = logging.getLogger("lantern.queue")


class DeckBusy(Exception):
    """Deck (or that slide) already queued/rendering — maps to HTTP 409."""


_lock = threading.Lock()
_wake = threading.Condition(_lock)
_jobs: deque = deque()       # {"deck_id": str, "slides": [n, ...]}
_cancel: set = set()         # deck_ids with cancellation requested
_active_deck: str | None = None
_active_slide: int | None = None
_worker: threading.Thread | None = None


def _pending_block() -> dict:
    return {"status": "pending", "image": None, "prompt": None, "model": None,
            "ms": None, "error": None, "rendered_at": None,
            "cost_estimate_usd": None}


def _queued_slides(deck_id: str) -> set:
    """Slides queued or in flight for this deck. Call under _lock."""
    ns = set()
    if _active_deck == deck_id and _active_slide is not None:
        ns.add(_active_slide)
    for job in _jobs:
        if job["deck_id"] == deck_id:
            ns.update(job["slides"])
    return ns


def _finalize_deck(deck_id: str) -> None:
    """Settle deck.status from its slides; drop stale 'pending' marks."""
    def mutate(deck):
        for slide in deck["slides"]:
            render = slide["render"]
            if render and render["status"] in ("pending", "rendering"):
                slide["render"] = None
        statuses = [s["render"]["status"] if s["render"] else None
                    for s in deck["slides"]]
        if any(status == "error" for status in statuses):
            deck["status"] = "error"
        elif statuses and all(status == "done" for status in statuses):
            deck["status"] = "done"
        else:
            deck["status"] = "outline"  # partial/canceled — resumable
    try:
        store.update_deck(deck_id, mutate)
    except store.StoreError:
        pass  # deck deleted mid-flight — nothing to settle


def _process(job: dict) -> None:
    global _active_slide
    deck_id = job["deck_id"]
    halted = None
    for n in job["slides"]:
        with _lock:
            if deck_id in _cancel:
                halted = "cancel"
                break
            _active_slide = n
        try:
            render_service.render_slide(deck_id, n)
        except render_service.AlreadyRendering:
            logger.warning("slide %d of %s claimed elsewhere — skipping", n, deck_id)
        except (gemini.RenderError, render_service.SlideNotFound,
                store.StoreError) as e:
            logger.warning("deck %s halted at slide %d: %s", deck_id, n, e)
            halted = "error"
            break
    _finalize_deck(deck_id)
    with _lock:
        _active_slide = None
        _cancel.discard(deck_id)
    if halted:
        logger.info("deck %s stopped early (%s)", deck_id, halted)


def _run() -> None:
    global _active_deck
    while True:
        with _wake:
            while not _jobs:
                _wake.wait()
            job = _jobs.popleft()
            _active_deck = job["deck_id"]
        try:
            _process(job)
        except Exception:  # the worker must never die
            logger.exception("render worker crashed on deck %s", job["deck_id"])
            _finalize_deck(job["deck_id"])
        finally:
            with _lock:
                _active_deck = None


def _ensure_worker() -> None:
    """Call under _lock."""
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_run, daemon=True,
                                   name="lantern-render-worker")
        _worker.start()


def enqueue_deck(deck_id: str) -> dict:
    """Queue every not-yet-done slide, in order. 409 if the deck is busy."""
    with _lock:
        if _active_deck == deck_id or any(j["deck_id"] == deck_id for j in _jobs):
            raise DeckBusy(f"deck {deck_id} is already rendering")
    deck = store.load_deck(deck_id)  # DeckNotFound propagates to the API layer
    pending = [s["n"] for s in deck["slides"]
               if not (s["render"] and s["render"]["status"] == "done")]
    if not pending:
        return store.update_deck(deck_id, lambda d: d.update(status="done"))

    def mutate(d):
        d["status"] = "rendering"
        for slide in d["slides"]:
            if slide["n"] in pending:
                slide["render"] = _pending_block()
    deck = store.update_deck(deck_id, mutate)
    with _wake:
        if _active_deck == deck_id or any(j["deck_id"] == deck_id for j in _jobs):
            raise DeckBusy(f"deck {deck_id} is already rendering")
        _cancel.discard(deck_id)
        _jobs.append({"deck_id": deck_id, "slides": pending})
        _ensure_worker()
        _wake.notify()
    logger.info("queued deck %s: %d slide(s) %s", deck_id, len(pending), pending)
    return deck


def enqueue_slide(deck_id: str, n: int) -> dict:
    """Queue one slide (repaint). 409 only if THAT slide is already queued."""
    with _lock:
        if n in _queued_slides(deck_id):
            raise DeckBusy(f"slide {n} of deck {deck_id} is already queued")

    def mutate(d):
        for slide in d["slides"]:
            if slide["n"] == n:
                break
        else:
            raise render_service.SlideNotFound(f"deck {deck_id} has no slide {n}")
        d["status"] = "rendering"
        for slide in d["slides"]:
            if slide["n"] == n:
                slide["render"] = _pending_block()
    deck = store.update_deck(deck_id, mutate)
    with _wake:
        if n in _queued_slides(deck_id):
            raise DeckBusy(f"slide {n} of deck {deck_id} is already queued")
        _cancel.discard(deck_id)
        _jobs.append({"deck_id": deck_id, "slides": [n]})
        _ensure_worker()
        _wake.notify()
    logger.info("queued single slide %d of deck %s", n, deck_id)
    return deck


def cancel(deck_id: str) -> dict:
    """Drain the deck's queued work; the in-flight slide finishes on its own."""
    with _lock:
        _cancel.add(deck_id)
        stale = [j for j in _jobs if j["deck_id"] == deck_id]
        for job in stale:
            _jobs.remove(job)
        active_here = _active_deck == deck_id
    if not active_here:
        # nothing in flight — settle status now instead of waiting on the worker
        _finalize_deck(deck_id)
        with _lock:
            _cancel.discard(deck_id)
    logger.info("cancel requested for deck %s (%d queued job(s) drained)",
                deck_id, len(stale))
    return store.load_deck(deck_id)


def status() -> dict:
    with _lock:
        return {
            "active_deck": _active_deck,
            "active_slide": _active_slide,
            "queued": [{"deck_id": j["deck_id"], "slides": list(j["slides"])}
                       for j in _jobs],
        }
