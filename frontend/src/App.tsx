import { useEffect, useState } from 'react'
import { AssistantSidebar } from './components/AssistantSidebar'
import { AssistantEditor } from './components/AssistantEditor'
import { AuthView } from './components/AuthView'
import { ConfirmProvider } from './components/ConfirmDialog'
import { PersonaView } from './components/PersonaView'
import { ChatPanel } from './components/ChatPanel'
import { ToastProvider } from './components/Toast'
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

const ChatIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-8z" />
  </svg>
)

const ToolsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2-2 2.6-2.6z" />
  </svg>
)

const MenuIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M4 6h16M4 12h16M4 18h16" />
  </svg>
)

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

  return (
    <ToastProvider>
      <ConfirmProvider>
        {user ? <AuthenticatedApp user={user} onLogout={handleLogout} /> : <AuthView onAuthenticated={setUser} />}
      </ConfirmProvider>
    </ToastProvider>
  )
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

  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  // Lives here, not in PersonaView, since it's a sibling to ChatPanel --
  // both are rendered by this component. Not reset on persona switch
  // (the "stage" div below is remounted via key={selected.persona_id},
  // but this state lives above that remount boundary) -- if you had chat
  // open, it stays open when you pick a different assistant.
  const [chatOpen, setChatOpen] = useState(true)

  useEffect(() => {
    Promise.all([listArchetypes(), listPersonas(), listToolCatalog(), listActivatedTools()])
      .then(([a, p, tc, at]) => {
        setArchetypes(a)
        setPersonas(p)
        setToolCatalog(tc)
        setActivatedTools(at)
      })
      .catch((e) => setLoadError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  function switchView(next: View) {
    setView(next)
    setMobileNavOpen(false)
  }

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

  function handlePersonaUpdated(persona: AssembledPersona) {
    setPersonas((prev) => prev.map((p) => (p.persona_id === persona.persona_id ? persona : p)))
    // Conditional, not a blind setSelected: PersonaView only ever edits the
    // already-selected persona (so this is a no-op switch there), but the
    // sidebar's inline rename can target any item -- renaming one you're
    // not currently viewing shouldn't yank the main panel over to it.
    setSelected((prev) => (prev?.persona_id === persona.persona_id ? persona : prev))
  }

  function handlePersonaDeleted(personaId: string) {
    setPersonas((prev) => prev.filter((p) => p.persona_id !== personaId))
    setSelected((prev) => (prev?.persona_id === personaId ? null : prev))
  }

  function handleToolUpdated(tool: ActivatedTool) {
    setActivatedTools((prev) => prev.map((t) => (t.tool_instance_id === tool.tool_instance_id ? tool : t)))
    setSelectedTool(tool)
  }

  function handleToolDeleted(toolInstanceId: string) {
    setActivatedTools((prev) => prev.filter((t) => t.tool_instance_id !== toolInstanceId))
    setSelectedTool((prev) => (prev?.tool_instance_id === toolInstanceId ? null : prev))
    // Mirrors the backend's cascade-detach (app/routers/tools.py) so a
    // persona's attached-tools list doesn't go stale until the next reload.
    setPersonas((prev) =>
      prev.map((p) =>
        p.tool_instance_ids.includes(toolInstanceId)
          ? { ...p, tool_instance_ids: p.tool_instance_ids.filter((id) => id !== toolInstanceId) }
          : p
      )
    )
  }

  return (
    <div className="app-shell-split">
      <nav className="nav-rail">
        <div className="nav-rail-brand">D</div>
        <button
          type="button"
          className={`nav-rail-item${view === 'assistants' ? ' active' : ''}`}
          onClick={() => switchView('assistants')}
        >
          <ChatIcon />
          <span>Assistants</span>
        </button>
        <button
          type="button"
          className={`nav-rail-item${view === 'tools' ? ' active' : ''}`}
          onClick={() => switchView('tools')}
        >
          <ToolsIcon />
          <span>Tools</span>
        </button>
      </nav>

      <div className={`sidebar-scrim${mobileNavOpen ? ' visible' : ''}`} onClick={() => setMobileNavOpen(false)} />

      <aside className={`sidebar${mobileNavOpen ? ' mobile-open' : ''}`}>
        {loading ? (
          <div>
            <div className="skeleton skeleton-list-item" />
            <div className="skeleton skeleton-list-item" />
            <div className="skeleton skeleton-list-item" />
          </div>
        ) : view === 'assistants' ? (
          <AssistantSidebar
            personas={personas}
            archetypes={archetypes}
            selectedId={selected?.persona_id ?? null}
            onSelect={(p) => {
              setSelected(p)
              setCreatingFrom(null)
              setMobileNavOpen(false)
            }}
            onCreateFromArchetype={(a) => {
              setCreatingFrom(a)
              setSelected(null)
              setMobileNavOpen(false)
            }}
            onRenamed={handlePersonaUpdated}
          />
        ) : (
          <ToolsSidebar
            catalog={toolCatalog}
            activatedTools={activatedTools}
            selectedId={selectedTool?.tool_instance_id ?? null}
            onSelect={(t) => {
              setSelectedTool(t)
              setActivatingFrom(null)
              setMobileNavOpen(false)
            }}
            onActivateFromCatalog={(def) => {
              setActivatingFrom(def)
              setSelectedTool(null)
              setMobileNavOpen(false)
            }}
          />
        )}
      </aside>

      <main className="main-panel">
        <header className="app-header app-header-row">
          <div className="app-header-title-row">
            <button type="button" className="mobile-nav-toggle" onClick={() => setMobileNavOpen((v) => !v)} aria-label="Menu">
              <MenuIcon />
            </button>
            <div>
              <h1 className="brand">Doppelganger</h1>
              <p className="muted">Dynamic persona voice service — build a persona, then talk to it.</p>
            </div>
          </div>
          <div className="app-header-user">
            <div className="app-header-user-avatar">{user.email[0]}</div>
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
                <div className="stage-main">
                  <PersonaView
                    persona={selected}
                    activatedTools={activatedTools}
                    onUpdated={handlePersonaUpdated}
                    onDeleted={handlePersonaDeleted}
                    chatOpen={chatOpen}
                    onToggleChat={() => setChatOpen((v) => !v)}
                  />
                </div>
                {chatOpen && (
                  <div className="stage-chat">
                    <ChatPanel personaId={selected.persona_id} personaName={selected.name} />
                  </div>
                )}
              </div>
            )}

            {!creatingFrom && !selected && !loading && (
              <div className="empty-state">
                <div className="empty-state-icon">
                  <ChatIcon />
                </div>
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
                onSaved={handleActivated}
                onCancel={() => setActivatingFrom(null)}
              />
            )}

            {!activatingFrom && selectedTool && (
              <ToolInstanceView
                tool={selectedTool}
                personas={personas}
                catalog={toolCatalog}
                onUpdated={handleToolUpdated}
                onDeleted={handleToolDeleted}
              />
            )}

            {!activatingFrom && !selectedTool && !loading && (
              <div className="empty-state">
                <div className="empty-state-icon">
                  <ToolsIcon />
                </div>
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
