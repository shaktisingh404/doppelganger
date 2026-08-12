// Mirrors backend/compiler/models.py 1:1 — keep field names/optionality in
// sync with the Pydantic models whenever the API contract changes.

export interface ArchetypeSpec {
  id: string
  display_name: string
  persona_text: string
  guardrail_additions: string[]
  tool_schema_stubs: Record<string, unknown>[]
}

export interface BusinessInfo {
  name: string
  address?: string | null
  phone?: string | null
  hours?: string | null
  services: string[]
  notes: string[]
}

export interface InstanceInput {
  archetype_id: string
  name: string
  language: string
  tone?: string | null
  description: string
  business_info?: BusinessInfo | null
}

export interface AssembledPersona {
  persona_id: string
  archetype_id: string
  name: string
  system_prompt: string
  version: string
  created_at: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
