# Sprint 2 report — Outline engine

## What shipped

- `outline_schema.py` (pure Pydantic): `StyleGuide` (3–5 hex palette via shared `validate_palette`, non-empty `art_direction`), `SlideSpec` (non-empty title/visual_description, ≤4 points of ≤12 words), `DeckOutline` (1–`LANTERN_MAX_SLIDES` slides).
- `outline.py`: `generate_outline(topic, source_notes, slide_count_hint, style_hints, client=None)` — Anthropic SDK on the pinned model, system prompt demanding strict JSON, a one-paragraph `art_direction`, painted-text brevity, a deliberate arc, 6–12 slides unhinted. On invalid output: exactly ONE repair round-trip carrying validator errors back, then a clean `OutlineError` with raw text logged. Client injectable for stubbed tests; SDK import deferred so pure paths run keyless. Exact system prompt mirrored in `docs/outline-prompt.md`.
- Endpoints: `POST /api/decks` (Pydantic model, whitespace topic 422s, slide_count clamped server-side to 1–16, provider failure → 503), `GET /api/decks/{id}`, `PATCH /api/decks/{id}` (title / partial style_guide with hex-validated palette / slide_size / full slide list with reorder-add-remove).
- Store additions: `LOCK` (process-wide RLock; every load-modify-save serialized, never held across network calls), `update_deck(id, mutate)`, pure `apply_slide_patches(deck, patches) -> (deck, moves)`, and `patch_slides(id, patches)` which renumbers contiguously, keeps render blocks only when all content fields are untouched, re-keys surviving images with two-phase renames (position == filename), and deletes orphaned PNGs.
- Frontend: `NewDeckPage` form (topic/notes/count/style-hints/size) → creates → routes to `OutlinePage`. `OutlinePage`: editable style-guide card (color-input palette chips with 3–5 bounds, typography/motif/tone, art_direction textarea), slide cards with inline editing, ↑↓ reorder, add/remove, debounced (800 ms) autosave gated on `isLoaded`, estimated-cost readout from pure `lib/cost.ts`, disabled "Render deck · ~$X (Sprint 4)" button.
- Verify: `scripts/verify_outline.py` (stubbed repair path, validator limits, PATCH semantics incl. render-clearing at store level) + `scripts/smoke_sprint2.py` (HTTP: 422/503/404/422-palette, PATCH reorder over the wire).

## What you need to do once

Nothing new. With `ANTHROPIC_API_KEY` in `.env`, re-run `python scripts/verify_outline.py` to exercise the live Haiku call (≈ $0.01).

## What's deferred

- **Live Haiku outline call** — no `ANTHROPIC_API_KEY` in this build environment. The script runs it automatically when the key exists and reports SKIPPED loudly otherwise. Verify A should run it.
- Autosave identity refresh uses index mapping after each PATCH response; an edit made during the ~10 ms in-flight window of a *local* save could theoretically misattribute slide identity. Single-user app, debounced saves — accepted and noted.

## Verification

- `verify_outline.py`: 14/14 offline checks pass (repair recovers in exactly 2 calls; double failure raises `OutlineError` after 2 calls; >12-word point trips validation; reorder renumbers from 1; untouched renders survive reorder with re-keyed image paths; edits clear renders; new slides land clean).
- `smoke_sprint2.py` against the running service: empty topic 422, keyless outline 503 (clean, JSON error body), GET/PATCH/DELETE round-trip, partial style_guide merge, bad palette 422, missing deck 404.
- `npm run build` clean (TS strict).
- Slide-count 40 request clamps to 16 before the outline call (asserted via the 503 path reaching the provider stage, and by code reading — the clamp precedes the call).

## Divergences

1. **PATCH also accepts `slide_size`** (not in the brief's PATCH list) — OutlinePage has the size knob, so the wire needed it. Additive; flagged for Verify A.
2. **`layout_hint` changes also clear a slide's render** — the brief says "content untouched"; layout_hint feeds the prompt, so it counts as content here. Flagged as interpretation.
3. **Reorder moves the PNGs** (two-phase rename) so surviving render blocks keep position == filename true. The brief implied renders survive reorder but didn't say who moves the files; the store does, inside `patch_slides`.
4. `smoke_sprint2.py` added beyond the brief's named scripts — the 422/503/404 wire contract wanted a live-service probe.
