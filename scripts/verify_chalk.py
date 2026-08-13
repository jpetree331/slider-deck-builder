"""Chalk verify — db, context assembly, allowlist sync, SSE protocol, key
containment. Offline by default (throwaway SQLite, stubbed providers).

    python scripts/verify_chalk.py                 # offline + live Haiku turn
                                                   #   (skipped without a key)
    python scripts/verify_chalk.py --live-gemini   # + one Gemini Flash turn

The live Haiku turn costs well under a cent and runs whenever
ANTHROPIC_API_KEY is set, per the Chalk plan's own verify step.
"""
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles

_tmpdir = tempfile.mkdtemp(prefix="lantern-verify-")
os.environ["CHALK_DB_PATH"] = str(Path(_tmpdir) / "chalk.db")
os.environ["LANTERN_DATA_DIR"] = _tmpdir

import httpx  # noqa: E402

from src.lantern import chalk_chat, chalk_db, config  # noqa: E402

FAILS = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


check("throwaway db in effect (guard against .env override)",
      str(config.CHALK_DB_PATH).startswith(_tmpdir))
if str(config.CHALK_DB_PATH) != os.environ["CHALK_DB_PATH"]:
    print("ABORT: real .env overrode CHALK_DB_PATH — refusing to test "
          "against the real chat db")
    sys.exit(1)

print("verify_chalk: migrations idempotent")
chalk_db.migrate()
chalk_db.migrate()
check("migrate twice, no error", True)

print("verify_chalk: CRUD + soft deletes")
project = chalk_db.create_project("Bio – Cells Unit")
check("project created", project["name"] == "Bio – Cells Unit")
chalk_db.update_project(project["id"], instructions="Be practical.",
                        context="Pacing guide text")
project = chalk_db.get_project(project["id"])
check("project fields persist",
      project["instructions"] == "Be practical."
      and project["context"] == "Pacing guide text")

conv = chalk_db.create_conversation(project["id"])
check("conversation defaults to the default model",
      conv["model"] == config.CHALK_DEFAULT_MODEL)
chalk_db.update_conversation(conv["id"], title="Membrane lab ideas",
                             model="gemini-flash-latest")
conv = chalk_db.get_conversation(conv["id"])
check("title + model patch", conv["title"] == "Membrane lab ideas"
      and conv["model"] == "gemini-flash-latest")

chalk_db.add_message(conv["id"], "user", "hello")
chalk_db.add_message(conv["id"], "assistant", "hi there")
check("messages round-trip",
      [m["role"] for m in chalk_db.list_messages(conv["id"])] == ["user", "assistant"])

conv2 = chalk_db.create_conversation(project["id"])
chalk_db.delete_conversation(conv2["id"])
check("soft-deleted conversation filtered from list",
      all(c["id"] != conv2["id"] for c in chalk_db.list_conversations(project["id"])))
with chalk_db.connect() as raw:
    row = raw.execute("select deleted_at from conversations where id = ?",
                      (conv2["id"],)).fetchone()
check("tombstone row still in sqlite with deleted_at set",
      row is not None and row["deleted_at"] is not None)

print("verify_chalk: sanitizers on corrupt rows")
with chalk_db.connect() as raw:
    raw.execute("pragma ignore_check_constraints = on")
    raw.execute("insert into messages (id, conversation_id, role, content, "
                "created_at) values ('ms_bad', ?, 'gremlin', 'x', '2026')",
                (conv["id"],))
msgs = chalk_db.list_messages(conv["id"])
check("bad-role row skipped without crash",
      all(m["id"] != "ms_bad" for m in msgs) and len(msgs) == 2)

print("verify_chalk: context assembly")
system, messages = chalk_chat.build_request("Be brief.", "", [], "question")
check("context suffix skipped when empty", system == "Be brief.")
system, _ = chalk_chat.build_request("Be brief.", "KNOWLEDGE", [], "q")
check("context quoted into system",
      system == "Be brief.\n\n---\nProject knowledge:\nKNOWLEDGE")
history = [{"role": "user", "content": "a" * 60},
           {"role": "assistant", "content": "b" * 60},
           {"role": "user", "content": "c" * 60}]
_, trimmed = chalk_chat.build_request("", "", history, "NEWEST", char_budget=100)
check("history trims from the front, newest user message survives",
      trimmed[-1]["content"] == "NEWEST" and len(trimmed) < 4)
_, untrimmed = chalk_chat.build_request("", "", history, "NEWEST",
                                       char_budget=10_000)
check("no trim under budget", len(untrimmed) == 4)

print("verify_chalk: model allowlist mirrors models.ts")
models_ts = (REPO / "dashboard" / "src" / "config" / "models.ts").read_text(
    encoding="utf-8")
ts_ids = set(re.findall(r"id:\s*'([^']+)'", models_ts))
check("same ids in models.ts and ALLOWED_MODELS",
      ts_ids == set(chalk_chat.ALLOWED_MODELS))
check("default model is allowlisted",
      config.CHALK_DEFAULT_MODEL in chalk_chat.ALLOWED_MODELS)
try:
    chalk_chat.resolve_provider("gpt-9000")
    check("unknown model raises ChatError", False)
except chalk_chat.ChatError as e:
    check("unknown model raises ChatError", e.status == 400)

print("verify_chalk: SSE protocol over the wire (stubbed provider)")
import asyncio  # noqa: E402

from src.lantern.api import app  # noqa: E402  (after env guards)

real_stream = chalk_chat.stream_chat


def stub_stream(model, system, messages, max_tokens=None):
    yield ("delta", "Hello ")
    yield ("delta", "teacher!")
    yield ("done", {"input_tokens": 12, "output_tokens": 4})


def stub_fail(model, system, messages, max_tokens=None):
    yield ("delta", "partial ")
    raise chalk_chat.ChatError("api.anthropic.com unreachable — check the "
                               "network", 503)


def parse_events(body: str) -> list:
    events = []
    for frame in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in frame.split("\n")
                     if ": " in line)
        if "data" in lines:
            events.append((lines.get("event"), json.loads(lines["data"])))
    return events


async def sse_checks():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 timeout=30) as client:
        chalk_chat.stream_chat = stub_stream
        async with client.stream(
                "POST", "/api/chalk/chat",
                json={"conversation_id": conv["id"], "content": "hi"}) as r:
            check("chat streams as text/event-stream",
                  r.headers["content-type"].startswith("text/event-stream"))
            body = "".join([chunk async for chunk in r.aiter_text()])
        events = parse_events(body)
        check("delta events then done",
              [e[0] for e in events] == ["delta", "delta", "done"])
        check("done carries message id + token counts",
              events[-1][1]["message_id"] and events[-1][1]["input_tokens"] == 12)
        msgs = chalk_db.list_messages(conv["id"])
        check("user + assistant rows persisted",
              msgs[-2]["role"] == "user" and msgs[-1]["content"] == "Hello teacher!")

        chalk_chat.stream_chat = stub_fail
        async with client.stream(
                "POST", "/api/chalk/chat",
                json={"conversation_id": conv["id"], "content": "again"}) as r:
            body = "".join([chunk async for chunk in r.aiter_text()])
        check("error event mapped with status",
              '"status": 503' in body and "unreachable" in body)
        check("partial text persisted on failure",
              chalk_db.list_messages(conv["id"])[-1]["content"] == "partial ")
        chalk_chat.stream_chat = real_stream

        r = await client.patch(f"/api/chalk/conversations/{conv['id']}",
                               json={"model": "gpt-9000"})
        check("bad model on conversation PATCH 422s", r.status_code == 422)
        r = await client.get("/api/chalk/health")
        check("chalk health shape",
              r.json()["default_model"] == config.CHALK_DEFAULT_MODEL)


try:
    asyncio.run(sse_checks())
finally:
    chalk_chat.stream_chat = real_stream

print("verify_chalk: key containment + zero-CDN in dist")
dist = REPO / "dashboard" / "dist"
if dist.exists():
    blobs = " ".join(p.read_text(encoding="utf-8", errors="ignore")
                     for p in dist.rglob("*")
                     if p.is_file() and p.suffix in (".js", ".css", ".html"))
    check("no sk-ant / ANTHROPIC in dist",
          "sk-ant" not in blobs and "ANTHROPIC" not in blobs)
    check("no googleapis host in dist (Gemini is server-side only)",
          "googleapis.com" not in blobs)
    check("no CDN fonts in dist", "fonts.googleapis" not in blobs
          and "fonts.gstatic" not in blobs)
else:
    check("dist exists to grep (run npm run build first)", False)

print("verify_chalk: lib purity")
for name in ("sse.ts", "chalkApi.ts"):
    src = (REPO / "dashboard" / "src" / "lib" / name).read_text(encoding="utf-8")
    check(f"lib/{name} has no React import", not re.search(r"from\s+'react", src))
for name in ("chalk_chat.py", "chalk_db.py"):
    src = (REPO / "src" / "lantern" / name).read_text(encoding="utf-8")
    check(f"{name} imports no FastAPI",
          not re.search(r"^\s*(import|from)\s+fastapi", src, re.MULTILINE))

print("verify_chalk: live Haiku turn")
if config.ANTHROPIC_API_KEY:
    got, usage = [], {}
    for kind, payload in chalk_chat.stream_chat(
            "claude-haiku-4-5", "Answer in exactly five words.",
            [{"role": "user", "content": "Say hi to a teacher."}]):
        (got if kind == "delta" else [None]).append(
            payload if kind == "delta" else usage.update(payload))
    text = "".join(t for t in got if isinstance(t, str))
    print(f"        Haiku said: {text!r}  ({usage})")
    check("live Haiku turn streams text and usage",
          len(text) > 0 and usage.get("output_tokens", 0) > 0)
else:
    print("  SKIPPED — ANTHROPIC_API_KEY not set")

if "--live-gemini" in sys.argv:
    if config.GEMINI_API_KEY:
        print("verify_chalk: live Gemini turn")
        got, usage = [], {}
        for kind, payload in chalk_chat.stream_chat(
                "gemini-flash-latest", "Answer in exactly five words.",
                [{"role": "user", "content": "Say hi to a teacher."}]):
            if kind == "delta":
                got.append(payload)
            else:
                usage = payload
        text = "".join(got)
        print(f"        Gemini said: {text!r}  ({usage})")
        check("live Gemini turn streams text", len(text) > 0)
    else:
        print("  SKIPPED --live-gemini: GEMINI_API_KEY not set")

if FAILS:
    print(f"\n{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("\nall chalk checks passed")
