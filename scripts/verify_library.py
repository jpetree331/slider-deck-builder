"""Sprint 5 verify — duplicate is deep and independent; delete leaves no
orphans. Headless, throwaway data dir.

Run from repo root: python scripts/verify_library.py
"""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

os.environ["LANTERN_DATA_DIR"] = tempfile.mkdtemp(prefix="lantern-verify-")

from src.lantern import store  # noqa: E402

FAILS = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


deck = store.create_deck(
    title="Original", topic="t",
    slides=[{"title": "A", "points": [], "visual_description": "v",
             "layout_hint": "split",
             "render": {"status": "done", "image": "slides/01.png",
                        "rendered_at": "2026-01-01T00:00:00+00:00",
                        "cost_estimate_usd": 0.134}}])
store.slide_image_path(deck["id"], 1).write_bytes(b"\x89PNG-fake")
(store.exports_dir(deck["id"]) / "lantern-original.pptx").write_bytes(b"old export")

print("verify_library: duplicate")
copy = store.duplicate_deck(deck["id"])
check("copy has a fresh id", copy["id"] != deck["id"] and copy["id"].startswith("dk_"))
check("copy titled (copy)", copy["title"] == "Original (copy)")
check("render blocks intact in copy",
      copy["slides"][0]["render"]["status"] == "done")
check("slide PNG copied",
      store.slide_image_path(copy["id"], 1).read_bytes() == b"\x89PNG-fake")
check("copy's exports/ is empty (derived artifacts, invariant 7)",
      list(store.exports_dir(copy["id"]).iterdir()) == [])

print("verify_library: independence")
def rename(d):
    d["title"] = "Copy edited"
    d["slides"][0]["title"] = "A edited"
store.update_deck(copy["id"], rename)
store.slide_image_path(copy["id"], 1).write_bytes(b"\x89PNG-new")
original = store.load_deck(deck["id"])
check("editing the copy leaves the original untouched",
      original["title"] == "Original" and original["slides"][0]["title"] == "A")
check("copy's PNG edit leaves the original's bytes alone",
      store.slide_image_path(deck["id"], 1).read_bytes() == b"\x89PNG-fake")

print("verify_library: delete leaves no orphans")
before = {p for p in Path(os.environ["LANTERN_DATA_DIR"]).rglob("*")}
store.delete_deck(copy["id"])
after = {p for p in Path(os.environ["LANTERN_DATA_DIR"]).rglob("*")}
gone = before - after
check("delete removed the whole copy folder",
      not store.deck_dir(copy["id"]).exists())
check("everything removed was inside the copy's folder",
      all(str(p).find(copy["id"]) != -1 for p in gone) and len(gone) >= 4)
check("original survives intact", store.load_deck(deck["id"])["title"] == "Original")

store.delete_deck(deck["id"])
leftovers = [p for p in Path(os.environ["LANTERN_DATA_DIR"]).rglob("*") if p.is_file()]
check("data dir has zero orphan files after both deletes", leftovers == [])

if FAILS:
    print(f"\n{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("\nall library checks passed")
