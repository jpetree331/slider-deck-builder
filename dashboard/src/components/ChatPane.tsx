import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { listMessages, patchConversation, transcriptMarkdown } from '../lib/chalkApi'
import type { ChalkConversation, ChalkMessage, ChalkProject } from '../lib/chalkApi'
import { streamSse } from '../lib/sse'
import { CHAT_MODELS } from '../config/models'
import './ChatPane.css'

export default function ChatPane({
  project,
  conversation,
  onConversationChange,
}: {
  project: ChalkProject
  conversation: ChalkConversation
  onConversationChange: (conversation: ChalkConversation) => void
}) {
  const [messages, setMessages] = useState<ChalkMessage[] | null>(null)
  const [draft, setDraft] = useState('')
  const [streamText, setStreamText] = useState<string | null>(null) // non-null while streaming
  const [toast, setToast] = useState<string | null>(null)
  const [lastFailed, setLastFailed] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)

  const reload = useCallback(
    () =>
      listMessages(conversation.id).then(setMessages, (e) =>
        setToast(e instanceof Error ? e.message : String(e)),
      ),
    [conversation.id],
  )

  useEffect(() => {
    reload()
  }, [reload])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, streamText])

  // abort a live stream when the pane unmounts (conversation switch)
  useEffect(() => () => abortRef.current?.abort(), [])

  async function send(content: string) {
    if (!content.trim() || streamText !== null) return
    setToast(null)
    setLastFailed(null)
    setDraft('')
    // optimistic user turn; the server persists it before streaming
    setMessages((prev) => [
      ...(prev ?? []),
      {
        id: `local-${Date.now()}`,
        conversation_id: conversation.id,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      },
    ])
    setStreamText('')
    if (conversation.title === 'New conversation') {
      patchConversation(conversation.id, { title: content.slice(0, 60) }).then(
        onConversationChange,
        () => {},
      )
    }
    const controller = new AbortController()
    abortRef.current = controller
    await streamSse(
      '/api/chalk/chat',
      { conversation_id: conversation.id, content },
      {
        onDelta: (text) => setStreamText((prev) => (prev ?? '') + text),
        onDone: () => {
          setStreamText(null)
          reload() // server truth, including the persisted assistant row
        },
        onError: ({ message }) => {
          setStreamText(null)
          setToast(message)
          setLastFailed(content)
          reload() // shows any persisted partial
        },
      },
      controller.signal,
    )
    // abort path: fetch resolves silently — fold in whatever the server kept
    if (controller.signal.aborted) {
      setStreamText(null)
      setTimeout(reload, 300)
    }
    composerRef.current?.focus()
  }

  function stop() {
    abortRef.current?.abort()
  }

  function exportTranscript() {
    if (!messages) return
    const md = transcriptMarkdown(project, conversation, messages)
    const blob = new Blob([md], { type: 'text/markdown' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${conversation.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'chat'}.md`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const model = CHAT_MODELS.find((m) => m.id === conversation.model)

  return (
    <div className="chat-pane">
      <div className="chat-head">
        <span className="chat-title" title={conversation.title}>
          {conversation.title}
        </span>
        <select
          className="chat-model"
          value={conversation.model}
          onChange={(e) =>
            patchConversation(conversation.id, { model: e.target.value }).then(
              onConversationChange,
              (err) => setToast(err instanceof Error ? err.message : String(err)),
            )
          }
          title={model?.note ?? ''}
        >
          {CHAT_MODELS.map((m) => (
            <option key={m.id} value={m.id} title={m.note}>
              {m.label}
            </option>
          ))}
        </select>
        <button className="ghost" onClick={exportTranscript} disabled={!messages?.length}>
          Export .md
        </button>
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        {messages === null && <div className="state-note">Opening the chat…</div>}
        {messages?.length === 0 && streamText === null && (
          <div className="state-note">
            <p>Ask anything — the project's instructions and knowledge ride along.</p>
          </div>
        )}
        {messages?.map((m) => <MessageBubble key={m.id} message={m} />)}
        {streamText !== null && (
          <div className="bubble assistant streaming">
            {streamText === '' ? (
              <span className="mono thinking">thinking…</span>
            ) : (
              <pre className="stream-raw">{streamText}</pre>
            )}
          </div>
        )}
      </div>

      {toast && (
        <div className="chat-toast">
          <span>{toast}</span>
          {lastFailed && (
            <button className="ghost" onClick={() => send(lastFailed)}>
              retry
            </button>
          )}
          <button className="ghost" onClick={() => setToast(null)}>
            ×
          </button>
        </div>
      )}

      <div className="chat-composer">
        <textarea
          ref={composerRef}
          rows={3}
          value={draft}
          placeholder="Enter to send · Shift+Enter for a new line · Esc stops a reply"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send(draft)
            } else if (e.key === 'Escape') {
              stop()
            }
          }}
          autoFocus
        />
        {streamText !== null ? (
          <button className="danger" onClick={stop}>
            Stop
          </button>
        ) : (
          <button className="primary" onClick={() => send(draft)} disabled={!draft.trim()}>
            Send
          </button>
        )}
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: ChalkMessage }) {
  const [copied, setCopied] = useState(false)
  if (message.role === 'user') {
    return <div className="bubble user">{message.content}</div>
  }
  return (
    <div className="bubble assistant">
      <div className="markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      </div>
      <button
        className="ghost copy-btn mono"
        onClick={() => {
          navigator.clipboard.writeText(message.content).then(() => {
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          })
        }}
      >
        {copied ? 'copied' : 'copy'}
      </button>
    </div>
  )
}
