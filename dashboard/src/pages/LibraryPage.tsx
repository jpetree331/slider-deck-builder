import { Link } from 'react-router-dom'
import { listDecks } from '../lib/api'
import { useAsync } from '../hooks/useAsync'
import './LibraryPage.css'

export default function LibraryPage() {
  const { data: decks, loading, error } = useAsync(listDecks, [])

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

  return (
    <div className="library-grid">
      {decks.map((d) => (
        <Link key={d.id} to={d.status === 'outline' ? `/decks/${d.id}/outline` : `/decks/${d.id}`}>
          <div className="deck-card">
            <div className="deck-cover">
              {d.cover ? (
                <img src={`/api/decks/${d.id}/slides/1.png`} alt="" loading="lazy" />
              ) : (
                <div className="deck-cover-placeholder">{d.title.slice(0, 1) || '?'}</div>
              )}
            </div>
            <div className="deck-meta">
              <div className="deck-title">{d.title}</div>
              <div className="mono deck-sub">
                {d.slide_count} slides · {d.status}
              </div>
            </div>
          </div>
        </Link>
      ))}
    </div>
  )
}
