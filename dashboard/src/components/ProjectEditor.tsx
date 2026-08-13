import { useState } from 'react'
import { patchProject } from '../lib/chalkApi'
import type { ChalkProject } from '../lib/chalkApi'
import './ProjectEditor.css'

/** Project instructions + pasted knowledge. Auto-saves on blur. */
export default function ProjectEditor({
  project,
  onSaved,
}: {
  project: ChalkProject
  onSaved: (project: ChalkProject) => void
}) {
  const [name, setName] = useState(project.name)
  const [instructions, setInstructions] = useState(project.instructions)
  const [context, setContext] = useState(project.context)
  const [state, setState] = useState<'saved' | 'saving' | 'error'>('saved')

  function saveIfChanged() {
    const patch: Record<string, string> = {}
    if (name.trim() && name !== project.name) patch.name = name.trim()
    if (instructions !== project.instructions) patch.instructions = instructions
    if (context !== project.context) patch.context = context
    if (Object.keys(patch).length === 0) return
    setState('saving')
    patchProject(project.id, patch).then(
      (updated) => {
        onSaved(updated)
        setState('saved')
      },
      () => setState('error'),
    )
  }

  return (
    <div className="project-editor" onBlur={saveIfChanged}>
      <div className="project-editor-head">
        <input
          className="project-editor-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Project name"
        />
        <span className="mono save-state">
          {state === 'saving' ? 'saving…' : state === 'error' ? 'save failed — retry by clicking away' : 'saved'}
        </span>
      </div>
      <label>
        Instructions <span className="hint">the system prompt — how the assistant should behave in this project</span>
        <textarea
          rows={6}
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          placeholder="e.g. You are helping plan a 9th-grade biology unit. Keep answers practical, aligned to NGSS, and sized for 50-minute periods."
        />
      </label>
      <label>
        Project knowledge <span className="hint">pasted content every chat in this project can see</span>
        <textarea
          rows={12}
          value={context}
          onChange={(e) => setContext(e.target.value)}
          placeholder="Paste the syllabus section, pacing guide, lab list, anything…"
        />
      </label>
    </div>
  )
}
