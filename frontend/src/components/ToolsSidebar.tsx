import { useState } from 'react'
import type { ActivatedTool, ToolDefinition } from '../types'

interface Props {
  catalog: ToolDefinition[]
  activatedTools: ActivatedTool[]
  selectedId: string | null
  onSelect: (tool: ActivatedTool) => void
  onActivateFromCatalog: (definition: ToolDefinition) => void
}

export function ToolsSidebar({ catalog, activatedTools, selectedId, onSelect, onActivateFromCatalog }: Props) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <>
      <div className="sidebar-header">
        <span>Tools</span>
        <span className="muted">{activatedTools.length}</span>
      </div>

      <div className="create-assistant">
        <button type="button" className="primary create-btn" onClick={() => setMenuOpen((v) => !v)}>
          <span aria-hidden="true">+</span> Activate Tool
        </button>
        {menuOpen && (
          <div className="create-menu">
            <div className="create-menu-label">Prebuilt tools</div>
            {catalog.map((t) => (
              <button
                key={t.id}
                type="button"
                className="create-menu-item"
                disabled={t.status !== 'available'}
                onClick={() => {
                  onActivateFromCatalog(t)
                  setMenuOpen(false)
                }}
              >
                <span className="create-menu-item-title">{t.display_name}</span>
                <span className="create-menu-item-sub">
                  {t.category}
                  {t.status !== 'available' && <span className={`status-pill ${t.status}`}>coming soon</span>}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="assistant-list">
        {activatedTools.length === 0 && <p className="muted sidebar-empty">No tools activated yet.</p>}
        {activatedTools.map((t) => (
          <button
            key={t.tool_instance_id}
            type="button"
            className={`assistant-list-item${t.tool_instance_id === selectedId ? ' selected' : ''}`}
            onClick={() => onSelect(t)}
          >
            <div className="list-item-avatar">{t.name[0]}</div>
            <span className="assistant-list-item-select">
              <span className="assistant-list-item-name">{t.name}</span>
              <span className="assistant-list-item-sub">{t.tool_id}</span>
            </span>
          </button>
        ))}
      </div>
    </>
  )
}
