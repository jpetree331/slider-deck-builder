import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getDeck, patchDeck, renderDeck } from '../lib/api'
import type { SlidePatchPayload } from '../lib/api'
import { estimateDeckCost, formatUsd } from '../lib/cost'
import type { SlideSize, StyleGuide } from '../lib/types'
import './OutlinePage.css'

const LAYOUT_HINTS = ['title card', 'split', 'full-bleed diagram', 'big number', 'quote', 'closer']

interface EditSlide {
  origN: number | null // server-side position this slide claims; null = new
  title: string
  pointsText: string // newline-separated in the editor
  visual_description: string
  layout_hint: string
  hasRender: boolean
}

export default function OutlinePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [style, setStyle] = useState<StyleGuide | null>(null)
  const [slides, setSlides] = useState<EditSlide[]>([])
  const [size, setSize] = useState<SlideSize>('2K')
  const [isLoaded, setIsLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<'saved' | 'saving' | 'dirty'>('saved')
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!id) return
    getDeck(id).then(
      (deck) => {
        setTitle(deck.title)
        setStyle(deck.style_guide)
        setSize(deck.slide_size)
        setSlides(
          deck.slides.map((s) => ({
            origN: s.n,
            title: s.title,
            pointsText: s.points.join('\n'),
            visual_description: s.visual_description,
            layout_hint: s.layout_hint,
            hasRender: s.render?.status === 'done',
          })),
        )
        setIsLoaded(true)
      },
      (e) => setError(e instanceof Error ? e.message : String(e)),
    )
  }, [id])

  const save = useCallback(() => {
    if (!id || !style) return
    // painted-text fields can't be empty (the server 422s them anyway) —
    // hold the save until the user finishes; the Render button stays disabled
    if (
      !style.art_direction.trim() ||
      slides.some((s) => !s.title.trim() || !s.visual_description.trim())
    )
      return
    setSaveState('saving')
    const payload: SlidePatchPayload[] = slides.map((s) => ({
      n: s.origN,
      title: s.title,
      points: s.pointsText
        .split('\n')
        .map((p) => p.trim())
        .filter(Boolean)
        .slice(0, 4),
      visual_description: s.visual_description,
      layout_hint: s.layout_hint,
    }))
    patchDeck(id, { title, style_guide: style, slides: payload, slide_size: size }).then(
      (deck) => {
        // server renumbered contiguously in our order — refresh identities
        setSlides((prev) =>
          prev.map((s, i) => ({
            ...s,
            origN: i + 1,
            hasRender: deck.slides[i]?.render?.status === 'done',
          })),
        )
        setSaveState('saved')
      },
      (e) => {
        setError(e instanceof Error ? e.message : String(e))
        setSaveState('dirty')
      },
    )
  }, [id, title, style, slides, size])

  // debounced autosave, gated on isLoaded
  useEffect(() => {
    if (!isLoaded) return
    setSaveState('dirty')
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(save, 800)
    return () => window.clearTimeout(timer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, style, slides, size, isLoaded])

  const cost = useMemo(() => estimateDeckCost(slides.length, size), [slides.length, size])
  const incomplete =
    !!style &&
    (!style.art_direction.trim() ||
      slides.some((s) => !s.title.trim() || !s.visual_description.trim()))

  if (error && !isLoaded) return <div className="state-note error">{error}</div>
  if (!isLoaded || !style) return <div className="state-note">Fetching the outline…</div>

  const patchSlide = (i: number, patch: Partial<EditSlide>) =>
    setSlides((prev) => prev.map((s, j) => (j === i ? { ...s, ...patch } : s)))

  const move = (i: number, dir: -1 | 1) =>
    setSlides((prev) => {
      const j = i + dir
      if (j < 0 || j >= prev.length) return prev
      const next = [...prev]
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })

  return (
    <div className="outline">
      <div className="outline-head">
        <input
          className="outline-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          aria-label="Deck title"
        />
        <div className="outline-head-right">
          <span className="mono save-state">
            {incomplete && saveState !== 'saved'
              ? 'every slide needs a headline & picture'
              : saveState === 'saved'
                ? 'saved'
                : saveState === 'saving'
                  ? 'saving…'
                  : 'editing…'}
          </span>
          <button
            className="primary"
            disabled={saveState !== 'saved'}
            title={saveState !== 'saved' ? 'Waiting for autosave…' : 'Paints every slide, in order'}
            onClick={() => {
              if (!id) return
              renderDeck(id).then(
                () => navigate(`/decks/${id}`),
                (e) => setError(e instanceof Error ? e.message : String(e)),
              )
            }}
          >
            Render {slides.length} slides · ~{formatUsd(cost)}
          </button>
        </div>
      </div>
      {error && <div className="state-note error">{error}</div>}

      <section className="style-card">
        <h2>Style guide</h2>
        <div className="palette-row">
          {style.palette.map((c, i) => (
            <span className="palette-chip" key={i}>
              <input
                type="color"
                value={c}
                onChange={(e) =>
                  setStyle({
                    ...style,
                    palette: style.palette.map((p, j) => (j === i ? e.target.value : p)),
                  })
                }
              />
              <span className="mono">{c}</span>
              {style.palette.length > 3 && (
                <button
                  type="button"
                  className="ghost chip-remove"
                  onClick={() =>
                    setStyle({ ...style, palette: style.palette.filter((_, j) => j !== i) })
                  }
                >
                  ×
                </button>
              )}
            </span>
          ))}
          {style.palette.length < 5 && (
            <button
              type="button"
              className="ghost"
              onClick={() => setStyle({ ...style, palette: [...style.palette, '#888888'] })}
            >
              + color
            </button>
          )}
        </div>
        <div className="style-grid">
          <label>
            Typography
            <input
              value={style.typography}
              onChange={(e) => setStyle({ ...style, typography: e.target.value })}
            />
          </label>
          <label>
            Motif
            <input value={style.motif} onChange={(e) => setStyle({ ...style, motif: e.target.value })} />
          </label>
          <label>
            Tone
            <input value={style.tone} onChange={(e) => setStyle({ ...style, tone: e.target.value })} />
          </label>
          <label>
            Image size
            <select value={size} onChange={(e) => setSize(e.target.value as SlideSize)}>
              <option value="1K">1K — draft</option>
              <option value="2K">2K — default</option>
              <option value="4K">4K — print</option>
            </select>
          </label>
        </div>
        <label className="art-direction">
          Art direction <span className="hint">the deck's whole visual identity — every slide obeys this verbatim</span>
          <textarea
            rows={4}
            value={style.art_direction}
            onChange={(e) => setStyle({ ...style, art_direction: e.target.value })}
          />
        </label>
      </section>

      <section className="slides-list">
        {slides.map((s, i) => (
          <div className="slide-card" key={i}>
            <div className="slide-card-head">
              <span className="mono slide-n">{String(i + 1).padStart(2, '0')}</span>
              <input
                className="slide-title"
                value={s.title}
                placeholder="Headline — painted verbatim"
                onChange={(e) => patchSlide(i, { title: e.target.value })}
              />
              <select
                value={LAYOUT_HINTS.includes(s.layout_hint) ? s.layout_hint : ''}
                onChange={(e) => patchSlide(i, { layout_hint: e.target.value })}
              >
                {!LAYOUT_HINTS.includes(s.layout_hint) && <option value="">layout…</option>}
                {LAYOUT_HINTS.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
              <div className="slide-tools">
                <button type="button" className="ghost" onClick={() => move(i, -1)} disabled={i === 0}>
                  ↑
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => move(i, 1)}
                  disabled={i === slides.length - 1}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="ghost danger"
                  onClick={() => setSlides((prev) => prev.filter((_, j) => j !== i))}
                  disabled={slides.length <= 1}
                >
                  remove
                </button>
              </div>
            </div>
            {s.hasRender && (
              <div className="mono rendered-note">
                painted — editing the text clears the picture (it would no longer match)
              </div>
            )}
            <div className="slide-card-body">
              <label>
                Points <span className="hint">one per line, ≤4, painted verbatim</span>
                <textarea
                  rows={3}
                  value={s.pointsText}
                  onChange={(e) => patchSlide(i, { pointsText: e.target.value })}
                />
              </label>
              <label>
                The picture <span className="hint">subject, composition, focal point</span>
                <textarea
                  rows={3}
                  value={s.visual_description}
                  onChange={(e) => patchSlide(i, { visual_description: e.target.value })}
                />
              </label>
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            setSlides((prev) => [
              ...prev,
              { origN: null, title: '', pointsText: '', visual_description: '', layout_hint: 'split', hasRender: false },
            ])
          }
          disabled={slides.length >= 16}
        >
          + Add slide
        </button>
      </section>

      <div className="outline-foot mono">
        {slides.length} slides · estimated {formatUsd(cost)} at {size} ·{' '}
        <a onClick={() => navigate('/')} className="foot-link">
          back to library
        </a>
      </div>
    </div>
  )
}
