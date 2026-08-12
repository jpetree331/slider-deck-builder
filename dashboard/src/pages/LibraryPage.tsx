import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { deleteDeck, duplicateDeck, listDecks, patchDeck, slideImageUrl } from '../lib/api'
import type { DeckSummary } from '../lib/types'
import { useAsync } from '../hooks/useAsync'
import './LibraryPage.css'

export default function LibraryPage() {
  const { data: decks, loading, error, reload } = useAsync(listDecks, [])
  const navigate = useNavigate()
  const [renaming, setRenaming] = useState<string | null>(null)
  const [renameText, setRenameText] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  if (loading) return <div className="state-note">Warming the lantern…</div>
  if (error)
    return (
      <div className="state-note error">
        Couldn't reach the Lantern service — is it running on port 8020?
        <div className="mono" style={{ marginTop: 'var(--space-3)' }}>{error.message}</div>
      </div>
    )

  if (!decks || decks.length === 0)
    return (
      <div className="state-note">
        <h2>No decks yet</h2>
        <p>Type a topic, get a presentation where every slide is one painting.</p>
        <Link to="/new">
          <button className="primary">Make your first deck</button>
        </Link>
      </div>
    )

  const run = async (id: string, fn: () => Promise<unknown>) => {
    setBusy(id)
    setActionError(null)
    try {
      await fn()
      reload()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const open = (d: DeckSummary) =>
    navigate(d.status === 'outline' ? `/decks/${d.id}/outline` : `/decks/${d.id}`)

  return (
    <>
      {actionError && <div className="state-note error">{actionError}</div>}
      <div className="library-grid">
        {decks.map((d) => (
          <div key={d.id} className="deck-card">
            <div
              className="deck-cover"
              role="button"
              tabIndex={0}
              onClick={() => open(d)}
              onKeyDown={(e) => e.key === 'Enter' && open(d)}
            >
              {d.cover ? (
                <img src={slideImageUrl(d.id, 1, d.updated_at)} alt="" loading="lazy" />
              ) : (
                <div className="deck-cover-placeholder">{d.title.slice(0, 1) || '?'}</div>
              )}
            </div>
            <div className="deck-meta">
              {renaming === d.id ? (
                <input
                  className="deck-rename"
                  value={renameText}
                  autoFocus
                  onChange={(e) => setRenameText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && renameText.trim())
                      run(d.id, () => patchDeck(d.id, { title: renameText.trim() })).then(() =>
                        setRenaming(null),
                      )
                    if (e.key === 'Escape') setRenaming(null)
                  }}
                  onBlur={() => setRenaming(null)}
                />
              ) : (
                <div className="deck-title" onDoubleClick={() => { setRenaming(d.id); setRenameText(d.title) }}>
                  {d.title}
                </div>
              )}
              <div className="mono deck-sub">
                {d.slide_count} slides · {d.status}
              </div>
              <div className="deck-actions">
                <button
                  className="ghost"
                  disabled={busy === d.id}
                  onClick={() => { setRenaming(d.id); setRenameText(d.title) }}
                >
                  rename
                </button>
                <button
                  className="ghost"
                  disabled={busy === d.id}
                  onClick={() => run(d.id, () => duplicateDeck(d.id))}
                >
                  duplicate
                </button>
                <button
                  className="ghost danger"
                  disabled={busy === d.id}
                  onClick={() => {
                    if (window.confirm(`Delete "${d.title}"? The pictures go with it.`))
                      run(d.id, () => deleteDeck(d.id))
                  }}
                >
                  delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
