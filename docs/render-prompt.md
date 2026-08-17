# Render prompt template (audit copy)

Source of truth: `src/lantern/prompts.py::compose_slide_prompt` — the ONLY place a Gemini prompt is assembled (Sacred Invariant 3). Keep in sync — Verify B diffs this file against the code.

```
Render slide {n} of {total} as ONE finished 16:9 presentation slide — a flat, edge-to-edge graphic design, not a photo of a screen or a mockup on a desk.

DECK ART DIRECTION (identical on every slide — do not drift):
{art_direction — verbatim}
Palette (use these colors and no others): {palette, comma-joined}
Typography: {typography}
Recurring motif: {motif}
Tone: {tone}

THIS SLIDE:
Layout: {layout_hint}                            ← omitted when empty
Headline (render this text verbatim, correctly spelled): "{title}"
Supporting lines (render each verbatim, correctly spelled, smaller than the headline):   ← omitted when no points
- "{point}"
The picture: {visual_description}

RULES:
- The headline must be legible from across a room.
- Render no text beyond the words quoted above — no watermarks, no lorem ipsum, no invented labels, no page numbers.
- Generous margins; keep everything important away from the edges.
- One cohesive composition filling the full 16:9 frame edge to edge — never a collage of mini-slides, never a border or frame around the design.
```

The prompt above is provider-agnostic — both painters' transports send it verbatim. How the style reference and the 16:9 pin ride along differs per provider:

**Gemini (the default painter).** For slides 2..N, when `slides/01.png` exists it is prepended as an `inline_data` part with the instruction (from `gemini.py::REF_INSTRUCTION`):

> Match the visual style, palette, and typographic treatment of this reference slide exactly; change only the content.

Every request body pins `generationConfig.imageConfig = {"aspectRatio": "16:9", "imageSize": <deck size>}` (Sacred Invariant 4).

**NanoGPT painters (2026-08-16, see DECISIONS.md).** The reference PNG rides as the `imageDataUrl` field — structurally, with NO instruction text appended (`nanogpt.py` refuses to touch the prompt; a future ref-nudge, if live painting shows one is needed, belongs in `nanogpt.py` as transport glue, never here or in `prompts.py`). NanoGPT's endpoint has no aspect-ratio field: 16:9 rides on each painter's per-model size token from `image_models.py` (`"4096x2304"`, `"16:9"`, `"1280*720"`, …). Painters whose tokens don't self-encode the frame (`1k/2k/4k`) are flagged in their dropdown note until `verify_image_models.py --live-aspect` confirms them. Text-only painters auto-route slides 2..N to their paired edit twin so the reference can ride at all.
