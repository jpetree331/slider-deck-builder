"""Outline engine — one Claude Haiku call (plus at most one repair round-trip)
turning a topic into a validated DeckOutline. The exact system prompt is
mirrored in docs/outline-prompt.md for audit; keep them in sync.
"""
import json
import logging
import re

from pydantic import ValidationError

from . import config
from .outline_schema import DeckOutline

logger = logging.getLogger("lantern.outline")

MAX_TOKENS = 4096


class OutlineError(Exception):
    """Outline generation failed after the repair round-trip."""


SYSTEM_PROMPT = """You are Lantern's outline engine. Given a topic (and optional source notes), design a slide deck where EVERY slide will be painted as a single 16:9 image by an image model.

Respond with STRICT JSON only — no markdown fences, no commentary — matching exactly this schema:

{
  "title": "short deck title",
  "style_guide": {
    "palette": ["#RRGGBB", "#RRGGBB", "#RRGGBB"],
    "typography": "e.g. high-contrast editorial serif headlines, clean humanist sans support",
    "motif": "one recurring visual device that appears on every slide",
    "art_direction": "ONE cohesive prose paragraph",
    "tone": "e.g. confident, museum-placard"
  },
  "slides": [
    {
      "title": "headline, will be painted verbatim",
      "points": ["at most 4 short lines"],
      "visual_description": "what the picture IS — subject, composition, focal point",
      "layout_hint": "title card | split | full-bleed diagram | big number | quote | closer"
    }
  ]
}

Rules:
- "art_direction" is the deck's entire visual identity — palette in words, texture, lighting, typographic attitude — written so an image model can obey it verbatim on every single slide. One concrete paragraph. No hedging, no options.
- "palette" is 3 to 5 hex colors chosen for the topic, darkest first.
- Slide text gets PAINTED into the image. Titles: short, declarative, spelling-critical. Points: at most 4 per slide, at most 12 words each; many slides are stronger with 0-2 points. Never write a paragraph as a point.
- "layout_hint" is one of: title card, split, full-bleed diagram, big number, quote, closer.
- Build a deliberate arc: slide 1 is a title card; the middle teaches one idea per slide; the final slide is a closer.
- "visual_description" says what the picture IS — subject, composition, focal point — never abstract vibes.
- When no slide count is requested, choose 6-12 slides."""


def _user_message(topic: str, source_notes: str, slide_count_hint: int | None,
                  style_hints: str) -> str:
    count = (f"exactly {slide_count_hint} slides" if slide_count_hint
             else "your choice, 6-12 slides")
    return (
        f"TOPIC (verbatim from the user):\n{topic}\n\n"
        f"SOURCE NOTES (verbatim from the user, may be empty):\n{source_notes or '(none)'}\n\n"
        f"Slide count: {count}\n"
        f"Style hints from the user: {style_hints or '(none)'}"
    )


def _extract_json(text: str) -> dict:
    """Tolerate a fenced or padded response, then parse strictly."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in response")
    return json.loads(t[start:end + 1])


def _default_client():
    import anthropic  # deferred so pure-path scripts run without the SDK key
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def generate_outline(topic: str, source_notes: str = "",
                     slide_count_hint: int | None = None,
                     style_hints: str = "", client=None) -> DeckOutline:
    """One Haiku call; on invalid JSON, exactly one repair round-trip carrying
    the validator errors back; then fail cleanly with the raw text logged."""
    client = client or _default_client()
    messages = [{"role": "user",
                 "content": _user_message(topic, source_notes, slide_count_hint,
                                          style_hints)}]
    last_raw = ""
    for attempt in ("first", "repair"):
        resp = client.messages.create(model=config.OUTLINE_MODEL,
                                      max_tokens=MAX_TOKENS,
                                      system=SYSTEM_PROMPT, messages=messages)
        last_raw = "".join(block.text for block in resp.content
                           if getattr(block, "type", "") == "text")
        try:
            outline = DeckOutline.model_validate(_extract_json(last_raw))
            logger.info("outline ok on %s attempt: %r, %d slides",
                        attempt, outline.title, len(outline.slides))
            return outline
        except (ValueError, ValidationError) as e:
            if attempt == "repair":
                break
            logger.warning("outline invalid, sending one repair round-trip: %s", e)
            messages.append({"role": "assistant", "content": last_raw})
            messages.append({"role": "user", "content": (
                "Your previous response failed validation with these errors:\n"
                f"{e}\n\nReply again with corrected STRICT JSON only, "
                "same schema, no commentary.")})
    logger.error("outline failed after repair; raw response:\n%s", last_raw)
    raise OutlineError("outline model returned invalid JSON twice; raw text logged")
