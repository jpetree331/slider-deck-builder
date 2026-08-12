# Sprint 3 report — Slide renderer

## What shipped

- `prompts.py` (pure): `compose_slide_prompt(style_guide, slide, n, total)` — frame line ("ONE finished 16:9 presentation slide — flat, edge-to-edge graphic design, not a photo of a screen"), deck block identical on every slide ("DECK ART DIRECTION (identical on every slide — do not drift):" + art_direction verbatim + palette + typography + motif + tone), slide block (layout hint, headline and points quoted verbatim with spelling-critical instruction, visual_description), rules block (room-legible headline, no un-quoted text, generous margins, no collage/frame). Template mirrored in `docs/render-prompt.md`.
- `gemini.py`: `render_image(prompt, size, style_ref_png)` — httpx POST to `{model}:generateContent` with `x-goog-api-key`, `responseModalities: ["TEXT","IMAGE"]`, `imageConfig: {aspectRatio: "16:9", imageSize}` pinned on EVERY request (invariant 4). Style ref goes in as a leading `inline_data` part plus the match-this-style instruction. No image in response → `RenderError` carrying the text parts. Timeout 120 s; ONE retry on 5xx/timeout with logged 3 s backoff; 4xx fails immediately. `COST_PER_IMAGE_USD = {1K: 0.134, 2K: 0.134, 4K: 0.24}` — the backend half of the cost seam with `lib/cost.ts`.
- `render_service.py`: `render_slide(deck_id, n)` — claims the slide under `store.LOCK` (409 via `AlreadyRendering` if mid-render), composes the prompt, loads slide 1's PNG as style ref for n>1 when present, renders with no lock held, Pillow-verifies the bytes, writes `slides/NN.png` atomically (tmp + `os.replace`), then records the full render block (exact prompt, model, ms, rendered_at, cost) and logs the cost line `lantern.render: slide N SIZE ~$est (deck total ~$sum)`. Failures record `status: error` + message; deck.json stays valid.
- `store.sweep_interrupted()`: boot-time sweep flips any `rendering` slide to `error: "interrupted"` (and a `rendering` deck to `error`); wired into FastAPI lifespan.
- Endpoints: `POST /api/decks/{id}/slides/{n}/render` (sync in FastAPI's worker threadpool; 409/404/503 mapped), `GET /api/decks/{id}/slides/{n}.png` streamed with `ETag` keyed on `rendered_at` (304 on If-None-Match) and `Cache-Control: no-cache` so repaints bust.
- `scripts/verify_render.py`: prints 3 prompt fixtures for eyeball review; asserts invariant 3 dynamically (sentinel per `StyleGuide.model_fields` — a new field that doesn't reach the prompt fails the script); verbatim text checks; request-body 16:9 checks; stubbed-pipeline checks (success bookkeeping, ref chain, failure path, 409 guard, boot sweep); `--live` renders one real slide when `GEMINI_API_KEY` is set.

## What you need to do once

With `GEMINI_API_KEY` in `.env` (paid tier): `python scripts/verify_render.py --live` (≈ $0.14) to confirm the REST contract against the real model.

## What's deferred

- **Live single-slide render** — no `GEMINI_API_KEY` in this build environment; the REST contract is built exactly to the brief's spec and the pipeline is fully exercised against a stub. Verify B's live probe covers this.
- Recon on the current Gemini docs could not be performed from this environment (no network fetch of docs); built against the brief's pinned REST contract verbatim. **Drift risk flagged**: if `gemini-3-pro-image-preview` or `imageConfig` moved, `verify_render.py --live` will surface it immediately as a clean 4xx `RenderError`.

## Verification

24/24 offline checks pass: every style_guide field reaches the prompt (sentinel-proofed), title/points verbatim, no points block when empty, aspectRatio 16:9 + imageSize in the actual request body, ref chain (absent for slide 1, slide 1's bytes for slide 2), success bookkeeping (exact prompt stored, cost 0.134, PNG at `slides/01.png`), failure bookkeeping (status error + message, deck.json valid), `AlreadyRendering` 409 guard, boot sweep flips to `error: interrupted`.

## Divergences

1. **Prompt rules slightly extended** beyond the brief's sketch: added "no page numbers" and "never a border or frame around the design" — both are classic image-model failure modes for slide renders. Same intent, tighter fence.
2. The cost line logs from logger `lantern.render` (render_service) rather than gemini.py, because the deck running total lives there; the constants stay in `gemini.py` where Verify B's seam check expects them.
3. `slide_image` endpoint returns 304 on ETag match — the brief only demanded cache headers keyed on `rendered_at`; the conditional response is the standard completion of that contract.
