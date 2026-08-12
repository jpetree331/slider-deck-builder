# Sprint 6 report — Export + ship

## What shipped

- Recon: python-pptx 1.0.2 and img2pdf 0.6.3 resolve and run on Python 3.12.10 (exercised by the verify script, not just installed).
- `export.py`: `export_deck(id, fmt, allow_partial)` → `exports/lantern-<slug>.<ext>`, **rebuilt on every call** (tmp + `os.replace`; invariant 7). PPTX: 13.333″ × 7.5″, one picture per slide, full-bleed (0,0 → full width/height), deck title in core doc properties. PDF: img2pdf, one page per slide, page size matched to the image aspect. ZIP: `01.png..NN.png` + `deck.json`. Slide order = `slides[].n` order in all three. All paths via store helpers.
- Endpoints: `POST /api/decks/{id}/export?fmt=pptx|pdf|zip[&allow_partial=true]` → `{download_url}`; 409 (`NotFullyRendered`) when the deck isn't fully rendered and the flag is absent; 409 (`NothingToExport`) at zero rendered slides. `GET /api/decks/{id}/exports/{filename}` streams with the right content-type and `attachment` disposition; path-shaped filenames refused; downloads sit behind the same Basic auth middleware as everything else.
- Frontend: Export ▾ menu on DeckPage (PPTX / PDF / ZIP, spinner label while exporting, browser download via the returned URL; partially rendered decks label the options "(painted only)" and send `allow_partial`).
- Ship docs: recipient-facing `README.md` (one-line thesis, "Make a deck in three moves", "Honest answers to fair questions" — per-deck cost, the slide-1 anchor behavior, edit-clears-picture, where decks live, Tailscale password, `interrupted` meaning). `RUNBOOK.md` completed: ports table, start/stop/restart, Task Scheduler steps, env knobs, logs, **Known failure modes → fixes** (8 rows incl. interrupted renders, paid-tier Gemini key, port conflict with the `netstat` one-liner), do-not-disturb inventory. `DECISIONS.md` seeded reverse-chronologically: 4 build-time decisions + the twelve locked decisions.

## What you need to do once

- On the deployment machine: register the Scheduled Task (RUNBOOK steps 1–5) and run the log-off/log-on health check.

## What's deferred

- **Task Scheduler registration + reboot-grade test** — this build ran on a non-target machine; registering a logon task here would be wrong. Steps are written and the `.cmd` is tested manually.
- Opening the PPTX in desktop PowerPoint — not installed here; python-pptx re-opens and verifies geometry/order instead. Final Verification should eyeball it in real PowerPoint.

## Verification

`verify_export.py`: 12/12 — slug strips punctuation; PPTX 13.333×7.5 with one full-bleed picture per slide at (0,0) and title in doc properties; PDF magic bytes + 3 pages; ZIP contents exactly `01–03.png + deck.json`; second export rewrites the file (mtime advances — rebuilt on demand); partial-without-flag 409s; `allow_partial` skips unrendered; zero-rendered 409s. `npm run build` clean.

## Divergences

1. **Partial exports from the UI send `allow_partial` automatically** when the deck has unpainted slides, labeled "(painted only)" — the brief gated partials behind the flag server-side (still true); the UI chooses convenience with honest labeling.
2. Task Scheduler registration written-not-executed (machine divergence, recorded in DECISIONS.md).
3. Export download endpoint reads bytes into memory rather than streaming from disk — deck exports are tens of MB at worst; simplicity won. Flag for Verify C if 4K × 16-slide decks make this matter.
