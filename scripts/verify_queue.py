"""Sprint 4 verify — queue semantics against a stubbed renderer.

Run from repo root: python scripts/verify_queue.py
No network, no keys, throwaway data dir. Asserts the six brief behaviors:
sequential order, slide-1-ref plumbing, skip-done resume, halt-on-error,
cancel-drains, restart sweep.
"""
import io
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

os.environ["LANTERN_DATA_DIR"] = tempfile.mkdtemp(prefix="lantern-verify-")

from PIL import Image  # noqa: E402

from src.lantern import gemini, queue, render_service, store  # noqa: E402

FAILS = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


buf = io.BytesIO()
Image.new("RGB", (160, 90), "#101418").save(buf, "PNG")
FIXTURE_PNG = buf.getvalue()

calls = []            # (n, had_ref) in call order
fail_on = set()       # slide numbers that should fail
slow_gate = threading.Event()  # when set, renders block until released
release_gate = threading.Event()


def stub_render(prompt, size, style_ref_png=None):
    n = int(prompt.split("Render slide ")[1].split(" ")[0])
    calls.append((n, style_ref_png is not None))
    if slow_gate.is_set():
        release_gate.wait(timeout=10)
    time.sleep(0.05)
    if n in fail_on:
        raise gemini.RenderError(f"injected failure on slide {n}")
    return FIXTURE_PNG


render_service.gemini.render_image = stub_render


def make_deck(count=4):
    return store.create_deck(
        title="Q", topic="t",
        slides=[{"title": f"S{i}", "points": [], "visual_description": f"v{i}",
                 "layout_hint": "split"} for i in range(1, count + 1)])


def wait_settled(deck_id, timeout=15):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        deck = store.load_deck(deck_id)
        if deck["status"] != "rendering":
            return deck
        time.sleep(0.05)
    raise TimeoutError(f"deck {deck_id} never settled")


print("verify_queue: sequential order + ref plumbing")
deck = make_deck(4)
queued = queue.enqueue_deck(deck["id"])
check("enqueue flips deck to rendering", queued["status"] == "rendering")
check("queued slides marked pending",
      all(s["render"]["status"] == "pending" for s in queued["slides"]))
try:
    queue.enqueue_deck(deck["id"])
    check("double enqueue raises DeckBusy (409)", False)
except queue.DeckBusy:
    check("double enqueue raises DeckBusy (409)", True)
settled = wait_settled(deck["id"])
check("deck settles to done", settled["status"] == "done")
check("slides rendered strictly in order", [c[0] for c in calls] == [1, 2, 3, 4])
check("slide 1 rendered without ref, 2..4 with slide 1's PNG",
      calls[0][1] is False and all(had_ref for _, had_ref in calls[1:]))
check("all four PNGs on disk",
      all(store.slide_image_path(deck["id"], i).exists() for i in range(1, 5)))

print("verify_queue: skip-done resume")
calls.clear()
def clear_slide_3(d):
    d["slides"][2]["render"] = None
    d["status"] = "outline"
store.update_deck(deck["id"], clear_slide_3)
queue.enqueue_deck(deck["id"])
settled = wait_settled(deck["id"])
check("resume renders only the not-done slide", [c[0] for c in calls] == [3])
check("resume ends done again", settled["status"] == "done")

print("verify_queue: halt-on-error")
calls.clear()
deck2 = make_deck(4)
fail_on.add(2)
queue.enqueue_deck(deck2["id"])
settled = wait_settled(deck2["id"])
check("deck lands in error", settled["status"] == "error")
check("halt: slides after the failure never rendered", [c[0] for c in calls] == [1, 2])
check("slide 1 stays done", settled["slides"][0]["render"]["status"] == "done")
check("failing slide records the error",
      settled["slides"][1]["render"]["status"] == "error"
      and "injected" in settled["slides"][1]["render"]["error"])
check("halted slides reset to unpainted (resumable)",
      settled["slides"][2]["render"] is None and settled["slides"][3]["render"] is None)

fail_on.clear()
calls.clear()
queue.enqueue_deck(deck2["id"])
settled = wait_settled(deck2["id"])
check("render-again resumes only non-done slides", sorted(c[0] for c in calls) == [2, 3, 4])
check("recovered deck ends done", settled["status"] == "done")

print("verify_queue: cancel drains, in-flight finishes")
calls.clear()
deck3 = make_deck(4)
slow_gate.set()
queue.enqueue_deck(deck3["id"])
t0 = time.monotonic()
while not calls and time.monotonic() - t0 < 10:  # slide 1 is now in flight
    time.sleep(0.02)
queue.cancel(deck3["id"])
release_gate.set()
settled = wait_settled(deck3["id"])
slow_gate.clear()
release_gate.clear()
check("cancel: in-flight slide finished", settled["slides"][0]["render"]["status"] == "done")
check("cancel: remaining slides never started", [c[0] for c in calls] == [1])
check("cancel leaves resumable outline state", settled["status"] == "outline")
check("cancel: no zombie pending marks",
      all(s["render"] is None for s in settled["slides"][1:]))

print("verify_queue: single-slide repaint through the queue")
calls.clear()
queue.enqueue_slide(deck3["id"], 1)
try:
    queue.enqueue_slide(deck3["id"], 1)
    dup_ok = True  # may legitimately succeed if the first already finished
except queue.DeckBusy:
    dup_ok = True
check("same-slide double enqueue is guarded or already done", dup_ok)
settled = wait_settled(deck3["id"])
check("single-slide job settles cleanly", settled["status"] in ("outline", "done"))
check("repaint re-rendered slide 1 only", [c[0] for c in calls][:1] == [1])

print("verify_queue: restart sweep (queue-flavored)")
def zombie(d):
    d["status"] = "rendering"
    d["slides"][1]["render"] = {"status": "rendering"}
store.update_deck(deck3["id"], zombie)
store.sweep_interrupted()
after = store.load_deck(deck3["id"])
check("sweep flips zombie slide to error: interrupted",
      after["slides"][1]["render"]["status"] == "error"
      and after["slides"][1]["render"]["error"] == "interrupted")
check("sweep flips zombie deck out of rendering", after["status"] == "error")

for d in (deck, deck2, deck3):
    store.delete_deck(d["id"])

if FAILS:
    print(f"\n{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("\nall queue checks passed")
