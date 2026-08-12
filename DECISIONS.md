# DECISIONS.md — Lantern

Reverse-chronological. Records reversals too.

## 2026-08-12 · S6 · Task Scheduler registration deferred to deployment
The build machine is not the deployment target; the registration steps are complete in RUNBOOK.md and take two minutes on the real host. Not a reversal of Locked Decision — the `.cmd` + Scheduler design stands.

## 2026-08-12 · S4 · Canceled/halted slides reset to unpainted, deck to `outline`
The brief's status enum has no `canceled`; `outline` with painted slides preserved is exactly "resumable", and stale `pending` chips on a non-rendering deck would read as stuck.

## 2026-08-12 · S2 · `layout_hint` edits also clear a slide's render
It feeds the prompt, so it is content. Brief said "content untouched"; this is the strict reading.

## 2026-08-12 · S1 · Repo root is this directory, not `E:\git\Lantern`
Owner's instruction at kickoff (GitHub: `jpetree331/slider-deck-builder`). `start-lantern.cmd` uses `%~dp0` so the repo works from any path.

## Locked at plan time (the twelve, verbatim from `lantern_master_plan.md`)

12. **Versions named at plan, locked at scaffold** — exact resolved versions recorded in `docs/reports/sprint-1.md` (Python 3.12.10, FastAPI 0.141.1, Vite 8.2, React 19.2.8, TS 6.0.2, …).
11. **Optional Basic auth** via `LANTERN_PASSWORD` (DashboardAuthMiddleware pattern) for Tailscale exposure.
10. **Styling: hand-written CSS with `tokens.css`** — no Tailwind, no component library. A gift app; the gift is to Jess.
9. **Export server-side:** python-pptx (full-bleed 16:9), img2pdf, zipfile. No client export libs.
8. **Prompt composition has ONE home:** `src/lantern/prompts.py::compose_slide_prompt()`. The frontend never assembles a Gemini prompt.
7. **Slide 1 is the style anchor.** Slides 2..N attach slide 1's PNG as reference. Repainting slide 1 later does not retro-restyle the others; the UI says so.
6. **Progress via polling, not SSE.** 2-second `GET /api/decks/{id}` while rendering. Dumb and debuggable.
5. **Aspect 16:9, default 2K** (1K/2K/4K knob per deck), `LANTERN_MAX_SLIDES=16` as the cost guard.
4. **Port 8020** service / **5179** Vite dev. Recorded in RUNBOOK.md.
3. **Models pinned:** outline `claude-haiku-4-5-20251001` (Anthropic SDK); render `gemini-3-pro-image-preview` (REST via httpx, no Google SDK).
2. **Store: filesystem, not Postgres.** A deck IS a folder of pictures plus one `deck.json`. Deliberate School-B deviation — portability and zip-backup win for a document-shaped app.
1. **Shape: local FastAPI service + Vite/React/TS frontend it serves.** Keys live in server `.env` only; no Supabase; product-app polish on the agent-service chassis — a deliberate hybrid.
