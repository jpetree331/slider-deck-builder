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
- **Stop:** Ctrl-C in the console, or `taskkill /f /im python.exe` (blunt — checks nothing else is using python), or End Task in Task Manager.
- **Restart:** stop, then start. Interrupted renders are swept to `error: "interrupted"` on boot — nothing gets stuck.

## Task Scheduler registration (run once, not yet executed)

1. Task Scheduler → Create Task → name `Lantern`.
2. Trigger: At log on (your user).
3. Action: Start a program → `start-lantern.cmd` in this repo's root; "Start in" = this repo's root.
4. Settings: "If the task fails, restart every 1 minute", up to 3 times.
5. Check: log off/on, then `curl http://localhost:8020/api/health` → `{"status":"ok","service":"lantern"}`.

## Env knobs

See `.env.example` — every knob is commented there. The two keys are server-side only, forever.

## Known failure modes → fixes

(Seeded in Sprint 6.)
