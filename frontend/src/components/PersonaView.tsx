import { useState } from 'react'
import { deletePersona, updatePersona, updatePersonaTools } from '../api'
import type { ActivatedTool, AssembledPersona } from '../types'

interface Props {
  persona: AssembledPersona
  activatedTools: ActivatedTool[]
  onUpdated: (persona: AssembledPersona) => void
  onDeleted: (personaId: string) => void
}

export function PersonaView({ persona, activatedTools, onUpdated, onDeleted }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [editingTools, setEditingTools] = useState(false)
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>(persona.tool_instance_ids)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  const [editingPersona, setEditingPersona] = useState(false)
  const [editName, setEditName] = useState(persona.name)
  const [editFirstMessage, setEditFirstMessage] = useState(persona.first_message)
  const [editSystemPrompt, setEditSystemPrompt] = useState(persona.system_prompt)
  const [savingPersona, setSavingPersona] = useState(false)
  const [personaError, setPersonaError] = useState<string | null>(null)

  const attachedTools = activatedTools.filter((t) => persona.tool_instance_ids.includes(t.tool_instance_id))

  function startEditing() {
    setSelectedToolIds(persona.tool_instance_ids)
    setEditingTools(true)
    setError(null)
  }

  function toggleTool(toolInstanceId: string) {
    setSelectedToolIds((prev) =>
      prev.includes(toolInstanceId) ? prev.filter((id) => id !== toolInstanceId) : [...prev, toolInstanceId]
    )
  }

  async function saveTools() {
    setSaving(true)
    setError(null)
    try {
      const updated = await updatePersonaTools(persona.persona_id, { tool_instance_ids: selectedToolIds })
      onUpdated(updated)
      setEditingTools(false)
    } catch (err) {
      setError(String(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete "${persona.name}"? This can't be undone.`)) return
    setDeleting(true)
    setError(null)
    try {
      await deletePersona(persona.persona_id)
      onDeleted(persona.persona_id)
    } catch (err) {
      setError(String(err))
      setDeleting(false)
    }
  }

  function startEditingPersona() {
    setEditName(persona.name)
    setEditFirstMessage(persona.first_message)
    setEditSystemPrompt(persona.system_prompt)
    setPersonaError(null)
    setEditingPersona(true)
  }

  async function savePersona(e: React.FormEvent) {
    e.preventDefault()
    setSavingPersona(true)
    setPersonaError(null)
    try {
      const updated = await updatePersona(persona.persona_id, {
        name: editName,
        system_prompt: editSystemPrompt,
        first_message: editFirstMessage,
      })
      onUpdated(updated)
      setEditingPersona(false)
    } catch (err) {
      setPersonaError(String(err))
    } finally {
      setSavingPersona(false)
    }
  }

  if (editingPersona) {
    return (
      <form className="editor" onSubmit={savePersona}>
        <div className="editor-top-row">
          <input
            className="editor-name-input"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            required
            placeholder="Assistant name"
          />
          <div className="editor-top-actions">
            <button type="button" className="link-button" onClick={() => setEditingPersona(false)}>
              Cancel
            </button>
            <button type="submit" className="primary" disabled={savingPersona || !editSystemPrompt.trim()}>
              {savingPersona ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>

        <label>
          First Message <span className="muted">(assistant speaks first — optional)</span>
          <textarea value={editFirstMessage} onChange={(e) => setEditFirstMessage(e.target.value)} rows={2} />
        </label>

        <label>
          System Prompt
          <textarea
            className="system-prompt-input"
            value={editSystemPrompt}
            onChange={(e) => setEditSystemPrompt(e.target.value)}
            rows={14}
            required
          />
        </label>

        {personaError && <p className="error">{personaError}</p>}
      </form>
    )
  }

  return (
    <div className="persona-view">
      <div className="persona-header">
        <div>
          <h2>{persona.name}</h2>
          <p className="muted">archetype: {persona.archetype_id ?? 'custom'}</p>
        </div>
        <div className="editor-top-actions">
          <button type="button" className="link-button" onClick={() => setExpanded((v) => !v)}>
            {expanded ? 'Hide system prompt' : 'Show system prompt'}
          </button>
          <button type="button" className="link-button" onClick={startEditingPersona}>
            Edit
          </button>
          <button type="button" className="link-button" onClick={handleDelete} disabled={deleting}>
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
      {error && !editingTools && <p className="error">{error}</p>}
      {persona.first_message && (
        <p className="persona-first-message">
          <span className="muted">First message:</span> {persona.first_message}
        </p>
      )}

      {!editingTools && (
        <p className="persona-first-message">
          <span className="muted">Tools:</span> {attachedTools.length > 0 ? attachedTools.map((t) => t.name).join(', ') : 'none'}{' '}
          <button type="button" className="link-button inline-link-button" onClick={startEditing}>
            Edit
          </button>
        </p>
      )}

      {editingTools && (
        <div className="tools-section persona-tools-edit">
          <div className="field-label-row-static">Tools</div>
          {activatedTools.length === 0 ? (
            <p className="muted">No tools activated yet — activate one from the Tools section in the sidebar.</p>
          ) : (
            <div className="tool-checkbox-list">
              {activatedTools.map((t) => (
                <label key={t.tool_instance_id} className="checkbox-row tool-checkbox-row">
                  <input
                    type="checkbox"
                    checked={selectedToolIds.includes(t.tool_instance_id)}
                    onChange={() => toggleTool(t.tool_instance_id)}
                  />
                  {t.name} <span className="muted">({t.tool_id})</span>
                </label>
              ))}
            </div>
          )}
          {error && <p className="error">{error}</p>}
          <div className="editor-top-actions">
            <button type="button" className="link-button" onClick={() => setEditingTools(false)}>
              Cancel
            </button>
            <button type="button" className="primary" onClick={saveTools} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}

      {expanded && <pre className="system-prompt">{persona.system_prompt}</pre>}
    </div>
  )
}
