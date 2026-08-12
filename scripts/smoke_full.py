"""End-to-end HTTP smoke over the full API surface — run while the service
is up. Seeds a rendered deck via the store (no API keys needed), exercises
every endpoint family over the wire, cleans up after itself.

    python scripts/smoke_full.py [--auth PASSWORD]
--auth: assert everything 401s bare and passes with Basic credentials.
"""
import io
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles
from PIL import Image  # noqa: E402

from src.lantern import store  # noqa: E402

BASE = "http://localhost:8020"
FAILS = []

AUTH = None
if "--auth" in sys.argv:
    AUTH = ("lantern", sys.argv[sys.argv.index("--auth") + 1])


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


client = httpx.Client(base_url=BASE, auth=AUTH, timeout=30)

deck = store.create_deck(
    title="Smoke Full", topic="t",
    slides=[{"title": f"S{i}", "points": [], "visual_description": "v",
             "layout_hint": "split",
             "render": {"status": "done", "image": f"slides/{i:02d}.png",
                        "rendered_at": f"2026-01-0{i}T00:00:00+00:00",
                        "cost_estimate_usd": 0.134}} for i in (1, 2)])
for i in (1, 2):
    Image.new("RGB", (320, 180), "#D96C3A").save(store.slide_image_path(deck["id"], i))
copy_id = None

try:
    if AUTH:
        print("smoke_full: auth wall")
        for probe in ("/api/health", f"/api/decks/{deck['id']}/slides/1.png", "/"):
            bare = httpx.get(BASE + probe)
            check(f"bare {probe} 401s", bare.status_code == 401)
        check("WWW-Authenticate offered",
              "www-authenticate" in httpx.get(BASE + "/api/health").headers)
        pre = httpx.options(BASE + "/api/decks", headers={
            "Origin": "http://localhost:5179",
            "Access-Control-Request-Method": "PATCH"})
        check("CORS preflight clears the auth wall with headers",
              pre.status_code == 200 and pre.headers.get(
                  "access-control-allow-origin") == "http://localhost:5179")

    print("smoke_full: core surface")
    check("health ok", client.get("/api/health").json()["service"] == "lantern")
    check("static root serves the app",
          "<title>Lantern</title>" in client.get("/").text)
    check("deep link serves the app shell (SPA fallback)",
          "<title>Lantern</title>" in client.get("/new").text)
    check("unknown /api path 404s, not swallowed by the SPA fallback",
          client.get("/api/totally-not-real").status_code == 404)

    print("smoke_full: PATCH mirrors painted-text validators")
    r = client.patch(f"/api/decks/{deck['id']}", json={
        "slides": [{"n": 1, "title": "  ", "points": [],
                    "visual_description": "v", "layout_hint": "split"}]})
    check("empty slide title 422s", r.status_code == 422)
    r = client.patch(f"/api/decks/{deck['id']}",
                     json={"style_guide": {"art_direction": "  "}})
    check("emptied art_direction 422s", r.status_code == 422)
    r = client.patch(f"/api/decks/{deck['id']}", json={
        "slides": [{"n": 1, "title": "T", "points": [
            "this single point rambles far past the twelve word ceiling that "
            "painted slides can tolerate"],
            "visual_description": "v", "layout_hint": "split"}]})
    check("over-long point 422s", r.status_code == 422)
    decks = client.get("/api/decks").json()["decks"]
    mine = next(d for d in decks if d["id"] == deck["id"])
    check("list carries cover for rendered deck", mine["cover"] == "slides/01.png")

    print("smoke_full: slide images")
    r = client.get(f"/api/decks/{deck['id']}/slides/1.png")
    check("PNG streams with content-type", r.status_code == 200
          and r.headers["content-type"] == "image/png")
    etag = r.headers.get("etag", "")
    check("ETag keyed on rendered_at", "2026-01-01" in etag)
    r304 = client.get(f"/api/decks/{deck['id']}/slides/1.png",
                      headers={"If-None-Match": etag})
    check("If-None-Match returns 304", r304.status_code == 304)
    check("missing slide image 404s",
          client.get(f"/api/decks/{deck['id']}/slides/9.png").status_code == 404)

    print("smoke_full: render queue over the wire")
    check("cancel on idle deck is clean",
          client.post(f"/api/decks/{deck['id']}/cancel").status_code == 200)
    check("render slide 99 404s",
          client.post(f"/api/decks/{deck['id']}/slides/99/render").status_code == 404)

    print("smoke_full: exports")
    for fmt in ("pptx", "pdf", "zip"):
        body = client.post(f"/api/decks/{deck['id']}/export?fmt={fmt}").json()
        url = body["download_url"]
        dl = client.get(url)
        check(f"{fmt}: exported and downloads with attachment disposition",
              dl.status_code == 200
              and "attachment" in dl.headers.get("content-disposition", "")
              and len(dl.content) > 500)
    check("bad fmt 422s",
          client.post(f"/api/decks/{deck['id']}/export?fmt=docx").status_code == 422)
    check("traversal filename 404s",
          client.get(f"/api/decks/{deck['id']}/exports/..%2Fdeck.json").status_code
          in (400, 404))

    print("smoke_full: duplicate + delete")
    copy = client.post(f"/api/decks/{deck['id']}/duplicate").json()
    copy_id = copy["id"]
    check("duplicate over the wire", copy["title"] == "Smoke Full (copy)")
    check("copy's PNG serves",
          client.get(f"/api/decks/{copy_id}/slides/1.png").status_code == 200)
    check("delete copy", client.delete(f"/api/decks/{copy_id}").status_code == 200)
    copy_id = None
finally:
    for did in (deck["id"], copy_id):
        if did and store.deck_dir(did).exists():
            store.delete_deck(did)

if FAILS:
    print(f"\n{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("\nfull smoke passed")
