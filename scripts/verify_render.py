"""Sprint 3 verify — prompt composition, invariant-3 guard, render pipeline.

Offline by default (stubbed gemini, throwaway data dir):
    python scripts/verify_render.py
With --live and GEMINI_API_KEY set, additionally renders ONE real slide
(≈ $0.14 at 2K):
    python scripts/verify_render.py --live
"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles

os.environ["LANTERN_DATA_DIR"] = tempfile.mkdtemp(prefix="lantern-verify-")

from PIL import Image  # noqa: E402

from src.lantern import gemini, render_service, store  # noqa: E402
from src.lantern.outline_schema import StyleGuide  # noqa: E402
from src.lantern.prompts import compose_slide_prompt  # noqa: E402

FAILS = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


STYLE = {
    "palette": ["#101418", "#F2E9DC", "#3AA6D9"],
    "typography": "editorial serif headlines, humanist sans support",
    "motif": "lock-and-key silhouettes",
    "art_direction": "A calm laboratory-notebook world: deep ink backgrounds, "
                     "cream paper shapes, one azure accent, soft window light.",
    "tone": "curious, precise",
}
SLIDES = [
    {"n": 1, "title": "How Enzymes Work", "points": [],
     "visual_description": "A giant brass lock and key floating over a dark lab bench.",
     "layout_hint": "title card", "render": None},
    {"n": 2, "title": "The Active Site", "points": ["Shape decides function",
                                                    "One enzyme, one job"],
     "visual_description": "Close crop of a substrate nesting into an enzyme pocket.",
     "layout_hint": "split", "render": None},
    {"n": 3, "title": "Thanks — go be a catalyst", "points": [],
     "visual_description": "The key turning; warm light spilling out of the lock.",
     "layout_hint": "closer", "render": None},
]

print("verify_render: prompt fixtures (eyeball these)")
print("=" * 72)
for s in SLIDES:
    print(compose_slide_prompt(STYLE, s, s["n"], len(SLIDES)))
    print("=" * 72)

print("verify_render: invariant 3 — every StyleGuide field consumed")
for field in StyleGuide.model_fields:
    sentinel = f"__SENTINEL_{field.upper()}__"
    style = dict(STYLE)
    style[field] = [f"#4B1D{i}F" for i in range(3)] if field == "palette" else sentinel
    prompt = compose_slide_prompt(style, SLIDES[0], 1, 3)
    present = ("#4B1D0F" in prompt) if field == "palette" else (sentinel in prompt)
    check(f"style_guide.{field} reaches the prompt", present)

print("verify_render: verbatim slide text")
p2 = compose_slide_prompt(STYLE, SLIDES[1], 2, 3)
check("title quoted verbatim", '"The Active Site"' in p2)
check("every point quoted verbatim",
      all(f'- "{pt}"' in p2 for pt in SLIDES[1]["points"]))
check("16:9 named in the frame line", "16:9" in p2)
p1 = compose_slide_prompt(STYLE, SLIDES[0], 1, 3)
check("no points block when slide has no points", "Supporting lines" not in p1)

print("verify_render: request body pins 16:9 (invariant 4)")
body = gemini._request_body("x", "2K", None)
check("aspectRatio 16:9 in body",
      body["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9")
check("imageSize plumbed", body["generationConfig"]["imageConfig"]["imageSize"] == "2K")
ref_body = gemini._request_body("x", "2K", b"pngbytes")
check("style ref becomes leading inline_data part",
      "inline_data" in ref_body["contents"][0]["parts"][0])
check("ref instruction present",
      ref_body["contents"][0]["parts"][1]["text"] == gemini.REF_INSTRUCTION)

print("verify_render: stubbed pipeline")
deck = store.create_deck(title="Fixture", topic="t", style_guide=STYLE,
                         slides=[dict(s) for s in SLIDES])
buf = io.BytesIO()
Image.new("RGB", (160, 90), "#101418").save(buf, "PNG")
FIXTURE_PNG = buf.getvalue()

real_render_image = gemini.render_image
captured = {}


def stub_ok(prompt, size, style_ref_png=None):
    captured["prompt"], captured["size"], captured["ref"] = prompt, size, style_ref_png
    return FIXTURE_PNG


render_service.gemini.render_image = stub_ok
slide = render_service.render_slide(deck["id"], 1)
check("slide 1 rendered done", slide["render"]["status"] == "done")
check("PNG landed at slides/01.png", store.slide_image_path(deck["id"], 1).exists())
check("render block records the exact prompt",
      slide["render"]["prompt"] == captured["prompt"]
      and '"How Enzymes Work"' in captured["prompt"])
check("cost estimate recorded", slide["render"]["cost_estimate_usd"] == 0.134)
check("no ref for slide 1", captured["ref"] is None)

render_service.render_slide(deck["id"], 2)
check("slide 2 got slide 1's PNG as style ref", captured["ref"] == FIXTURE_PNG)

def stub_fail(prompt, size, style_ref_png=None):
    raise gemini.RenderError("model exploded (injected)")

render_service.gemini.render_image = stub_fail
try:
    render_service.render_slide(deck["id"], 3)
    check("failed render raises RenderError", False)
except gemini.RenderError:
    check("failed render raises RenderError", True)
reloaded = store.load_deck(deck["id"])
check("failed slide marked error with message",
      reloaded["slides"][2]["render"]["status"] == "error"
      and "injected" in reloaded["slides"][2]["render"]["error"])
check("deck.json still valid after failure",
      json.loads((store.deck_dir(deck["id"]) / "deck.json").read_text(encoding="utf-8"))["id"] == deck["id"])

print("verify_render: 409 guard + boot sweep")
def mark_rendering(d):
    d["slides"][2]["render"] = {"status": "rendering"}
store.update_deck(deck["id"], mark_rendering)
try:
    render_service.render_slide(deck["id"], 3)
    check("mid-render slide 409s (AlreadyRendering)", False)
except render_service.AlreadyRendering:
    check("mid-render slide 409s (AlreadyRendering)", True)
swept = store.sweep_interrupted()
after = store.load_deck(deck["id"])
check("boot sweep flips rendering → error: interrupted",
      swept == 1 and after["slides"][2]["render"]["status"] == "error"
      and after["slides"][2]["render"]["error"] == "interrupted")

render_service.gemini.render_image = real_render_image

if "--live" in sys.argv:
    if os.environ.get("GEMINI_API_KEY"):
        print("verify_render: LIVE render of one slide (≈ $0.14)")
        live = render_service.render_slide(deck["id"], 1)
        img = Image.open(store.slide_image_path(deck["id"], 1))
        ratio = img.width / img.height
        check("live PNG opens and is 16:9-ish", abs(ratio - 16 / 9) < 0.05)
        check("live render block complete",
              live["render"]["status"] == "done" and live["render"]["ms"] > 0)
    else:
        print("  SKIPPED --live: GEMINI_API_KEY not set")
else:
    print("  (offline run — pass --live with GEMINI_API_KEY for one real "
          "render, ≈ $0.14)")

store.delete_deck(deck["id"])

if FAILS:
    print(f"\n{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("\nall render checks passed")
