"""HTTP smoke test for Sprint 2 endpoints — run while the service is up.
Creates a deck directly through the store (no API key needed), then exercises
GET/PATCH/DELETE over HTTP. Uses the real data dir; cleans up after itself.
"""
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles
from src.lantern import store  # noqa: E402

BASE = "http://localhost:8020/api"
FAILS = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


deck = store.create_deck(
    title="Smoke", topic="smoke topic", slides=[
        {"title": "A", "points": ["p1"], "visual_description": "va", "layout_hint": "split"},
        {"title": "B", "points": [], "visual_description": "vb", "layout_hint": "quote"},
    ])
try:
    r = httpx.post(f"{BASE}/decks", json={"topic": "   "})
    check("empty topic 422s", r.status_code == 422)

    r = httpx.post(f"{BASE}/decks", json={"topic": "real topic", "slide_count": 40})
    check("no-key outline fails as clean 503 (clamp path exercised)",
          r.status_code == 503)

    r = httpx.get(f"{BASE}/decks/{deck['id']}")
    check("GET returns the deck", r.status_code == 200 and r.json()["title"] == "Smoke")

    r = httpx.patch(f"{BASE}/decks/{deck['id']}", json={
        "title": "Smoke renamed",
        "style_guide": {"tone": "warm"},
        "slides": [
            {"n": 2, "title": "B", "points": [], "visual_description": "vb",
             "layout_hint": "quote"},
            {"n": 1, "title": "A", "points": ["p1"], "visual_description": "va",
             "layout_hint": "split"},
        ],
    })
    body = r.json()
    check("PATCH renames", body["title"] == "Smoke renamed")
    check("PATCH merges style_guide partially",
          body["style_guide"]["tone"] == "warm"
          and body["style_guide"]["palette"] == store.DEFAULT_PALETTE)
    check("PATCH reorders and renumbers",
          [s["title"] for s in body["slides"]] == ["B", "A"]
          and [s["n"] for s in body["slides"]] == [1, 2])

    r = httpx.patch(f"{BASE}/decks/{deck['id']}", json={
        "style_guide": {"palette": ["#123", "#456"]}})
    check("bad palette 422s", r.status_code == 422)

    r = httpx.get(f"{BASE}/decks/dk_nope")
    check("missing deck 404s", r.status_code == 404)

    r = httpx.delete(f"{BASE}/decks/{deck['id']}")
    check("DELETE works over HTTP", r.status_code == 200)
    check("deck folder gone", not store.deck_dir(deck["id"]).exists())
finally:
    if store.deck_dir(deck["id"]).exists():
        store.delete_deck(deck["id"])

if FAILS:
    print(f"\n{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("\nsmoke sprint2 passed")
