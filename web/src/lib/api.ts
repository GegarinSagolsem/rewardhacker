import type { Me, Member, Org, Role, Run, RunDetail, RunStatus, Task, TraceDoc, User } from './types'

const TOKEN_KEY = 'rh-token'

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string | null) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token)
      else localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* private mode: token lives only in memory for this tab */
    }
  },
}

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Called on any 401 so the app can drop the session. Set by the auth provider. */
let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

function messageFrom(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0] as { msg?: string; loc?: unknown[] }
      const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : ''
      return field && first.msg ? `${field}: ${first.msg}` : (first.msg ?? fallback)
    }
  }
  return fallback
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  let res: Response
  try {
    res = await fetch(path, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the API. Is `rh serve` running?')
  }
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized()
    throw new ApiError(res.status, messageFrom(body, `${res.status} ${res.statusText}`))
  }
  return body as T
}

const json = (data: unknown) => JSON.stringify(data)

export const api = {
  register: (email: string, password: string) =>
    request<User>('/api/auth/register', { method: 'POST', body: json({ email, password }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>('/api/auth/login', { method: 'POST', body: json({ email, password }) }),
  me: () => request<Me>('/api/auth/me'),

  createOrg: (name: string) => request<Org>('/api/orgs', { method: 'POST', body: json({ name }) }),
  members: (org: string) => request<Member[]>(`/api/orgs/${org}/members`),
  addMember: (org: string, email: string, role: Role) =>
    request<Member>(`/api/orgs/${org}/members`, { method: 'POST', body: json({ email, role }) }),
  updateMember: (org: string, userId: string, role: Role) =>
    request<Member>(`/api/orgs/${org}/members/${userId}`, { method: 'PATCH', body: json({ role }) }),
  removeMember: (org: string, userId: string) =>
    request<void>(`/api/orgs/${org}/members/${userId}`, { method: 'DELETE' }),

  tasks: (org: string) => request<Task[]>(`/api/orgs/${org}/tasks?limit=200`),
  task: (org: string, id: string) => request<Task>(`/api/orgs/${org}/tasks/${id}`),
  uploadTask: (org: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Task>(`/api/orgs/${org}/tasks`, { method: 'POST', body: form })
  },

  runs: (org: string, opts: { taskId?: string; status?: RunStatus } = {}) => {
    const q = new URLSearchParams({ limit: '200' })
    if (opts.taskId) q.set('task_id', opts.taskId)
    if (opts.status) q.set('status', opts.status)
    return request<Run[]>(`/api/orgs/${org}/runs?${q}`)
  },
  run: (org: string, id: string) => request<RunDetail>(`/api/orgs/${org}/runs/${id}`),
  traces: (org: string, id: string) => request<TraceDoc[]>(`/api/orgs/${org}/runs/${id}/traces`),
  startRun: (org: string, taskId: string, includeLlm: boolean) =>
    request<Run>(`/api/orgs/${org}/tasks/${taskId}/runs`, {
      method: 'POST',
      body: json({ include_llm: includeLlm }),
    }),
}
