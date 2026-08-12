"""Outline payload schema — pure Pydantic, framework-free on purpose
(no FastAPI imports) so verify scripts can exercise it headless.

The limits here are load-bearing: slide text gets PAINTED into images,
and long text breaks slides.
"""
import re

from pydantic import BaseModel, Field, field_validator

from . import config

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

MAX_POINTS = 4
MAX_POINT_WORDS = 12


def validate_palette(v: list[str]) -> list[str]:
    """Shared by StyleGuide and the PATCH request model in api.py."""
    for c in v:
        if not _HEX_RE.match(c):
            raise ValueError(f"palette entry {c!r} is not a #RRGGBB hex color")
    return v


class StyleGuide(BaseModel):
    palette: list[str] = Field(min_length=3, max_length=5)
    typography: str
    motif: str
    art_direction: str  # THE consistency field — quoted verbatim into every slide prompt
    tone: str

    @field_validator("palette")
    @classmethod
    def palette_is_hex(cls, v: list[str]) -> list[str]:
        return validate_palette(v)

    @field_validator("art_direction")
    @classmethod
    def art_direction_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("art_direction must be a cohesive prose paragraph, not empty")
        return v


class SlideSpec(BaseModel):
    title: str
    points: list[str] = Field(default_factory=list, max_length=MAX_POINTS)
    visual_description: str
    layout_hint: str = ""

    @field_validator("title", "visual_description")
    @classmethod
    def required_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must be non-empty — this text drives the painting")
        return v

    @field_validator("points")
    @classmethod
    def points_are_short(cls, v: list[str]) -> list[str]:
        for p in v:
            if len(p.split()) > MAX_POINT_WORDS:
                raise ValueError(
                    f"point {p!r} is over {MAX_POINT_WORDS} words — long text breaks slides")
        return v


class DeckOutline(BaseModel):
    title: str
    style_guide: StyleGuide
    slides: list[SlideSpec] = Field(min_length=1, max_length=config.MAX_SLIDES)

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("deck title must be non-empty")
        return v
