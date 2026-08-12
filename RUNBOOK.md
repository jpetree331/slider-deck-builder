# Lantern RUNBOOK

## Ports

| Port | What | Notes |
|---|---|---|
| 8020 | Lantern FastAPI service | claimed — 8000/8001/8002/8005/8007/8010 belong to other services |
| 5179 | Vite dev server | dev only; 5173/5174/5178 belong to other frontends |

## Start / stop / restart

- **Start (dev, backend):** `.venv\Scripts\python.exe -m src.lantern.api` from the repo root, or double-click `start-lantern.cmd` (logs append to `data\service.log`).
- **Start (dev, frontend):** `npm run dev` inside `dashboard/` → http://localhost:5179 (proxies `/api` to 8020).
- **Production:** `npm run build` inside `dashboard/`, then just the backend — it serves `dashboard/dist` itself at http://localhost:8020/.
- **Stop:** Ctrl-C in the console, or End Task on the `python.exe` running from this repo's `.venv` in Task Manager.
- **Restart:** stop, then start. The boot sweep flips anything stuck in `rendering` to `error: "interrupted"` — restarts never leave zombie state; hit Render to resume.

## Task Scheduler registration (run once on the machine that hosts Lantern)

1. Task Scheduler → Create Task → name `Lantern`.
2. Trigger: **At log on** (your user).
3. Action: Start a program → `start-lantern.cmd` in this repo's root; **Start in** = this repo's root.
4. Settings: **If the task fails, restart every 1 minute**, up to **3** times. Uncheck "Stop the task if it runs longer than".
5. Verify: log off/on, then `curl http://localhost:8020/api/health` → `{"status":"ok","service":"lantern"}` without touching a terminal.

*(Not yet registered — this build ran on a different machine than the deployment target. Do steps 1–5 when deploying.)*

## Env knobs

Every knob is documented inline in `.env.example` — keys, port, data dir, password, model pins, slide cap. `.env` overrides shell env (path-anchored `load_dotenv(..., override=True)`).

## Logs

- `data/api.log` — rotating (2 MB × 3), all `lantern.*` loggers. Every successful render logs one cost line: `lantern.render: slide N SIZE ~$est (deck total ~$sum)`.
- `data/service.log` — stdout/stderr appended by `start-lantern.cmd`.

## Known failure modes → fixes

| Symptom | Cause | Fix |
|---|---|---|
| Slide chip says `error: interrupted` | Service restarted mid-paint (boot sweep marked it) | Open the deck, hit **Render** (or the slide's **Paint**) — only missing slides re-render |
| Render fails instantly, deck goes `error`, message mentions `HTTP 400/403/404` from Google | `GEMINI_API_KEY` is free-tier (Nano Banana Pro needs paid), the key is wrong, or the pinned model string moved | Check the key in Google AI Studio billing; if the model moved, update `LANTERN_IMAGE_MODEL` in `.env` and record it in DECISIONS.md |
| `POST /api/decks` returns 503 | Anthropic key missing/invalid, or the outline model returned junk twice | Check `ANTHROPIC_API_KEY`; `data/api.log` has the raw model response |
| Service won't start; log says port 8020 in use | Another process claimed 8020 | `netstat -ano \| findstr :8020` → identify the PID; either stop it or set `LANTERN_PORT` to a free port and update this table |
| Browser asks for a password | `LANTERN_PASSWORD` is set | That's the point — any username, that password. Blank it in `.env` and restart to disable |
| Everything 401s from a phone over Tailscale | Password set, phone browser cached bad credentials | Reopen the site, re-enter; or use an incognito tab |
| Deck folder exists but the library shows nothing / skips it | Corrupt `deck.json` (the log says "skipping unreadable deck folder") | The PNGs are safe. Restore `deck.json` from a backup zip, or rebuild it by hand from the schema in `BUILD_BRIEF.md` |
| Images look stale after a repaint | Aggressive proxy cache | Hard refresh; image URLs are versioned by `rendered_at` and the API sends `no-cache` + ETag, so plain reloads always revalidate |

## Do-not-disturb inventory

- `data/decks/**` — the decks themselves. Never hand-edit `deck.json` while the service is mid-render.
- `.env` — the only place keys live. Never commit it, never paste it into a deck.
