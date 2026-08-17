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
# Owner reversal 2026-08-13 (see DECISIONS.md): Gemini 3.1 Pro writes richer
# image briefs than Haiku did. Any claude-* id here routes back through the
# Anthropic SDK — Haiku remains one .env edit away.
OUTLINE_MODEL = os.environ.get("LANTERN_OUTLINE_MODEL", "gemini-3.1-pro-preview")
IMAGE_MODEL = os.environ.get("LANTERN_IMAGE_MODEL", "gemini-3-pro-image-preview")
MAX_SLIDES = int(os.environ.get("LANTERN_MAX_SLIDES", "16"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
NANOGPT_API_KEY = os.environ.get("NANOGPT_API_KEY", "")

# Chalk (the chat tab) — CHALK_-prefixed knobs, consolidated from its plan
CHALK_DB_PATH = Path(os.environ.get("CHALK_DB_PATH", "data/chalk.db"))
if not CHALK_DB_PATH.is_absolute():
    CHALK_DB_PATH = REPO_ROOT / CHALK_DB_PATH
CHALK_DEFAULT_MODEL = os.environ.get("CHALK_DEFAULT_MODEL", "claude-haiku-4-5")
CHALK_MAX_TOKENS = int(os.environ.get("CHALK_MAX_TOKENS", "8192"))
CHALK_HISTORY_CHAR_BUDGET = int(os.environ.get("CHALK_HISTORY_CHAR_BUDGET",
                                               "100000"))

VITE_DEV_ORIGIN = "http://localhost:5179"
