"""Image-model registry verify — TS/Python parity, resolver behavior, the
NanoGPT transport (stubbed), and price drift against NanoGPT's live catalog.

    python scripts/verify_image_models.py           # offline + drift check
    python scripts/verify_image_models.py --live    # + one real ~$0.01 paint
    python scripts/verify_image_models.py --live-aspect
                                                    # + one paint per NanoGPT
                                                    #   painter (~$0.35 total),
                                                    #   asserting 16:9 output

The drift check hits GET nano-gpt.com/api/v1/image-models?detailed=true —
free, unauthenticated, read-only — so unlike the paid --live paints it runs
by default. Unreachable network prints SKIPPED and stays green; an actual
price/id/capability mismatch FAILS, loudly, because a stale price table
lies to the Render button.
"""
import base64
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1252 consoles

os.environ["LANTERN_DATA_DIR"] = tempfile.mkdtemp(prefix="lantern-verify-")

import httpx  # noqa: E402

from src.lantern import config, image_models, nanogpt  # noqa: E402

FAILS = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL") + f"  {name}")
    if not cond:
        FAILS.append(name)


def close(a, b):
    return a is not None and b is not None and abs(a - b) < 1e-9


# ── registry shape ──────────────────────────────────────────────────────────
print("verify_image_models: registry shape")
SIZES = ("1K", "2K", "4K")
for mid, entry in image_models.IMAGE_MODELS.items():
    ok = (entry["provider"] in ("gemini", "nanogpt")
          and all(sz in entry["sizes"] for sz in SIZES)
          and all(sz in entry["price_usd"] for sz in SIZES))
    edit = entry["edit"]
    if edit is not None:
        ok = ok and edit["id"] and edit["size"] and edit["price_usd"] > 0
    check(f"{mid} row is complete", ok)
check("default model is registered",
      image_models.DEFAULT_IMAGE_MODEL in image_models.IMAGE_MODELS)
check("every text-only painter has an edit twin (anchoring must survive)",
      all(e["edit"] for e in image_models.IMAGE_MODELS.values()
          if not e["image_to_image"]))

# ── resolver behavior ───────────────────────────────────────────────────────
print("verify_image_models: resolve_model")
r = image_models.resolve_model("gemini-3-pro-image-preview", "2K", True)
check("gemini + ref stays itself (i2i)",
      r.id == "gemini-3-pro-image-preview" and r.provider == "gemini"
      and r.size == "2K" and close(r.price_usd, 0.134))
r = image_models.resolve_model("flux-2-klein-4b", "2K", False)
check("flux klein slide 1 paints the base model",
      r.id == "flux-2-klein-4b" and r.size == "1280*720"
      and close(r.price_usd, 0.0102))
r = image_models.resolve_model("flux-2-klein-4b", "2K", True)
check("flux klein + ref routes to the edit twin at the edit price",
      r.id == "wavespeed-ai/flux-2-klein-base-4b/edit" and r.size == "auto"
      and close(r.price_usd, 0.015))
r = image_models.resolve_model("nano-banana-pro", "4K", True)
check("nano-banana-pro prices vary by size",
      r.size == "4k" and close(r.price_usd, 0.24))
try:
    image_models.resolve_model("dall-e-1917", "2K", False)
    check("unknown id raises ImageModelError", False)
except image_models.ImageModelError:
    check("unknown id raises ImageModelError", True)
try:
    image_models.resolve_model("seedream-v4.5", "8K", False)
    check("bad size raises ImageModelError", False)
except image_models.ImageModelError:
    check("bad size raises ImageModelError", True)

print("verify_image_models: estimate_deck_cost is exact, not flat")
check("3-slide flux klein deck = base + 2×edit",
      close(image_models.estimate_deck_cost(3, "2K", "flux-2-klein-4b"),
            0.0102 + 2 * 0.015))
check("3-slide gemini deck stays flat",
      close(image_models.estimate_deck_cost(3, "2K", "gemini-3-pro-image-preview"),
            3 * 0.134))
check("0 slides cost nothing",
      image_models.estimate_deck_cost(0, "2K", "seedream-v4.5") == 0.0)

# ── TS mirror parity ────────────────────────────────────────────────────────
print("verify_image_models: imageModels.ts mirrors image_models.py")
ts_text = (REPO / "dashboard" / "src" / "config" / "imageModels.ts").read_text(
    encoding="utf-8")
array_src = ts_text.split("IMAGE_MODELS: ImageModel[] = [", 1)[1].rsplit("]", 1)[0]
ts_rows = {}
for block in re.findall(r"\{\n(.*?)\n  \},", array_src, re.S):
    mid = re.search(r"^\s{4}id: '([^']+)'", block, re.M)
    provider = re.search(r"provider: '(\w+)'", block)
    i2i = re.search(r"imageToImage: (true|false)", block)
    prices = re.search(
        r"priceUsd: \{ '1K': ([\d.]+), '2K': ([\d.]+), '4K': ([\d.]+) \}", block)
    edit = re.search(r"edit: \{ id: '([^']+)', size: '([^']+)', priceUsd: ([\d.]+) \}",
                     block)
    if not (mid and provider and i2i and prices):
        continue
    ts_rows[mid.group(1)] = {
        "provider": provider.group(1),
        "i2i": i2i.group(1) == "true",
        "price_usd": {"1K": float(prices.group(1)), "2K": float(prices.group(2)),
                      "4K": float(prices.group(3))},
        "edit": ({"id": edit.group(1), "size": edit.group(2),
                  "price_usd": float(edit.group(3))} if edit else None),
    }
check("parsed every ts row (parser vs file drift)",
      len(ts_rows) == len(image_models.IMAGE_MODELS))
check("same ids in imageModels.ts and image_models.py",
      set(ts_rows) == set(image_models.IMAGE_MODELS))
for mid, ts in sorted(ts_rows.items()):
    py = image_models.IMAGE_MODELS.get(mid)
    if py is None:
        continue
    check(f"{mid}: provider/i2i match",
          ts["provider"] == py["provider"] and ts["i2i"] == py["image_to_image"])
    check(f"{mid}: prices match",
          all(close(ts["price_usd"][sz], py["price_usd"][sz]) for sz in SIZES))
    if py["edit"] or ts["edit"]:
        check(f"{mid}: edit twin matches",
              bool(py["edit"]) and bool(ts["edit"])
              and ts["edit"]["id"] == py["edit"]["id"]
              and close(ts["edit"]["price_usd"], py["edit"]["price_usd"]))
ts_default = re.search(r"DEFAULT_IMAGE_MODEL = '([^']+)'", ts_text)
check("default id matches across the seam",
      ts_default and ts_default.group(1) == image_models.DEFAULT_IMAGE_MODEL)

# ── nanogpt transport (stubbed httpx) ───────────────────────────────────────
print("verify_image_models: nanogpt transport (stubbed)")
_real_post = nanogpt.httpx.post
_real_key = config.NANOGPT_API_KEY

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


config.NANOGPT_API_KEY = ""
try:
    nanogpt.render_image("seedream-v4.5", "p", "4096x2304")
    check("missing key fails before any network call", False)
except nanogpt.RenderError as e:
    check("missing key fails before any network call", "NANOGPT_API_KEY" in str(e))
config.NANOGPT_API_KEY = "test-key"

calls = []


def _post_ok(url, json=None, headers=None, timeout=None):
    calls.append(json)
    return _Resp(200, {"created": 0, "cost": 0.04, "remainingBalance": 9.96,
                       "data": [{"b64_json": base64.b64encode(PNG_1PX).decode()}]})


nanogpt.httpx.post = _post_ok
png, cost = nanogpt.render_image("seedream-v4.5", "a prompt", "4096x2304",
                                 style_ref_png=PNG_1PX)
check("b64 image decodes and metered cost returns",
      png == PNG_1PX and close(cost, 0.04))
check("request carries model/size/b64 format and the ref as a data url",
      calls[-1]["model"] == "seedream-v4.5"
      and calls[-1]["size"] == "4096x2304"
      and calls[-1]["response_format"] == "b64_json"
      # refs ship as bounded JPEG since 2026-08-17 — full-res PNGs 413'd at
      # NanoGPT's request-size cap (see verify_render's payload-cap checks)
      and calls[-1]["imageDataUrl"].startswith("data:image/jpeg;base64,"))
check("no ref -> no imageDataUrl key",
      (nanogpt.render_image("seedream-v4.5", "p", "auto"),
       "imageDataUrl" not in calls[-1])[1])

nanogpt.httpx.post = lambda *a, **k: _Resp(401, {"error": "bad key"})
try:
    nanogpt.render_image("seedream-v4.5", "p", "auto")
    check("401 -> key-rejected message, no retry", False)
except nanogpt.RenderError as e:
    check("401 -> key-rejected message, no retry", "key rejected" in str(e))

nanogpt.httpx.post = lambda *a, **k: _Resp(402, {"error": "balance"})
try:
    nanogpt.render_image("seedream-v4.5", "p", "auto")
    check("402 -> balance message", False)
except nanogpt.RenderError as e:
    check("402 -> balance message", "balance too low" in str(e))

_attempts = {"n": 0}


def _post_flaky(url, json=None, headers=None, timeout=None):
    _attempts["n"] += 1
    if _attempts["n"] == 1:
        return _Resp(503, {"error": "warming up"})
    return _post_ok(url, json=json, headers=headers, timeout=timeout)


_sleep, nanogpt.time.sleep = nanogpt.time.sleep, lambda s: None
nanogpt.httpx.post = _post_flaky
png, _ = nanogpt.render_image("seedream-v4.5", "p", "auto")
check("5xx retries once then succeeds", _attempts["n"] == 2 and png == PNG_1PX)

_drops = {"n": 0}


def _post_dropped(url, json=None, headers=None, timeout=None):
    _drops["n"] += 1
    if _drops["n"] == 1:
        raise nanogpt.httpx.ConnectError("server disconnected (injected)")
    return _post_ok(url, json=json, headers=headers, timeout=timeout)


nanogpt.httpx.post = _post_dropped
png, _ = nanogpt.render_image("seedream-v4.5", "p", "auto")
check("dropped connection retries once then succeeds",
      _drops["n"] == 2 and png == PNG_1PX)
nanogpt.time.sleep = _sleep
nanogpt.httpx.post = _real_post
config.NANOGPT_API_KEY = _real_key

# ── key containment (invariant 1) — same discipline as verify_chalk.py ──────
print("verify_image_models: no NanoGPT key material in the built bundle")
dist = REPO / "dashboard" / "dist"
if dist.exists():
    blob = "".join(p.read_text(encoding="utf-8", errors="ignore")
                   for p in dist.rglob("*.js"))
    # display labels say "NanoGPT" (fine, metadata); the env-var name and the
    # API host must never ship to the browser
    check("no NANOGPT_API_KEY name in dist", "NANOGPT" not in blob)
    check("no nano-gpt.com host in dist", "nano-gpt.com" not in blob)
else:
    print("  SKIPPED — dashboard/dist not built")

# ── live catalog price drift (default-on, tolerant of no network) ───────────
print("verify_image_models: price drift vs NanoGPT's live catalog")
CATALOG = "https://nano-gpt.com/api/v1/image-models?detailed=true"
try:
    live = {m["id"]: m for m in httpx.get(CATALOG, timeout=30).json()["data"]}
except Exception as e:  # unreachable/misshapen — offline runs stay green
    print(f"  SKIPPED — catalog unreachable ({type(e).__name__}); "
          "drift not checked this run")
    live = None
if live is not None:
    for mid, entry in sorted(image_models.IMAGE_MODELS.items()):
        if entry["provider"] != "nanogpt":
            continue
        targets = [(mid, entry["sizes"], entry["price_usd"], entry["image_to_image"])]
        if entry["edit"]:
            e = entry["edit"]
            targets.append((e["id"], {sz: e["size"] for sz in SIZES},
                            {sz: e["price_usd"] for sz in SIZES}, True))
        for tid, sizes, prices, want_i2i in targets:
            cat = live.get(tid)
            check(f"{tid} still exists in the catalog", cat is not None)
            if cat is None:
                continue
            per_image = (cat.get("pricing") or {}).get("per_image") or {}
            check(f"{tid} prices match the catalog",
                  all(close(prices[sz], per_image.get(sizes[sz]))
                      for sz in SIZES))
            check(f"{tid} image-input capability holds",
                  bool((cat.get("capabilities") or {}).get("image_to_image"))
                  == want_i2i)

# ── live paints (opt-in, spends real money) ─────────────────────────────────
live_flags = {a for a in sys.argv[1:]}
if ("--live" in live_flags or "--live-aspect" in live_flags):
    if not config.NANOGPT_API_KEY:
        print("  SKIPPED — NANOGPT_API_KEY not set; no live paint")
    else:
        from PIL import Image  # noqa: E402
        to_paint = ([mid for mid, e in image_models.IMAGE_MODELS.items()
                     if e["provider"] == "nanogpt"]
                    if "--live-aspect" in live_flags else ["flux-2-klein-4b"])
        for mid in to_paint:
            r = image_models.resolve_model(mid, "2K", False)
            print(f"verify_image_models: LIVE paint {mid} (~${r.price_usd})")
            try:
                png, cost = nanogpt.render_image(
                    r.id, "A single lit paper lantern on a dark wall, "
                          "warm ember light, wide 16:9 composition.", r.size)
                img = Image.open(io.BytesIO(png))
                ratio = img.width / img.height
                check(f"{mid} painted a real image "
                      f"({img.width}x{img.height}, cost ${cost})", True)
                check(f"{mid} output is ~16:9 (got {ratio:.2f})",
                      abs(ratio - 16 / 9) < 0.12)
            except nanogpt.RenderError as e:
                check(f"{mid} live paint ({e})", False)

print()
if FAILS:
    print(f"{len(FAILS)} CHECK(S) FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
