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

// Injected verbatim into the prompt, same as BusinessInfo — see
// backend/compiler/assembly.py::_reference_files_section.
export interface ReferenceFile {
  filename: string
  content: string
}

export interface InstanceInput {
  archetype_id: string
  name: string
  language: string
  tone?: string | null
  description: string
  business_info?: BusinessInfo | null
  // How the persona should converse (pacing, formality, question style,
  // escalation) — distinct from `description`, which is what it knows.
  conversational_style?: string | null
  reference_files?: ReferenceFile[]
}

export interface AssembledPersona {
  persona_id: string
  archetype_id?: string | null
  name: string
  first_message: string
  system_prompt: string
  version: string
  created_at: string
  tool_instance_ids: string[]
  // Non-null means a public chat link is live for this persona — see
  // ShareLinkResponse / PublicPersonaInfo below.
  share_token?: string | null
}

// POST /personas/generate response — text only, nothing stored yet.
export interface GeneratePromptResponse {
  system_prompt: string
}

// POST /personas body — the (possibly hand-edited) result of generation,
// or hand-typed text, becoming a real persona.
export interface CreatePersonaRequest {
  name: string
  system_prompt: string
  first_message?: string
  archetype_id?: string | null
  tool_instance_ids?: string[]
}

export interface UpdatePersonaRequest {
  name: string
  system_prompt: string
  first_message?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// Mirrors backend/tools/models.py 1:1.

export interface ToolConfigField {
  key: string
  label: string
  placeholder?: string | null
  required: boolean
  multiline: boolean
}

export interface ToolDefinition {
  id: string
  display_name: string
  description: string
  category: string
  status: 'available' | 'coming_soon'
  config_fields: ToolConfigField[]
}

// One routable target for a handoff tool: an existing persona plus the
// description that tells the model when this destination fits.
export interface HandoffDestination {
  persona_id: string
  description: string
}

export interface ActivatedTool {
  tool_instance_id: string
  tool_id: string
  name: string
  config: Record<string, string>
  destinations: HandoffDestination[]
  created_at: string
}

export interface ActivateToolRequest {
  tool_id: string
  name: string
  config?: Record<string, string>
  destinations?: HandoffDestination[]
}

export interface UpdateToolRequest {
  name: string
  config?: Record<string, string>
  destinations?: HandoffDestination[]
}

export interface UpdatePersonaToolsRequest {
  tool_instance_ids: string[]
}

// Mirrors backend/auth/schemas.py 1:1.

export interface UserPublic {
  id: string
  email: string
  created_at: string
}

export interface AuthToken {
  access_token: string
  token_type: string
  user: UserPublic
}

// Mirrors the new share-link/public-chat shapes in backend/app/schemas.py.

export interface ShareLinkResponse {
  share_token: string
}

// What an anonymous visitor is allowed to know about a shared persona —
// deliberately just the name, nothing persona-internal.
export interface PublicPersonaInfo {
  name: string
}

export interface PublicSessionResponse {
  session_id: string
}
