"""Lantern config — path-anchored dotenv load, typed reads, inline defaults.

Every knob lives here; no other module calls os.environ for LANTERN_* values.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=True)

PORT = int(os.environ.get("LANTERN_PORT", "8020"))
DATA_DIR = Path(os.environ.get("LANTERN_DATA_DIR", "data"))
if not DATA_DIR.is_absolute():
    DATA_DIR = REPO_ROOT / DATA_DIR
PASSWORD = os.environ.get("LANTERN_PASSWORD", "")
OUTLINE_MODEL = os.environ.get("LANTERN_OUTLINE_MODEL", "claude-haiku-4-5-20251001")
IMAGE_MODEL = os.environ.get("LANTERN_IMAGE_MODEL", "gemini-3-pro-image-preview")
MAX_SLIDES = int(os.environ.get("LANTERN_MAX_SLIDES", "16"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

VITE_DEV_ORIGIN = "http://localhost:5179"
