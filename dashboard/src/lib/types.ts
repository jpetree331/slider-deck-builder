// Mirrors src/lantern/store.py's deck.json field-for-field (snake_case across
// the wire, kept snake_case here so the mirror is greppable).
// Framework-free on purpose — no React imports — so verify scripts can
// exercise this headless (Sacred Invariant 5).

export type SlideSize = '1K' | '2K' | '4K'
export type DeckStatus = 'outline' | 'rendering' | 'done' | 'error'
export type RenderStatus = 'pending' | 'rendering' | 'done' | 'error'

export interface StyleGuide {
  palette: string[] // 3–5 hex
  typography: string
  motif: string
  art_direction: string // THE consistency field — quoted verbatim into every slide prompt
  tone: string
}

export interface SlideRender {
  status: RenderStatus
  image: string | null // "slides/01.png"
  prompt: string | null // exact final prompt sent
  model: string | null
  ms: number | null
  error: string | null
  rendered_at: string | null
  cost_estimate_usd: number | null
}

export interface Slide {
  n: number
  title: string // rendered verbatim into the image
  points: string[] // ≤4 short lines, rendered verbatim
  visual_description: string
  layout_hint: string
  render: SlideRender | null
}

export interface Deck {
  id: string
  title: string
  topic: string // verbatim user ask
  source_notes: string // optional pasted content, verbatim
  style_guide: StyleGuide
  slide_size: SlideSize
  aspect_ratio: '16:9'
  status: DeckStatus
  slides: Slide[]
  created_at: string
  updated_at: string
}

export interface DeckSummary {
  id: string
  title: string
  status: DeckStatus
  slide_count: number
  updated_at: string
  cover: string | null
}
