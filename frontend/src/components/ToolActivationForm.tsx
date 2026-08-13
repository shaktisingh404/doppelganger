import { useState } from 'react'
import { activateTool } from '../api'
import type { ActivatedTool, AssembledPersona, HandoffDestination, ToolDefinition } from '../types'

interface Props {
  definition: ToolDefinition
  personas: AssembledPersona[]
  onActivated: (tool: ActivatedTool) => void
  onCancel: () => void
}

const EMPTY_DESTINATION: HandoffDestination = { persona_id: '', description: '' }

export function ToolActivationForm({ definition, personas, onActivated, onCancel }: Props) {
  const [name, setName] = useState(definition.display_name)
  const [config, setConfig] = useState<Record<string, string>>({})
  const [destinations, setDestinations] = useState<HandoffDestination[]>([{ ...EMPTY_DESTINATION }])
  const [activating, setActivating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isHandoff = definition.id === 'handoff'

  const missingRequired = isHandoff
    ? destinations.some((d) => !d.persona_id || !d.description.trim())
    : definition.config_fields.some((f) => f.required && !config[f.key]?.trim())

  function updateDestination(index: number, patch: Partial<HandoffDestination>) {
    setDestinations((prev) => prev.map((d, i) => (i === index ? { ...d, ...patch } : d)))
  }

  function removeDestination(index: number) {
    setDestinations((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setActivating(true)
    setError(null)
    try {
      const tool = await activateTool(
        isHandoff
          ? { tool_id: definition.id, name, destinations }
          : { tool_id: definition.id, name, config }
      )
      onActivated(tool)
    } catch (err) {
      setError(String(err))
    } finally {
      setActivating(false)
    }
  }

  return (
    <form className="editor" onSubmit={handleSubmit}>
      <div className="editor-top-row">
        <input
          className="editor-name-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          placeholder="Tool name"
        />
        <div className="editor-top-actions">
          <button type="button" className="link-button" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={activating || missingRequired}>
            {activating ? 'Activating…' : 'Activate'}
          </button>
        </div>
      </div>

      <p className="muted">{definition.description}</p>

      {isHandoff ? (
        <div className="destinations-section">
          <div className="field-label-row-static">Destinations</div>
          {personas.length === 0 && (
            <p className="muted">You need at least one other assistant created before you can route to it.</p>
          )}
          {destinations.map((dest, i) => (
            <div key={i} className="destination-row">
              <select
                value={dest.persona_id}
                onChange={(e) => updateDestination(i, { persona_id: e.target.value })}
                required
              >
                <option value="" disabled>
                  Select an assistant
                </option>
                {personas.map((p) => (
                  <option key={p.persona_id} value={p.persona_id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <textarea
                value={dest.description}
                onChange={(e) => updateDestination(i, { description: e.target.value })}
                rows={2}
                required
                placeholder="When should the model hand off to this assistant?"
              />
              {destinations.length > 1 && (
                <button
                  type="button"
                  className="link-button destination-remove"
                  onClick={() => removeDestination(i)}
                >
                  Remove
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            className="generate-btn"
            onClick={() => setDestinations((prev) => [...prev, { ...EMPTY_DESTINATION }])}
          >
            + Add Destination
          </button>
        </div>
      ) : (
        definition.config_fields.map((field) => (
          <label key={field.key}>
            {field.label} {!field.required && <span className="muted">(optional)</span>}
            {field.multiline ? (
              <textarea
                value={config[field.key] ?? ''}
                onChange={(e) => setConfig((prev) => ({ ...prev, [field.key]: e.target.value }))}
                rows={3}
                required={field.required}
                placeholder={field.placeholder ?? undefined}
              />
            ) : (
              <input
                value={config[field.key] ?? ''}
                onChange={(e) => setConfig((prev) => ({ ...prev, [field.key]: e.target.value }))}
                required={field.required}
                placeholder={field.placeholder ?? undefined}
              />
            )}
          </label>
        ))
      )}

      {error && <p className="error">{error}</p>}
    </form>
  )
}
