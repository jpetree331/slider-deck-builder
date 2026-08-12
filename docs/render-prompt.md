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

For slides 2..N, when `slides/01.png` exists it is prepended as an `inline_data` part with the instruction (from `gemini.py::REF_INSTRUCTION`):

> Match the visual style, palette, and typographic treatment of this reference slide exactly; change only the content.

Every request body pins `generationConfig.imageConfig = {"aspectRatio": "16:9", "imageSize": <deck size>}` (Sacred Invariant 4).
