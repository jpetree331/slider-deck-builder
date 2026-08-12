"""Sprint 1 verify — store round-trip + corrupt-file sanitizers, headless.

Run from repo root: python scripts/verify_store.py
Uses a throwaway data dir; touches nothing in data/.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles

_tmp = tempfile.mkdtemp(prefix="lantern-verify-")
os.environ["LANTERN_DATA_DIR"] = _tmp  # must precede the config import

from src.lantern import store  # noqa: E402

FAILS = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


print("verify_store: round-trip")
deck = store.create_deck(
    title="Test Deck", topic="verbatim topic text!", source_notes="notes, verbatim",
    style_guide={"palette": ["#0E1420", "#F2E9DC", "#D96C3A"],
                 "typography": "serif", "motif": "cut paper",
                 "art_direction": "warm editorial", "tone": "confident"},
    slides=[{"title": "One", "points": ["a", "b"], "visual_description": "a thing",
             "layout_hint": "title card", "render": None}],
)
check("create returns id with dk_ prefix", deck["id"].startswith("dk_"))
check("topic stored verbatim", deck["topic"] == "verbatim topic text!")

loaded = store.load_deck(deck["id"])
check("load round-trips title", loaded["title"] == "Test Deck")
check("slide renumbered to 1", loaded["slides"][0]["n"] == 1)

loaded["title"] = "Renamed"
store.save_deck(loaded)
check("atomic save persists", store.load_deck(deck["id"])["title"] == "Renamed")
check("no tmp file left behind",
      not (store.deck_dir(deck["id"]) / "deck.json.tmp").exists())

summaries = store.list_decks()
check("list contains the deck", any(d["id"] == deck["id"] for d in summaries))
check("summary shape", {"id", "title", "status", "slide_count", "updated_at",
                        "cover"} <= set(summaries[0].keys()))

print("verify_store: sanitizers")
bad = store.sanitize_deck({
    "id": deck["id"], "title": 42, "slide_size": "9K", "status": "exploded",
    "style_guide": {"palette": ["red", "#GGGGGG", "#111111"]},
    "slides": ["not a slide", {"no": "fields"}, {"title": "Kept", "visual_description": "v"}],
})
check("bad title coerced", bad["title"] == "Untitled deck")
check("bad slide_size clamped to 2K", bad["slide_size"] == "2K")
check("bad status coerced to outline", bad["status"] == "outline")
check("invalid palette falls back to default", bad["style_guide"]["palette"] == store.DEFAULT_PALETTE)
check("malformed slides dropped, good one kept",
      len(bad["slides"]) == 1 and bad["slides"][0]["title"] == "Kept")

print("verify_store: corrupt file")
corrupt_dir = store.deck_dir("dk_corrupt00")
corrupt_dir.mkdir(parents=True)
(corrupt_dir / "deck.json").write_text('{"id": "dk_corrupt00", "title": "trunca',
                                       encoding="utf-8")
try:
    store.load_deck("dk_corrupt00")
    check("corrupt deck raises clean StoreError", False)
except store.StoreError:
    check("corrupt deck raises clean StoreError", True)
except Exception as e:  # noqa: BLE001
    print(f"        (raised {type(e).__name__} instead)")
    check("corrupt deck raises clean StoreError", False)
check("list skips corrupt deck without crashing",
      all(d["id"] != "dk_corrupt00" for d in store.list_decks()))

print("verify_store: delete")
store.delete_deck(deck["id"])
check("delete removes folder", not store.deck_dir(deck["id"]).exists())
try:
    store.load_deck(deck["id"])
    check("load after delete raises DeckNotFound", False)
except store.DeckNotFound:
    check("load after delete raises DeckNotFound", True)

print("verify_store: purity")
import re  # noqa: E402
src = (REPO / "src" / "lantern" / "store.py").read_text(encoding="utf-8")
check("store.py imports no FastAPI",
      not re.search(r"^\s*(import|from)\s+fastapi", src, re.MULTILINE))

if FAILS:
    print(f"\n{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("\nall store checks passed")
