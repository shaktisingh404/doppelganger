import { useState } from 'react'
import { deleteTool } from '../api'
import { useConfirm } from './ConfirmDialog'
import { useToast } from './Toast'
import { ToolActivationForm } from './ToolActivationForm'
import type { ActivatedTool, AssembledPersona, ToolDefinition } from '../types'

interface Props {
  tool: ActivatedTool
  personas: AssembledPersona[]
  catalog: ToolDefinition[]
  onUpdated: (tool: ActivatedTool) => void
  onDeleted: (toolInstanceId: string) => void
}

export function ToolInstanceView({ tool, personas, catalog, onUpdated, onDeleted }: Props) {
  const confirm = useConfirm()
  const showToast = useToast()
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const personaName = (personaId: string) => personas.find((p) => p.persona_id === personaId)?.name ?? '(deleted)'
  const attachedTo = personas.filter((p) => p.tool_instance_ids.includes(tool.tool_instance_id))
  const definition = catalog.find((d) => d.id === tool.tool_id)

  async function handleDelete() {
    const message =
      attachedTo.length > 0
        ? `"${tool.name}" is attached to ${attachedTo.map((p) => p.name).join(', ')}. Deleting it will disconnect it from ${attachedTo.length === 1 ? 'that assistant' : 'those assistants'}.`
        : `Delete "${tool.name}"? This can't be undone.`
    if (!(await confirm({ message, confirmLabel: 'Delete', danger: true }))) return

    setDeleting(true)
    try {
      await deleteTool(tool.tool_instance_id)
      onDeleted(tool.tool_instance_id)
    } catch (err) {
      showToast(String(err))
      setDeleting(false)
    }
  }

  if (editing && definition) {
    return (
      <ToolActivationForm
        definition={definition}
        personas={personas}
        existing={tool}
        onSaved={(updated) => {
          onUpdated(updated)
          setEditing(false)
        }}
        onCancel={() => setEditing(false)}
      />
    )
  }

  return (
    <div className="persona-view">
      <div className="persona-header">
        <div>
          <h2>{tool.name}</h2>
          <p className="muted">tool: {tool.tool_id}</p>
        </div>
        <div className="editor-top-actions">
          <button type="button" className="link-button" onClick={() => setEditing(true)} disabled={!definition}>
            Edit
          </button>
          <button type="button" className="link-button danger" onClick={handleDelete} disabled={deleting}>
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {tool.destinations.length > 0 && (
        <dl className="tool-config-list">
          {tool.destinations.map((d, i) => (
            <div key={i} className="tool-config-row">
              <dt className="muted">{personaName(d.persona_id)}</dt>
              <dd>{d.description}</dd>
            </div>
          ))}
        </dl>
      )}

      {Object.keys(tool.config).length > 0 && (
        <dl className="tool-config-list">
          {Object.entries(tool.config).map(([key, value]) => (
            <div key={key} className="tool-config-row">
              <dt className="muted">{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      <p className="muted">Attach this tool to an assistant from its editor's Tools section to put it to use.</p>
    </div>
  )
}
