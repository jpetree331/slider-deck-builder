# Lantern 🏮

Type a topic, get a presentation where every slide is a single beautiful picture. And in the **Chalk** tab: a private Claude/Gemini chat with Projects, for lesson planning on networks where claude.ai is filtered but the APIs aren't.

Claude Haiku writes the outline and a style guide; Gemini's Nano Banana Pro paints every slide as one 16:9 image; Lantern keeps them coherent, lets you edit and repaint, and exports to PowerPoint, PDF, or a zip of pictures. Everything lives on your own machine — a deck is just a folder.

## Make a deck in three moves

1. **New deck** — say what it's about (paste your notes in if you have them), pick a slide count or let it choose.
2. **Edit the outline** — the style guide and every slide's words are yours to change. Everything autosaves.
3. **Render** — watch the paintings arrive one by one. Present it full-screen, or export.

## Starting it

- Once: copy `.env.example` to `.env` and add your two API keys (the comments in the file say exactly where to get them). Then `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`, and inside `dashboard/`: `npm install && npm run build`.
- Every day: double-click `start-lantern.cmd` (or let Task Scheduler do it — see `RUNBOOK.md`), then open **http://localhost:8020**.

## The Chalk tab — chat with Projects

Click **Chalk — chat** in the header (or go to `/chalk`). A *project* holds instructions (how the assistant should behave) and pasted knowledge (a syllabus, a pacing guide); every chat inside that project carries both automatically. Conversations stream live, render markdown, and export to clean `.md` transcripts. The model dropdown offers **Claude Haiku 4.5** (the default — fast and cheap) plus **Gemini Flash/Pro (latest)**, using the same two API keys the deck side already has. Enter sends, Shift+Enter makes a new line, Esc stops a reply mid-stream (the partial is kept). Chat history lives in one file, `data/chalk.db` — copy it and you've backed it up. Fonts are bundled with the app, so nothing needs the open internet except the model calls themselves.

## Honest answers to fair questions

**What does a deck cost?** Each painted slide is about $0.13 at the default 2K size, so a 10-slide deck is roughly $1.30–1.50, plus a penny or so for the outline. 4K roughly doubles the pictures' cost. The Render button always shows the estimate before you spend, and there's a hard 16-slide cap per deck.

**Why did repainting slide 1 not change the other slides?** Slide 1 is the style anchor: when slides 2+ are painted, they look at slide 1's picture *at that moment*. Repainting slide 1 later doesn't reach back and restyle the others — repaint them too if you want them to follow the new look.

**Can I edit a slide after it's painted?** Yes — but editing its words clears its picture, because the picture would no longer match what it says. Save your edit and it repaints.

**Where are my decks?** `data/decks/` — each deck is one folder with the pictures and a `deck.json`. Copy the folder and you've backed up the deck; zip it and you've shared it. The PPTX/PDF/ZIP exports are rebuilt from the pictures on every click, so they're never stale.

**Is it safe to open over Tailscale?** Set `LANTERN_PASSWORD` in `.env` first — then everything (app, images, downloads) requires it. Your API keys never leave the server; the browser never talks to Anthropic or Google.

**Why does a slide say `error: interrupted`?** The machine restarted mid-painting. Nothing is stuck — hit Render again and it finishes just the missing ones.

## For builders

`BUILD_BRIEF.md` and `lantern_master_plan.md` are the contract; `docs/reports/` is the build history; `RUNBOOK.md` is ops; `DECISIONS.md` records what's locked and why.
