// SSE-over-POST reader — EventSource can't POST, so we read the stream off
// a fetch response body. Framework-free on purpose — no React imports
// (Chalk divergence rule 4).

export interface ChatDone {
  message_id: string | null
  input_tokens: number
  output_tokens: number
}

export interface ChatStreamError {
  status: number
  message: string
}

export interface StreamHandlers {
  onDelta: (text: string) => void
  onDone: (payload: ChatDone) => void
  onError: (payload: ChatStreamError) => void
}

/** POST `body` to `url` and dispatch the delta/done/error SSE protocol.
 * Resolves when the stream closes; abort via the signal keeps partials. */
export async function streamSse(
  url: string,
  body: unknown,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    handlers.onError({ status: 0, message: 'Lantern service unreachable — is it running?' })
    return
  }
  if (!res.ok || !res.body) {
    let message = res.statusText
    try {
      const parsed = await res.json()
      if (typeof parsed?.detail === 'string') message = parsed.detail
    } catch {
      /* keep statusText */
    }
    handlers.onError({ status: res.status, message })
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        dispatch(frame, handlers)
      }
    }
  } catch (e) {
    if ((e as Error).name !== 'AbortError') {
      handlers.onError({ status: 0, message: 'stream interrupted — partial reply kept' })
    }
  }
}

function dispatch(frame: string, handlers: StreamHandlers): void {
  let event = 'message'
  const data: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trim())
  }
  if (!data.length) return
  let payload: unknown
  try {
    payload = JSON.parse(data.join('\n'))
  } catch {
    return
  }
  if (event === 'delta') handlers.onDelta((payload as { text: string }).text ?? '')
  else if (event === 'done') handlers.onDone(payload as ChatDone)
  else if (event === 'error') handlers.onError(payload as ChatStreamError)
}
