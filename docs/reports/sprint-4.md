# Sprint 4 report — Deck orchestration

## What shipped

- `queue.py`: ONE background worker thread, one job at a time — sequential by design (slide 1 must finish before 2..N reference it). Deck job = ordered pending slide list. `enqueue_deck` (skips `done` slides — resume for free; 409 `DeckBusy` on double-enqueue, checked again under the lock at append time), `enqueue_slide` (single repaint; 409 only when that slide is already queued/in flight), `cancel` (drains queued work, in-flight slide finishes; settles status immediately when nothing is in flight), `status()` snapshot. Deck transitions: `outline → rendering → done | error`; first failure halts the remainder, done slides stay done, halted slides reset to unpainted so the same Render button resumes. Worker is crash-proof (top-level exception guard finalizes the deck). All mutations go through store (invariant 2).
- Endpoints: `POST /api/decks/{id}/render` (409 when busy), `POST /api/decks/{id}/cancel`, and the Sprint 3 single-slide endpoint now routes through the queue (async — returns the deck with the slide `pending`).
- `DeckPage` progress grid: one card per slide — thumb or layout-hint placeholder, status chip (`unpainted / pending / painting / done / error`), pulsing veil while queued/painting, error message inline (incl. `interrupted`), per-slide **Paint / Repaint / Edit & repaint**. Edit & repaint opens an inline editor, PATCHes the full slide list (content change clears the render server-side), then enqueues. Slide 1 carries the style-anchor note from Locked Decision 7. Polls `GET /api/decks/{id}` every 2 s only while `status === "rendering"` — the interval is torn down on terminal states and unmount (no immortal intervals). Footer shows spend-so-far from recorded `cost_estimate_usd`.
- `OutlinePage`'s Render button went live: label shows count + estimate ("Render 8 slides · ~$1.07"), disabled until autosave settles, navigates to DeckPage.
- `scripts/verify_queue.py`: renderer stubbed (fixture PNG after 50 ms, failure injection, blocking gate for cancel timing).

## What you need to do once

Nothing new.

## What's deferred

- Live 2-slide cohesion render (`--live`, ≈ $0.28) — no `GEMINI_API_KEY` in the build environment; Verify B's live probe covers style-ref cohesion judgment.

## Verification

`verify_queue.py`: 25/25 — sequential order `[1,2,3,4]`; ref plumbing (no ref for slide 1, slide 1's bytes for 2..4); double-enqueue 409; skip-done resume (only slide 3 re-rendered); halt-on-error (slides 3–4 never started, failing slide records the message, deck `error`, re-render resumes exactly the non-done set and ends `done`); cancel mid-flight (in-flight slide finished, remainder drained, resumable `outline`, no zombie `pending` marks); single-slide repaint; restart sweep flips zombie slide → `error: interrupted` and deck out of `rendering`. `npm run build` clean.

## Divergences

1. **Halted/canceled slides reset to `render: null`** rather than staying `pending` — a `pending` chip on a deck that isn't rendering reads as stuck; unpainted is the truthful state. Resume behavior identical.
2. **Cancel settles deck status to `outline`** (resumable) rather than leaving `rendering`/introducing a new enum value — the brief's status enum has no `canceled`, and `outline` with painted slides is exactly "resumable".
3. `enqueue_slide` allows queueing a slide while the deck renders another (it just runs after — sequential worker makes this safe); 409 is reserved for the same slide being queued twice. The brief's 409 language was deck-level; flagged as interpretation.
