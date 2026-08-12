import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { cancelRender, getDeck, patchDeck, renderDeck, renderSlide, slideImageUrl } from '../lib/api'
import type { SlidePatchPayload } from '../lib/api'
import { COST_PER_IMAGE_USD, formatUsd } from '../lib/cost'
import type { Deck, Slide } from '../lib/types'
import './DeckPage.css'

function chipLabel(slide: Slide): string {
  if (!slide.render) return 'unpainted'
  if (slide.render.status === 'rendering') return 'painting'
  return slide.render.status // pending | done | error
}

export default function DeckPage() {
  const { id } = useParams<{ id: string }>()
  const [deck, setDeck] = useState<Deck | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editing, setEditing] = useState<number | null>(null) // slide n being edited

  useEffect(() => {
    if (!id) return
    let alive = true
    getDeck(id).then(
      (d) => alive && setDeck(d),
      (e) => alive && setError(e instanceof Error ? e.message : String(e)),
    )
    return () => {
      alive = false
    }
  }, [id])

  // poll every 2s while rendering; the interval dies on terminal states
  useEffect(() => {
    if (!id || deck?.status !== 'rendering') return
    const timer = window.setInterval(() => {
      getDeck(id).then(setDeck, () => {})
    }, 2000)
    return () => window.clearInterval(timer)
  }, [id, deck?.status])

  const act = useCallback((p: Promise<Deck>) => {
    setActionError(null)
    p.then(setDeck, (e) => setActionError(e instanceof Error ? e.message : String(e)))
  }, [])

  const notDone = useMemo(
    () => (deck ? deck.slides.filter((s) => s.render?.status !== 'done').length : 0),
    [deck],
  )
  const spentSoFar = useMemo(
    () =>
      deck
        ? deck.slides.reduce((sum, s) => sum + (s.render?.cost_estimate_usd ?? 0), 0)
        : 0,
    [deck],
  )

  if (error) return <div className="state-note error">{error}</div>
  if (!deck) return <div className="state-note">Opening the deck…</div>

  const estimate = notDone * COST_PER_IMAGE_USD[deck.slide_size]

  return (
    <div className="deckpage">
      <header className="deckpage-bar">
        <Link to="/" className="ghost-link mono">
          ← library
        </Link>
        <h1>{deck.title}</h1>
        <div className="deckpage-bar-right">
          <span className={`mono status-chip status-${deck.status}`}>{deck.status}</span>
          <Link to={`/decks/${deck.id}/outline`}>
            <button className="ghost">Edit outline</button>
          </Link>
          {deck.status === 'rendering' ? (
            <button className="danger" onClick={() => id && act(cancelRender(id))}>
              Cancel
            </button>
          ) : (
            notDone > 0 && (
              <button className="primary" onClick={() => id && act(renderDeck(id))}>
                {notDone === deck.slides.length
                  ? `Render ${notDone} slides · ~${formatUsd(estimate)}`
                  : `Resume ${notDone} left · ~${formatUsd(estimate)}`}
              </button>
            )
          )}
        </div>
      </header>
      {actionError && <div className="state-note error">{actionError}</div>}

      <div className="progress-grid">
        {deck.slides.map((s) => (
          <div key={s.n} className="progress-card">
            <div className="progress-thumb">
              {s.render?.status === 'done' && s.render.image ? (
                <img src={slideImageUrl(deck.id, s.n, s.render.rendered_at)} alt={s.title} />
              ) : (
                <div className="progress-placeholder">
                  <span className="mono">{s.layout_hint || 'slide'}</span>
                  <strong>{s.title}</strong>
                </div>
              )}
              {(chipLabel(s) === 'painting' || chipLabel(s) === 'pending') && (
                <div className="progress-veil">
                  <span className="mono">{chipLabel(s) === 'painting' ? 'painting…' : 'queued'}</span>
                </div>
              )}
            </div>
            <div className="progress-meta">
              <span className="mono slide-n">{String(s.n).padStart(2, '0')}</span>
              <span className={`mono chip chip-${chipLabel(s)}`}>{chipLabel(s)}</span>
              <span className="progress-actions">
                {s.render?.status === 'done' && (
                  <>
                    <button
                      className="ghost"
                      title={
                        s.n === 1
                          ? 'Repainting slide 1 will not restyle already-painted slides — the style reference is consumed at render time.'
                          : 'Same prompt, new roll'
                      }
                      onClick={() => id && act(renderSlide(id, s.n))}
                    >
                      Repaint
                    </button>
                    <button className="ghost" onClick={() => setEditing(editing === s.n ? null : s.n)}>
                      Edit &amp; repaint
                    </button>
                  </>
                )}
                {(!s.render || s.render.status === 'error') && (
                  <button className="ghost" onClick={() => id && act(renderSlide(id, s.n))}>
                    Paint
                  </button>
                )}
              </span>
            </div>
            {s.n === 1 && s.render?.status === 'done' && deck.slides.some((o) => o.n !== 1 && o.render?.status === 'done') && (
              <div className="mono anchor-note">
                style anchor — repainting it won't restyle the painted slides
              </div>
            )}
            {s.render?.status === 'error' && (
              <div className="mono render-error">{s.render.error}</div>
            )}
            {editing === s.n && (
              <SlideEditor
                deck={deck}
                slide={s}
                onDone={(d) => {
                  setDeck(d)
                  setEditing(null)
                }}
                onError={(m) => setActionError(m)}
              />
            )}
          </div>
        ))}
      </div>

      <footer className="deckpage-foot mono">
        {deck.slides.length} slides · {deck.slide_size} · spent so far ~{formatUsd(spentSoFar)}
      </footer>
    </div>
  )
}

function SlideEditor({
  deck,
  slide,
  onDone,
  onError,
}: {
  deck: Deck
  slide: Slide
  onDone: (deck: Deck) => void
  onError: (message: string) => void
}) {
  const [title, setTitle] = useState(slide.title)
  const [pointsText, setPointsText] = useState(slide.points.join('\n'))
  const [visual, setVisual] = useState(slide.visual_description)
  const [busy, setBusy] = useState(false)

  async function saveAndRepaint() {
    setBusy(true)
    try {
      // full slide list, each claiming its current identity; the edited one
      // changes content, which clears its render server-side
      const slides: SlidePatchPayload[] = deck.slides.map((s) => ({
        n: s.n,
        title: s.n === slide.n ? title : s.title,
        points:
          s.n === slide.n
            ? pointsText.split('\n').map((p) => p.trim()).filter(Boolean).slice(0, 4)
            : s.points,
        visual_description: s.n === slide.n ? visual : s.visual_description,
        layout_hint: s.layout_hint,
      }))
      await patchDeck(deck.id, { slides })
      onDone(await renderSlide(deck.id, slide.n))
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <div className="slide-editor">
      <label>
        Headline
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Points <span className="hint">one per line, ≤4</span>
        <textarea rows={3} value={pointsText} onChange={(e) => setPointsText(e.target.value)} />
      </label>
      <label>
        The picture
        <textarea rows={3} value={visual} onChange={(e) => setVisual(e.target.value)} />
      </label>
      <button className="primary" disabled={busy} onClick={saveAndRepaint}>
        {busy ? 'Saving…' : 'Save & repaint'}
      </button>
    </div>
  )
}
