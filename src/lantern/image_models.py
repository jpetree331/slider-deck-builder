"""Image model registry — id -> provider/size/price, plus the one resolver.

Framework-free on purpose — no FastAPI, no httpx — so verify scripts can
exercise it headless (Sacred Invariant 5). The list's source of truth is
dashboard/src/config/imageModels.ts; IMAGE_MODELS below mirrors it row for
row — keep the two in sync (verify_image_models.py checks ids AND prices,
and compares prices against NanoGPT's live public catalog).

resolve_model() is the ONLY place that answers "which model actually gets
called, at what size token, for what price" — including the FLUX pairing:
a text-only model auto-routes to its paired edit variant when a style
anchor exists (slides 2+), so anchoring survives on every painter.
"""
from collections import namedtuple

DEFAULT_IMAGE_MODEL = "gemini-3-pro-image-preview"

_SIZES = ("1K", "2K", "4K")


class ImageModelError(Exception):
    """Unknown image model id — the API layer 400s this before render time."""


def _flat(token: str, usd: float) -> tuple[dict, dict]:
    return ({sz: token for sz in _SIZES}, {sz: usd for sz in _SIZES})


def _row(provider: str, i2i: bool, sizes: dict, price_usd: dict,
         edit: dict | None = None) -> dict:
    return {"provider": provider, "image_to_image": i2i, "sizes": sizes,
            "price_usd": price_usd, "edit": edit}


IMAGE_MODELS = {
    "gemini-3-pro-image-preview": _row(
        "gemini", True,
        {"1K": "1K", "2K": "2K", "4K": "4K"},
        {"1K": 0.134, "2K": 0.134, "4K": 0.24}),
    "seedream-v4.5": _row("nanogpt", True, *_flat("4096x2304", 0.04)),
    "bytedance/seedream-v5.0-pro": _row("nanogpt", True, *_flat("16:9", 0.09)),
    "qwen-image-3-pro": _row(
        "nanogpt", True,
        {"1K": "1k", "2K": "2k", "4K": "2k"},
        {"1K": 0.04, "2K": 0.075, "4K": 0.075}),
    "nano-banana-pro": _row(
        "nanogpt", True,
        {"1K": "1k", "2K": "2k", "4K": "4k"},
        {"1K": 0.14, "2K": 0.14, "4K": 0.24}),
    "flux-2-klein-4b": _row(
        "nanogpt", False, *_flat("1280*720", 0.0102),
        edit={"id": "wavespeed-ai/flux-2-klein-base-4b/edit",
              "size": "auto", "price_usd": 0.015}),
    "flux-2-pro": _row(
        "nanogpt", False, *_flat("1280*720", 0.051),
        edit={"id": "flux-2-pro-image-to-image",
              "size": "auto", "price_usd": 0.051}),
}

ResolvedModel = namedtuple("ResolvedModel", "id provider size price_usd")


def resolve_model(image_model_id: str, size: str, has_ref: bool) -> ResolvedModel:
    """The actual (model, size token, price) for one slide's paint."""
    entry = IMAGE_MODELS.get(image_model_id)
    if entry is None:
        raise ImageModelError(f"unknown image model {image_model_id!r} "
                              "(see dashboard/src/config/imageModels.ts)")
    if size not in _SIZES:
        raise ImageModelError(f"bad image size {size!r}")
    edit = entry["edit"]
    if has_ref and not entry["image_to_image"] and edit:
        return ResolvedModel(edit["id"], entry["provider"],
                             edit["size"], edit["price_usd"])
    return ResolvedModel(image_model_id, entry["provider"],
                         entry["sizes"][size], entry["price_usd"][size])


def estimate_deck_cost(slide_count: int, size: str, image_model_id: str) -> float:
    """Exact plan-time total: slide 1 paints unanchored, slides 2+ carry the
    style ref (the queue guarantees that order), so FLUX-paired decks price
    the two variants honestly instead of pretending one flat rate."""
    if slide_count <= 0:
        return 0.0
    total = resolve_model(image_model_id, size, False).price_usd
    if slide_count > 1:
        total += (slide_count - 1) * resolve_model(image_model_id, size, True).price_usd
    return total
