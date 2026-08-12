"""Sprint 2 verify — outline engine, PATCH semantics, repair path.

Run from repo root: python scripts/verify_outline.py
The repair-path and PATCH checks are offline (stubbed client, throwaway data
dir). The live Haiku check runs only when ANTHROPIC_API_KEY is set (≈ a cent);
otherwise it reports SKIPPED loudly.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles

os.environ["LANTERN_DATA_DIR"] = tempfile.mkdtemp(prefix="lantern-verify-")

from src.lantern import store  # noqa: E402
from src.lantern.outline import OutlineError, generate_outline  # noqa: E402

FAILS = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


VALID = json.dumps({
    "title": "How Enzymes Work",
    "style_guide": {
        "palette": ["#101418", "#F2E9DC", "#3AA6D9"],
        "typography": "editorial serif headlines, humanist sans support",
        "motif": "lock-and-key silhouettes",
        "art_direction": "A calm laboratory-notebook world: deep ink backgrounds, "
                         "cream paper shapes, one azure accent, soft window light.",
        "tone": "curious, precise",
    },
    "slides": [
        {"title": "How Enzymes Work", "points": [], "layout_hint": "title card",
         "visual_description": "A giant lock and key floating over a dark lab bench."},
        {"title": "The Active Site", "points": ["Shape decides function"],
         "layout_hint": "split",
         "visual_description": "Close crop of a substrate nesting into an enzyme pocket."},
    ],
})


class StubClient:
    """Anthropic-shaped stub: returns scripted responses in order."""

    def __init__(self, responses):
        self.calls = 0
        self._responses = responses
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        text = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


print("verify_outline: repair path")
stub = StubClient(['{"title": "broken", "slides": [', VALID])
outline = generate_outline("enzymes", client=stub)
check("repair path recovers on second attempt", outline.title == "How Enzymes Work")
check("exactly one repair round-trip (2 calls)", stub.calls == 2)

stub_bad = StubClient(["not json at all"])
try:
    generate_outline("enzymes", client=stub_bad)
    check("double failure raises OutlineError", False)
except OutlineError:
    check("double failure raises OutlineError", True)
check("failure stops after the single repair (2 calls)", stub_bad.calls == 2)

print("verify_outline: validator limits")
too_wordy = json.loads(VALID)
too_wordy["slides"][1]["points"] = [
    "this point rambles on for far too many words to ever paint legibly onto a slide"]
wordy_stub = StubClient([json.dumps(too_wordy), VALID])
generate_outline("enzymes", client=wordy_stub)
check(">12-word point triggers the repair round-trip", wordy_stub.calls == 2)

print("verify_outline: PATCH semantics (store level — no renders exist yet)")
deck = store.create_deck(
    title="T", topic="t", slides=[
        {"title": "A", "points": ["p"], "visual_description": "va", "layout_hint": "split",
         "render": {"status": "done", "image": "slides/01.png"}},
        {"title": "B", "points": [], "visual_description": "vb", "layout_hint": "split",
         "render": {"status": "done", "image": "slides/02.png"}},
        {"title": "C", "points": [], "visual_description": "vc", "layout_hint": "split",
         "render": None},
    ])

# untouched content, reordered: renders survive, ns renumber, images re-keyed
patched, moves = store.apply_slide_patches(
    dict(deck), [
        {"n": 2, "title": "B", "points": [], "visual_description": "vb", "layout_hint": "split"},
        {"n": 1, "title": "A", "points": ["p"], "visual_description": "va", "layout_hint": "split"},
        {"n": 3, "title": "C", "points": [], "visual_description": "vc", "layout_hint": "split"},
    ])
check("reorder renumbers contiguously from 1",
      [s["n"] for s in patched["slides"]] == [1, 2, 3])
check("untouched renders survive reorder",
      patched["slides"][0]["render"] is not None and patched["slides"][1]["render"] is not None)
check("render image paths re-keyed to new positions",
      patched["slides"][0]["render"]["image"] == "slides/01.png"
      and patched["slides"][1]["render"]["image"] == "slides/02.png")
check("moves reported for the file layer", sorted(moves) == [(1, 2), (2, 1)])

# edited content: render cleared
patched2, _ = store.apply_slide_patches(
    store.load_deck(deck["id"]), [
        {"n": 1, "title": "A edited", "points": ["p"], "visual_description": "va",
         "layout_hint": "split"},
        {"n": 2, "title": "B", "points": [], "visual_description": "vb", "layout_hint": "split"},
    ])
check("editing slide text clears its render", patched2["slides"][0]["render"] is None)
check("untouched slide keeps its render", patched2["slides"][1]["render"] is not None)
check("removing a slide shrinks the deck", len(patched2["slides"]) == 2)

# new slide
patched3, _ = store.apply_slide_patches(
    store.load_deck(deck["id"]), [
        {"n": None, "title": "New opener", "points": [], "visual_description": "v",
         "layout_hint": "title card"},
        {"n": 1, "title": "A", "points": ["p"], "visual_description": "va", "layout_hint": "split"},
    ])
check("new slide lands with no render and n=1",
      patched3["slides"][0]["render"] is None and patched3["slides"][0]["n"] == 1)
check("shifted slide keeps render, re-keyed",
      patched3["slides"][1]["render"]["image"] == "slides/02.png")

store.delete_deck(deck["id"])

print("verify_outline: live Haiku call")
if os.environ.get("ANTHROPIC_API_KEY"):
    live = generate_outline("How enzymes work", slide_count_hint=7)
    check("live outline validates", live.title.strip() != "")
    check("live outline honors slide count", len(live.slides) == 7)
    check("live art_direction is a real paragraph", len(live.art_direction_words()) > 15
          if hasattr(live, "art_direction_words")
          else len(live.style_guide.art_direction.split()) > 15)
else:
    print("  SKIPPED — ANTHROPIC_API_KEY not set; run again with the key to "
          "exercise the real model (≈ $0.01)")

if FAILS:
    print(f"\n{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("\nall outline checks passed")
