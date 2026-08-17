"""Lantern deck store — the ONLY module that touches the deck folder layout.

Framework-free on purpose — no FastAPI imports — exercised headless by scripts/.
A deck IS a folder: data/decks/<id>/deck.json + slides/NN.png + exports/.
Every deck.json write is atomic: write deck.json.tmp, then os.replace
(Sacred Invariant 2). load_deck() sanitizes defensively — corrupt or partial
files coerce to safe defaults or raise a clean StoreError, never crash.
"""
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config, image_models

logger = logging.getLogger("lantern.store")

SLIDE_SIZES = ("1K", "2K", "4K")
DECK_STATUSES = ("outline", "rendering", "done", "error")
RENDER_STATUSES = ("pending", "rendering", "done", "error")

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_PALETTE = ["#0E1420", "#F2E9DC", "#D96C3A"]


class StoreError(Exception):
    """Clean, catchable failure — deck missing or unreadable."""


class DeckNotFound(StoreError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


# Brief spells it makeId — keep both names honest.
makeId = make_id


def decks_root() -> Path:
    return config.DATA_DIR / "decks"


def deck_dir(deck_id: str) -> Path:
    # Refuse path-traversal-shaped ids before they touch the filesystem.
    if not re.fullmatch(r"[A-Za-z0-9_-]+", deck_id or ""):
        raise DeckNotFound(f"invalid deck id: {deck_id!r}")
    return decks_root() / deck_id


def slides_dir(deck_id: str) -> Path:
    return deck_dir(deck_id) / "slides"


def exports_dir(deck_id: str) -> Path:
    return deck_dir(deck_id) / "exports"


# Slides store the painter's honest format (2026-08-17, see DECISIONS.md):
# painters generate JPEG almost always, and transcoding to PNG quintupled
# deck weight for zero quality gain. Position == filename still holds;
# only the extension varies.
SLIDE_IMAGE_EXTS = ("png", "jpg")


def slide_image_name(n: int, ext: str = "png") -> str:
    return f"{int(n):02d}.{ext}"


def slide_image_path(deck_id: str, n: int, ext: str = "png") -> Path:
    return slides_dir(deck_id) / slide_image_name(n, ext)


def find_slide_image(deck_id: str, n: int) -> Path | None:
    """The slide's image on disk, whatever honest extension it carries."""
    for ext in SLIDE_IMAGE_EXTS:
        path = slides_dir(deck_id) / slide_image_name(n, ext)
        if path.exists():
            return path
    return None


# ── sanitizers ──────────────────────────────────────────────────────────────

def _safe_str(v, default: str = "") -> str:
    return v if isinstance(v, str) else default


def _sanitize_palette(v) -> list:
    colors = [c for c in v if isinstance(c, str) and _HEX_RE.match(c)] if isinstance(v, list) else []
    return colors[:5] if len(colors) >= 3 else list(DEFAULT_PALETTE)


def _sanitize_style_guide(v) -> dict:
    v = v if isinstance(v, dict) else {}
    return {
        "palette": _sanitize_palette(v.get("palette")),
        "typography": _safe_str(v.get("typography")),
        "motif": _safe_str(v.get("motif")),
        "art_direction": _safe_str(v.get("art_direction")),
        "tone": _safe_str(v.get("tone")),
    }


def _sanitize_render(v):
    if not isinstance(v, dict):
        return None
    status = v.get("status")
    if status not in RENDER_STATUSES:
        logger.warning("dropping render block with bad status %r", status)
        return None
    return {
        "status": status,
        "image": _safe_str(v.get("image")) or None,
        "prompt": _safe_str(v.get("prompt")) or None,
        "model": _safe_str(v.get("model")) or None,
        "ms": v.get("ms") if isinstance(v.get("ms"), (int, float)) else None,
        "error": _safe_str(v.get("error")) or None,
        "rendered_at": _safe_str(v.get("rendered_at")) or None,
        "cost_estimate_usd": v.get("cost_estimate_usd")
        if isinstance(v.get("cost_estimate_usd"), (int, float)) else None,
    }


def _sanitize_slide(v, n: int):
    if not isinstance(v, dict):
        logger.warning("dropping malformed slide at position %d (not an object)", n)
        return None
    title = _safe_str(v.get("title"))
    visual = _safe_str(v.get("visual_description"))
    if not title and not visual:
        logger.warning("dropping malformed slide at position %d (no title, no visual)", n)
        return None
    points = v.get("points")
    points = [p for p in points if isinstance(p, str)] if isinstance(points, list) else []
    return {
        "n": n,
        "title": title,
        "points": points,
        "visual_description": visual,
        "layout_hint": _safe_str(v.get("layout_hint")),
        "render": _sanitize_render(v.get("render")),
    }


def sanitize_deck(raw, fallback_id: str = "") -> dict:
    """Coerce a loaded deck.json into a shape the app can always trust."""
    raw = raw if isinstance(raw, dict) else {}
    slides = []
    for item in raw.get("slides") if isinstance(raw.get("slides"), list) else []:
        s = _sanitize_slide(item, len(slides) + 1)
        if s is not None:
            slides.append(s)
    slide_size = raw.get("slide_size")
    if slide_size not in SLIDE_SIZES:
        slide_size = "2K"
    # pre-Painter decks have no field; unknown ids coerce to the default —
    # this clamp IS the migration, same as slide_size's
    image_model = raw.get("image_model")
    if image_model not in image_models.IMAGE_MODELS:
        image_model = image_models.DEFAULT_IMAGE_MODEL
    status = raw.get("status")
    if status not in DECK_STATUSES:
        status = "outline"
    now = _now()
    return {
        "id": _safe_str(raw.get("id")) or fallback_id or make_id("dk"),
        "title": _safe_str(raw.get("title"), "Untitled deck"),
        "topic": _safe_str(raw.get("topic")),
        "source_notes": _safe_str(raw.get("source_notes")),
        "style_guide": _sanitize_style_guide(raw.get("style_guide")),
        "slide_size": slide_size,
        "image_model": image_model,
        "aspect_ratio": "16:9",
        "status": status,
        "slides": slides,
        "created_at": _safe_str(raw.get("created_at"), now),
        "updated_at": _safe_str(raw.get("updated_at"), now),
    }


# One process, many threads (API + render worker): serialize every
# load-modify-save through this lock. Never hold it across a network call.
LOCK = threading.RLock()


def atomic_replace(src: Path, dst: Path, attempts: int = 6) -> None:
    """os.replace with a short retry ladder. On Windows, a concurrent reader
    holding the destination open (a 2s status poll, a thumbnail fetch, an
    antivirus scan) fails the swap with PermissionError; the window is
    milliseconds, so a bounded backoff absorbs it."""
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.02 * (attempt + 1))


def update_deck(deck_id: str, mutate):
    """Load → mutate(deck) → atomic save, under LOCK. Returns the saved deck.
    mutate may return a replacement dict or edit in place and return None."""
    with LOCK:
        deck = load_deck(deck_id)
        result = mutate(deck)
        return save_deck(result if isinstance(result, dict) else deck)


# ── slide patch semantics ───────────────────────────────────────────────────

_CONTENT_FIELDS = ("title", "points", "visual_description", "layout_hint")


def apply_slide_patches(deck: dict, patches: list) -> tuple[dict, list]:
    """Replace deck['slides'] with the patched, reordered list. Pure.

    Each patch dict may carry 'n' — the slide's CURRENT position — to claim
    that slide's identity (and its render block); n=None means a new slide.
    Positions renumber contiguously from 1 in the order given. A slide keeps
    its render block only if all content fields are untouched; otherwise the
    render is cleared to None, because the picture no longer matches the words.

    Returns (deck, moves) where moves is [(old_n, new_n), ...] for kept
    renders whose position changed — the caller must move the PNGs to match,
    because position == filename is the store layout.
    """
    existing = {s["n"]: s for s in deck["slides"]}
    new_slides, moves = [], []
    for i, patch in enumerate(patches):
        n = i + 1
        old = existing.pop(patch.get("n"), None)  # identity claims are one-shot
        slide = {
            "n": n,
            "title": _safe_str(patch.get("title")),
            "points": [p for p in patch.get("points", []) if isinstance(p, str)],
            "visual_description": _safe_str(patch.get("visual_description")),
            "layout_hint": _safe_str(patch.get("layout_hint")),
            "render": None,
        }
        if old is not None and all(slide[f] == old[f] for f in _CONTENT_FIELDS):
            slide["render"] = dict(old["render"]) if old["render"] else None
            if slide["render"] and old["n"] != n:
                moves.append((old["n"], n))
                if slide["render"].get("image"):
                    # re-key the position, keep the file's honest extension
                    old_name = slide["render"]["image"].rpartition("/")[2]
                    ext = old_name.rpartition(".")[2] or "png"
                    slide["render"]["image"] = f"slides/{slide_image_name(n, ext)}"
        new_slides.append(slide)
    deck["slides"] = new_slides
    return deck, moves


def patch_slides(deck_id: str, patches: list) -> dict:
    """Atomic PATCH: apply patches, move position-keyed PNGs two-phase,
    delete orphaned PNGs, save. The one entry point for slide edits."""
    with LOCK:
        deck = load_deck(deck_id)
        deck, moves = apply_slide_patches(deck, patches)
        sdir = slides_dir(deck_id)
        # two-phase rename so swaps can't collide; extension travels with file
        staged = []
        for old_n, new_n in moves:
            src = find_slide_image(deck_id, old_n)
            if src is not None:
                ext = src.suffix.lstrip(".")
                tmp = sdir / f"move-{new_n:02d}.tmp"
                atomic_replace(src, tmp)
                staged.append((tmp, sdir / slide_image_name(new_n, ext)))
        for tmp, dst in staged:
            atomic_replace(tmp, dst)
        # remove images no slide claims any more (deleted or content-edited)
        claimed = {s["render"]["image"].rpartition("/")[2]
                   for s in deck["slides"]
                   if s["render"] and s["render"].get("image")}
        if sdir.exists():
            for ext in SLIDE_IMAGE_EXTS:
                for image in sdir.glob(f"*.{ext}"):
                    if image.name not in claimed:
                        image.unlink()
                        logger.info("removed orphan %s from deck %s",
                                    image.name, deck_id)
        return save_deck(deck)


# ── CRUD ────────────────────────────────────────────────────────────────────

def create_deck(*, title: str, topic: str, source_notes: str = "",
                style_guide: dict | None = None, slides: list | None = None,
                slide_size: str = "2K",
                image_model: str = image_models.DEFAULT_IMAGE_MODEL) -> dict:
    deck_id = make_id("dk")
    now = _now()
    deck = sanitize_deck({
        "id": deck_id,
        "title": title,
        "topic": topic,
        "source_notes": source_notes,
        "style_guide": style_guide or {},
        "slide_size": slide_size,
        "image_model": image_model,
        "aspect_ratio": "16:9",
        "status": "outline",
        "slides": slides or [],
        "created_at": now,
        "updated_at": now,
    }, fallback_id=deck_id)
    # sanitize_deck fills palette defaults but must not eat verbatim user words
    deck["topic"] = topic
    deck["source_notes"] = source_notes
    d = deck_dir(deck_id)
    (d / "slides").mkdir(parents=True, exist_ok=True)
    (d / "exports").mkdir(parents=True, exist_ok=True)
    save_deck(deck)
    logger.info("created deck %s (%r, %d slides)", deck_id, title, len(deck["slides"]))
    return deck


def load_deck(deck_id: str) -> dict:
    path = deck_dir(deck_id) / "deck.json"
    # under LOCK so an in-process reader can never hold the file open across
    # a concurrent save's replace (Windows denies the swap in that window)
    with LOCK:
        if not path.exists():
            raise DeckNotFound(f"deck {deck_id} not found")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logger.warning("deck %s has unreadable deck.json: %s", deck_id, e)
            raise StoreError(f"deck {deck_id} is unreadable: {e}") from e
    return sanitize_deck(raw, fallback_id=deck_id)


def save_deck(deck: dict) -> dict:
    deck["updated_at"] = _now()
    with LOCK:
        d = deck_dir(deck["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "deck.json.tmp"
        tmp.write_text(json.dumps(deck, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        atomic_replace(tmp, d / "deck.json")
    return deck


def list_decks() -> list:
    root = decks_root()
    if not root.exists():
        return []
    out = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        try:
            deck = load_deck(entry.name)
        except StoreError:
            logger.warning("skipping unreadable deck folder %s in listing", entry.name)
            continue
        cover = find_slide_image(deck["id"], 1)
        out.append({
            "id": deck["id"],
            "title": deck["title"],
            "status": deck["status"],
            "slide_count": len(deck["slides"]),
            "updated_at": deck["updated_at"],
            "cover": f"slides/{cover.name}" if cover is not None else None,
        })
    out.sort(key=lambda d: d["updated_at"], reverse=True)
    return out


def duplicate_deck(deck_id: str) -> dict:
    """Deep copy under a fresh id: deck.json + slide images. exports/ stays
    empty — exports are derived artifacts, rebuilt on demand (invariant 7)."""
    with LOCK:
        deck = load_deck(deck_id)
        new_id = make_id("dk")
        dst = deck_dir(new_id)
        (dst / "slides").mkdir(parents=True, exist_ok=True)
        (dst / "exports").mkdir(parents=True, exist_ok=True)
        src_slides = slides_dir(deck_id)
        if src_slides.exists():
            for ext in SLIDE_IMAGE_EXTS:
                for image in src_slides.glob(f"*.{ext}"):
                    (dst / "slides" / image.name).write_bytes(image.read_bytes())
        deck["id"] = new_id
        deck["title"] = f"{deck['title']} (copy)"
        now = _now()
        deck["created_at"] = now
        if deck["status"] == "rendering":  # copying mid-render: settle the copy
            deck["status"] = "outline"
            for slide in deck["slides"]:
                if slide["render"] and slide["render"]["status"] in ("pending",
                                                                    "rendering"):
                    slide["render"] = None
        save_deck(deck)
    logger.info("duplicated deck %s -> %s", deck_id, new_id)
    return deck


def sweep_interrupted() -> int:
    """Boot-time sweep: any slide stuck in 'rendering' flips to
    error: 'interrupted'; a deck stuck in 'rendering' flips to 'error'.
    Restarts never leave zombie state. Returns the number of decks touched."""
    touched = 0
    root = decks_root()
    if not root.exists():
        return 0
    with LOCK:
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            try:
                deck = load_deck(entry.name)
            except StoreError:
                continue
            dirty = False
            for slide in deck["slides"]:
                render = slide["render"]
                if render and render["status"] == "rendering":
                    render["status"] = "error"
                    render["error"] = "interrupted"
                    dirty = True
            if deck["status"] == "rendering":
                deck["status"] = "error"
                dirty = True
            if dirty:
                save_deck(deck)
                touched += 1
                logger.warning("swept interrupted render state in deck %s", deck["id"])
    return touched


def delete_deck(deck_id: str) -> None:
    d = deck_dir(deck_id)
    if not d.exists():
        raise DeckNotFound(f"deck {deck_id} not found")
    # bottom-up removal, no shutil surprises with read-only bits on Windows
    for path in sorted(d.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    d.rmdir()
    logger.info("deleted deck %s", deck_id)
