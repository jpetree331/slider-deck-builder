# Attachments report — source material with vision

Owner ask: attach a PDF / DOCX / PPTX as source material for the outline ("look at this information and revamp this slide deck") — including the **visuals**, not just text, especially when revamping a PPTX.

## What shipped

- `src/lantern/extract.py` (framework-free): `extract_content(filename, bytes)` → text + embedded images.
  - **PPTX**: per-slide text with `[Slide N]` markers, speaker notes, embedded pictures (`slide N` provenance notes).
  - **DOCX**: paragraphs, tables flattened to `a | b` rows, embedded images.
  - **PDF**: per-page text; embedded images via pypdf (no rasterizer). Image-only PDFs (scans) succeed with images and empty text; text-and-image-free files fail with a friendly 422.
  - Image pipeline: dedupe by hash, icon filter (<3 KB or <64 px), largest-first cap of **8**, downscale to ≤1024 px, re-encode JPEG q80, base64. Text clamped at 80 k chars with a visible truncation note. Password-protected/damaged files → clean `ExtractError`.
- `POST /api/extract` (multipart; 20 MB → 413, bad type → 422). **Extract-and-discard**: the file is never written to disk.
- Outline vision: `generate_outline(..., images=)` sends the images as base64 vision blocks ahead of the user text, plus an "ATTACHED VISUALS" pointer naming their origins; the system prompt (and its audit copy in `docs/outline-prompt.md`) instructs Haiku to carry their subject matter and visual character into `art_direction`/`visual_description`s — or depart deliberately when asked.
- `NewDeckPage`: 📎 attach button (multi-file), extracted text appended into the **editable** source-notes textarea under `--- Attached: name ---` headers (invariant 6 — what you see is exactly what Haiku gets), image thumbnails as removable chips with a count line, reading indicator, mapped errors inline.
- New deps: pypdf 6.16.0, python-docx 1.2.0, python-multipart 0.0.32 (requirements.txt updated — the lock grows).

## The honest limit (told to the user in UI + README)

We extract the document's text and **embedded images** — not a rasterized screenshot of each slide's layout. Rendering a PPTX's true look requires PowerPoint itself; text + imagery + Haiku vision covers the practical "revamp" need. Scanned PDFs with no text layer yield only their images (or a clear error when they have neither).

## Verification

`verify_extract.py` — 21/21 offline + 1 live: fixture PPTX/DOCX/PDF built in-memory by the same libraries (incompressible noise images so the icon filter is honestly exercised); slide markers + speaker notes; table flattening; hand-assembled text PDF; img2pdf image-only PDF; unknown-type and damaged-file errors; truncation note; icon filtering + dedupe + ≤1024 downscale; stub-client proof that image blocks precede the text block and the no-image path stays a plain string; HTTP contract (200 with images over the wire, 422 friendly, 413 oversize); **live Haiku vision outline** (real API, 2 slides, ~1 cent) validates.

Regression: `verify_outline.py`, `verify_chalk.py` still green; `npm run build` clean.

## Deferred

- OCR for scanned PDFs (would need tesseract or a vision-extraction call — new decision, not a stub).
- Page/slide rasterization (needs PowerPoint/LibreOffice — out of stack).
- Attach-to-existing-outline: revamping is a new-deck flow by design (attach the old deck, describe the revamp in the topic box).
