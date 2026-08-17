# DECISIONS.md — Lantern

Reverse-chronological. Records reversals too.

## 2026-08-16 · Render · EXTENSION of Locked Decision 3's render pin — NanoGPT painters join the roster
Owner call. Locked Decision 3 pinned render to `gemini-3-pro-image-preview`; that pin now names the *default* rather than the *only* painter. Each deck carries an `image_model` (a "Painter" dropdown beside Image size on New Deck and Outline), chosen from a curated list in `dashboard/src/config/imageModels.ts` mirrored by `src/lantern/image_models.py` — the Chalk models.ts triad, applied to images, now with prices in the seam. Six NanoGPT models (Seedream 4.5 at 4¢/slide through Nano Banana Pro resold at $0.14) ride a new `NANOGPT_API_KEY` via `src/lantern/nanogpt.py`; the Gemini default never touches it. Text-only FLUX painters auto-route slides 2+ to their image-input edit twin so slide-1 style anchoring survives on every painter, and estimates price that honestly (slide 1 at base, slides 2+ at the twin's rate). NanoGPT responses meter actual cost — that number is recorded over the plan-time estimate when present. `verify_image_models.py` checks TS↔Python parity AND live price drift against NanoGPT's public catalog on every run (free endpoint; offline runs skip, real drift fails). Qwen Image 3 Pro and Nano Banana Pro (via NanoGPT) ship flagged: their size tokens (`1k/2k/4k`) don't self-encode an aspect ratio and NanoGPT's endpoint takes no explicit aspect field, so their 16:9 behavior is unconfirmed until the first `--live-aspect` paint; either comes off the list if it can't hold the frame (invariant 4 outranks any one painter).

## 2026-08-13 · Outline · REVERSAL of Locked Decision 3's outline pin — Gemini 3.1 Pro replaces Haiku
Owner call, with a stated reason: Haiku wrote the per-slide image briefs "as if it were making the images out of code" — timid, diagram-shaped — while the painter can render anything. `generate_outline` is now provider-aware (`gemini-*` → REST with forced-JSON responses; `claude-*` → Anthropic SDK; same prompt, validators, and single repair round-trip either way), the default is `gemini-3.1-pro-preview`, and the system prompt now explicitly tells the writer it is briefing a state-of-the-art image model. Haiku is one `.env` edit away (`LANTERN_OUTLINE_MODEL=claude-haiku-4-5-20251001`). Outline cost rises from ~1¢ to a few cents.

## 2026-08-13 · Attachments · Extract-and-discard, with vision
PDF/DOCX/PPTX attachments extract server-side (pypdf / python-docx / the python-pptx we already ship): text lands in the editable source-notes box (invariant 6 — the user sees exactly what Haiku gets), and up to 8 embedded images (deduped, icon-filtered, downscaled to ≤1024px JPEG) ride to the ONE outline call as Haiku vision blocks so a "revamp this deck" can carry the original's visual character. Files are never written to disk; decks stay pictures + one JSON. Known limit, stated in the UI and README: embedded images and text — not a rasterized screenshot of each slide (that would require PowerPoint itself).

## 2026-08-13 · Chalk · Consolidated into Lantern as the /chalk tab
Chalk (`chalk_master_plan.md`) shares Lantern's chassis by design — same FastAPI + built-Vite shape, same fonts/tokens, same port claims. One app resolves the 8020/5179 collision. Owner call: dropdown = Haiku (default) + Gemini models instead of the plan's Sonnet, since both keys already live in `.env`. Routes namespaced `/api/chalk/*` (diverges from the plan's bare `/api/projects` to avoid colliding with deck routes).

## 2026-08-13 · Chalk · SQLite arrives — for chat only
`data/chalk.db` per Chalk's own locked decision (stdlib `sqlite3`, no ORM, no new deps). NOT a reversal of Lantern's "filesystem, not Postgres" — decks stay folders; conversation data is append-heavy and relational, and one `.db` file rides the same zip backup.

## 2026-08-13 · Chalk · Fonts self-hosted via @fontsource, Google CDN links removed
Chalk's zero-CDN rule, applied app-wide: the whole UI now renders correctly on filtered school networks and offline. Strictly better for the deck side too.

## 2026-08-13 · Chalk · SSE for chat; polling stays for renders
Lantern's "polling, not SSE" locked decision was scoped to render progress and stands. Chat streams over SSE-on-POST per Chalk's locked decision. Two transports, two features, both loud here.

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
