"""NanoGPT image provider — REST client, httpx only (no SDK), mirrors
gemini.py's shape: one render_image(), one retry on 5xx/timeout, 4xx fails
fast with a human message. Which model to call and at what size is decided
upstream by image_models.resolve_model() — this module is dumb transport.

Unlike gemini.py, no REF_INSTRUCTION text is prepended for style anchors:
NanoGPT's imageDataUrl field IS the "match this reference" signal. If live
painting ever shows an i2i model needs a textual nudge too, add it as
REF_INSTRUCTION here (transport glue, never prompts.py — Invariant 3).

Returns (png_bytes, actual_cost_usd | None) — NanoGPT meters real cost per
response; render_service records it over the plan-time estimate when present.
"""
import base64
import logging
import time

import httpx

from . import config

logger = logging.getLogger("lantern.nanogpt")

ENDPOINT = "https://nano-gpt.com/v1/images/generations"
TIMEOUT_S = 180


class NanoGPTError(Exception):
    """NanoGPT provider failure — maps to HTTP 503."""


class RenderError(NanoGPTError):
    """Provider failure or no image in the response — maps to HTTP 503."""


def _request_body(model: str, prompt: str, size: str,
                  style_ref_png: bytes | None) -> dict:
    body = {"model": model, "prompt": prompt, "size": size,
            "response_format": "b64_json", "n": 1}
    if style_ref_png:
        b64 = base64.b64encode(style_ref_png).decode("ascii")
        body["imageDataUrl"] = f"data:image/png;base64,{b64}"
    return body


def _extract_image(data: dict) -> tuple[bytes, float | None]:
    cost = data.get("cost") if isinstance(data.get("cost"), (int, float)) else None
    items = data.get("data") or []
    first = items[0] if items and isinstance(items[0], dict) else {}
    if first.get("b64_json"):
        return base64.b64decode(first["b64_json"]), cost
    if first.get("url"):
        # some routes hand back a short-lived signed URL despite b64_json —
        # fetch it now, before it expires
        resp = httpx.get(first["url"], timeout=TIMEOUT_S)
        if resp.status_code < 400 and resp.content:
            return resp.content, cost
        raise RenderError(f"image URL fetch failed — HTTP {resp.status_code}")
    raise RenderError(f"model returned no image — {str(data)[:300]}")


def _friendly(status: int, body: str) -> str:
    if status in (401, 403):
        return "NanoGPT API key rejected — check NANOGPT_API_KEY in .env"
    if status == 402:
        return "NanoGPT balance too low to paint — top up at nano-gpt.com"
    return f"NanoGPT HTTP {status}: {body[:300]}"


def render_image(model: str, prompt: str, size: str,
                 style_ref_png: bytes | None = None) -> tuple[bytes, float | None]:
    """POST to NanoGPT; retry once on 5xx/timeout with a logged backoff."""
    if not config.NANOGPT_API_KEY:
        raise RenderError("NANOGPT_API_KEY is not set — add it to .env")
    body = _request_body(model, prompt, size, style_ref_png)
    headers = {"Authorization": f"Bearer {config.NANOGPT_API_KEY}"}
    last_error = "unknown"
    for attempt in (1, 2):
        try:
            resp = httpx.post(ENDPOINT, json=body, headers=headers,
                              timeout=TIMEOUT_S)
        except httpx.TimeoutException:
            last_error = f"timeout after {TIMEOUT_S}s"
        except httpx.TransportError as e:
            raise RenderError(f"nano-gpt.com unreachable — {e}")
        else:
            if resp.status_code < 400:
                data = resp.json()
                png, cost = _extract_image(data)
                balance = data.get("remainingBalance")
                if cost is not None:
                    logger.info("nanogpt: %s cost $%.4f%s", model, cost,
                                f" (balance ${balance:.2f})"
                                if isinstance(balance, (int, float)) else "")
                return png, cost
            last_error = _friendly(resp.status_code, resp.text)
            if resp.status_code < 500:  # 4xx won't improve on retry
                raise RenderError(last_error)
        if attempt == 1:
            logger.warning("render attempt failed (%s) — one retry in 3s", last_error)
            time.sleep(3)
    raise RenderError(f"render failed after retry — {last_error}")
