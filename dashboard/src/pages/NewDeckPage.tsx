import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createDeck, extractFile } from '../lib/api'
import type { AttachedImage } from '../lib/api'
import { DEFAULT_IMAGE_MODEL, IMAGE_MODELS } from '../config/imageModels'
import type { SlideSize } from '../lib/types'
import './NewDeckPage.css'

const MAX_ATTACHED_IMAGES = 8

export default function NewDeckPage() {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [notes, setNotes] = useState('')
  const [slideCount, setSlideCount] = useState('')
  const [styleHints, setStyleHints] = useState('')
  const [size, setSize] = useState<SlideSize>('2K')
  const [imageModel, setImageModel] = useState(DEFAULT_IMAGE_MODEL)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extracting, setExtracting] = useState<string | null>(null)
  const [attachError, setAttachError] = useState<string | null>(null)
  const [images, setImages] = useState<AttachedImage[]>([])
  const fileInput = useRef<HTMLInputElement>(null)

  async function attachFiles(files: FileList | null) {
    if (!files?.length) return
    setAttachError(null)
    for (const file of Array.from(files)) {
      setExtracting(file.name)
      try {
        const result = await extractFile(file)
        if (result.text) {
          setNotes((prev) =>
            `${prev.trimEnd()}${prev.trim() ? '\n\n' : ''}` +
            `--- Attached: ${result.filename} ---\n${result.text}`,
          )
        }
        if (result.images.length) {
          setImages((prev) => [...prev, ...result.images].slice(0, MAX_ATTACHED_IMAGES))
        }
      } catch (err) {
        // shown right beside the button — an attach failure must never just blink
        const message = err instanceof Error ? err.message : String(err)
        setAttachError(
          message === 'Not Found'
            ? 'the running service is older than this page — restart Lantern, then retry'
            : `${file.name}: ${message}`,
        )
      }
    }
    setExtracting(null)
    if (fileInput.current) fileInput.current.value = ''
  }

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
        image_model: imageModel,
        images: images.length ? images : undefined,
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
        Say what the deck is about. The outline model sketches the slides and a style
        guide; you edit; then the painting starts.
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
        Source notes{' '}
        <span className="hint">
          optional — paste or attach; e.g. attach last year's deck and ask for a revamp in the topic box
        </span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Paste lecture notes, a syllabus section, anything… or attach a file below"
          rows={8}
        />
        <span className="attach-row">
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.docx,.pptx"
            multiple
            hidden
            onChange={(e) => attachFiles(e.target.files)}
          />
          <button
            type="button"
            className="ghost"
            disabled={extracting !== null}
            onClick={() => fileInput.current?.click()}
          >
            {extracting ? `Reading ${extracting}…` : '📎 Attach PDF / DOCX / PPTX'}
          </button>
          {attachError ? (
            <span className="attach-error">{attachError}</span>
          ) : (
            <span className="hint">
              text lands right here to edit; the document's images ride along so the outline can
              see the original look — the file itself isn't kept
            </span>
          )}
        </span>
        {images.length > 0 && (
          <span className="image-chips">
            {images.map((img, i) => (
              <span className="image-chip" key={i} title={img.note}>
                <img src={`data:${img.media_type};base64,${img.data}`} alt={img.note} />
                <button
                  type="button"
                  className="ghost chip-x"
                  onClick={() => setImages((prev) => prev.filter((_, j) => j !== i))}
                >
                  ×
                </button>
              </span>
            ))}
            <span className="hint">
              {images.length} image{images.length > 1 ? 's' : ''} will be shown to the outline model
            </span>
          </span>
        )}
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
        <label>
          Painter
          <select value={imageModel} onChange={(e) => setImageModel(e.target.value)}>
            {IMAGE_MODELS.map((m) => (
              <option key={m.id} value={m.id} title={m.note}>
                {m.label}
              </option>
            ))}
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
        {busy ? 'Sketching the outline…' : 'Draft the outline'}
      </button>
    </form>
  )
}
