import { useState } from 'react'
import { ArchetypePicker } from './components/ArchetypePicker'
import { PersonaForm } from './components/PersonaForm'
import { PersonaView } from './components/PersonaView'
import { ChatPanel } from './components/ChatPanel'
import type { ArchetypeSpec, AssembledPersona } from './types'

type Stage = 'pick' | 'form' | 'chat'

function App() {
  const [stage, setStage] = useState<Stage>('pick')
  const [archetype, setArchetype] = useState<ArchetypeSpec | null>(null)
  const [persona, setPersona] = useState<AssembledPersona | null>(null)

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="brand">Doppelganger</h1>
        <p className="muted">Dynamic persona voice service — build a persona, then talk to it.</p>
      </header>

      <main>
        {stage === 'pick' && (
          <ArchetypePicker
            onSelect={(a) => {
              setArchetype(a)
              setStage('form')
            }}
          />
        )}

        {stage === 'form' && archetype && (
          <PersonaForm
            archetype={archetype}
            onBack={() => setStage('pick')}
            onCreated={(p) => {
              setPersona(p)
              setStage('chat')
            }}
          />
        )}

        {stage === 'chat' && persona && (
          <div className="stage">
            <button className="link-button" onClick={() => setStage('pick')} type="button">
              ← Start a new persona
            </button>
            <PersonaView persona={persona} />
            <ChatPanel personaId={persona.persona_id} personaName={persona.name} />
          </div>
        )}
      </main>
    </div>
  )
}

export default App
