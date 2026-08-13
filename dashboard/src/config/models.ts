// THE chat model list — the only place models are defined (Chalk divergence
// rule 5: components never branch on model id). The backend mirrors these ids
// in src/lantern/chalk_chat.py::ALLOWED_MODELS; verify_chalk.py checks the
// two stay in sync. To add a model: add a row here AND there.
//
// The gemini-*-latest ids are Google's tracking aliases — they follow the
// current fast/strongest text model without this file needing updates.

export interface ChatModel {
  id: string
  label: string
  provider: 'anthropic' | 'google'
  note: string
}

export const CHAT_MODELS: ChatModel[] = [
  {
    id: 'claude-haiku-4-5',
    label: 'Claude Haiku 4.5',
    provider: 'anthropic',
    note: 'default — fast, cheap, great for lesson planning',
  },
  {
    id: 'gemini-flash-latest',
    label: 'Gemini Flash (latest)',
    provider: 'google',
    note: "tracks Google's current fast model",
  },
  {
    id: 'gemini-pro-latest',
    label: 'Gemini Pro (latest)',
    provider: 'google',
    note: "tracks Google's strongest text model",
  },
]
