// The ONLY fetch site in the app — every network call goes through here.
// Framework-free on purpose — no React imports (Sacred Invariant 5).

import type { Deck, DeckSummary, SlideSize, StyleGuide } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // FormData sets its own multipart boundary — only JSON bodies get a header
  const jsonBody = init?.body != null && !(init.body instanceof FormData)
  const res = await fetch(path, {
    headers: jsonBody ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
      else if (Array.isArray(body?.detail))
        // FastAPI 422s carry a list of validation errors — surface the messages
        detail = body.detail
          .map((d: { msg?: string }) => d?.msg ?? JSON.stringify(d))
          .join('; ')
    } catch {
      /* non-JSON error body — keep statusText */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export function health(): Promise<{ status: string; service: string }> {
  return request('/api/health')
}

export async function listDecks(): Promise<DeckSummary[]> {
  const body = await request<{ decks: DeckSummary[] }>('/api/decks')
  return body.decks
}

export function deleteDeck(id: string): Promise<{ ok: boolean }> {
  return request(`/api/decks/${id}`, { method: 'DELETE' })
}

export interface CreateDeckPayload {
  topic: string
  source_notes?: string
  slide_count?: number | null
  style_hints?: string
  slide_size?: SlideSize
  images?: AttachedImage[] // ride to the one outline call, then discarded
}

export interface SlidePatchPayload {
  n: number | null // the slide's CURRENT server-side position; null = new slide
  title: string
  points: string[]
  visual_description: string
  layout_hint: string
}

export interface PatchDeckPayload {
  title?: string
  style_guide?: Partial<StyleGuide>
  slides?: SlidePatchPayload[]
  slide_size?: SlideSize
}

export function createDeck(payload: CreateDeckPayload): Promise<Deck> {
  return request('/api/decks', { method: 'POST', body: JSON.stringify(payload) })
}

export function getDeck(id: string): Promise<Deck> {
  return request(`/api/decks/${id}`)
}

export function patchDeck(id: string, payload: PatchDeckPayload): Promise<Deck> {
  return request(`/api/decks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function renderDeck(id: string): Promise<Deck> {
  return request(`/api/decks/${id}/render`, { method: 'POST' })
}

export function cancelRender(id: string): Promise<Deck> {
  return request(`/api/decks/${id}/cancel`, { method: 'POST' })
}

export function renderSlide(id: string, n: number): Promise<Deck> {
  return request(`/api/decks/${id}/slides/${n}/render`, { method: 'POST' })
}

export function duplicateDeck(id: string): Promise<Deck> {
  return request(`/api/decks/${id}/duplicate`, { method: 'POST' })
}

export interface AttachedImage {
  media_type: string
  data: string // base64 — already downscaled server-side
  note: string // e.g. "slide 3", "page 2"
}

export interface ExtractResult {
  filename: string
  kind: 'pdf' | 'docx' | 'pptx'
  text: string
  chars: number
  truncated: boolean
  images: AttachedImage[]
}

/** Extract an attachment's text server-side. The file is never stored. */
export function extractFile(file: File): Promise<ExtractResult> {
  const form = new FormData()
  form.append('file', file)
  return request('/api/extract', { method: 'POST', body: form })
}

export type ExportFormat = 'pptx' | 'pdf' | 'zip'

export function exportDeck(
  id: string,
  fmt: ExportFormat,
  allowPartial = false,
): Promise<{ download_url: string }> {
  const partial = allowPartial ? '&allow_partial=true' : ''
  return request(`/api/decks/${id}/export?fmt=${fmt}${partial}`, { method: 'POST' })
}

/** Image URL for a rendered slide; rendered_at busts the cache on repaint. */
export function slideImageUrl(id: string, n: number, renderedAt: string | null): string {
  const v = renderedAt ? `?v=${encodeURIComponent(renderedAt)}` : ''
  return `/api/decks/${id}/slides/${n}.png${v}`
}
