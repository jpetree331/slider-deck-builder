"""Chalk chat engine — context assembly + provider streaming.

Framework-free on purpose (no FastAPI imports) so verify scripts can exercise
it headless. The model list's source of truth is
dashboard/src/config/models.ts; ALLOWED_MODELS below mirrors it — keep the
two in sync (verify_chalk.py checks).

Both providers stream as generators yielding ("delta", text) tuples and
finally ("done", {"input_tokens": int, "output_tokens": int}).
"""
import json
import logging

import httpx

from . import config

logger = logging.getLogger("lantern.chalk.chat")

# id -> provider. Mirrors dashboard/src/config/models.ts (THE model list).
ALLOWED_MODELS = {
    "claude-haiku-4-5": "anthropic",
    "gemini-flash-latest": "google",
    "gemini-pro-latest": "google",
}

GEMINI_STREAM_ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/"
                          "models/{model}:streamGenerateContent?alt=sse")
TIMEOUT_S = 120


class ChatError(Exception):
    """Mapped, user-facing chat failure. Carries an HTTP-ish status."""

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


def build_request(instructions: str, context: str, history: list,
                  new_content: str,
                  char_budget: int | None = None) -> tuple[str, list]:
    """(system, messages) for a chat turn. History is trimmed from the FRONT
    to fit the char budget; the newest user message always survives."""
    budget = char_budget if char_budget is not None else config.CHALK_HISTORY_CHAR_BUDGET
    system = instructions or ""
    if context:
        system = f"{system}\n\n---\nProject knowledge:\n{context}" if system \
            else f"---\nProject knowledge:\n{context}"

    turns = [{"role": m["role"], "content": m["content"]} for m in history]
    turns.append({"role": "user", "content": new_content})
    kept = [turns[-1]]  # the newest user message is non-negotiable
    used = len(turns[-1]["content"])
    for turn in reversed(turns[:-1]):
        used += len(turn["content"])
        if used > budget:
            break
        kept.insert(0, turn)
    if len(kept) < len(turns):
        logger.info("history trimmed to %d of %d turns (budget %d chars)",
                    len(kept), len(turns), budget)
    return system, kept


def resolve_provider(model: str) -> str:
    provider = ALLOWED_MODELS.get(model)
    if provider is None:
        raise ChatError(f"model {model!r} is not in the allowlist "
                        "(see src/config/models.ts)", status=400)
    return provider


def stream_chat(model: str, system: str, messages: list,
                max_tokens: int | None = None):
    provider = resolve_provider(model)
    max_tokens = max_tokens or config.CHALK_MAX_TOKENS
    if provider == "anthropic":
        yield from _stream_anthropic(model, system, messages, max_tokens)
    else:
        yield from _stream_gemini(model, system, messages, max_tokens)


# ── Anthropic ───────────────────────────────────────────────────────────────

def _stream_anthropic(model: str, system: str, messages: list,
                      max_tokens: int):
    import anthropic  # deferred so pure paths run keyless
    if not config.ANTHROPIC_API_KEY:
        raise ChatError("ANTHROPIC_API_KEY is not set — add it to .env", 503)
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    try:
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield ("delta", text)
            final = stream.get_final_message()
        yield ("done", {"input_tokens": final.usage.input_tokens,
                        "output_tokens": final.usage.output_tokens})
    except anthropic.AuthenticationError:
        raise ChatError("API key rejected — check ANTHROPIC_API_KEY in .env", 401)
    except anthropic.RateLimitError as e:
        retry = getattr(e, "response", None)
        retry_after = retry.headers.get("retry-after") if retry else None
        suffix = f" — retry after {retry_after}s" if retry_after else ""
        raise ChatError(f"Anthropic rate limit hit{suffix}", 429)
    except anthropic.APIConnectionError:
        raise ChatError("api.anthropic.com unreachable — check the network", 503)
    except anthropic.APIStatusError as e:
        raise ChatError(f"Anthropic error {e.status_code}: {e.message}", 503)


# ── Gemini (REST, no SDK — same idiom as gemini.py) ─────────────────────────

def _gemini_body(system: str, messages: list, max_tokens: int) -> dict:
    body = {
        "contents": [
            {"role": "user" if m["role"] == "user" else "model",
             "parts": [{"text": m["content"]}]}
            for m in messages
        ],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    return body


def _stream_gemini(model: str, system: str, messages: list, max_tokens: int):
    if not config.GEMINI_API_KEY:
        raise ChatError("GEMINI_API_KEY is not set — add it to .env", 503)
    url = GEMINI_STREAM_ENDPOINT.format(model=model)
    usage = {"input_tokens": 0, "output_tokens": 0}
    try:
        with httpx.stream("POST", url,
                          json=_gemini_body(system, messages, max_tokens),
                          headers={"x-goog-api-key": config.GEMINI_API_KEY},
                          timeout=TIMEOUT_S) as resp:
            if resp.status_code >= 400:
                detail = resp.read().decode("utf-8", "replace")[:300]
                if resp.status_code in (401, 403):
                    raise ChatError("Google API key rejected — check "
                                    "GEMINI_API_KEY in .env", 401)
                if resp.status_code == 429:
                    raise ChatError("Gemini rate limit hit — try again shortly", 429)
                raise ChatError(f"Gemini error {resp.status_code}: {detail}", 503)
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    chunk = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                for candidate in chunk.get("candidates", [])[:1]:
                    for part in (candidate.get("content") or {}).get("parts", []):
                        if part.get("text"):
                            yield ("delta", part["text"])
                meta = chunk.get("usageMetadata")
                if meta:
                    usage = {"input_tokens": meta.get("promptTokenCount", 0),
                             "output_tokens": meta.get("candidatesTokenCount", 0)}
    except httpx.TransportError:
        raise ChatError("generativelanguage.googleapis.com unreachable — "
                        "check the network", 503)
    yield ("done", usage)
