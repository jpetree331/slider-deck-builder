"""Lantern FastAPI service — assembled in the canonical order:
dotenv (via config) → logging → CORS → /api router → auth middleware →
StaticFiles mounted LAST → uvicorn.run.

Run: python -m src.lantern.api  (from the repo root), or start-lantern.cmd.
"""
import base64
import logging
from logging.handlers import RotatingFileHandler

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from . import config, store

# ── logging idiom ───────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
config.DATA_DIR.mkdir(parents=True, exist_ok=True)
_file_handler = RotatingFileHandler(config.DATA_DIR / "api.log",
                                    maxBytes=2 * 1024 * 1024, backupCount=3,
                                    encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(_file_handler)
logger = logging.getLogger("lantern.api")

app = FastAPI(title="Lantern", docs_url=None, redoc_url=None)

# CORS locked to the Vite dev origin; production is same-origin via StaticFiles.
app.add_middleware(CORSMiddleware,
                   allow_origins=[config.VITE_DEV_ORIGIN],
                   allow_methods=["*"], allow_headers=["*"],
                   allow_credentials=True)

api_router = APIRouter()


@api_router.get("/health")
def health():
    return {"status": "ok", "service": "lantern"}


@api_router.get("/decks")
def list_decks():
    return {"decks": store.list_decks()}


@api_router.delete("/decks/{deck_id}")
def delete_deck(deck_id: str):
    try:
        store.delete_deck(deck_id)
    except store.DeckNotFound:
        raise HTTPException(404, f"deck {deck_id} not found")
    return {"ok": True}


def _load_or_404(deck_id: str) -> dict:
    try:
        return store.load_deck(deck_id)
    except store.DeckNotFound:
        raise HTTPException(404, f"deck {deck_id} not found")
    except store.StoreError as e:
        raise HTTPException(500, str(e))


app.include_router(api_router, prefix="/api")


# ── optional Basic auth (DashboardAuthMiddleware pattern) ───────────────────
class DashboardAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Auth when LANTERN_PASSWORD is set; inert when it isn't.
    Username is ignored — the password is the whole secret."""

    async def dispatch(self, request: Request, call_next):
        if not config.PASSWORD:
            return await call_next(request)
        header = request.headers.get("authorization", "")
        if header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8")
                _, _, password = decoded.partition(":")
                if password == config.PASSWORD:
                    return await call_next(request)
            except Exception:
                pass
        return Response(status_code=401, content="Lantern: password required",
                        headers={"WWW-Authenticate": 'Basic realm="lantern"'})


app.add_middleware(DashboardAuthMiddleware)

# ── static frontend, mounted LAST so /api routes win ────────────────────────
_dist = config.REPO_ROOT / "dashboard" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="dashboard")
else:
    logger.info("dashboard/dist not found — dev mode, use the Vite server on 5179")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=config.PORT)
