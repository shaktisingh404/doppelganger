import { useState } from 'react'
import { updatePersona } from '../api'
import type { ArchetypeSpec, AssembledPersona } from '../types'

interface Props {
  personas: AssembledPersona[]
  archetypes: ArchetypeSpec[]
  selectedId: string | null
  onSelect: (persona: AssembledPersona) => void
  onCreateFromArchetype: (archetype: ArchetypeSpec) => void
  onRenamed: (persona: AssembledPersona) => void
}

export function AssistantSidebar({
  personas,
  archetypes,
  selectedId,
  onSelect,
  onCreateFromArchetype,
  onRenamed,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [renameError, setRenameError] = useState<string | null>(null)

  function startRename(p: AssembledPersona) {
    setRenamingId(p.persona_id)
    setRenameValue(p.name)
    setRenameError(null)
  }

  async function commitRename(p: AssembledPersona) {
    const name = renameValue.trim()
    // No-op edits (blank, or unchanged) don't need a round trip.
    if (!name || name === p.name) {
      setRenamingId(null)
      return
    }
    try {
      const updated = await updatePersona(p.persona_id, {
        name,
        system_prompt: p.system_prompt,
        first_message: p.first_message,
      })
      onRenamed(updated)
      setRenamingId(null)
    } catch (err) {
      setRenameError(String(err))
    }
  }

  return (
    <>
      <div className="sidebar-header">
        <span>Assistants</span>
        <span className="muted">{personas.length}</span>
      </div>

      <div className="create-assistant">
        <button type="button" className="primary create-btn" onClick={() => setMenuOpen((v) => !v)}>
          + Create Assistant
        </button>
        {menuOpen && (
          <div className="create-menu">
            <div className="create-menu-label">Start from a prebuilt persona</div>
            {archetypes.map((a) => (
              <button
                key={a.id}
                type="button"
                className="create-menu-item"
                onClick={() => {
                  onCreateFromArchetype(a)
                  setMenuOpen(false)
                }}
              >
                <span className="create-menu-item-title">{a.display_name}</span>
                <span className="create-menu-item-sub">{a.id}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="assistant-list">
        {personas.length === 0 && <p className="muted sidebar-empty">No assistants yet.</p>}
        {personas.map((p) => (
          <div
            key={p.persona_id}
            className={`assistant-list-item${p.persona_id === selectedId ? ' selected' : ''}`}
          >
            {renamingId === p.persona_id ? (
              <input
                className="assistant-rename-input"
                autoFocus
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onBlur={() => commitRename(p)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commitRename(p)
                  if (e.key === 'Escape') setRenamingId(null)
                }}
              />
            ) : (
              <button type="button" className="assistant-list-item-select" onClick={() => onSelect(p)}>
                <span className="assistant-list-item-name">{p.name}</span>
                <span className="assistant-list-item-sub">{p.archetype_id ?? 'custom'}</span>
              </button>
            )}
            {renamingId !== p.persona_id && (
              <button
                type="button"
                className="assistant-list-item-rename"
                onClick={() => startRename(p)}
                aria-label={`Rename ${p.name}`}
                title="Rename"
              >
                ✎
              </button>
            )}
          </div>
        ))}
        {renameError && <p className="error">{renameError}</p>}
      </div>
    </>
  )
}
