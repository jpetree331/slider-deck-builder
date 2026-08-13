# Chalk — Master Build Plan

A local, single-user Claude chat app with Projects (instructions + pasted knowledge + conversation history), built to run on the school laptop where claude.ai is filtered but api.anthropic.com is not. Codename **Chalk** — rename freely; if you do, rename the env prefix and DB file to match in Sprint 0.

## Locked decisions (do not relitigate)

- **FastAPI + raw `sqlite3` + SQLite, no ORM.** Loopback-only, single user, zero hosting cost. Supabase is out for this project (free tier exhausted, and there's no multi-device requirement). The whole RLS layer is deliberately absent — the trust boundary is the machine, stated here so the deviation is loud, not silent.
- **Vite + React + TypeScript frontend, served as built static files by FastAPI.** One process, one port at runtime. Vite dev server is for development only.
- **Versions pinned at scaffold.** Target React 19, Vite 8, TypeScript 5.x, Python 3.12+, current `fastapi`/`uvicorn`/`anthropic` SDK. Sprint 0 records the exact pins in its report; nothing inherits versions from older repos.
- **Design-token CSS, no Tailwind, no component library.** `src/tokens.css` + hand-rolled primitives. Fonts self-hosted via `@fontsource` (Libre Franklin UI, Playfair Display headings, IBM Plex Mono code). **Zero CDN references anywhere** — see Guardrails.
- **Streaming via SSE over `fetch` + ReadableStream.** EventSource can't POST, so the client reads the stream off a POST response body.
- **Default model `claude-haiku-4-5`; `claude-sonnet-4-6` available in a dropdown.** The model list lives in `src/config/models.ts` and nowhere else — no per-model branching in components.
- **Port 8020** for the app (API + static). **5179** for Vite dev. Both documented in RUNBOOK.md. (Claimed elsewhere: 8000–8010 range by the agent family, 5005/5006, 5173/5174/5178, 5433/6543.)
- **`ANTHROPIC_API_KEY` lives server-side only**, standard name so the SDK auto-detects it. It never appears in the client bundle, an HTTP response, or a log line.
- **Soft deletes** via `deleted_at` tombstones on projects and conversations.

## How to run this plan

Three threads, per your current split: a **build thread** runs the sprint prompts in order; a **verify thread on a different model** runs VERIFY PROMPT A after Sprints 0–1, VERIFY PROMPT B after Sprints 2–3, and the FINAL VERIFY after Sprint 4. Each prompt below is paste-ready and self-contained. Save the standing brief as `BUILD_BRIEF.md` in the repo root before Sprint 0.

⚠️ **GATE A — resolve before Sprint 0:** confirm the school laptop has Python 3.12+ available (it very likely does, since it runs the deck builder's backend). If it can't run Python at all, stop and re-plan the backend as Node/Express — don't improvise a pivot mid-sprint.

---

# STANDING BRIEF (save as BUILD_BRIEF.md)

# BUILD_BRIEF.md — Chalk (codename: Chalk)

Local Claude chat app for lesson planning. Claude-Projects-style: a **project** holds instructions (system prompt) and pasted knowledge; **conversations** live inside projects; the backend holds the API key and streams responses. Built for one user (Jess), runs on `127.0.0.1`, and must function on a school network where the *only* reachable external host is `api.anthropic.com`.

## Stack & environment

- Windows 11, repo at `E:\git\chalk\` (dev machine); deployed by copying the repo to the school laptop and running a `.cmd` wrapper. No Vercel, no Docker, no CI.
- Backend: Python 3.12+, FastAPI, `uvicorn[standard]`, `anthropic` (official SDK), `python-dotenv`, stdlib `sqlite3`. Pin exact versions in `requirements.txt` at scaffold.
- Frontend: Vite 8 + React 19 + TypeScript 5.x, `react-markdown` + `remark-gfm`, `@fontsource/libre-franklin`, `@fontsource/playfair-display`, `@fontsource/ibm-plex-mono`. Pin at scaffold.
- Runtime: FastAPI on **port 8020**, binding **127.0.0.1 only**, serving `frontend/dist` at `/` (SPA fallback to `index.html`) and the API at `/api/*`. Vite dev on 5179 with a proxy of `/api` → `http://127.0.0.1:8020`.
- DB: SQLite at `data/chalk.db` (gitignored), path overridable via `CHALK_DB_PATH`.

## Repo skeleton

```
chalk/
  BUILD_BRIEF.md
  README.md               # written FOR JESS-AT-SCHOOL, not devs
  RUNBOOK.md              # port claim, start/stop, env, backup, troubleshooting
  docs/reports/           # sprint-N.md reports land here
  start-chalk.cmd         # double-clickable: venv + PYTHONUTF8=1 + uvicorn on 8020
  backend/
    app.py                # FastAPI app: routes, SSE, static mount
    db.py                 # connection, migration runner, row helpers
    anthropic_chat.py     # context assembly + streaming call (framework-free)
    migrations/           # 0001_init.sql ... numbered, idempotent
    requirements.txt
  frontend/
    src/
      pages/ChatPage.tsx  # the single page; layout composition only
      components/         # Sidebar, ChatPane, MessageBubble, ProjectEditor, ModelPicker, Toast
      lib/                # api.ts, sse.ts, ids.ts, sanitize.ts — framework-free, no React imports
      config/models.ts    # THE model list: id, label, note
      tokens.css
    vite.config.ts
  data/                   # gitignored; chalk.db lives here
  .env.example
  .gitignore
```

## The autonomy clause (applies to every sprint)

Work autonomously to completion. Do not stop to ask for confirmation on reversible implementation choices — pick the sound default, note it in your summary, and keep going. Never: change the locked stack, add paid services or external hosts, bind to anything other than 127.0.0.1, or move the API key toward the client, without flagging first.

## The Recon → Build → Verify contract

Every sprint runs RECON (read the brief, the repo, and prior sprint reports before writing), BUILD, VERIFY (do this, don't skip), then writes `docs/reports/sprint-N.md` in the standard shape (What shipped / What you need to do once / What's deferred / Verification) and reports any divergences from the plan. Commit as `Sprint N: <thing>`.

## Divergence rules (do NOT break these without flagging)

1. `ANTHROPIC_API_KEY` never leaves the server process. Not in the bundle, not in any response body, not in logs, not in an error message.
2. Runtime network surface is exactly one external host: `api.anthropic.com`. No CDN fonts, scripts, analytics, or icon kits. Everything ships in the bundle.
3. Bind 127.0.0.1 only. Never 0.0.0.0.
4. `frontend/src/lib/` is framework-free — no React imports — so it can be tested in plain Node. Say so in file headers. Same for `backend/anthropic_chat.py` (no FastAPI imports).
5. The model list exists only in `src/config/models.ts`. Components never branch on model id.
6. No message content at INFO log level. Log ids, timings, token counts — never lesson text. It's a school laptop.
7. Design-token CSS only. All colors/spacing/fonts come from `tokens.css` variables.

## Schema (source of truth — DDL sketch, adapt idiomatically)

Migrations are numbered idempotent SQL in `backend/migrations/`, run in order by `db.py` at startup (`create table if not exists` style; header comment "Idempotent: safe to re-run"). Ids are `crypto.randomUUID()`-style uuids generated server-side. Timestamps ISO-8601 UTC text.

```sql
create table if not exists projects (
  id          text primary key,
  name        text not null,
  instructions text not null default '',   -- the system prompt
  context      text not null default '',   -- pasted "project knowledge"
  created_at  text not null,
  updated_at  text not null,
  deleted_at  text
);

create table if not exists conversations (
  id          text primary key,
  project_id  text not null references projects(id) on delete cascade,
  title       text not null default 'New conversation',
  model       text not null default 'claude-haiku-4-5',
  created_at  text not null,
  updated_at  text not null,
  deleted_at  text
);

create table if not exists messages (
  id              text primary key,
  conversation_id text not null references conversations(id) on delete cascade,
  role            text not null check (role in ('user','assistant')),
  content         text not null,
  created_at      text not null
);
```

## API surface

- `GET /api/health` → `{ ok, default_model, db_path }`. Never echoes the key or whether it's set beyond `ok`.
- `GET/POST /api/projects`, `PATCH /api/projects/{id}`, `DELETE /api/projects/{id}` (soft — sets `deleted_at`).
- `GET /api/projects/{id}/conversations`, `POST /api/conversations`, `PATCH /api/conversations/{id}` (title, model), `DELETE` (soft).
- `GET /api/conversations/{id}/messages`.
- `POST /api/chat` `{ conversation_id, content, model? }` → `text/event-stream`. Server persists the user message first, then streams. Events: `delta` `{text}`, `done` `{message_id, input_tokens, output_tokens}`, `error` `{status, message}`. On client abort, persist whatever accumulated.

**Context assembly** (in `anthropic_chat.py`): `system` = project `instructions` + `"\n\n---\nProject knowledge:\n"` + `context` (skip the suffix when context is empty). `messages` = conversation history oldest-first, trimmed from the front to fit `CHALK_HISTORY_CHAR_BUDGET` (default 100000 chars), always keeping the newest user message. `max_tokens` = `CHALK_MAX_TOKENS` (default 8192). Model aliases resolve through `models.ts` on the client; the server passes the id through and validates it against an allowlist mirroring that file.

**Error mapping**: Anthropic 401 → `error` event "API key rejected — check ANTHROPIC_API_KEY in .env"; 429 → surface retry-after; connection failure → "api.anthropic.com unreachable — check the network." The UI shows these as a toast plus an inline retry on the failed turn.

## .env.example (commit this, heavily commented)

```ini
# Anthropic API key — console.anthropic.com → Settings → API keys.
# Server-side ONLY. This file is an example; the real key goes in .env,
# which is gitignored and must never be committed. Set a monthly spend
# limit on the key in the console — Haiku is cheap, but limits are free.
ANTHROPIC_API_KEY=

# Where the SQLite file lives. Default: data/chalk.db
CHALK_DB_PATH=data/chalk.db

# Default model for new conversations. Options mirror src/config/models.ts.
CHALK_DEFAULT_MODEL=claude-haiku-4-5

# Response cap per turn and history budget per request.
CHALK_MAX_TOKENS=8192
CHALK_HISTORY_CHAR_BUDGET=100000

# Port — claimed in RUNBOOK.md. Change only with a RUNBOOK update.
CHALK_PORT=8020
```

## Guardrails carried throughout

- Defensive-load sanitizers on everything read from SQLite (`safeString`, clamp roles to the enum, coerce missing fields to defaults) so corrupt storage never crashes the app. `ids.ts` exports `makeId(prefix)` with a non-crypto fallback.
- The README opens with a one-line thesis and Jess-facing headings ("Why this exists", "Start it", "Honest answers to fair questions" — what it costs per chat, where the data lives, what happens when the API is down).
- Backup story: `data/chalk.db` is a single file; RUNBOOK says to copy it into the E:\git zip ritual. No sync seam this phase — if one is ever wanted, it's a new decision, not a stub.

---

# PHASE 1 — SPINE

## Sprint 0 — Scaffold & skeleton

### RECON
Read `BUILD_BRIEF.md` end to end. Check Python and Node versions available. Confirm ports 8020/5179 are free.

### BUILD
1. Scaffold the repo skeleton exactly as drawn in the brief: Vite+React+TS in `frontend/`, FastAPI app in `backend/`, `start-chalk.cmd`, `.env.example`, `.gitignore` (covers `.env`, `data/`, `node_modules/`, `dist/`, `__pycache__/`).
2. Pin exact versions in `requirements.txt` and `package.json`; record them in the sprint report as the locked set.
3. `tokens.css`: cream/ink palette, spacing scale, radius, and the three font families wired via `@fontsource` imports. A `components/ui.tsx` with `Button`, `Card`, `TextArea` primitives consuming only tokens.
4. `db.py`: connection factory (`sqlite3.Row`), migration runner over `backend/migrations/`, and `0001_init.sql` with the full schema.
5. `app.py`: health route, static mount of `frontend/dist` with SPA fallback, 127.0.0.1 bind, port from env.
6. `RUNBOOK.md`: port claim, dev vs. school-laptop run instructions, backup note, troubleshooting stub.
7. Build the frontend once so `dist/` exists and the single-process run works.

### VERIFY (do this, don't skip)
- `start-chalk.cmd` from a fresh shell → app loads at `http://127.0.0.1:8020`, health returns ok, fonts render (visibly not Times/Arial) with wifi OFF.
- `python -c "import backend.db"` migration run is idempotent — run twice, no error.
- `netstat` confirms the bind is 127.0.0.1:8020, not 0.0.0.0.
- Report to `docs/reports/sprint-0.md`.

## Sprint 1 — Data layer & streaming chat endpoint

### RECON
Read sprint-0 report and `db.py`. Read the API surface and context-assembly sections of the brief.

### BUILD
1. CRUD routes for projects and conversations per the brief, soft deletes included. Server-side uuid generation; `updated_at` maintained on writes.
2. `anthropic_chat.py`: pure function `build_request(project, history, new_content, model, budgets) -> (system, messages)` with the char-budget trim, plus a thin streaming wrapper around the SDK. No FastAPI imports; header comment says why.
3. `POST /api/chat` SSE route implementing the event protocol, persistence order, abort handling, and the error mapping from the brief.
4. Allowlist validation of `model` against the same ids as `config/models.ts` (duplicate the two ids in one backend constant with a comment pointing at the source of truth).
5. `scripts/verify-sprint1.py`: spot-check that exercises CRUD + a real one-turn chat against the live API (reads `.env`), printing token usage.

### VERIFY (do this, don't skip)
- Run the spot-check with a real key: creates project → conversation → sends "say hi in five words" → streams deltas → row lands in `messages` with role `assistant`.
- Kill the network mid-stream (airplane mode) → `error` event arrives, partial text persisted, server stays up.
- `grep -ri "sk-ant" backend/ frontend/` → hits only in `.env` (which is gitignored) and nowhere else. Confirm no log line contains message content.
- Report to `docs/reports/sprint-1.md`.

---

## VERIFY PROMPT A — run in a separate thread, different model (after Sprints 0–1)

You are the verification pass for Chalk, sprints 0–1. RECON: read `BUILD_BRIEF.md`, `docs/reports/sprint-0.md`, `sprint-1.md`, then the code in `backend/` and `frontend/src/lib/`. Do not write features. Your job: (1) re-run every VERIFY step from both sprints yourself, don't trust the reports; (2) audit the seams — migration runner vs. schema, SSE protocol vs. what `app.py` actually emits, model allowlist vs. `config/models.ts`; (3) hunt divergence-rule violations, especially key leakage into bundle/logs/responses, any external host other than api.anthropic.com, and any 0.0.0.0 bind. Fix nothing beyond one-line obvious breakages; list everything else. Write `docs/reports/verify-A.md`: What passed / What failed (with repro) / Divergences found / Recommended fixes for Sprint 2's RECON.

---

# PHASE 2 — THE ROOM

## Sprint 2 — App shell: sidebar, projects, editor

### RECON
Read verify-A report and fix anything it flagged for this sprint first. Read `tokens.css` and `ui.tsx`.

### BUILD
1. `ChatPage.tsx` layout: left sidebar (projects list → conversations list nested under the active project), main pane placeholder.
2. Project create/rename/soft-delete in the sidebar; `ProjectEditor` panel with `instructions` and `context` textareas, auto-save on blur with a saved/saving indicator (per-slice save gated on an `isLoaded` flag).
3. Conversation create/rename/soft-delete; switching conversations loads messages via `lib/api.ts`.
4. `lib/api.ts`: typed fetch wrapper with the throw-on-error idiom; `lib/sanitize.ts` applied to every load.
5. Empty states written in plain warm language ("No projects yet — make one for a unit or a prep").

### VERIFY (do this, don't skip)
- Create "Bio – Cells Unit" with instructions + pasted context; restart the server; everything is still there.
- Soft-delete a conversation → gone from UI; row still in SQLite with `deleted_at` set.
- No Supabase, no fetch to any host other than same-origin `/api`.
- Report to `docs/reports/sprint-2.md`.

## Sprint 3 — Chat pane: streaming, markdown, errors

### RECON
Read sprint-2 report. Read the SSE protocol section of the brief and `lib/sse.ts` expectations.

### BUILD
1. `lib/sse.ts`: POST + ReadableStream parser for the delta/done/error protocol, with an `AbortController` hook-up. Framework-free.
2. `ChatPane` + `MessageBubble`: user/assistant turns, streaming text renders as it arrives, then re-renders through `react-markdown` + `remark-gfm` on `done` (tables and code blocks styled from tokens; IBM Plex Mono for code).
3. Stop button (aborts stream, keeps partial), retry-on-error inline, toast for the mapped error messages.
4. Auto-title: first user message's first 60 chars becomes the conversation title if untitled.
5. `ModelPicker` reading `config/models.ts`, defaulting from `/api/health`'s `default_model`, persisting per-conversation via PATCH.

### VERIFY (do this, don't skip)
- Full lesson-planning exchange streams smoothly on Haiku; a follow-up turn shows the model remembers the conversation (history is actually being sent).
- Switch a conversation to Sonnet mid-thread → next turn uses it (check server log's model id).
- Markdown torture test: a response with a table, a numbered list, and a code block renders cleanly.
- Stop mid-stream → partial text persists after reload.
- Report to `docs/reports/sprint-3.md`.

---

## VERIFY PROMPT B — separate thread, different model (after Sprints 2–3)

You are the verification pass for Chalk, sprints 2–3. RECON: read the brief, reports for sprints 2–3 and verify-A, then `frontend/src/`. Re-run every VERIFY step yourself. Audit specifically: (1) `lib/` purity — zero React imports, header comments present; (2) sanitizers actually applied on every load path (try hand-corrupting a row in SQLite: app must not crash); (3) token discipline — grep components for hex colors or font names that bypass `tokens.css`; (4) model branching — confirm no component branches on model id; (5) build `dist/` fresh and grep it for `ANTHROPIC`, `sk-ant`, and any absolute external URL. Write `docs/reports/verify-B.md` in the same shape as verify-A.

---

# PHASE 3 — POLISH

## Sprint 4 — Export, ergonomics, school-day hardening

### RECON
Read verify-B and fix its flagged items first. Skim all prior reports for deferred items; pull in any that are small.

### BUILD
1. Export conversation → downloads a clean `.md` transcript (title, date, project name, turns); copy-message button on each assistant turn.
2. Keyboard ergonomics: Enter sends / Shift+Enter newline, Esc aborts a stream, focus returns to the composer after send.
3. Edit-and-resend the last user turn (replaces the tail of the conversation from that point; old tail rows hard-deleted with a comment saying this is the one sanctioned hard delete).
4. A quiet header status dot driven by `/api/health` polling every 60s: green ok / amber API unreachable — tooltip carries the mapped message.
5. README.md and RUNBOOK.md finished to brief spec, including the school-laptop install path (copy repo, `python -m venv`, `pip install -r`, paste key into `.env`, double-click `start-chalk.cmd`).

### VERIFY (do this, don't skip)
- Export a real conversation and open the `.md` — readable, no HTML artifacts.
- Edit-and-resend produces a coherent thread with no orphan rows (check SQLite).
- Fresh-machine simulation: clone to a new folder, follow README verbatim, reach a working chat in under 10 minutes.
- Report to `docs/reports/sprint-4.md`.

---

## FINAL VERIFY — separate thread, different model (after Sprint 4)

You are the final verification pass for Chalk. RECON: read everything in `docs/reports/` and the brief, then the full codebase. Then run the release checklist end to end, yourself:

1. **Filter simulation (the reason this app exists):** with all network access disabled, the app loads and browses history cleanly and chat fails with the mapped "unreachable" toast — no hangs, no white screens, no console CDN errors. Re-enable network: chat streams.
2. **Key containment:** fresh `vite build`; grep `dist/` for `ANTHROPIC`, `sk-ant`, `api.anthropic.com`. All fetches in dist are same-origin. Grep server logs from a full session for lesson text — none at INFO.
3. **Bind & port:** 127.0.0.1:8020 confirmed; RUNBOOK documents it.
4. **Durability:** restart server + browser → projects, instructions, context, conversations, titles, models all intact. Corrupt one row by hand → app degrades to defaults, doesn't crash.
5. **Contract fidelity:** schema matches the brief's DDL; SSE events match the protocol; every divergence anywhere in the reports is either resolved or explicitly accepted.
6. **Report** `docs/reports/final-verify.md`: Ship / Don't-ship-yet with the exact remaining list. Be the friend who tells the truth, not the consultant who softens it.
