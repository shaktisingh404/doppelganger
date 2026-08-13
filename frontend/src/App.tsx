import { useEffect, useState } from 'react'
import { AssistantSidebar } from './components/AssistantSidebar'
import { AssistantEditor } from './components/AssistantEditor'
import { AuthView } from './components/AuthView'
import { PersonaView } from './components/PersonaView'
import { ChatPanel } from './components/ChatPanel'
import { ToolsSidebar } from './components/ToolsSidebar'
import { ToolActivationForm } from './components/ToolActivationForm'
import { ToolInstanceView } from './components/ToolInstanceView'
import {
  getAuthToken,
  getMe,
  listArchetypes,
  listActivatedTools,
  listPersonas,
  listToolCatalog,
  setAuthToken,
  setOnUnauthorized,
} from './api'
import type { ActivatedTool, ArchetypeSpec, AssembledPersona, ToolDefinition, UserPublic } from './types'

type View = 'assistants' | 'tools'

function App() {
  const [user, setUser] = useState<UserPublic | null>(null)
  // Distinguishes "still checking a stored token" from "checked, logged out"
  // — without it the login screen flashes for a moment on every reload.
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    setOnUnauthorized(() => {
      setAuthToken(null)
      setUser(null)
    })
    if (!getAuthToken()) {
      setAuthChecked(true)
      return
    }
    getMe()
      .then(setUser)
      .catch(() => setAuthToken(null))
      .finally(() => setAuthChecked(true))
  }, [])

  function handleLogout() {
    setAuthToken(null)
    setUser(null)
  }

  if (!authChecked) return null
  if (!user) return <AuthView onAuthenticated={setUser} />

  return <AuthenticatedApp user={user} onLogout={handleLogout} />
}

function AuthenticatedApp({ user, onLogout }: { user: UserPublic; onLogout: () => void }) {
  const [view, setView] = useState<View>('assistants')
  const [archetypes, setArchetypes] = useState<ArchetypeSpec[]>([])
  const [personas, setPersonas] = useState<AssembledPersona[]>([])
  const [selected, setSelected] = useState<AssembledPersona | null>(null)
  const [creatingFrom, setCreatingFrom] = useState<ArchetypeSpec | null>(null)

  const [toolCatalog, setToolCatalog] = useState<ToolDefinition[]>([])
  const [activatedTools, setActivatedTools] = useState<ActivatedTool[]>([])
  const [selectedTool, setSelectedTool] = useState<ActivatedTool | null>(null)
  const [activatingFrom, setActivatingFrom] = useState<ToolDefinition | null>(null)

  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listArchetypes(), listPersonas(), listToolCatalog(), listActivatedTools()])
      .then(([a, p, tc, at]) => {
        setArchetypes(a)
        setPersonas(p)
        setToolCatalog(tc)
        setActivatedTools(at)
      })
      .catch((e) => setLoadError(String(e)))
  }, [])

  function handleCreated(persona: AssembledPersona) {
    setPersonas((prev) => [...prev, persona])
    setSelected(persona)
    setCreatingFrom(null)
  }

  function handleActivated(tool: ActivatedTool) {
    setActivatedTools((prev) => [...prev, tool])
    setSelectedTool(tool)
    setActivatingFrom(null)
  }

  function handlePersonaToolsUpdated(persona: AssembledPersona) {
    setPersonas((prev) => prev.map((p) => (p.persona_id === persona.persona_id ? persona : p)))
    setSelected(persona)
  }

  return (
    <div className="app-shell-split">
      <aside className="sidebar">
        <nav className="view-tabs">
          <button
            type="button"
            className={`view-tab${view === 'assistants' ? ' active' : ''}`}
            onClick={() => setView('assistants')}
          >
            Assistants
          </button>
          <button
            type="button"
            className={`view-tab${view === 'tools' ? ' active' : ''}`}
            onClick={() => setView('tools')}
          >
            Tools
          </button>
        </nav>

        {view === 'assistants' ? (
          <AssistantSidebar
            personas={personas}
            archetypes={archetypes}
            selectedId={selected?.persona_id ?? null}
            onSelect={(p) => {
              setSelected(p)
              setCreatingFrom(null)
            }}
            onCreateFromArchetype={(a) => {
              setCreatingFrom(a)
              setSelected(null)
            }}
          />
        ) : (
          <ToolsSidebar
            catalog={toolCatalog}
            activatedTools={activatedTools}
            selectedId={selectedTool?.tool_instance_id ?? null}
            onSelect={(t) => {
              setSelectedTool(t)
              setActivatingFrom(null)
            }}
            onActivateFromCatalog={(def) => {
              setActivatingFrom(def)
              setSelectedTool(null)
            }}
          />
        )}
      </aside>

      <main className="main-panel">
        <header className="app-header app-header-row">
          <div>
            <h1 className="brand">Doppelganger</h1>
            <p className="muted">Dynamic persona voice service — build a persona, then talk to it.</p>
          </div>
          <div className="app-header-user">
            <span className="muted">{user.email}</span>
            <button type="button" className="link-button" onClick={onLogout}>
              Log out
            </button>
          </div>
        </header>

        {loadError && <p className="error">Failed to load: {loadError}</p>}

        {view === 'assistants' && (
          <>
            {creatingFrom && (
              // Keyed so picking a different archetype while already editing
              // (Create Assistant again) remounts with fresh field state
              // instead of carrying over the previous archetype's edits.
              <AssistantEditor
                key={creatingFrom.id}
                archetype={creatingFrom}
                activatedTools={activatedTools}
                onCreated={handleCreated}
                onCancel={() => setCreatingFrom(null)}
              />
            )}

            {!creatingFrom && selected && (
              // Keyed on persona_id so switching assistants remounts this
              // subtree — ChatPanel's message state must not carry over from
              // the previously selected persona.
              <div className="stage" key={selected.persona_id}>
                <PersonaView persona={selected} activatedTools={activatedTools} onToolsUpdated={handlePersonaToolsUpdated} />
                <ChatPanel personaId={selected.persona_id} personaName={selected.name} />
              </div>
            )}

            {!creatingFrom && !selected && (
              <div className="empty-state">
                <p className="muted">Select an assistant on the left, or create a new one from a prebuilt persona.</p>
              </div>
            )}
          </>
        )}

        {view === 'tools' && (
          <>
            {activatingFrom && (
              <ToolActivationForm
                key={activatingFrom.id}
                definition={activatingFrom}
                personas={personas}
                onActivated={handleActivated}
                onCancel={() => setActivatingFrom(null)}
              />
            )}

            {!activatingFrom && selectedTool && <ToolInstanceView tool={selectedTool} personas={personas} />}

            {!activatingFrom && !selectedTool && (
              <div className="empty-state">
                <p className="muted">Select a tool on the left, or activate one from the prebuilt catalog.</p>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

export default App
