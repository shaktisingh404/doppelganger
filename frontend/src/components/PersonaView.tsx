import { useState } from 'react'
import { updatePersonaTools } from '../api'
import type { ActivatedTool, AssembledPersona } from '../types'

interface Props {
  persona: AssembledPersona
  activatedTools: ActivatedTool[]
  onToolsUpdated: (persona: AssembledPersona) => void
}

export function PersonaView({ persona, activatedTools, onToolsUpdated }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [editingTools, setEditingTools] = useState(false)
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>(persona.tool_instance_ids)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      onToolsUpdated(updated)
      setEditingTools(false)
    } catch (err) {
      setError(String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="persona-view">
      <div className="persona-header">
        <div>
          <h2>{persona.name}</h2>
          <p className="muted">archetype: {persona.archetype_id ?? 'custom'}</p>
        </div>
        <button type="button" className="link-button" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Hide system prompt' : 'Show system prompt'}
        </button>
      </div>
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
