"""Chalk chat store — stdlib sqlite3, no ORM, framework-free on purpose
(no FastAPI imports) so verify scripts can exercise it headless.

Migrations are numbered idempotent SQL in chalk_migrations/, run in order at
startup. Defensive-load sanitizers on every read — corrupt rows coerce to
safe defaults or get skipped with a logged warning, never crash the app.
"""
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .store import make_id

logger = logging.getLogger("lantern.chalk.db")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "chalk_migrations"

ROLES = ("user", "assistant")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(v, default: str = "") -> str:
    return v if isinstance(v, str) else default


def connect() -> sqlite3.Connection:
    config.CHALK_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.CHALK_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma foreign_keys = on")
    return conn


def migrate() -> None:
    """Run every numbered migration, in order. Idempotent by construction."""
    with connect() as conn:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.executescript(path.read_text(encoding="utf-8"))
    logger.info("chalk db ready at %s", config.CHALK_DB_PATH)


# ── sanitizers ──────────────────────────────────────────────────────────────

def _project_row(row) -> dict:
    return {
        "id": _safe_str(row["id"]),
        "name": _safe_str(row["name"], "Untitled project"),
        "instructions": _safe_str(row["instructions"]),
        "context": _safe_str(row["context"]),
        "created_at": _safe_str(row["created_at"]),
        "updated_at": _safe_str(row["updated_at"]),
    }


def _conversation_row(row) -> dict:
    return {
        "id": _safe_str(row["id"]),
        "project_id": _safe_str(row["project_id"]),
        "title": _safe_str(row["title"], "New conversation"),
        "model": _safe_str(row["model"], config.CHALK_DEFAULT_MODEL),
        "created_at": _safe_str(row["created_at"]),
        "updated_at": _safe_str(row["updated_at"]),
    }


def _message_row(row) -> dict | None:
    role = row["role"]
    if role not in ROLES:
        logger.warning("skipping message %s with bad role %r", row["id"], role)
        return None
    return {
        "id": _safe_str(row["id"]),
        "conversation_id": _safe_str(row["conversation_id"]),
        "role": role,
        "content": _safe_str(row["content"]),
        "created_at": _safe_str(row["created_at"]),
    }


# ── projects ────────────────────────────────────────────────────────────────

def list_projects() -> list:
    with connect() as conn:
        rows = conn.execute(
            "select * from projects where deleted_at is null "
            "order by updated_at desc").fetchall()
    return [_project_row(r) for r in rows]


def get_project(project_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "select * from projects where id = ? and deleted_at is null",
            (project_id,)).fetchone()
    return _project_row(row) if row else None


def create_project(name: str) -> dict:
    pid, now = make_id("pj"), _now()
    with connect() as conn:
        conn.execute(
            "insert into projects (id, name, created_at, updated_at) "
            "values (?, ?, ?, ?)", (pid, name, now, now))
    logger.info("created project %s", pid)
    return get_project(pid)


def update_project(project_id: str, *, name=None, instructions=None,
                   context=None) -> dict | None:
    sets, args = ["updated_at = ?"], [_now()]
    for column, value in (("name", name), ("instructions", instructions),
                          ("context", context)):
        if value is not None:
            sets.append(f"{column} = ?")
            args.append(value)
    args.append(project_id)
    with connect() as conn:
        conn.execute(f"update projects set {', '.join(sets)} "
                     "where id = ? and deleted_at is null", args)
    return get_project(project_id)


def delete_project(project_id: str) -> None:
    """Soft delete — tombstone the project and its conversations."""
    now = _now()
    with connect() as conn:
        conn.execute("update projects set deleted_at = ?, updated_at = ? "
                     "where id = ?", (now, now, project_id))
        conn.execute("update conversations set deleted_at = ?, updated_at = ? "
                     "where project_id = ? and deleted_at is null",
                     (now, now, project_id))
    logger.info("soft-deleted project %s", project_id)


# ── conversations ───────────────────────────────────────────────────────────

def list_conversations(project_id: str) -> list:
    with connect() as conn:
        rows = conn.execute(
            "select * from conversations where project_id = ? "
            "and deleted_at is null order by updated_at desc",
            (project_id,)).fetchall()
    return [_conversation_row(r) for r in rows]


def get_conversation(conversation_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "select * from conversations where id = ? and deleted_at is null",
            (conversation_id,)).fetchone()
    return _conversation_row(row) if row else None


def create_conversation(project_id: str, model: str | None = None) -> dict:
    cid, now = make_id("cv"), _now()
    with connect() as conn:
        conn.execute(
            "insert into conversations (id, project_id, model, created_at, "
            "updated_at) values (?, ?, ?, ?, ?)",
            (cid, project_id, model or config.CHALK_DEFAULT_MODEL, now, now))
    logger.info("created conversation %s in project %s", cid, project_id)
    return get_conversation(cid)


def update_conversation(conversation_id: str, *, title=None,
                        model=None) -> dict | None:
    sets, args = ["updated_at = ?"], [_now()]
    for column, value in (("title", title), ("model", model)):
        if value is not None:
            sets.append(f"{column} = ?")
            args.append(value)
    args.append(conversation_id)
    with connect() as conn:
        conn.execute(f"update conversations set {', '.join(sets)} "
                     "where id = ? and deleted_at is null", args)
    return get_conversation(conversation_id)


def delete_conversation(conversation_id: str) -> None:
    now = _now()
    with connect() as conn:
        conn.execute("update conversations set deleted_at = ?, updated_at = ? "
                     "where id = ?", (now, now, conversation_id))
    logger.info("soft-deleted conversation %s", conversation_id)


# ── messages ────────────────────────────────────────────────────────────────

def list_messages(conversation_id: str) -> list:
    with connect() as conn:
        # rowid = insertion order; created_at text can tie within the clock's
        # resolution, and a random-id tiebreak would scramble turns
        rows = conn.execute(
            "select * from messages where conversation_id = ? "
            "order by rowid", (conversation_id,)).fetchall()
    return [m for m in (_message_row(r) for r in rows) if m is not None]


def add_message(conversation_id: str, role: str, content: str) -> dict:
    if role not in ROLES:
        raise ValueError(f"bad role {role!r}")
    mid, now = make_id("ms"), _now()
    with connect() as conn:
        conn.execute(
            "insert into messages (id, conversation_id, role, content, "
            "created_at) values (?, ?, ?, ?, ?)",
            (mid, conversation_id, role, content, now))
        conn.execute("update conversations set updated_at = ? where id = ?",
                     (now, conversation_id))
    # log ids and sizes, never content — it's a school laptop
    logger.info("message %s (%s, %d chars) -> conversation %s",
                mid, role, len(content), conversation_id)
    return {"id": mid, "conversation_id": conversation_id, "role": role,
            "content": content, "created_at": now}
