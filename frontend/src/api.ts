import type {
  ActivatedTool,
  ActivateToolRequest,
  ArchetypeSpec,
  AssembledPersona,
  AuthToken,
  ChatMessage,
  CreatePersonaRequest,
  GeneratePromptResponse,
  InstanceInput,
  ToolDefinition,
  UpdatePersonaToolsRequest,
  UserPublic,
} from './types'

const BASE = '/api'
const TOKEN_KEY = 'doppelganger_token'

let authToken: string | null = localStorage.getItem(TOKEN_KEY)

export function setAuthToken(token: string | null) {
  authToken = token
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function getAuthToken(): string | null {
  return authToken
}

// Set by App on mount so a 401 from any call (token expired, revoked) drops
// the user back to the login screen instead of surfacing as a fetch error.
export let onUnauthorized: (() => void) | null = null
export function setOnUnauthorized(handler: (() => void) | null) {
  onUnauthorized = handler
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (authToken) headers.Authorization = `Bearer ${authToken}`
  const res = await fetch(`${BASE}${path}`, { headers, ...options })
  if (res.status === 401) {
    onUnauthorized?.()
  }
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export function register(email: string, password: string): Promise<AuthToken> {
  return request('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export function login(email: string, password: string): Promise<AuthToken> {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export function getMe(): Promise<UserPublic> {
  return request('/auth/me')
}

export function listArchetypes(): Promise<ArchetypeSpec[]> {
  return request('/archetypes')
}

export function listPersonas(): Promise<AssembledPersona[]> {
  return request('/personas')
}

export function generateSystemPrompt(input: InstanceInput): Promise<GeneratePromptResponse> {
  return request('/personas/generate', { method: 'POST', body: JSON.stringify(input) })
}

export function createPersona(input: CreatePersonaRequest): Promise<AssembledPersona> {
  return request('/personas', { method: 'POST', body: JSON.stringify(input) })
}

export function updatePersonaTools(personaId: string, input: UpdatePersonaToolsRequest): Promise<AssembledPersona> {
  return request(`/personas/${personaId}/tools`, { method: 'PUT', body: JSON.stringify(input) })
}

export function sendChatMessage(personaId: string, message: string): Promise<{ reply: string }> {
  return request(`/personas/${personaId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

export function getChatHistory(personaId: string): Promise<ChatMessage[]> {
  return request(`/personas/${personaId}/chat/history`)
}

export function listToolCatalog(): Promise<ToolDefinition[]> {
  return request('/tools/catalog')
}

export function listActivatedTools(): Promise<ActivatedTool[]> {
  return request('/tools')
}

export function activateTool(input: ActivateToolRequest): Promise<ActivatedTool> {
  return request('/tools', { method: 'POST', body: JSON.stringify(input) })
}
