import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  createConversation,
  createProject,
  deleteConversation,
  deleteProject,
  listConversations,
  listProjects,
} from '../lib/chalkApi'
import type { ChalkConversation, ChalkProject } from '../lib/chalkApi'
import ProjectEditor from '../components/ProjectEditor'
import ChatPane from '../components/ChatPane'
import './ChalkPage.css'

export default function ChalkPage() {
  const [projects, setProjects] = useState<ChalkProject[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<ChalkConversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState<string | null>(null)

  const activeProject = projects?.find((p) => p.id === activeProjectId) ?? null
  const activeConversation =
    conversations.find((c) => c.id === activeConversationId) ?? null

  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e))

  useEffect(() => {
    listProjects().then(setProjects, fail)
  }, [])

  const openProject = useCallback((projectId: string) => {
    setActiveProjectId(projectId)
    setActiveConversationId(null)
    setEditorOpen(false)
    listConversations(projectId).then(
      (convs) => {
        setConversations(convs)
        if (convs.length > 0) setActiveConversationId(convs[0].id)
        else setEditorOpen(true) // fresh project — start with its instructions
      },
      fail,
    )
  }, [])

  async function addProject(name: string) {
    try {
      const project = await createProject(name)
      setProjects((prev) => [project, ...(prev ?? [])])
      setNewProjectName(null)
      openProject(project.id)
    } catch (e) {
      fail(e)
    }
  }

  async function addConversation() {
    if (!activeProjectId) return
    try {
      const conv = await createConversation(activeProjectId)
      setConversations((prev) => [conv, ...prev])
      setActiveConversationId(conv.id)
      setEditorOpen(false)
    } catch (e) {
      fail(e)
    }
  }

  const replaceConversation = (updated: ChalkConversation) =>
    setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))

  return (
    <div className="chalk">
      <header className="chalk-bar">
        <Link to="/" className="wordmark">
          Chalk<span className="ember">.</span>
        </Link>
        <nav className="chalk-tabs mono">
          <Link to="/" className="chalk-tab">
            decks
          </Link>
          <span className="chalk-tab current">chat</span>
        </nav>
      </header>

      <div className="chalk-body">
        <aside className="chalk-sidebar">
          <div className="chalk-sidebar-head">
            <span className="mono">projects</span>
            <button className="ghost" onClick={() => setNewProjectName('')}>
              + new
            </button>
          </div>
          {newProjectName !== null && (
            <input
              className="chalk-newproject"
              autoFocus
              placeholder="e.g. Bio – Cells Unit"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newProjectName.trim()) addProject(newProjectName.trim())
                if (e.key === 'Escape') setNewProjectName(null)
              }}
              onBlur={() => setNewProjectName(null)}
            />
          )}
          {projects === null && !error && <div className="chalk-side-note mono">loading…</div>}
          {projects?.length === 0 && newProjectName === null && (
            <div className="chalk-side-note">
              No projects yet — make one for a unit or a prep.
            </div>
          )}
          {projects?.map((p) => (
            <div key={p.id} className={`chalk-project${p.id === activeProjectId ? ' current' : ''}`}>
              <button className="chalk-project-name" onClick={() => openProject(p.id)}>
                {p.name}
              </button>
              {p.id === activeProjectId && (
                <>
                  <div className="chalk-project-tools">
                    <button className="ghost" onClick={() => setEditorOpen((v) => !v)}>
                      {editorOpen ? 'close instructions' : 'instructions'}
                    </button>
                    <button className="ghost" onClick={addConversation}>
                      + chat
                    </button>
                    <button
                      className="ghost danger"
                      onClick={() => {
                        if (!window.confirm(`Delete project "${p.name}" and its chats?`)) return
                        deleteProject(p.id).then(() => {
                          setProjects((prev) => (prev ?? []).filter((x) => x.id !== p.id))
                          setActiveProjectId(null)
                          setConversations([])
                          setActiveConversationId(null)
                        }, fail)
                      }}
                    >
                      delete
                    </button>
                  </div>
                  {conversations.map((c) => (
                    <div
                      key={c.id}
                      className={`chalk-conversation${c.id === activeConversationId ? ' current' : ''}`}
                    >
                      <button
                        className="chalk-conversation-title"
                        onClick={() => {
                          setActiveConversationId(c.id)
                          setEditorOpen(false)
                        }}
                        title={c.title}
                      >
                        {c.title}
                      </button>
                      {c.id === activeConversationId && (
                        <button
                          className="ghost danger chalk-conv-delete"
                          onClick={() => {
                            if (!window.confirm(`Delete "${c.title}"?`)) return
                            deleteConversation(c.id).then(() => {
                              setConversations((prev) => prev.filter((x) => x.id !== c.id))
                              setActiveConversationId(null)
                            }, fail)
                          }}
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                </>
              )}
            </div>
          ))}
        </aside>

        <main className="chalk-main">
          {error && <div className="state-note error">{error}</div>}
          {!activeProject && !error && (
            <div className="state-note">
              <h2>Chalk</h2>
              <p>
                A project holds your instructions and pasted knowledge; chats live inside it.
                Pick a project on the left, or make one.
              </p>
            </div>
          )}
          {activeProject && editorOpen && (
            <ProjectEditor
              key={activeProject.id}
              project={activeProject}
              onSaved={(p) =>
                setProjects((prev) => (prev ?? []).map((x) => (x.id === p.id ? p : x)))
              }
            />
          )}
          {activeProject && !editorOpen && !activeConversation && (
            <div className="state-note">
              <p>No chat open in {activeProject.name}.</p>
              <button className="primary" onClick={addConversation}>
                Start a chat
              </button>
            </div>
          )}
          {activeProject && !editorOpen && activeConversation && (
            <ChatPane
              key={activeConversation.id}
              project={activeProject}
              conversation={activeConversation}
              onConversationChange={replaceConversation}
            />
          )}
        </main>
      </div>
    </div>
  )
}
