import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { cancelRender, exportDeck, getDeck, patchDeck, renderDeck, renderSlide, slideImageUrl } from '../lib/api'
import type { ExportFormat, SlidePatchPayload } from '../lib/api'
import { estimateSlideCost, formatUsd } from '../lib/cost'
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
  const [mode, setMode] = useState<'grid' | 'present'>('grid')
  const [exportOpen, setExportOpen] = useState(false)
  const [exporting, setExporting] = useState<ExportFormat | null>(null)

  useEffect(() => {
    if (!id) return
    let alive = true
    getDeck(id).then(
      (d) => {
        if (!alive) return
        setDeck(d)
        // a finished deck opens straight into the viewer — the picture IS the interface
        if (d.status === 'done') setMode('present')
      },
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

  // exact, not flat: slide 1 paints unanchored, later slides carry the style
  // ref (and may route through a painter's edit twin at its own price)
  const estimate = deck.slides
    .filter((s) => s.render?.status !== 'done')
    .reduce(
      (sum, s) => sum + estimateSlideCost(deck.image_model, deck.slide_size, s.n !== 1),
      0,
    )
  const anyDone = deck.slides.some((s) => s.render?.status === 'done')

  if (mode === 'present')
    return <Presenter deck={deck} onExit={() => setMode('grid')} />

  return (
    <div className="deckpage">
      <header className="deckpage-bar">
        <Link to="/" className="ghost-link mono">
          ← library
        </Link>
        <h1>{deck.title}</h1>
        <div className="deckpage-bar-right">
          <span className={`mono status-chip status-${deck.status}`}>{deck.status}</span>
          {anyDone && (
            <button onClick={() => setMode('present')} title="← → to navigate, F for fullscreen, Esc to come back">
              Present
            </button>
          )}
          {anyDone && (
            <span className="export-menu">
              <button onClick={() => setExportOpen((v) => !v)}>
                {exporting ? `Exporting ${exporting}…` : 'Export ▾'}
              </button>
              {exportOpen && !exporting && (
                <span className="export-pop">
                  {(['pptx', 'pdf', 'zip'] as ExportFormat[]).map((fmt) => (
                    <button
                      key={fmt}
                      className="ghost"
                      onClick={async () => {
                        if (!id) return
                        setExporting(fmt)
                        setActionError(null)
                        try {
                          const { download_url } = await exportDeck(id, fmt, notDone > 0)
                          window.location.assign(download_url)
                        } catch (e) {
                          setActionError(e instanceof Error ? e.message : String(e))
                        } finally {
                          setExporting(null)
                          setExportOpen(false)
                        }
                      }}
                    >
                      {fmt.toUpperCase()}
                      {notDone > 0 && ' (painted only)'}
                    </button>
                  ))}
                </span>
              )}
            </span>
          )}
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

function Presenter({ deck, onExit }: { deck: Deck; onExit: () => void }) {
  const [i, setI] = useState(0)
  const slides = deck.slides
  const slide = slides[i]

  const step = useCallback(
    (delta: number) =>
      setI((v) => Math.max(0, Math.min(slides.length - 1, v + delta))),
    [slides.length],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') step(1)
      else if (e.key === 'ArrowLeft') step(-1)
      else if (e.key === 'f' || e.key === 'F') {
        if (document.fullscreenElement) void document.exitFullscreen()
        else void document.documentElement.requestFullscreen()
      } else if (e.key === 'Escape') {
        // in fullscreen the browser consumes Esc to exit fullscreen first
        if (!document.fullscreenElement) onExit()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step, onExit])

  // preload the neighbors so ←/→ never flashes
  useEffect(() => {
    for (const j of [i - 1, i + 1]) {
      const s = slides[j]
      if (s?.render?.status === 'done') {
        const img = new Image()
        img.src = slideImageUrl(deck.id, s.n, s.render.rendered_at)
      }
    }
  }, [i, slides, deck.id])

  return (
    <div className="presenter">
      <div className="presenter-stage">
        {slide.render?.status === 'done' && slide.render.image ? (
          <img
            src={slideImageUrl(deck.id, slide.n, slide.render.rendered_at)}
            alt={slide.title}
          />
        ) : (
          <div className="presenter-unpainted">
            <span className="mono">unpainted</span>
            <strong>{slide.title}</strong>
          </div>
        )}
        <div className="presenter-zone presenter-zone-left" onClick={() => step(-1)} />
        <div className="presenter-zone presenter-zone-right" onClick={() => step(1)} />
      </div>
      <button className="ghost presenter-exit mono" onClick={onExit} title="Esc">
        ✕ grid
      </button>
      <span className="mono presenter-counter">
        {String(i + 1).padStart(2, '0')} / {String(slides.length).padStart(2, '0')}
      </span>
      <div className="presenter-filmstrip">
        {slides.map((s, j) => (
          <button
            key={s.n}
            className={`presenter-thumb${j === i ? ' current' : ''}`}
            onClick={() => setI(j)}
            title={s.title}
          >
            {s.render?.status === 'done' && s.render.image ? (
              <img src={slideImageUrl(deck.id, s.n, s.render.rendered_at)} alt="" loading="lazy" />
            ) : (
              <span className="mono">{s.n}</span>
            )}
          </button>
        ))}
      </div>
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
