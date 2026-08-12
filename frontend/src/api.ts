import type { ArchetypeSpec, AssembledPersona, ChatMessage, InstanceInput } from './types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export function listArchetypes(): Promise<ArchetypeSpec[]> {
  return request('/archetypes')
}

export function createPersona(input: InstanceInput): Promise<AssembledPersona> {
  return request('/personas', { method: 'POST', body: JSON.stringify(input) })
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
