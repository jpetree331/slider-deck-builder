# Sprint 5 report — Viewer + library

## What shipped

- **GATE A check (recon):** nothing this sprint assumes multi-user. Lantern stays single-user; the optional Basic password remains the only auth. Gate closed for this build — if biology-team accounts ever become real, that's the flagged store redesign.
- `store.duplicate_deck`: deep copy under a fresh id — deck.json + slide PNGs; title gets " (copy)"; `exports/` deliberately left empty (derived artifacts, invariant 7); a mid-render source settles the copy to a clean resumable state. `POST /api/decks/{id}/duplicate` endpoint.
- `LibraryPage` for real: cover = slide 1 thumbnail (cache-busted by `updated_at`) or monogram placeholder; title/status/slide-count; sorted by `updated_at` (server-side); inline rename (double-click or button, Enter saves via PATCH, Esc cancels); duplicate; delete with confirm ("The pictures go with it."). Server list order already `updated_at` desc.
- `DeckPage` present mode — the picture IS the interface: a `done` deck opens straight into the viewer. Keyboard ← → (and space) navigate, F toggles fullscreen, Esc exits to the grid view (browser eats Esc-in-fullscreen first, as it should). Click zones left/right 30%. Slide counter in Plex Mono ("03 / 08"). Thin filmstrip rail with thumbs, click to jump. Grid view (the Sprint 4 progress grid with repaint affordances) reachable via "✕ grid" / Esc; "Present" button returns.
- Present-mode polish: neighbors preloaded on every index change so arrows never flash; `object-fit: contain` on a true-black stage (`--stage`) so 16:9 letterboxes cleanly on any screen.
- Empty/loading/error states across all pages, in-voice, no lorem ("Warming the lantern…", "No decks yet — type a topic, get a presentation where every slide is one painting.").
- `scripts/verify_library.py`: duplicate deep-copy checks, independence checks (edit copy → original untouched, byte-level PNG isolation), delete-leaves-no-orphans walk of the data dir.

## What you need to do once

Nothing new. Phone-over-Tailscale spot-check belongs to the Final Verification round (needs the Tailscale network, absent in this build environment).

## What's deferred

- Tailscale phone check (environment) — the viewer is plain `<img>` + same-origin API with Basic auth, no exotic APIs, so nothing architecturally blocks it; still must be eyeballed on real hardware.

## Verification

- `verify_library.py`: 11/11 — fresh id, "(copy)" title, render blocks intact, PNG bytes copied, empty `exports/`, edit-the-copy independence, byte-level image isolation, no-orphan delete (before/after walk of `data/`), original survives.
- `npm run build` clean.
- Viewer keyboard/fullscreen/filmstrip logic exercised by reading + the Final round's live pass (no rendered deck exists in this environment to click through — noted honestly).

## Divergences

1. **Rename is double-click *or* an explicit button** — the brief said "rename inline"; the button makes the affordance discoverable on touch devices (Tailscale phone use is a stated scenario).
2. **Space also advances** in present mode — standard presenter-remote behavior, additive.
3. Duplicate of a mid-render deck settles the copy to `outline` and drops pending marks — the brief didn't specify; a copy referencing a render-in-progress would be born stale.
