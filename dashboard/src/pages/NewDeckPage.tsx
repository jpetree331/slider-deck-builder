import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createDeck } from '../lib/api'
import type { SlideSize } from '../lib/types'
import './NewDeckPage.css'

export default function NewDeckPage() {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [notes, setNotes] = useState('')
  const [slideCount, setSlideCount] = useState('')
  const [styleHints, setStyleHints] = useState('')
  const [size, setSize] = useState<SlideSize>('2K')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!topic.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      const deck = await createDeck({
        topic,
        source_notes: notes,
        slide_count: slideCount ? Number(slideCount) : null,
        style_hints: styleHints,
        slide_size: size,
      })
      navigate(`/decks/${deck.id}/outline`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setBusy(false)
    }
  }

  return (
    <form className="new-deck" onSubmit={submit}>
      <h1>New deck</h1>
      <p className="new-deck-lede">
        Say what the deck is about. Haiku sketches the outline and a style guide;
        you edit; then the painting starts.
      </p>

      <label>
        Topic
        <textarea
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. The cell membrane and transport, for 9th-grade biology"
          rows={3}
          autoFocus
          required
        />
      </label>

      <label>
        Source notes <span className="hint">optional — pasted content the outline should honor</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Paste lecture notes, a syllabus section, anything…"
          rows={6}
        />
      </label>

      <div className="new-deck-row">
        <label>
          Slides <span className="hint">blank = model decides (6–12)</span>
          <input
            type="number"
            min={1}
            max={16}
            value={slideCount}
            onChange={(e) => setSlideCount(e.target.value)}
            placeholder="auto"
          />
        </label>
        <label>
          Image size
          <select value={size} onChange={(e) => setSize(e.target.value as SlideSize)}>
            <option value="1K">1K — draft</option>
            <option value="2K">2K — default</option>
            <option value="4K">4K — print (≈2× cost)</option>
          </select>
        </label>
      </div>

      <label>
        Style hints <span className="hint">optional — nudge the art direction</span>
        <input
          value={styleHints}
          onChange={(e) => setStyleHints(e.target.value)}
          placeholder="e.g. cut-paper collage, warm museum lighting"
        />
      </label>

      {error && <div className="state-note error">{error}</div>}

      <button className="primary new-deck-submit" disabled={busy || !topic.trim()}>
        {busy ? 'Haiku is sketching the outline…' : 'Draft the outline'}
      </button>
    </form>
  )
}
