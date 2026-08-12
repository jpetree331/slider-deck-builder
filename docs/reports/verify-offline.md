# Verification round (offline) — combined A/B/C audit + fixes

An independent audit agent (different model, zero build context, read-only) walked all three seam matrices from the master plan, the seven Sacred Invariants, and the queue/auth surfaces, alongside re-runs of the full script suite and live-service smoke tests on this machine. Live-model probes (Verify A's real Haiku call, Verify B's ≈$0.45 render probe, Verify C's optional ≈$0.30) were **not** run — no API keys exist in this environment. They remain open for the Final Verification round on the deployment machine.

## Audit results

- **Seam matrix A (Sprints 1–2): 5/5 PASS** — deck.json ↔ Pydantic ↔ types.ts field-for-field; POST/PATCH wire contracts; outline → store with nothing invented/dropped; cost constants identical in `cost.ts` and `gemini.py`.
- **Seam matrix B (Sprints 3–4): 6/6 PASS** — every SlideSpec and StyleGuide field reaches the prompt; PATCH-clears-render → skip-done resume; render status enums identical across store/TS/DeckPage incl. `error: interrupted`; zero-padding agreement between disk names and URLs with `rendered_at` cache-busting; ref chain (n>1 only, graceful when 01.png missing); polling intervals die on terminal states.
- **Seam matrix C (Sprints 5–6): 6/6 PASS** — export paths via store helpers; slide order identical in PPTX/PDF/ZIP; full-bleed geometry; duplicate deep with empty `exports/`; export downloads behind the auth middleware (verified live); zero-orphan delete.
- **Sacred Invariants: 7/7 PASS** (invariant 6 was "pass at creation, degraded at edit time" — fixed below).
- Queue race review: the enqueue check-then-act window self-heals (one job wins the full slide set, the loser gets a clean 409) — confirmed with an injected-delay race test, left as-is.

## Defects found and fixed this round

1. **[MEDIUM] PATCH bypassed the painted-text validators** (`api.py`) — an autosaved edit could empty a slide title or the deck's `art_direction`, and the next render would burn the blank into a paid image. Fixed: `SlidePatch` now mirrors `outline_schema`'s rules (non-empty title/visual_description, ≤4 points of ≤12 words), `StyleGuidePatch` refuses an emptied `art_direction` — all 422 with readable messages. `api.ts` renders FastAPI's 422 detail arrays as sentences; `OutlinePage` holds autosave while a painted-text field is empty and says so in the status slot ("every slide needs a headline & picture"), keeping the Render button disabled.
2. **[MEDIUM, found in re-runs] Windows file-swap race** (`store.py`) — `os.replace` on `deck.json` fails with `PermissionError` when a concurrent reader holds the destination open; the 2-second status poll during renders is exactly such a reader, so this was a real intermittent production crash on the target OS (it struck once in this round's suite re-run). Fixed: `load_deck`/`save_deck` serialize under `store.LOCK`, and all atomic swaps (deck.json, reorder moves, slide PNGs) go through `store.atomic_replace` — a bounded retry ladder (6 × 20–120 ms) that also absorbs out-of-process readers like antivirus scans. `verify_queue.py` then passed 4/4 consecutive runs.
3. **[LOW-MEDIUM] Verify scripts crashed on stock cp1252 consoles** (`scripts/*.py`) — unicode in check output (`→`, `≈`) raised `UnicodeEncodeError` unless `PYTHONUTF8=1` happened to be set, breaking the "do this, don't skip" gates on the project's own target OS. Fixed: every script reconfigures stdout to UTF-8 with `errors="replace"` at startup.
4. **[LOW] Auth middleware smothered CORS preflights** (`api.py`) — `DashboardAuthMiddleware` ended up outermost, so an `OPTIONS` preflight got a blank 401 with no CORS headers when `LANTERN_PASSWORD` was set. Fixed by registration order (Starlette prepends, so CORS is registered last → runs outermost); preflights carry no credentials by spec, so answering them before auth is correct. The brief's literal assembly order produced this — divergence flagged: the *effective* order now matches the brief's intent.
5. **[LOW] SPA fallback swallowed unknown `/api/*` paths** (`api.py`) — a typo'd endpoint returned 200 + index.html instead of a JSON 404, which would surface as a confusing client parse error. Fixed: the fallback excludes `api/` (and `assets/`, which must 404 honestly).

Related, found by in-browser testing just before the audit landed: deep links (`/new`, `/decks/{id}`) hard-404'd because `StaticFiles(html=True)` has no SPA fallback — `SpaStaticFiles` added (the audit reviewed the fixed version and confirmed it, minus defect 5 above). This mattered for the phone-over-Tailscale scenario, where a shared deck URL is the front door.

## Accepted nitpicks (no change)

- `export.py` joins the literal `"deck.json"` onto `store.deck_dir(...)` for the ZIP — the filename is a fixed constant of the store layout.
- Dead-defensive `AlreadyRendering` handler in the queue's single-worker loop — harmless.
- Canceled decks read as `outline` — already a recorded decision in DECISIONS.md.
- Export downloads buffer in memory — fine at this app's sizes; revisit only if 4K × 16 decks make it matter.

## Post-fix verification

All suites green after the fixes: `verify_store` 18/18 · `verify-sprint1` all · `verify_outline` 14/14 · `verify_render` 24/24 · `verify_queue` 25/25 × 4 consecutive runs · `verify_library` 11/11 · `verify_export` 12/12 · `smoke_full` 25/25 open **and** 30/30 behind Basic auth (incl. new regression checks: deep-link fallback, `/api` 404 honesty, empty-title/art_direction/long-point 422s, CORS preflight clearing the auth wall with headers). `npm run build` clean.

## Still open for Final Verification (needs keys / target machine)

- Live Haiku outline (≈$0.01), live single-slide render (≈$0.14), live 3-slide cohesion probe (≈$0.45), full-deck end-to-end (≈$1.20) — the scripts gate these behind key presence and `--live` and say what they cost.
- PPTX opened in desktop PowerPoint; Task Scheduler registration + reboot test; phone-over-Tailscale pass.
