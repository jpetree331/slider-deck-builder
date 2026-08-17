"""Render one slide end-to-end: bookkeeping via store, prompt via prompts,
pixels via the deck's chosen painter (gemini or nanogpt, resolved through
image_models), validation via Pillow, atomic PNG write.
"""
import io
import logging
import time
from datetime import datetime, timezone

from PIL import Image

from . import gemini, image_models, nanogpt, prompts, store

logger = logging.getLogger("lantern.render")

# Both providers' failures, for queue.py's except tuple — plain tuple on
# purpose, no shared base class until a third provider earns one.
RenderProviderError = (gemini.RenderError, nanogpt.RenderError)


class SlideNotFound(Exception):
    pass


class AlreadyRendering(Exception):
    """This slide is mid-render — maps to HTTP 409."""


def _find_slide(deck: dict, n: int) -> dict:
    for slide in deck["slides"]:
        if slide["n"] == n:
            return slide
    raise SlideNotFound(f"deck {deck['id']} has no slide {n}")


def render_slide(deck_id: str, n: int) -> dict:
    """Render slide n. Raises AlreadyRendering (409), SlideNotFound (404),
    or gemini.RenderError (503). On failure the slide's render block records
    the error and deck.json stays valid."""
    # 1. claim the slide (atomic, under LOCK, never across the network call)
    with store.LOCK:
        deck = store.load_deck(deck_id)
        slide = _find_slide(deck, n)
        if slide["render"] and slide["render"]["status"] == "rendering":
            raise AlreadyRendering(f"slide {n} is already rendering")
        model_id = deck["image_model"]
        slide["render"] = {"status": "rendering", "image": None, "prompt": None,
                           "model": model_id, "ms": None, "error": None,
                           "rendered_at": None, "cost_estimate_usd": None}
        store.save_deck(deck)
        prompt = prompts.compose_slide_prompt(deck["style_guide"], slide, n,
                                              len(deck["slides"]))
        size = deck["slide_size"]

    # 2. slide 1 is the style anchor: attach its PNG for n>1 when it exists
    style_ref = None
    if n > 1:
        anchor = store.slide_image_path(deck_id, 1)
        if anchor.exists():
            style_ref = anchor.read_bytes()

    # 3. paint (no lock held), validate, write atomically. resolve_model picks
    # the actual painter: text-only models auto-route to their edit twin when
    # a style ref rides along, so anchoring survives on every painter.
    t0 = time.monotonic()
    actual_cost = None
    try:
        resolved = image_models.resolve_model(model_id, size, style_ref is not None)
        if resolved.provider == "gemini":
            png = gemini.render_image(prompt, resolved.size, style_ref)
        else:
            png, actual_cost = nanogpt.render_image(resolved.id, prompt,
                                                    resolved.size, style_ref)
        img = Image.open(io.BytesIO(png))
        img.load()  # full decode — corrupt bytes never land on disk
        if img.format != "PNG":
            # painters return JPEG/WebP at will; slides/NN.png must BE png —
            # the first consumer to trust the extension (NanoGPT refs) 413'd
            out = io.BytesIO()
            (img if img.mode in ("RGB", "RGBA", "L") else img.convert("RGB")
             ).save(out, "PNG")
            png = out.getvalue()
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        with store.LOCK:
            deck = store.load_deck(deck_id)
            try:
                slide = _find_slide(deck, n)
            except SlideNotFound:  # slide edited away mid-render
                raise gemini.RenderError(str(e))
            slide["render"] = {"status": "error", "image": None, "prompt": prompt,
                               "model": model_id, "ms": ms,
                               "error": str(e), "rendered_at": None,
                               "cost_estimate_usd": None}
            store.save_deck(deck)
        logger.warning("slide %d of deck %s failed after %dms: %s", n, deck_id, ms, e)
        if isinstance(e, RenderProviderError):
            raise
        raise gemini.RenderError(f"render pipeline failure: {e}") from e

    ms = int((time.monotonic() - t0) * 1000)
    path = store.slide_image_path(deck_id, n)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".png.tmp")
    tmp.write_bytes(png)
    store.atomic_replace(tmp, path)  # retry-hardened for Windows readers

    # 4. record the full render block — the model that ACTUALLY painted (edit
    # twin included) and the metered cost when the provider reported one
    est = actual_cost if actual_cost is not None else resolved.price_usd
    with store.LOCK:
        deck = store.load_deck(deck_id)
        slide = _find_slide(deck, n)
        slide["render"] = {
            "status": "done",
            "image": f"slides/{store.slide_image_name(n)}",
            "prompt": prompt,
            "model": resolved.id,
            "ms": ms,
            "error": None,
            "rendered_at": datetime.now(timezone.utc).isoformat(),
            "cost_estimate_usd": est,
        }
        store.save_deck(deck)
        total = sum(s["render"]["cost_estimate_usd"] or 0 for s in deck["slides"]
                    if s["render"] and s["render"]["status"] == "done")
    logger.info("lantern.render: slide %d %s ~$%.3f (deck total ~$%.2f)",
                n, size, est, total)
    return slide
