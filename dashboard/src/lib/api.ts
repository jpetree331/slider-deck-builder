// The ONLY fetch site in the app — every network call goes through here.
// Framework-free on purpose — no React imports (Sacred Invariant 5).

import type { DeckSummary } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
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
