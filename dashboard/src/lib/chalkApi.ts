// Chalk (chat tab) API wrappers — same request idiom as api.ts, the only
// other fetch site being lib/sse.ts for the stream itself.
// Framework-free on purpose — no React imports (Sacred Invariant 5 /
// Chalk divergence rule 4).

import { request } from './api'

export interface ChalkProject {
  id: string
  name: string
  instructions: string
  context: string
  created_at: string
  updated_at: string
}

export interface ChalkConversation {
  id: string
  project_id: string
  title: string
  model: string
  created_at: string
  updated_at: string
}

export interface ChalkMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export function chalkHealth(): Promise<{ ok: boolean; default_model: string }> {
  return request('/api/chalk/health')
}

export async function listProjects(): Promise<ChalkProject[]> {
  const body = await request<{ projects: ChalkProject[] }>('/api/chalk/projects')
  return body.projects
}

export function createProject(name: string): Promise<ChalkProject> {
  return request('/api/chalk/projects', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function patchProject(
  id: string,
  patch: Partial<Pick<ChalkProject, 'name' | 'instructions' | 'context'>>,
): Promise<ChalkProject> {
  return request(`/api/chalk/projects/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export function deleteProject(id: string): Promise<{ ok: boolean }> {
  return request(`/api/chalk/projects/${id}`, { method: 'DELETE' })
}

export async function listConversations(projectId: string): Promise<ChalkConversation[]> {
  const body = await request<{ conversations: ChalkConversation[] }>(
    `/api/chalk/projects/${projectId}/conversations`,
  )
  return body.conversations
}

export function createConversation(projectId: string): Promise<ChalkConversation> {
  return request('/api/chalk/conversations', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId }),
  })
}

export function patchConversation(
  id: string,
  patch: Partial<Pick<ChalkConversation, 'title' | 'model'>>,
): Promise<ChalkConversation> {
  return request(`/api/chalk/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export function deleteConversation(id: string): Promise<{ ok: boolean }> {
  return request(`/api/chalk/conversations/${id}`, { method: 'DELETE' })
}

export async function listMessages(conversationId: string): Promise<ChalkMessage[]> {
  const body = await request<{ messages: ChalkMessage[] }>(
    `/api/chalk/conversations/${conversationId}/messages`,
  )
  return body.messages
}

/** Build a clean markdown transcript for export. Pure. */
export function transcriptMarkdown(
  project: ChalkProject,
  conversation: ChalkConversation,
  messages: ChalkMessage[],
): string {
  const lines = [
    `# ${conversation.title}`,
    '',
    `*Project: ${project.name} · ${conversation.model} · exported ${new Date().toISOString().slice(0, 10)}*`,
    '',
  ]
  for (const m of messages) {
    lines.push(m.role === 'user' ? '## You' : '## Assistant', '', m.content, '')
  }
  return lines.join('\n')
}
