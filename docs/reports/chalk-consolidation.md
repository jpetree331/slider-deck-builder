# Chalk consolidation report — the /chalk chat tab

Chalk (`chalk_master_plan.md`) consolidated into Lantern as a separate tab, per the owner's ask: build only what's needed, Haiku as the chat default, Gemini models in the dropdown (both keys already in `.env`).

## Fit verdict (asked for honestly, given honestly)

**It fits.** Chalk's plan targets the same chassis Lantern already has — FastAPI serving a built Vite/React/TS frontend, token CSS with the same three fonts, `.cmd` + RUNBOOK ops, server-side keys — and both plans claim ports 8020/5179, a collision consolidation dissolves. The reconciliations that were decision-level are recorded in DECISIONS.md: SQLite for chat data only, self-hosted fonts app-wide, SSE scoped to chat while render progress keeps polling.

## What shipped

**Backend** (`src/lantern/`):
- `chalk_migrations/0001_init.sql` — projects / conversations / messages, soft-delete tombstones, per the plan's DDL.
- `chalk_db.py` (framework-free) — stdlib sqlite3 (WAL, foreign keys, per-call connections), numbered idempotent migrations run at boot, defensive sanitizers on every read (bad-role rows skipped with a logged warning), message ordering by `rowid` (insertion order — `created_at` text can tie within clock resolution).
- `chalk_chat.py` (framework-free) — `build_request` context assembly (instructions + "Project knowledge:" suffix skipped when empty; history trimmed from the front to `CHALK_HISTORY_CHAR_BUDGET`, newest user message always kept); provider streaming for **Anthropic** (SDK stream, mapped 401/429/connection errors) and **Gemini** (REST `streamGenerateContent?alt=sse` via httpx, same no-SDK idiom as the image side); `ALLOWED_MODELS` mirroring `models.ts`.
- `chalk_api.py` — `/api/chalk/*`: health, projects/conversations CRUD with soft deletes, `POST /chat` streaming SSE (`delta`/`done`/`error` protocol; user message persisted BEFORE streaming; partials persisted on error and on client abort; no message content in logs). Sits behind the same Basic-auth middleware as everything else.
- `config.py` + `.env.example`: `CHALK_DB_PATH`, `CHALK_DEFAULT_MODEL`, `CHALK_MAX_TOKENS`, `CHALK_HISTORY_CHAR_BUDGET`.

**Frontend** (`dashboard/src/`):
- `config/models.ts` — THE model list: Claude Haiku 4.5 (default), Gemini Flash (latest), Gemini Pro (latest). The `-latest` aliases were confirmed against Google's live models endpoint with the real key; they track Google's current models with no file edits.
- `lib/sse.ts` (framework-free) — SSE-over-POST reader with AbortController.
- `lib/chalkApi.ts` (framework-free) — typed wrappers + pure `transcriptMarkdown` export helper.
- `ChalkPage` (+ css) — full-viewport tab: sidebar (projects → nested conversations, create/delete, instructions toggle), warm empty states.
- `ProjectEditor` — name/instructions/knowledge, autosave on blur with saved/saving indicator.
- `ChatPane` — streaming bubbles (markdown via react-markdown + remark-gfm on done, tokens-only styling incl. tables/code), model dropdown persisting per-conversation, auto-title from the first message, Stop (keeps partial), inline retry on mapped errors, copy-per-message, Export `.md`, Enter/Shift+Enter/Esc.
- Fonts self-hosted via `@fontsource`; Google Fonts `<link>`s removed from `index.html`. App shell gains the **Chalk — chat** tab; `/chalk` is a bare route.

## Built deliberately smaller than the plan (consolidation)

- No separate repo/scaffold/cmd/port claim — Lantern's chassis serves.
- Deferred from Chalk Sprint 4: edit-and-resend, the 60s health status dot (errors already surface per-turn), fresh-machine timing test.
- Routes namespaced `/api/chalk/*` rather than the plan's bare `/api/projects` (deck routes own that space).

## Verification

`verify_chalk.py` — 36/36: throwaway-db isolation guard; migrations idempotent (run twice); CRUD + tombstones (row survives with `deleted_at`, filtered from lists); corrupt-row sanitizer; context assembly (suffix skip, front-trim, newest-survives); models.ts ↔ ALLOWED_MODELS sync; unknown model → 400/422; SSE protocol over ASGI (delta/done shape, both rows persisted, error event carries mapped 503, **partial persisted on failure**); key containment (no `sk-ant`/`ANTHROPIC`/`googleapis`/CDN-font strings in `dist/`); lib purity both sides; **live Haiku turn** (streamed text + usage, under a cent); **live Gemini Flash turn** (`--live-gemini`).

UI end-to-end on an isolated instance (port 8022, throwaway db): created a project, started a chat, sent a real message — Haiku streamed and rendered as markdown, auto-title fired; switched the dropdown to Gemini Flash mid-thread — the reply correctly referenced the Haiku turns (history threads across providers). `npm run build` clean.

One bug found & fixed during verification: message ordering originally sorted by `created_at` text; same-microsecond writes tied and the random-id tiebreak could scramble turns. Now `rowid`.

## What you need to do once

- **Restart the Lantern service** — the new `/api/chalk/*` routes and the migrated `chalk.db` arrive on boot (frontend is already built). Renders in flight will be swept to `error: interrupted` and are resumable, so restart at a quiet moment.
- Optionally add the `CHALK_*` knobs to `.env` (defaults are sensible without them).
