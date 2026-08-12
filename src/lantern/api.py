"""Lantern FastAPI service — assembled in the canonical order:
dotenv (via config) → logging → CORS → /api router → auth middleware →
StaticFiles mounted LAST → uvicorn.run.

Run: python -m src.lantern.api  (from the repo root), or start-lantern.cmd.
"""
import base64
import logging
from logging.handlers import RotatingFileHandler

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from . import config, gemini, outline, render_service, store
from .outline_schema import validate_palette

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

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    swept = store.sweep_interrupted()  # restarts never leave zombie state
    if swept:
        logger.info("boot sweep: marked interrupted renders in %d deck(s)", swept)
    yield


app = FastAPI(title="Lantern", docs_url=None, redoc_url=None, lifespan=_lifespan)

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


# ── Sprint 2: outline engine ────────────────────────────────────────────────

class CreateDeckRequest(BaseModel):
    topic: str
    source_notes: str = ""
    slide_count: int | None = None
    style_hints: str = ""
    slide_size: Literal["1K", "2K", "4K"] = "2K"

    @field_validator("topic")
    @classmethod
    def topic_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("topic must be non-empty")
        return v


class SlidePatch(BaseModel):
    n: int | None = None  # slide's CURRENT position, None = new slide
    title: str = ""
    points: list[str] = []
    visual_description: str = ""
    layout_hint: str = ""


class StyleGuidePatch(BaseModel):
    palette: list[str] | None = None
    typography: str | None = None
    motif: str | None = None
    art_direction: str | None = None
    tone: str | None = None

    @field_validator("palette")
    @classmethod
    def palette_is_hex(cls, v):
        if v is not None:
            validate_palette(v)
            if not 3 <= len(v) <= 5:
                raise ValueError("palette must be 3-5 colors")
        return v


class PatchDeckRequest(BaseModel):
    title: str | None = None
    style_guide: StyleGuidePatch | None = None
    slides: list[SlidePatch] | None = None
    slide_size: Literal["1K", "2K", "4K"] | None = None


@api_router.post("/decks")
def create_deck(req: CreateDeckRequest):
    count = None
    if req.slide_count is not None:
        count = max(1, min(config.MAX_SLIDES, req.slide_count))  # the cost guard
    try:
        result = outline.generate_outline(req.topic, req.source_notes, count,
                                          req.style_hints)
    except outline.OutlineError as e:
        raise HTTPException(503, str(e))
    except Exception as e:  # provider/SDK failures (bad key, network, 5xx)
        logger.exception("outline call failed")
        raise HTTPException(503, f"outline model unavailable: {e}")
    deck = store.create_deck(
        title=result.title, topic=req.topic, source_notes=req.source_notes,
        style_guide=result.style_guide.model_dump(),
        slides=[s.model_dump() for s in result.slides],
        slide_size=req.slide_size)
    return deck


@api_router.get("/decks/{deck_id}")
def get_deck(deck_id: str):
    return _load_or_404(deck_id)


@api_router.patch("/decks/{deck_id}")
def patch_deck(deck_id: str, req: PatchDeckRequest):
    with store.LOCK:
        deck = _load_or_404(deck_id)

        def mutate(d):
            if req.title is not None and req.title.strip():
                d["title"] = req.title.strip()
            if req.slide_size is not None:
                d["slide_size"] = req.slide_size
            if req.style_guide is not None:
                for key, value in req.style_guide.model_dump(exclude_none=True).items():
                    d["style_guide"][key] = value

        deck = store.update_deck(deck_id, mutate)
        if req.slides is not None:
            deck = store.patch_slides(deck_id,
                                      [s.model_dump() for s in req.slides])
    return deck


# ── Sprint 3: slide renderer ────────────────────────────────────────────────

@api_router.post("/decks/{deck_id}/slides/{n}/render")
def render_slide(deck_id: str, n: int):
    _load_or_404(deck_id)
    try:
        return render_service.render_slide(deck_id, n)
    except render_service.AlreadyRendering as e:
        raise HTTPException(409, str(e))
    except render_service.SlideNotFound as e:
        raise HTTPException(404, str(e))
    except gemini.RenderError as e:
        raise HTTPException(503, str(e))


@api_router.get("/decks/{deck_id}/slides/{n}.png")
def slide_image(deck_id: str, n: int, request: Request):
    deck = _load_or_404(deck_id)
    path = store.slide_image_path(deck_id, n)
    if not path.exists():
        raise HTTPException(404, f"slide {n} has no image yet")
    rendered_at = ""
    for slide in deck["slides"]:
        if slide["n"] == n and slide["render"]:
            rendered_at = slide["render"].get("rendered_at") or ""
    etag = f'"{rendered_at or int(path.stat().st_mtime)}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    return Response(path.read_bytes(), media_type="image/png",
                    headers={"ETag": etag, "Cache-Control": "no-cache"})


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
