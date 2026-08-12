import { useState } from 'react'
import type { AssembledPersona } from '../types'

interface Props {
  persona: AssembledPersona
}

export function PersonaView({ persona }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="persona-view">
      <div className="persona-header">
        <div>
          <h2>{persona.name}</h2>
          <p className="muted">archetype: {persona.archetype_id}</p>
        </div>
        <button type="button" className="link-button" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Hide system prompt' : 'Show system prompt'}
        </button>
      </div>
      {expanded && <pre className="system-prompt">{persona.system_prompt}</pre>}
    </div>
  )
}
