"""Gemini (Nano Banana Pro) REST client — no Google SDK dependency, httpx only.

Every request pins aspectRatio 16:9 (Sacred Invariant 4). Per-image prices
live in image_models.py (mirrored by dashboard/src/config/imageModels.ts) —
this module is dumb transport, same as nanogpt.py.
"""
import base64
import logging
import time

import httpx

from . import config

logger = logging.getLogger("lantern.gemini")

ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/models/"
            "{model}:generateContent")
TIMEOUT_S = 120

VALID_SIZES = ("1K", "2K", "4K")

REF_INSTRUCTION = ("Match the visual style, palette, and typographic treatment "
                   "of this reference slide exactly; change only the content.")


class GeminiError(Exception):
    """Gemini provider failure — maps to HTTP 503."""


class RenderError(GeminiError):
    """Provider failure or no image in the response — maps to HTTP 503."""


def _request_body(prompt: str, size: str, style_ref_png: bytes | None) -> dict:
    parts = []
    if style_ref_png:
        parts.append({"inline_data": {
            "mime_type": "image/png",
            "data": base64.b64encode(style_ref_png).decode("ascii"),
        }})
        parts.append({"text": REF_INSTRUCTION})
    parts.append({"text": prompt})
    return {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            # 16:9 is pinned on EVERY request — never omitted (invariant 4)
            "imageConfig": {"aspectRatio": "16:9", "imageSize": size},
        },
    }


def _extract_image(data: dict) -> bytes:
    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
    texts = []
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
        if part.get("text"):
            texts.append(part["text"])
    detail = " / ".join(texts) or f"empty response: {str(data)[:300]}"
    raise RenderError(f"model returned no image — {detail}")


def generate_text(model: str, system: str, contents: list,
                  max_tokens: int = 8192, force_json: bool = False) -> str:
    """Non-streaming text generation — used by the outline engine when the
    outline model is a Gemini id. contents follows the REST shape
    ([{role, parts}]); images ride as inline_data parts."""
    if not config.GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY is not set — add it to .env")
    body = {"contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens}}
    if force_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    url = ENDPOINT.format(model=model)
    try:
        resp = httpx.post(url, json=body,
                          headers={"x-goog-api-key": config.GEMINI_API_KEY},
                          timeout=TIMEOUT_S)
    except httpx.TransportError as e:
        raise GeminiError(f"generativelanguage.googleapis.com unreachable — {e}")
    if resp.status_code >= 400:
        raise GeminiError(f"Gemini {model} error HTTP {resp.status_code}: "
                          f"{resp.text[:300]}")
    data = resp.json()
    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
    text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        reason = (candidates[0].get("finishReason") if candidates
                  else data.get("promptFeedback", {}).get("blockReason", "empty"))
        raise GeminiError(f"Gemini {model} returned no text ({reason})")
    return text


def render_image(prompt: str, size: str, style_ref_png: bytes | None = None) -> bytes:
    """POST to Gemini; retry once on 5xx/timeout with a logged backoff."""
    if size not in VALID_SIZES:
        raise RenderError(f"bad image size {size!r}")
    if not config.GEMINI_API_KEY:
        raise RenderError("GEMINI_API_KEY is not set — add it to .env")
    url = ENDPOINT.format(model=config.IMAGE_MODEL)
    body = _request_body(prompt, size, style_ref_png)
    last_error = "unknown"
    for attempt in (1, 2):
        try:
            resp = httpx.post(url, json=body,
                              headers={"x-goog-api-key": config.GEMINI_API_KEY},
                              timeout=TIMEOUT_S)
        except httpx.TimeoutException:
            last_error = f"timeout after {TIMEOUT_S}s"
        else:
            if resp.status_code < 400:
                return _extract_image(resp.json())
            last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code < 500:  # 4xx won't improve on retry
                raise RenderError(last_error)
        if attempt == 1:
            logger.warning("render attempt failed (%s) — one retry in 3s", last_error)
            time.sleep(3)
    raise RenderError(f"render failed after retry — {last_error}")
