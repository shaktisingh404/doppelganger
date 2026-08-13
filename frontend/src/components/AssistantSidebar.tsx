import { useState } from 'react'
import type { ArchetypeSpec, AssembledPersona } from '../types'

interface Props {
  personas: AssembledPersona[]
  archetypes: ArchetypeSpec[]
  selectedId: string | null
  onSelect: (persona: AssembledPersona) => void
  onCreateFromArchetype: (archetype: ArchetypeSpec) => void
}

export function AssistantSidebar({ personas, archetypes, selectedId, onSelect, onCreateFromArchetype }: Props) {
  const [menuOpen, setMenuOpen] = useState(false)

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
          <button
            key={p.persona_id}
            type="button"
            className={`assistant-list-item${p.persona_id === selectedId ? ' selected' : ''}`}
            onClick={() => onSelect(p)}
          >
            <span className="assistant-list-item-name">{p.name}</span>
            <span className="assistant-list-item-sub">{p.archetype_id ?? 'custom'}</span>
          </button>
        ))}
      </div>
    </>
  )
}
