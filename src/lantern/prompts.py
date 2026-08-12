"""Prompt composition — the ONLY place a Gemini slide prompt is assembled
(Sacred Invariant 3). Framework-free and pure on purpose — no FastAPI imports —
exercised headless by scripts/verify_render.py, which asserts that every
style_guide field is consumed here so the invariant can't rot.

The rendered template is mirrored in docs/render-prompt.md; keep in sync.
"""


def compose_slide_prompt(style_guide: dict, slide: dict, n: int, total: int) -> str:
    """One art brief per slide: a deck block identical on every slide
    (art_direction verbatim — THE consistency field) plus this slide's
    layout, verbatim text, and picture description."""
    lines = [
        f"Render slide {n} of {total} as ONE finished 16:9 presentation slide — "
        "a flat, edge-to-edge graphic design, not a photo of a screen or a "
        "mockup on a desk.",
        "",
        "DECK ART DIRECTION (identical on every slide — do not drift):",
        style_guide["art_direction"],
        f"Palette (use these colors and no others): {', '.join(style_guide['palette'])}",
        f"Typography: {style_guide['typography']}",
        f"Recurring motif: {style_guide['motif']}",
        f"Tone: {style_guide['tone']}",
        "",
        "THIS SLIDE:",
    ]
    if slide.get("layout_hint"):
        lines.append(f"Layout: {slide['layout_hint']}")
    lines.append(
        f'Headline (render this text verbatim, correctly spelled): "{slide["title"]}"')
    points = slide.get("points") or []
    if points:
        lines.append("Supporting lines (render each verbatim, correctly spelled, "
                     "smaller than the headline):")
        lines.extend(f'- "{p}"' for p in points)
    lines += [
        f"The picture: {slide['visual_description']}",
        "",
        "RULES:",
        "- The headline must be legible from across a room.",
        "- Render no text beyond the words quoted above — no watermarks, "
        "no lorem ipsum, no invented labels, no page numbers.",
        "- Generous margins; keep everything important away from the edges.",
        "- One cohesive composition filling the full 16:9 frame edge to edge — "
        "never a collage of mini-slides, never a border or frame around the design.",
    ]
    return "\n".join(lines)
