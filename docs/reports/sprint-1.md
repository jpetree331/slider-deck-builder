# Sprint 1 report — Chassis

## What shipped

- Repo skeleton: `src/lantern/` (config, store, api), `dashboard/` (Vite + React + TS), `scripts/`, `docs/reports/`, `data/` (gitignored, `.gitkeep`), `RUNBOOK.md` + `DECISIONS.md` stubs, placeholder `README.md`, `.gitignore`, `BUILD_BRIEF.md`.
- `config.py`: path-anchored dotenv load with override, typed reads with inline defaults for every `LANTERN_*` knob.
- `store.py` (framework-free): `make_id`/`makeId`, `deck_dir`, `create_deck`, `load_deck` with defensive sanitizers, atomic `save_deck` (tmp + `os.replace`), `list_decks`, `delete_deck`. Path-traversal-shaped ids refused.
- `api.py` in the canonical order: dotenv (via config) → logging idiom with RotatingFileHandler (`data/api.log`, 2 MB × 3) → CORS locked to `http://localhost:5179` → `APIRouter` under `/api` → health probe → `DashboardAuthMiddleware` (Basic auth when `LANTERN_PASSWORD` set, inert otherwise) → StaticFiles on `dashboard/dist` mounted LAST → `uvicorn.run(127.0.0.1:8020)`. Endpoints: health, list decks, delete deck.
- Dashboard: Vite 8 scaffold, port 5179 with `/api` proxy, `tokens.css` (warm bookish: Playfair Display / Libre Franklin / IBM Plex Mono on a dark gallery-wall canvas, spacing/radius/color custom properties only), router with `LibraryPage` (real empty state pulling `GET /api/decks`) and stub `NewDeckPage` / `OutlinePage` / `DeckPage`, `lib/types.ts` mirroring `deck.json` field-for-field, `lib/api.ts` as the only fetch site.
- Ops: `start-lantern.cmd` (PYTHONUTF8=1, repo-relative, append-to-log), RUNBOOK ports table + start/stop/restart + Task Scheduler steps (written, not executed).
- Verify scripts: `scripts/verify_store.py`, `scripts/verify-sprint1.mjs`.

## Version lock (exact resolved versions)

| Piece | Version |
|---|---|
| Python | 3.12.10 |
| fastapi | 0.141.1 |
| uvicorn | 0.52.1 |
| httpx | 0.28.1 |
| anthropic | 0.121.0 |
| pydantic | 2.13.4 |
| python-dotenv | 1.2.2 |
| Pillow | 12.3.0 |
| python-pptx | 1.0.2 |
| img2pdf | 0.6.3 |
| Node | 26.5.0 |
| npm | 11.17.0 |
| vite | ^8.2.0 |
| react / react-dom | ^19.2.8 |
| typescript | ~6.0.2 |
| @vitejs/plugin-react | ^6.0.4 |
| react-router-dom | ^7 (see dashboard/package.json) |

## What you need to do once

- Copy `.env.example` → `.env`, add the two API keys.
- `python -m venv .venv` + `pip install -r requirements.txt`; `npm install` in `dashboard/`.
- Register the Task Scheduler entry per RUNBOOK when deploying for real.

## What's deferred

- Everything Sprint 2+ (outline, render, queue, viewer, export).
- Manual Ctrl-C-mid-save stress test: atomicity is by construction (tmp + `os.replace` is atomic on NTFS) and the verify script asserts no tmp residue; the interactive kill test wasn't run in this environment.

## Verification

- `verify_store.py`: all 18 checks pass (round-trip, sanitizers, corrupt-file clean error, list skips corrupt, delete, purity).
- `verify-sprint1.mjs`: all checks pass (lib purity, ports/proxy, env surface, canonical order, types mirror, ops files).
- `npm run build` clean; service boots; `GET /api/health` → `{"status":"ok","service":"lantern"}`; static root serves the built app with `/api` still winning.
- With `LANTERN_PASSWORD=test`: bare health call → 401 with `WWW-Authenticate`; with Basic credentials → 200.

## Divergences

1. **Repo root** is this directory (`Slide-Builder`, GitHub `jpetree331/slider-deck-builder`), not `E:\git\Lantern` — per the owner's instruction at kickoff. All plan references to the old path map here.
2. **TypeScript resolved to 6.0.2** (plan named 5.x) — current create-vite template; kept, now part of the lock.
3. **Node is 26.5.0** (plan named 22 LTS) — what the build machine runs; kept.
4. **oxlint** ships in the current create-vite template instead of eslint; kept.
5. `start-lantern.cmd` uses `%~dp0` instead of a hard-coded `cd /d` path so the script survives the repo-root divergence.
6. Store helper is `make_id` (Python idiom) with a `makeId` alias preserving the brief's spelling.
7. Purity checks in verify scripts match actual `import` statements, not substrings — the naive version false-positived on docstrings that *state* the invariant.
