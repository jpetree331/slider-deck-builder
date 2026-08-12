# Lantern — Master Build Plan
*A slide deck maker in the spirit of Kimi's retired visual mode: every slide is one gorgeous generated picture. Haiku organizes; Nano Banana Pro paints.*

Codename **Lantern** — after the magic lantern, the original one-picture-per-slide projector. Rename freely; find-and-replace is cheap now.

---

## Locked decisions (do not relitigate)

1. **Shape: local FastAPI service + Vite/React/TS frontend it serves.** Keys live in the server's `.env` and never reach the browser; no new Supabase project (free tier is spent); deck folders zip straight into the existing E:\git backup ritual; Tailscale makes it reachable from school. Product-app polish on the agent-service chassis — a deliberate hybrid, stated here so nobody "corrects" it either direction.
2. **Store: filesystem, not Postgres.** A deck IS a folder of pictures plus one `deck.json`. This is a flagged, deliberate deviation from the FastAPI family's School-B Postgres pattern — portability and zip-backup win for a document-shaped app.
3. **Models pinned:** outline = `claude-haiku-4-5-20251001` (Anthropic Python SDK); render = `gemini-3-pro-image-preview` (Nano Banana Pro, REST via httpx — no Google SDK dependency). Fable verifies both strings against current docs in Sprint 2/3 recon and reports if either has moved.
4. **Port 8020** for the service (unclaimed: 8000/8001/8002/8005/8007/8010 are taken). **Vite dev 5179** (5173/5174/5178 taken). Both recorded in RUNBOOK.md.
5. **Aspect 16:9, default size 2K** (1K/2K/4K knob per deck). ~$0.13–0.15 per 2K image at plan time → a 10-slide deck ≈ $1.30–1.50 plus pennies of Haiku; 4K roughly doubles it. `LANTERN_MAX_SLIDES=16` clamp as the cost guard.
6. **Progress via polling, not SSE.** Frontend polls `GET /api/decks/{id}` every 2s while rendering. Dumb and debuggable.
7. **Slide 1 is the style anchor.** Slides 2..N attach slide 1's PNG as a reference image so the deck stays visually coherent. Regenerating slide 1 later does not retro-invalidate the others (the ref is consumed at render time); the UI says so.
8. **Prompt composition has ONE home:** `src/lantern/prompts.py::compose_slide_prompt()`. The frontend never assembles a Gemini prompt.
9. **Export server-side:** python-pptx (full-bleed 16:9), img2pdf, zipfile. No client export libs.
10. **Styling: hand-written CSS with `tokens.css`.** No Tailwind, no component library — this is a gift app, and the gift is to Jess.
11. **Optional Basic auth** via `LANTERN_PASSWORD` (the established DashboardAuthMiddleware pattern) since the service will be exposed over Tailscale.
12. **Versions named now, recorded exactly at scaffold:** Python 3.12; FastAPI ≥0.115, uvicorn ≥0.32, httpx ≥0.27, anthropic (current), python-dotenv ≥1.0, Pillow, python-pptx, img2pdf; Node 22 LTS, Vite 8, React 19, TypeScript 5.x. Sprint 1's report records the exact resolved versions as the lock.

## How to run this plan

1. Create `E:\git\Lantern`. Save the **Standing Brief** below as `BUILD_BRIEF.md` in the repo root before Sprint 1.
2. Run **build sprints in your build thread**, one paste per sprint, in order.
3. After Sprints 2, 4, and 6, open a **fresh Claude Code thread on a different model** and paste the matching **Verify Sprint** — the verify prompts are written for an agent with zero build context, on purpose. Same for the Final Verification round.
4. Commits map 1:1: `Sprint 3: slide renderer`, `Verify B: fixes`. Reports land in `docs/reports/`.
5. **Verify B, Verify C, and Final Verification spend real API money** (roughly $0.45, $0.30, and $1.20 respectively at 2K). It's the only honest way to check an image pipeline; the prompts say exactly what they'll spend before they spend it.

---

# STANDING BRIEF (save as `BUILD_BRIEF.md`)

# BUILD_BRIEF.md — Lantern (codename: Lantern)

One-line thesis: type a topic, get a presentation where every slide is a single beautiful picture — outline by Claude Haiku, paintings by Gemini Nano Banana Pro, assembled and exported locally.

## Stack & environment

- Target machine: Windows 11 Pro ("dreammachine"), repo at `E:\git\Lantern`. Deployed as a local service via `.cmd` wrapper + Task Scheduler; reachable remotely over Tailscale.
- Backend: Python 3.12, FastAPI ≥0.115, uvicorn ≥0.32, httpx ≥0.27, anthropic SDK (current), python-dotenv ≥1.0, Pillow, python-pptx, img2pdf. No database — filesystem store (see Deck store). No Docker. Port **8020**.
- Frontend: Vite 8 + React 19 + TypeScript, hand-written CSS with `src/styles/tokens.css` (no Tailwind, no component libs). Dev server port **5179**, proxying `/api` → `http://localhost:8020`. Production build served by FastAPI StaticFiles mounted last.
- Models: `LANTERN_OUTLINE_MODEL=claude-haiku-4-5-20251001`, `LANTERN_IMAGE_MODEL=gemini-3-pro-image-preview`. Gemini is called over REST: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` with header `x-goog-api-key`, body `generationConfig.responseModalities=["TEXT","IMAGE"]` and `generationConfig.imageConfig={"aspectRatio":"16:9","imageSize":"2K"}`; image bytes come back base64 in `candidates[0].content.parts[].inlineData.data`. Reference images go in as `inline_data` parts. Verify the model strings against current docs during recon; report drift, don't silently swap.
- Record exact resolved versions in the Sprint 1 report; they become the lock.

## The autonomy clause (applies to every sprint)

Work autonomously to completion. Do not stop to ask for confirmation on reversible implementation choices — pick the sound default, note it in your summary, and keep going. Never: change the locked stack, add paid services beyond the two APIs, add a database, or weaken the keys-stay-server-side boundary without flagging.

## The Recon → Build → Verify → Divergence contract

Every sprint runs RECON (read before writing), BUILD, VERIFY (do this, don't skip), and DIVERGENCE (report every departure from this brief or the sprint prompt — seam auditors read these). Reports go to `docs/reports/sprint-N.md` with the shape: What shipped / What you need to do once / What's deferred / Verification / Divergences.

## Sacred invariants (do NOT break these without flagging)

1. `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` exist only in the server `.env`. No client-side call to Anthropic or Google, ever.
2. All deck reads/writes go through `src/lantern/store.py`. Every `deck.json` write is atomic (write `deck.json.tmp`, then `os.replace`). No other module touches the deck folder layout.
3. `src/lantern/prompts.py::compose_slide_prompt(style_guide, slide, n, total)` is the ONLY place a Gemini prompt is assembled, and it consumes **every** field of `style_guide`.
4. Every render request pins `aspectRatio: "16:9"`. Never omitted.
5. `dashboard/src/lib/` (TS) and `src/lantern/{store,prompts,outline_schema}.py` stay framework-free/pure — no React imports, no FastAPI imports — so verify scripts can exercise them headless. Say so in file headers.
6. The user's own words survive: `topic` and `source_notes` are stored verbatim and quoted into the outline call; slide `title`/`points` text is rendered verbatim into images (Haiku writes it, Jess can edit it, Gemini paints exactly it).
7. Exports are derived artifacts, rebuilt on demand from the PNGs — never a second source of truth.

## Locked decisions (do not relitigate)

The twelve decisions from the Master Plan header apply verbatim; keep this brief and that list together in the repo.

## Decision gates

- ⚠️ **GATE A — resolve before Sprint 5:** does the biology team ever get accounts? Lantern is single-user by design (no auth beyond the optional Basic password). If real multi-user demand appears, that's a store redesign — decide before building the library UI, not after.

## Deck store (source of truth — sketch, adapt idiomatically)

```
data/decks/<deck_id>/
  deck.json          # everything below
  slides/01.png ...  # zero-padded, position == filename
  exports/           # lantern-<slug>.pptx / .pdf / .zip, rebuilt on demand
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

---

# PHASE 1 — CHASSIS & OUTLINE

## Sprint 1 — Chassis

### RECON
Read `BUILD_BRIEF.md` in full. Confirm nothing occupies port 8020 and that `E:\git\Lantern` is the repo root. List current stable versions of the pinned packages (pip/npm view) before installing.

### BUILD
1. Repo skeleton: `src/lantern/` (backend), `dashboard/` (Vite app), `scripts/`, `docs/reports/`, `data/` (gitignored except `.gitkeep`), `RUNBOOK.md` + `DECISIONS.md` stubs, `README.md` placeholder, `.gitignore` (data/, .env, node_modules, dist, __pycache__).
2. `requirements.txt` from the brief's pinned block. `.env.example` per the Guardrails section, `LANTERN_`-prefixed knobs: `LANTERN_PORT=8020`, `LANTERN_DATA_DIR=data`, `LANTERN_PASSWORD=`, `LANTERN_OUTLINE_MODEL=...`, `LANTERN_IMAGE_MODEL=...`, `LANTERN_MAX_SLIDES=16`, plus the two keys.
3. `src/lantern/config.py`: path-anchored dotenv load with override (`load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)`), typed reads with inline defaults for every knob.
4. `src/lantern/store.py` (pure, framework-free): `makeId(prefix)`, `deck_dir(id)`, `create_deck(...)`, `load_deck(id)` with sanitizers, `save_deck(deck)` atomic, `list_decks()` (id/title/status/updated_at/cover path), `delete_deck(id)`. File-header note: "framework-free on purpose — exercised headless by scripts/".
5. `src/lantern/api.py` assembled in the canonical order: dotenv → logging idiom → CORS locked to `http://localhost:5179` → `api_router = APIRouter()` included with `prefix="/api"` → health probe `{"status":"ok","service":"lantern"}` → `DashboardAuthMiddleware` (Basic auth when `LANTERN_PASSWORD` set) → StaticFiles on `dashboard/dist` mounted LAST → `uvicorn.run(host="127.0.0.1", port=...)`. Endpoints this sprint: health, `GET /api/decks` (list), `DELETE /api/decks/{id}`.
6. Dashboard scaffold: Vite 8 + React 19 + TS, `server.port: 5179`, `/api` proxy to 8020. `src/styles/tokens.css` — warm bookish direction: Playfair Display for display type, Libre Franklin for UI, IBM Plex Mono for metadata; a dark gallery-wall canvas so the slide images are the brightest thing on screen; spacing/radius/color custom properties only (no raw hex in components). Pages as stubs: `LibraryPage`, `NewDeckPage`, `OutlinePage`, `DeckPage`, with router and an empty-state Library that renders from `GET /api/decks`. `src/lib/types.ts` mirroring `deck.json` field-for-field, and `src/lib/api.ts` fetch wrappers (the only fetch site).
7. `scripts/verify-sprint1.mjs` + `scripts/verify_store.py`: store round-trip (create → load → mutate → atomic save → list → delete), corrupt-file sanitizer check (truncated JSON loads to a safe deck or a clean error, never a crash).
8. Windows ops: `start-lantern.cmd` (`PYTHONUTF8=1`, `cd /d E:\git\Lantern`, append-to-log), RUNBOOK.md ports table (8020 service / 5179 dev) + start/stop/restart, Task Scheduler registration steps written but not executed.

### VERIFY (do this, don't skip)
- `python scripts/verify_store.py` and `node scripts/verify-sprint1.mjs` pass.
- Service boots via the `.cmd`; `curl http://localhost:8020/api/health` returns ok; with `LANTERN_PASSWORD=test` set, the same call 401s without credentials and passes with them.
- `npm run dev` on 5179 shows the Library empty state pulling through the proxy; `npm run build` then hitting `http://localhost:8020/` serves the built app with `/api/health` still winning over static.
- Kill the process mid-`save_deck` (simulate: write a huge deck in a loop and Ctrl-C) — `deck.json` on disk is always valid JSON.

### DIVERGENCE
Report any departure from the brief, including versions that resolved differently than named. Record exact versions in `docs/reports/sprint-1.md` — they are now the lock.

---

## Sprint 2 — Outline engine

### RECON
Read `BUILD_BRIEF.md`, `docs/reports/sprint-1.md`, `store.py`, `types.ts`. Check Anthropic docs for the current Haiku model string; if `claude-haiku-4-5-20251001` has been superseded, flag it in Divergences but build against the brief's pin unless it's actually dead.

### BUILD
1. `src/lantern/outline_schema.py` (pure): Pydantic models for the outline payload — `StyleGuide`, `SlideSpec`, `DeckOutline` — with validators: 3–5 hex colors, non-empty `art_direction`, 1–`LANTERN_MAX_SLIDES` slides, every slide has `title` + `visual_description`, `points` ≤ 4 entries of ≤ 12 words each (they get painted; long text breaks slides).
2. `src/lantern/outline.py`: `generate_outline(topic, source_notes, slide_count_hint, style_hints) -> DeckOutline`. Anthropic SDK, pinned model, system prompt that demands: strict JSON only matching the schema; a **cohesive one-paragraph `art_direction`** (this is the deck's whole visual identity — palette, texture, lighting, typographic attitude — written so an image model can obey it verbatim on every slide); slide text written to be *painted*, i.e. short, declarative, spelling-critical; a deliberate arc (title card → content → closer). Default slide count 6–12 when no hint. On invalid JSON: one repair round-trip sending the validator errors back, then fail cleanly with the raw text logged.
3. Endpoints: `POST /api/decks` `{topic, source_notes?, slide_count?, style_hints?, slide_size?}` → clamp count → call outline → `store.create_deck` → return full deck. `GET /api/decks/{id}`. `PATCH /api/decks/{id}` accepting edits to `title`, `style_guide.*`, and per-slide `title/points/visual_description/layout_hint` + slide reorder/add/remove (positions renumber; slides with an existing render keep their render block only if content untouched — otherwise render is cleared to null, because the picture no longer matches the words).
4. Frontend: `NewDeckPage` form (topic textarea, optional notes, slide count, style hints, size select) → creates → routes to `OutlinePage`. `OutlinePage`: style guide card (editable palette chips, typography, motif, art_direction textarea), slide list with inline editing/reorder/add/remove, autosave via PATCH (debounced, gated on an `isLoaded` flag), estimated cost readout (`slides × per-image estimate` from a pure helper in `src/lib/cost.ts`), and a disabled "Render deck" button labeled "Sprint 4".
5. `scripts/verify_outline.py`: runs one REAL Haiku outline ("How enzymes work, 7 slides") and validates; also feeds a deliberately broken JSON through the repair path via a stubbed client.

### VERIFY (do this, don't skip)
- Real outline call returns valid `DeckOutline` first try or after one repair; deck lands on disk; Library shows it; OutlinePage round-trips edits (reload the page — edits persisted).
- Reordering renumbers `n` contiguously from 1; editing a slide's text clears its render block (assert in a store-level test since no renders exist yet).
- Slide-count 40 request clamps to 16; empty topic 422s.

### DIVERGENCE
Report, especially: any outline-schema field added/renamed (Verify A diffs it against `types.ts` and this brief), and the exact system prompt saved to `docs/outline-prompt.md` for audit.

---

## VERIFY SPRINT A — audit Sprints 1–2 and their seams

*Run this in a fresh Claude Code thread on a different model than the build.*

You are a verification agent. You did not build this code and owe it no loyalty. Repo: `E:\git\Lantern`.

### RECON
Read `BUILD_BRIEF.md`, `docs/reports/sprint-1.md`, `docs/reports/sprint-2.md` (including Divergences), then the source. Build a mental model before judging.

### AUDIT
**Sprint 1 checklist:** brief invariants 2/5 hold in `store.py` (atomicity actually uses temp+`os.replace`; no FastAPI/React imports in pure modules); auth middleware inert when password unset; StaticFiles mounted last; `.env.example` comments say where every value comes from; RUNBOOK ports table matches reality; corrupt `deck.json` loads without crashing.

**Sprint 2 checklist:** validator limits match the brief (hex palette, ≤4 points, ≤12 words, clamp to `LANTERN_MAX_SLIDES`); repair path triggers exactly once; PATCH clears `render` when slide content changes; verbatim invariant 6 (topic/notes stored unmodified).

**Seam matrix — check each producer↔consumer pair field-for-field:**
| Seam | Producer | Consumer | Check |
|---|---|---|---|
| deck.json ↔ Pydantic | store.py | outline_schema.py | same fields, same enums, same optionality |
| deck.json ↔ TS | store.py | dashboard/src/lib/types.ts | field-for-field diff; snake_case consistent across the wire |
| POST/PATCH contracts | api.py | src/lib/api.ts | request/response shapes, error statuses (409/422/503) handled client-side |
| Outline → store | outline.py | store.create_deck | no field invented in one and dropped by the other |
| Cost helper | src/lib/cost.ts | OutlinePage | per-image constant matches the brief's estimate; pure module, no React import |

Run `scripts/verify_store.py`, `verify-sprint1.mjs`, and `verify_outline.py` (one real Haiku call, ≈ a cent).

### FIX
Repair every discrepancy you find. Fixing beats filing: small, surgical commits under `Verify A: fixes`. If a fix would violate a locked decision, do not make it — escalate in the report instead.

### REPORT
`docs/reports/verify-A.md`: What was checked / Seam matrix results (pass/fail per row) / What was fixed / What remains (with severity) / Divergences from the brief you ratified vs. rejected.

---

# PHASE 2 — RENDER PIPELINE

## Sprint 3 — Slide renderer

### RECON
Read `BUILD_BRIEF.md`, reports for 1/2/A. Check current Gemini docs for `gemini-3-pro-image-preview`: model string alive? `imageConfig` still `{aspectRatio, imageSize}`? Note findings in Divergences; build against the pin unless it's dead, in which case use the current Nano Banana Pro string and flag loudly.

### BUILD
1. `src/lantern/prompts.py` (pure): `compose_slide_prompt(style_guide, slide, n, total) -> str`. Structure, roughly:
   - Frame: "Render slide {n} of {total} as ONE finished 16:9 presentation slide — a flat, edge-to-edge graphic design, not a photo of a screen or a mockup on a desk."
   - Deck block, identical every slide: `art_direction` verbatim, palette, typography, motif, tone — prefixed "DECK ART DIRECTION (identical on every slide — do not drift):".
   - Slide block: layout_hint; `Headline (render this text verbatim, correctly spelled): "{title}"`; supporting lines verbatim; `visual_description`.
   - Rules: headline legible from across a room; no text beyond what is quoted; generous margins; no watermarks, no lorem ipsum.
   - Must consume every `style_guide` field (invariant 3) — write a unit check in `scripts/` that greps/asserts this so it can't rot.
2. `src/lantern/gemini.py`: `render_image(prompt, size, style_ref_png: bytes|None) -> bytes`. httpx POST to the REST endpoint; `responseModalities:["TEXT","IMAGE"]`; `imageConfig:{aspectRatio:"16:9", imageSize:size}`; when `style_ref_png` present, prepend an `inline_data` image part plus the instruction "Match the visual style, palette, and typographic treatment of this reference slide exactly; change only the content." Extract first `inlineData` part; no image in response → raise with the text parts as the error message. Timeout 120s; retry once on 5xx/timeout with a logged backoff. One cost line per success: `lantern.render: slide {n} {size} ~${est} (deck total ~${sum})`.
3. `src/lantern/render_service.py`: `render_slide(deck_id, n)` — load deck, guard slide exists, set `render.status=rendering` (atomic save), compose prompt, load slide 1's PNG as ref when `n>1` and it exists, call gemini, `Pillow`-validate the bytes decode as an image, write `slides/NN.png` atomically (tmp + replace), fill the full `render` block including exact `prompt`, `ms`, `cost_estimate_usd`.
4. Endpoint: `POST /api/decks/{id}/slides/{n}/render` (409 if that slide is already rendering) → runs synchronously in a worker thread, returns the updated slide. Static image serving: `GET /api/decks/{id}/slides/{n}.png` streamed from disk with cache headers keyed on `rendered_at`.
5. Boot-time sweep (invariant from Guardrails): any `render.status=="rendering"` found at startup flips to `error:"interrupted"`.
6. `scripts/verify_render.py`: composes prompts for a 3-slide fixture and prints them for eyeball review (no API), then — behind a `--live` flag — renders ONE real slide (≈ $0.14) and asserts the PNG + deck.json bookkeeping.

### VERIFY (do this, don't skip)
- Prompt fixtures read as coherent art briefs; every style_guide field appears; slide text is quoted verbatim.
- `--live` single render: PNG opens, is 16:9, lands at `slides/01.png`; `render` block complete with the exact prompt.
- Error injection: point `LANTERN_IMAGE_MODEL` at a garbage string → 503 to the client, slide `render.status=error` with a useful message, deck.json still valid.
- Kill the service mid-render, restart → slide shows `error: interrupted`, nothing stuck.

### DIVERGENCE
Report — especially any change to the REST contract discovered in recon, and the final prompt template copied into `docs/render-prompt.md`.

---

## Sprint 4 — Deck orchestration

### RECON
Read brief + reports 1/2/A/3. Understand `render_service.render_slide` and the 409 guard before wrapping a queue around them.

### BUILD
1. `src/lantern/queue.py`: single background worker (one `threading.Thread`, one job at a time — sequential is the *feature*: slide 1 must finish before 2..N can reference it). Deck-level job = ordered list of pending slide numbers. API: `enqueue_deck(id)` (skips slides already `done` — that's resume for free), `enqueue_slide(id, n)`, `cancel(id)` (drains that deck's remaining jobs; in-flight slide finishes), `status()`. Deck `status` transitions: `outline → rendering → done` | `error` (first failing slide halts the deck's remaining queue, deck.status=error, everything already done stays done — resumable by rendering again).
2. Endpoints: `POST /api/decks/{id}/render` (whole deck; 409 if already rendering), `POST /api/decks/{id}/cancel`, and single-slide re-render reuses Sprint 3's endpoint but routes through the queue.
3. Frontend `DeckPage`, rendering state: progress grid — one card per slide showing thumb-or-placeholder, status chip (`pending / painting / done / error`), the error message when present, and a per-slide re-render button. Poll `GET /api/decks/{id}` every 2s while `status=="rendering"`; stop when terminal. `OutlinePage`'s Render button goes live: shows the cost estimate in the button label ("Render 8 slides · ~$1.10"), navigates to DeckPage.
4. Regenerate affordance: on a `done` slide card, "Repaint" (same prompt, new roll) and "Edit & repaint" (opens the slide's `visual_description`/text inline, saves via PATCH — which clears the render — then enqueues). Slide 1 repaint shows the one-line note from Locked decision 7.
5. `scripts/verify_queue.py`: with `gemini.render_image` stubbed to return a fixture PNG after 100ms (and to fail on demand), assert: sequential order, slide-1-ref plumbing (ref bytes passed for n>1), skip-done resume, halt-on-error, cancel drains, restart sweep.

### VERIFY (do this, don't skip)
- `verify_queue.py` passes all six behaviors against the stub.
- With a real deck of 2 slides (`--live`, ≈ $0.28): both render in order, second visibly matches the first's style, DeckPage progress grid updates live via polling, cancel mid-deck leaves a clean resumable state.

### DIVERGENCE
Report, especially any place the queue had to touch deck.json outside `store.py` (it must not — invariant 2).

---

## VERIFY SPRINT B — audit Sprints 3–4 and their seams

*Fresh thread, different model. This sprint spends ≈ $0.45 of real Gemini credit; it says so here so nobody is surprised.*

You are a verification agent auditing a render pipeline you did not build. Repo: `E:\git\Lantern`.

### RECON
Read `BUILD_BRIEF.md`, reports 3, 4, and A (for previously ratified divergences), then `prompts.py`, `gemini.py`, `render_service.py`, `queue.py`.

### AUDIT
**Sprint 3 checklist:** invariant 3 (single prompt home + all style_guide fields consumed — run the guard script and also read it skeptically); invariant 4 (16:9 pinned in the actual request body); PNG writes atomic; error paths produce valid deck.json; boot sweep works.

**Sprint 4 checklist:** strict sequencing; halt-on-error; resume skips `done`; cancel semantics match the brief; 409s on double-render; polling stops on terminal states (no immortal intervals in DeckPage).

**Seam matrix:**
| Seam | Producer | Consumer | Check |
|---|---|---|---|
| Outline spec → prompt | outline_schema fields | compose_slide_prompt | every SlideSpec field either painted or deliberately unused (say which) |
| PATCH-clears-render (S2) → queue (S4) | api PATCH | enqueue_deck skip-done | edited slide re-renders; untouched slides don't |
| render block ↔ TS | render_service | types.ts + DeckPage | status enum strings identical; DeckPage renders every status incl. `error: interrupted` |
| Image URL ↔ files | NN.png on disk | `GET .../slides/{n}.png` + `<img>` | zero-padding agreement; cache header actually busts on repaint |
| Ref chain | slide 1 PNG | gemini.render_image style_ref | ref passed for n>1, absent for n=1, absent gracefully when 01.png missing |
| Cost | gemini.py log + cost.ts | OutlinePage button | same constant; button estimate ≈ logged total |

**Live probe (≈ $0.45):** create a 3-slide deck on a real topic, render it end-to-end from the UI. Judge cohesion between slides 2–3 and slide 1 like a human would. Then repaint slide 2 and confirm the file replaced (mtime/bytes) with no orphan files anywhere in the deck folder.

### FIX
Repair what you find; `Verify B: fixes`. Locked decisions stay locked — escalate, don't "improve."

### REPORT
`docs/reports/verify-B.md`, same shape as verify-A, plus: paste the three live prompts and a one-paragraph honest judgment of image cohesion (this is the product; if the decks aren't gorgeous yet, say so and say why — prompt template tweaks are in-scope fixes).

---

# PHASE 3 — VIEWER, EXPORT & SHIP

## Sprint 5 — Viewer + library

### RECON
Read brief + all reports. GATE A check: brief says single-user; confirm nothing this sprint assumes otherwise.

### BUILD
1. `LibraryPage` for real: deck grid, cover = slide 1 thumbnail (placeholder art when unrendered), title/status/updated, sorted by `updated_at`; rename inline; duplicate (`POST /api/decks/{id}/duplicate` — copies folder under a new id, clears exports/); delete with confirm (removes the folder — verify no orphans).
2. `DeckPage`, done state: full-screen viewer — the picture IS the interface. Keyboard ← → and F for fullscreen; click zones left/right; slide counter in Plex Mono; a thin filmstrip rail; Esc back to grid view (the Sprint 4 progress grid becomes the deck's grid view with repaint affordances).
3. Present mode polish: preload next/prev images; `object-fit: contain` on a true-black stage so 16:9 letterboxes cleanly on any screen.
4. Empty/loading/error states across all pages, in-voice (short, warm, no lorem).

### VERIFY (do this, don't skip)
- Keyboard nav, fullscreen, filmstrip on a rendered deck; duplicate produces an independent editable copy; delete leaves no directory behind.
- Open the viewer from a phone over Tailscale (with `LANTERN_PASSWORD` set) — images load, nav works.

### DIVERGENCE
Report.

---

## Sprint 6 — Export + ship

### RECON
Read brief + reports. Confirm python-pptx and img2pdf resolve on Python 3.12.

### BUILD
1. `src/lantern/export.py`: `export_deck(id, fmt)` → `exports/lantern-<slug>.<ext>`, rebuilt every call (invariant 7). PPTX: 13.333"×7.5" slide size, one picture per slide, full-bleed (0,0 to full width/height), deck title in doc properties. PDF: img2pdf, one page per slide, page size matched to image aspect. ZIP: `01.png..NN.png` + `deck.json`.
2. Endpoint `POST /api/decks/{id}/export?fmt=pptx|pdf|zip` → `{download_url}`; `GET /api/decks/{id}/exports/{filename}` streams with correct content-type + attachment disposition. 409 when the deck isn't fully rendered (partial export behind `?allow_partial=true` skips unrendered slides).
3. Frontend: export menu on DeckPage (three formats, spinner, browser download).
4. Ship it: recipient-facing `README.md` (one-line thesis; "Make a deck in three moves"; "Honest answers to fair questions" — including what it costs per deck and that repainting slide 1 won't restyle the others); RUNBOOK completed (ports table, start/stop/restart via Task Scheduler, env knobs, **Known failure modes → fixes**: interrupted renders, paid-tier Gemini key errors, port conflicts); register the Scheduled Task (logon trigger, restart-on-failure ×3); DECISIONS.md seeded with the twelve locked decisions, reverse-chronological.

### VERIFY (do this, don't skip)
- Export all three formats from a rendered deck; PPTX opens in PowerPoint with edge-to-edge images and correct order; PDF pages match; ZIP contents complete.
- Reboot-grade test: log off/on → Task Scheduler brings Lantern up → health probe green without touching a terminal.

### DIVERGENCE
Report.

---

## VERIFY SPRINT C — audit Sprints 5–6 and their seams

*Fresh thread, different model. Spends ≈ $0.30 only if it needs to render (prefer reusing Verify B's deck).*

You are a verification agent. Repo: `E:\git\Lantern`. Read `BUILD_BRIEF.md`, reports 5, 6, B; then audit.

### AUDIT
**Sprint 5:** duplicate is deep and independent (edit the copy, original untouched); delete removes the whole folder; viewer preloads (network tab); no per-page fetch outside `src/lib/api.ts`.

**Sprint 6:** exports rebuilt on demand (mtime changes each call), never treated as source of truth; partial-export flag behavior; RUNBOOK failure modes actually reproduce and the listed fixes work (test at least the port-conflict one); Task Scheduler entry survives a restart.

**Seam matrix:**
| Seam | Producer | Consumer | Check |
|---|---|---|---|
| Store paths | store.py layout | export.py | export reads via store helpers, not hand-built paths |
| Slide order | slides[].n | PPTX/PDF/ZIP | order identical in all three artifacts |
| Aspect | 16:9 PNGs | PPTX geometry | full-bleed, no letterbox/stretch in PowerPoint |
| Duplicate | duplicate endpoint | exports/ + render blocks | copied deck has empty exports/; render blocks intact and images present |
| Auth | DashboardAuthMiddleware | export download URLs | downloads are behind the same Basic auth |
| Delete | delete_deck | filesystem | zero orphans (walk data/ before/after) |

### FIX / REPORT
Fix surgically (`Verify C: fixes`), escalate anything touching locked decisions, write `docs/reports/verify-C.md` in the standard shape.

---

# FINAL VERIFICATION ROUND — the whole lantern, lit

*Fresh thread, different model than any build sprint. Spends ≈ $1.20 of real Gemini credit on one full deck; that is the point.*

You are the final verification agent for Lantern. Assume nothing any report claims; re-establish it. Repo: `E:\git\Lantern`.

### RECON
Read `BUILD_BRIEF.md`, all sprint and verify reports, RUNBOOK, DECISIONS, README. Note every "What's deferred" and every escalation — you'll disposition each one.

### AUDIT — end to end
1. **Cold start honesty:** fresh venv from `requirements.txt`, fresh `npm ci && npm run build`, `.env` recreated from `.env.example` alone (real keys in, nothing else). If `.env.example`'s comments aren't enough to do this without reading source, that's a defect — fix the comments.
2. **The real run (≈ $1.20):** from the UI, create "The cell membrane and transport — 8 slides" with source notes pasted in. Judge the outline as a teacher would (arc, slide text brevity, art_direction coherence). Render the full deck. Watch the progress grid. Then: repaint one slide, edit-and-repaint another, export all three formats, open the PPTX.
3. **Resilience:** kill the service mid-deck → restart → interrupted slide marked, resume completes only the remainder. Cancel works. Double-render 409s.
4. **Remote:** full flow from a second device over Tailscale with `LANTERN_PASSWORD` set; confirm nothing (network tab) ever shipped an API key or called Google/Anthropic from the browser.
5. **Cross-seam rollup:** re-run the A, B, and C seam matrices as spot-checks (one probe per row, not the full ceremony). Any row that regressed gets fixed and called out loudly.
6. **Invariant sweep:** all seven Sacred Invariants, checked against code as it exists now, not as reports describe it.
7. **Cost ledger:** sum the logged render costs for this session; confirm the OutlinePage estimate was within ~20% of reality; note current per-image pricing if it has drifted from the brief.

### FIX
Repair defects found; `Final verify: fixes`. Anything that would relitigate a locked decision goes in the report as a recommendation, not a change.

### REPORT — `docs/reports/final-verify.md`
What was verified end-to-end / The real deck (attach the topic, slide count, total spend, and your honest one-paragraph review of whether the deck is *gorgeous* — the bar is Kimi's visual mode, not "images appeared") / Fixed this round / Known issues by severity / Deferred items dispositioned (ship-without vs. next-phase) / Locked-decision recommendations, if any.

Lantern ships when this report exists and its Known Issues list contains nothing severity-high.
