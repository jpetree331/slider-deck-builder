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
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from . import chalk_db, config, export, outline, queue, render_service, store
from .chalk_api import chalk_router
from .outline_schema import MAX_POINT_WORDS, MAX_POINTS, validate_palette

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
    chalk_db.migrate()  # idempotent — numbered SQL, safe on every boot
    yield


app = FastAPI(title="Lantern", docs_url=None, redoc_url=None, lifespan=_lifespan)

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

    # mirror outline_schema's painted-text limits — edits must not be able to
    # degrade what the outline validators enforced (invariant 6's other half)
    @field_validator("title", "visual_description")
    @classmethod
    def painted_text_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must be non-empty — this text drives the painting")
        return v

    @field_validator("points")
    @classmethod
    def points_are_short(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_POINTS:
            raise ValueError(f"at most {MAX_POINTS} points per slide — they get painted")
        for p in v:
            if len(p.split()) > MAX_POINT_WORDS:
                raise ValueError(f"point {p!r} is over {MAX_POINT_WORDS} words — "
                                 "long text breaks slides")
        return v


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

    @field_validator("art_direction")
    @classmethod
    def art_direction_nonempty(cls, v):
        if v is not None and not v.strip():
            raise ValueError("art_direction is the deck's whole visual identity "
                             "— it can't be emptied")
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


# ── Sprint 3/4: render pipeline ─────────────────────────────────────────────

@api_router.post("/decks/{deck_id}/slides/{n}/render")
def render_slide(deck_id: str, n: int):
    """Single-slide (re)render — routed through the queue since Sprint 4."""
    _load_or_404(deck_id)
    try:
        return queue.enqueue_slide(deck_id, n)
    except queue.DeckBusy as e:
        raise HTTPException(409, str(e))
    except render_service.SlideNotFound as e:
        raise HTTPException(404, str(e))


@api_router.post("/decks/{deck_id}/render")
def render_deck(deck_id: str):
    _load_or_404(deck_id)
    try:
        return queue.enqueue_deck(deck_id)
    except queue.DeckBusy as e:
        raise HTTPException(409, str(e))


@api_router.post("/decks/{deck_id}/cancel")
def cancel_render(deck_id: str):
    _load_or_404(deck_id)
    return queue.cancel(deck_id)


# ── Sprint 5: library ───────────────────────────────────────────────────────

@api_router.post("/decks/{deck_id}/duplicate")
def duplicate_deck(deck_id: str):
    _load_or_404(deck_id)
    return store.duplicate_deck(deck_id)


# ── Sprint 6: export ────────────────────────────────────────────────────────

_EXPORT_TYPES = {"pptx": ("application/vnd.openxmlformats-officedocument"
                          ".presentationml.presentation"),
                 "pdf": "application/pdf",
                 "zip": "application/zip"}


@api_router.post("/decks/{deck_id}/export")
def export_deck(deck_id: str, fmt: Literal["pptx", "pdf", "zip"],
                allow_partial: bool = False):
    _load_or_404(deck_id)
    try:
        path = export.export_deck(deck_id, fmt, allow_partial=allow_partial)
    except (export.NotFullyRendered, export.NothingToExport) as e:
        raise HTTPException(409, str(e))
    return {"download_url": f"/api/decks/{deck_id}/exports/{path.name}"}


@api_router.get("/decks/{deck_id}/exports/{filename}")
def download_export(deck_id: str, filename: str):
    _load_or_404(deck_id)
    path = store.exports_dir(deck_id) / filename
    # exports_dir is flat — refuse anything path-shaped
    if "/" in filename or "\\" in filename or ".." in filename or not path.exists():
        raise HTTPException(404, f"no export named {filename}")
    ext = filename.rpartition(".")[2]
    return Response(path.read_bytes(),
                    media_type=_EXPORT_TYPES.get(ext, "application/octet-stream"),
                    headers={"Content-Disposition":
                             f'attachment; filename="{filename}"'})


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


api_router.include_router(chalk_router)  # the Chalk chat tab: /api/chalk/*
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

# CORS locked to the Vite dev origin; production is same-origin via StaticFiles.
# Registered AFTER the auth middleware on purpose: add_middleware prepends, so
# CORS ends up OUTERMOST and browser preflights (which carry no credentials)
# get their headers instead of a blank 401 when LANTERN_PASSWORD is set.
app.add_middleware(CORSMiddleware,
                   allow_origins=[config.VITE_DEV_ORIGIN],
                   allow_methods=["*"], allow_headers=["*"],
                   allow_credentials=True)

# ── static frontend, mounted LAST so /api routes win ────────────────────────
class SpaStaticFiles(StaticFiles):
    """Serve the built app; unknown non-API paths fall back to index.html so
    deep links (/new, /decks/xyz) survive hard refreshes and shared URLs."""

    async def get_response(self, path: str, scope):
        # real files (hashed bundles) and unmatched /api/* paths must 404
        # honestly, not serve HTML — a typo'd endpoint should surface as a
        # clean ApiError, never a JSON-parse failure on index.html
        # (path arrives os-normalized — backslashes on Windows)
        norm = path.replace("\\", "/")
        fallback = not (norm.startswith("assets/") or norm.startswith("api/")
                        or norm == "api")
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404 and fallback:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and fallback:
            return await super().get_response("index.html", scope)
        return response


_dist = config.REPO_ROOT / "dashboard" / "dist"
if _dist.exists():
    app.mount("/", SpaStaticFiles(directory=_dist, html=True), name="dashboard")
else:
    logger.info("dashboard/dist not found — dev mode, use the Vite server on 5179")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=config.PORT)
