# NanoGPT painters — feature report (2026-08-16)

## What shipped

- **Per-deck painter choice.** `deck.json` gains `image_model` (default
  `gemini-3-pro-image-preview` — Locked Decision 3's pin now names the default,
  not the only painter; see the 2026-08-16 DECISIONS.md entry). A "Painter"
  `<select>` sits beside Image size on New Deck and Outline; the choice
  autosaves with the outline and the Render button's estimate follows it live.
- **The registry triad, applied to images.** `dashboard/src/config/imageModels.ts`
  is THE painter list (id, label, provider, i2i flag, per-size resolution
  tokens, per-size USD, optional edit twin), mirrored by
  `src/lantern/image_models.py` (pure, framework-free).
  `image_models.resolve_model(id, size, has_ref)` is the single answer to
  "which model actually paints, at what size token, for what price."
- **Six NanoGPT painters** through one new transport module
  (`src/lantern/nanogpt.py`, httpx-only, mirrors `gemini.py`'s retry/4xx
  idiom; `POST https://nano-gpt.com/v1/images/generations`, key via new
  `NANOGPT_API_KEY` in `.env` only): Seedream 4.5 (4¢, 4096×2304),
  Seedream 5.0 Pro (9¢), Qwen Image 3 Pro (4–7.5¢), Nano Banana Pro resold
  (14–24¢), FLUX.2 Klein 4B (~1¢ at 720p), FLUX.2 Pro (5.1¢ at 720p).
- **Style anchoring survives every painter.** i2i-capable models take the
  slide-1 PNG as `imageDataUrl`; text-only FLUX models auto-route slides 2..N
  to their paired edit twin (Klein → Klein Base Edit at 1.5¢; Pro → Pro
  image-to-image at the same 5.1¢). The render block records the twin's id —
  whichever model actually painted.
- **Honest costs, both directions.** Estimates are exact (slide 1 at base
  price, slides 2+ at the twin's rate — `estimate_deck_cost` /
  `cost.ts::estimateDeckCost`), and NanoGPT's metered per-response `cost` is
  recorded into `cost_estimate_usd` over the plan-time number when present.
  `gemini.py`'s old `COST_PER_IMAGE_USD` table moved into the registry so
  exactly one Python-side number exists per (painter, size).
- **`scripts/verify_image_models.py`**: registry shape, resolver behavior,
  exact-estimate math, TS↔Python parity (ids, providers, i2i, every price,
  edit twins), stubbed transport (b64/401/402/5xx-retry/keyless), dist
  key-containment grep, and a **default-on** price-drift check against
  NanoGPT's free public catalog (offline runs print SKIPPED; a real
  price/id/capability mismatch FAILS). `--live` paints one ~$0.01 Klein
  image; `--live-aspect` paints one image per NanoGPT painter (~35¢ total)
  and asserts the output is ~16:9.

## What you need to do once

- Put a `NANOGPT_API_KEY` in `.env` (nano-gpt.com → API) and top up the
  pay-as-you-go balance. The Gemini default never touches it.
- Run `python scripts/verify_image_models.py --live-aspect` (~35¢) to settle
  the two flagged painters (below).

## What's deferred

- **Qwen Image 3 Pro and Nano Banana Pro (via NanoGPT) ship flagged**: their
  `1k/2k/4k` size tokens don't self-encode 16:9 and NanoGPT's endpoint has no
  aspect field, so their frame behavior is unknown until the first
  `--live-aspect` paint. Either comes off the list if it can't hold 16:9
  (invariant 4 outranks any one painter).
- `remainingBalance` from NanoGPT responses is logged (`lantern.nanogpt`
  INFO lines) but not surfaced in the UI — an account-level number with no
  deck-scoped home; a `/api` balance readout is a clean follow-up if wanted.
- No textual ref-instruction is sent to NanoGPT i2i painters (`imageDataUrl`
  is the signal). If live decks drift stylistically, the nudge belongs in
  `nanogpt.py` as a REF_INSTRUCTION equivalent — transport glue, never
  `prompts.py`.

## Verification

- `verify_image_models.py`: all checks passed, including the live catalog
  drift check against nano-gpt.com (all six painter ids + both edit twins
  confirmed present, prices and i2i capabilities matching) — run 2026-08-16.
- `verify_render.py`: all checks passed, including the new section — nanogpt
  dispatch, FLUX edit-twin routing with the ref riding along, metered-cost
  recording, `nanogpt.RenderError` propagation, and the queue's catch tuple.
- `verify_store.py`: `image_model` sanitizer checks (missing → default,
  unknown → default, valid NanoGPT id round-trips) — all passed.
- `verify_queue.py`, `verify_chalk.py`: regression-clean after the change.
- `npm run build`: type-checks and builds; booted service answers
  `/api/health` and 422s an unknown painter id on `POST /api/decks`.

## Divergences

1. **`queue.py`'s except clause uses `(*render_service.RenderProviderError, …)`
   unpacking** — the first cut nested the tuple, which Python 3 rejects at
   raise time ("catching classes that do not inherit from BaseException");
   the worker's crash-guard masked it in one verify run before it was caught
   and fixed. Recorded here because the failure mode was invisible-by-design.
2. **`.env`'s `LANTERN_DATA_DIR`/`CHALK_DB_PATH` are now commented out**
   (values were identical to the built-in defaults). `.env` overrides shell
   env by design, so filled-in values were silently redirecting every verify
   script's throwaway data dir to the real `data/` folder — `verify_chalk.py`
   refused to run because of it; the other scripts have no such guard. One
   corrupt verify fixture (`dk_corrupt00`) that had landed in `data/decks/`
   was removed.
3. **The price-drift check runs by default, not behind `--live`** — the
   catalog GET is free, unauthenticated, and read-only, unlike the paid
   paints every other `--live` flag gates. Offline runs stay green (SKIPPED),
   real drift fails loudly.
