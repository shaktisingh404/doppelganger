import { useEffect, useState } from 'react'
import { listArchetypes } from '../api'
import type { ArchetypeSpec } from '../types'

interface Props {
  onSelect: (archetype: ArchetypeSpec) => void
}

export function ArchetypePicker({ onSelect }: Props) {
  const [archetypes, setArchetypes] = useState<ArchetypeSpec[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listArchetypes()
      .then(setArchetypes)
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <p className="error">Failed to load archetypes: {error}</p>
  if (!archetypes) return <p className="muted">Loading archetypes…</p>

  return (
    <div className="stage">
      <h1>Choose a persona archetype</h1>
      <div className="card-grid">
        {archetypes.map((a) => (
          <button key={a.id} className="archetype-card" onClick={() => onSelect(a)}>
            <h3>{a.display_name}</h3>
            <p>{a.persona_text}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
