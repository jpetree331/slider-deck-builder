# BUILD_BRIEF.md — Lantern (codename: Lantern)

One-line thesis: type a topic, get a presentation where every slide is a single beautiful picture — outline by Claude Haiku, paintings by Gemini Nano Banana Pro, assembled and exported locally.

## Stack & environment

- Repo root: this directory (`Slide-Builder`; GitHub remote `jpetree331/slider-deck-builder`). The master plan named `E:\git\Lantern` — the actual root is a recorded divergence, everything else stands. Deployed as a local service via `.cmd` wrapper + Task Scheduler; reachable remotely over Tailscale.
- Backend: Python 3.12, FastAPI ≥0.115, uvicorn ≥0.32, httpx ≥0.27, anthropic SDK (current), python-dotenv ≥1.0, Pillow, python-pptx, img2pdf. No database — filesystem store (see Deck store). No Docker. Port **8020**.
- Frontend: Vite + React + TypeScript, hand-written CSS with `src/styles/tokens.css` (no Tailwind, no component libs). Dev server port **5179**, proxying `/api` → `http://localhost:8020`. Production build served by FastAPI StaticFiles mounted last.
- Models: `LANTERN_OUTLINE_MODEL=claude-haiku-4-5-20251001`, `LANTERN_IMAGE_MODEL=gemini-3-pro-image-preview`. Gemini is called over REST: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` with header `x-goog-api-key`, body `generationConfig.responseModalities=["TEXT","IMAGE"]` and `generationConfig.imageConfig={"aspectRatio":"16:9","imageSize":"2K"}`; image bytes come back base64 in `candidates[0].content.parts[].inlineData.data`. Reference images go in as `inline_data` parts. Verify the model strings against current docs during recon; report drift, don't silently swap.
- Record exact resolved versions in the Sprint 1 report; they become the lock.

## The autonomy clause (applies to every sprint)

Work autonomously to completion. Do not stop to ask for confirmation on reversible implementation choices — pick the sound default, note it in your summary, and keep going. Never: change the locked stack, add paid services beyond the two APIs, add a database, or weaken the keys-stay-server-side boundary without flagging.

## The Recon → Build → Verify → Divergence contract

Every sprint runs RECON (read before writing), BUILD, VERIFY (do this, don't skip), and DIVERGENCE (report every departure from this brief or the sprint prompt — seam auditors read these). Reports go to `docs/reports/sprint-N.md` with the shape: What shipped / What you need to do once / What's deferred / Verification / Divergences.

## Sacred invariants (do NOT break these without flagging)

1. `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and `NANOGPT_API_KEY` exist only in the server `.env`. No client-side call to Anthropic, Google, or NanoGPT, ever.
2. All deck reads/writes go through `src/lantern/store.py`. Every `deck.json` write is atomic (write `deck.json.tmp`, then `os.replace`). No other module touches the deck folder layout.
3. `src/lantern/prompts.py::compose_slide_prompt(style_guide, slide, n, total)` is the ONLY place a Gemini prompt is assembled, and it consumes **every** field of `style_guide`.
4. Every render request pins `aspectRatio: "16:9"`. Never omitted.
5. `dashboard/src/lib/` (TS) and `src/lantern/{store,prompts,outline_schema,image_models}.py` stay framework-free/pure — no React imports, no FastAPI imports — so verify scripts can exercise them headless. Say so in file headers.
6. The user's own words survive: `topic` and `source_notes` are stored verbatim and quoted into the outline call; slide `title`/`points` text is rendered verbatim into images (Haiku writes it, Jess can edit it, Gemini paints exactly it).
7. Exports are derived artifacts, rebuilt on demand from the PNGs — never a second source of truth.

## Locked decisions (do not relitigate)

The twelve decisions from the Master Plan header (`lantern_master_plan.md`) apply verbatim; keep this brief and that list together in the repo.

## Decision gates

- ⚠️ **GATE A — resolve before Sprint 5:** does the biology team ever get accounts? Lantern is single-user by design (no auth beyond the optional Basic password). If real multi-user demand appears, that's a store redesign — decide before building the library UI, not after.

## Deck store (source of truth — sketch, adapt idiomatically)

```
data/decks/<deck_id>/
  deck.json            # everything below
  slides/01.jpg ...    # zero-padded, position == filename; extension = the
                       #   painter's honest format, jpg or png (2026-08-17 —
                       #   PNG-wrapping painter JPEGs quintupled deck weight)
  exports/             # lantern-<slug>.pptx / .pdf / .zip, rebuilt on demand
```

```jsonc
// deck.json
{
  "id": "dk_9f3a2c81",              // makeId('dk') — non-secure-context-safe helper
  "title": "Cell Transport",
  "topic": "verbatim user ask",
  "source_notes": "optional pasted content, verbatim",
  "style_guide": {
    "palette": ["#0E1420", "#F2E9DC", "#D96C3A"],   // 3–5 hex
    "typography": "high-contrast editorial serif headlines, clean humanist sans support",
    "motif": "cut-paper diagrams, long soft shadows",
    "art_direction": "one cohesive prose paragraph — THE consistency field, quoted verbatim into every slide prompt",
    "tone": "confident, museum-placard"
  },
  "slide_size": "2K",               // "1K" | "2K" | "4K"
  "image_model": "gemini-3-pro-image-preview",  // a painter id from dashboard/src/config/imageModels.ts (2026-08-16)
  "aspect_ratio": "16:9",
  "status": "outline",              // outline | rendering | done | error
  "slides": [{
    "n": 1,
    "title": "headline, rendered verbatim",
    "points": ["≤4 short lines, rendered verbatim"],
    "visual_description": "what the picture IS — subject, composition, focal point",
    "layout_hint": "title card | split | full-bleed diagram | big number | quote | closer",
    "render": null                  // or:
    // { "status": "pending|rendering|done|error", "image": "slides/01.png",
    //   "prompt": "exact final prompt sent", "model": "...", "ms": 21400,
    //   "error": null, "rendered_at": "iso", "cost_estimate_usd": 0.14 }
  }],
  "created_at": "iso", "updated_at": "iso"
}
```

Defensive-load sanitizers are an invariant: `store.load_deck()` coerces bad/missing fields to safe defaults (clamp slide_size to the enum, drop malformed slides with a logged warning, never crash the app on a corrupt file).

## Guardrails carried throughout

- `.env.example` heavily commented: where each value comes from and its security stance ("Anthropic Console → API Keys — outline model only, never sent to the browser"; "Google AI Studio → Get API key — gemini-3-pro-image-preview requires a paid-tier key"; "LANTERN_PASSWORD optional — when set, Basic auth guards everything; set it before exposing over Tailscale").
- Cost visibility: every render logs one line with per-image estimate and running deck total; the outline screen shows an estimated deck cost before the Render button.
- `LANTERN_MAX_SLIDES=16` clamp enforced server-side in the outline endpoint.
- On boot, any slide stuck in `rendering` flips to `error: "interrupted"` — restarts never leave zombie state.
- 503 for upstream/provider failures, 409 for conflicts (e.g. render requested while deck already rendering), Pydantic request models, plain-dict JSON responses.
- Logging idiom: `logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")`, dotted child loggers (`lantern.api`, `lantern.render`), RotatingFileHandler to `data/api.log` (2 MB × 3).
