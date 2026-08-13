import { useState } from 'react'
import { deletePersona, disableSharing, enableSharing, updatePersona, updatePersonaTools } from '../api'
import { useConfirm } from './ConfirmDialog'
import { useToast } from './Toast'
import type { ActivatedTool, AssembledPersona } from '../types'

interface Props {
  persona: AssembledPersona
  activatedTools: ActivatedTool[]
  onUpdated: (persona: AssembledPersona) => void
  onDeleted: (personaId: string) => void
  chatOpen: boolean
  onToggleChat: () => void
}

type Tab = 'assistant' | 'tools' | 'share'

const AssistantIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-8z" />
  </svg>
)

const ToolsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2-2 2.6-2.6z" />
  </svg>
)

const LinkIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 17H7a5 5 0 1 1 0-10h2M15 7h2a5 5 0 1 1 0 10h-2M8 12h8" />
  </svg>
)

const ExpandIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3m11-5v3a2 2 0 0 1-2 2h-3" />
  </svg>
)

const CopyIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
)

export function PersonaView({ persona, activatedTools, onUpdated, onDeleted, chatOpen, onToggleChat }: Props) {
  const confirm = useConfirm()
  const showToast = useToast()

  const [tab, setTab] = useState<Tab>('assistant')
  const [promptExpanded, setPromptExpanded] = useState(false)
  const [idCopied, setIdCopied] = useState(false)

  const [selectedToolIds, setSelectedToolIds] = useState<string[]>(persona.tool_instance_ids)
  const [savingTools, setSavingTools] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const [sharing, setSharing] = useState(false)
  const [linkCopied, setLinkCopied] = useState(false)

  const [editingPersona, setEditingPersona] = useState(false)
  const [editName, setEditName] = useState(persona.name)
  const [editFirstMessage, setEditFirstMessage] = useState(persona.first_message)
  const [editSystemPrompt, setEditSystemPrompt] = useState(persona.system_prompt)
  const [savingPersona, setSavingPersona] = useState(false)
  const [personaError, setPersonaError] = useState<string | null>(null)

  const toolsChanged =
    selectedToolIds.length !== persona.tool_instance_ids.length ||
    selectedToolIds.some((id) => !persona.tool_instance_ids.includes(id))

  function switchTab(next: Tab) {
    setTab(next)
    setEditingPersona(false)
    setSelectedToolIds(persona.tool_instance_ids)
  }

  function toggleTool(toolInstanceId: string) {
    setSelectedToolIds((prev) =>
      prev.includes(toolInstanceId) ? prev.filter((id) => id !== toolInstanceId) : [...prev, toolInstanceId]
    )
  }

  async function saveTools() {
    setSavingTools(true)
    try {
      const updated = await updatePersonaTools(persona.persona_id, { tool_instance_ids: selectedToolIds })
      onUpdated(updated)
    } catch (err) {
      showToast(String(err))
    } finally {
      setSavingTools(false)
    }
  }

  async function handleDelete() {
    if (!(await confirm({ message: `Delete "${persona.name}"? This can't be undone.`, confirmLabel: 'Delete', danger: true }))) return
    setDeleting(true)
    try {
      await deletePersona(persona.persona_id)
      onDeleted(persona.persona_id)
    } catch (err) {
      showToast(String(err))
      setDeleting(false)
    }
  }

  const shareUrl = persona.share_token ? `${window.location.origin}/share/${persona.share_token}` : null

  async function handleEnableShare() {
    setSharing(true)
    try {
      const { share_token } = await enableSharing(persona.persona_id)
      onUpdated({ ...persona, share_token })
    } catch (err) {
      showToast(String(err))
    } finally {
      setSharing(false)
    }
  }

  async function handleDisableShare() {
    if (!(await confirm('Disable the public link? It will stop working immediately.'))) return
    setSharing(true)
    try {
      await disableSharing(persona.persona_id)
      onUpdated({ ...persona, share_token: null })
    } catch (err) {
      showToast(String(err))
    } finally {
      setSharing(false)
    }
  }

  async function handleCopyLink() {
    if (!shareUrl) return
    await navigator.clipboard.writeText(shareUrl)
    setLinkCopied(true)
    setTimeout(() => setLinkCopied(false), 1500)
  }

  async function handleCopyId() {
    await navigator.clipboard.writeText(persona.persona_id)
    setIdCopied(true)
    setTimeout(() => setIdCopied(false), 1500)
  }

  function startEditingPersona() {
    setEditName(persona.name)
    setEditFirstMessage(persona.first_message)
    setEditSystemPrompt(persona.system_prompt)
    setPersonaError(null)
    setEditingPersona(true)
  }

  async function savePersona(e: React.FormEvent) {
    e.preventDefault()
    setSavingPersona(true)
    setPersonaError(null)
    try {
      const updated = await updatePersona(persona.persona_id, {
        name: editName,
        system_prompt: editSystemPrompt,
        first_message: editFirstMessage,
      })
      onUpdated(updated)
      setEditingPersona(false)
    } catch (err) {
      setPersonaError(String(err))
    } finally {
      setSavingPersona(false)
    }
  }

  const shortId = `${persona.persona_id.slice(0, 8)}…${persona.persona_id.slice(-6)}`

  return (
    <div className="persona-view">
      <div className="persona-header">
        {editingPersona ? (
          <input
            className="editor-name-input"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            required
            placeholder="Assistant name"
            form="persona-edit-form"
          />
        ) : (
          <div className="persona-view-identity">
            <h2>{persona.name}</h2>
            <span className="badge">{persona.archetype_id ?? 'custom'}</span>
            <button type="button" className="badge badge-id" onClick={handleCopyId} title="Copy assistant ID">
              {idCopied ? 'Copied!' : shortId}
              <CopyIcon />
            </button>
          </div>
        )}

        <div className="editor-top-actions">
          <button
            type="button"
            className={`chat-toggle-btn${chatOpen ? ' active' : ''}`}
            onClick={onToggleChat}
            aria-pressed={chatOpen}
          >
            <AssistantIcon /> {chatOpen ? 'Hide Chat' : 'Chat'}
          </button>
          {editingPersona ? (
            <>
              <button type="button" className="link-button" onClick={() => setEditingPersona(false)}>
                Cancel
              </button>
              <button
                type="submit"
                form="persona-edit-form"
                className="primary"
                disabled={savingPersona || !editSystemPrompt.trim()}
              >
                {savingPersona ? 'Saving…' : 'Save'}
              </button>
            </>
          ) : (
            <>
              <button type="button" className="link-button" onClick={startEditingPersona}>
                Edit
              </button>
              <button type="button" className="link-button danger" onClick={handleDelete} disabled={deleting}>
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </>
          )}
        </div>
      </div>

      <nav className="detail-tabs">
        <button type="button" className={`detail-tab${tab === 'assistant' ? ' active' : ''}`} onClick={() => switchTab('assistant')}>
          <AssistantIcon /> Assistant
        </button>
        <button type="button" className={`detail-tab${tab === 'tools' ? ' active' : ''}`} onClick={() => switchTab('tools')}>
          <ToolsIcon /> Tools{persona.tool_instance_ids.length > 0 ? ` (${persona.tool_instance_ids.length})` : ''}
        </button>
        <button type="button" className={`detail-tab${tab === 'share' ? ' active' : ''}`} onClick={() => switchTab('share')}>
          <LinkIcon /> Share
        </button>
      </nav>

      {tab === 'assistant' &&
        (editingPersona ? (
          <form id="persona-edit-form" onSubmit={savePersona}>
            <div className="section-block">
              <div className="section-label-row">
                <span className="section-label">First Message</span>
                <span className="muted">assistant speaks first — optional</span>
              </div>
              <textarea value={editFirstMessage} onChange={(e) => setEditFirstMessage(e.target.value)} rows={2} />
            </div>

            <div className="section-block">
              <div className="section-label-row">
                <span className="section-label">System Prompt</span>
              </div>
              <textarea
                className="prompt-box"
                value={editSystemPrompt}
                onChange={(e) => setEditSystemPrompt(e.target.value)}
                rows={16}
                required
              />
            </div>

            {personaError && <p className="error">{personaError}</p>}
          </form>
        ) : (
          <>
            <div className="section-block">
              <div className="section-label-row">
                <span className="section-label">First Message</span>
              </div>
              {persona.first_message ? (
                <p className="persona-first-message">{persona.first_message}</p>
              ) : (
                <p className="muted">No first message — the assistant waits for the caller to speak first.</p>
              )}
            </div>

            <div className="section-block">
              <div className="section-label-row">
                <span className="section-label">System Prompt</span>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setPromptExpanded((v) => !v)}
                  aria-label={promptExpanded ? 'Collapse' : 'Expand'}
                  title={promptExpanded ? 'Collapse' : 'Expand'}
                >
                  <ExpandIcon />
                </button>
              </div>
              <pre className={`prompt-box${promptExpanded ? ' expanded' : ''}`}>{persona.system_prompt}</pre>
            </div>
          </>
        ))}

      {tab === 'tools' && (
        <div className="section-block tools-section">
          {activatedTools.length === 0 ? (
            <p className="muted">No tools activated yet — activate one from the Tools section in the sidebar.</p>
          ) : (
            <div className="tool-checkbox-list">
              {activatedTools.map((t) => (
                <label key={t.tool_instance_id} className="checkbox-row tool-checkbox-row">
                  <input
                    type="checkbox"
                    checked={selectedToolIds.includes(t.tool_instance_id)}
                    onChange={() => toggleTool(t.tool_instance_id)}
                  />
                  {t.name} <span className="muted">({t.tool_id})</span>
                </label>
              ))}
            </div>
          )}
          <div className="editor-top-actions">
            <button type="button" className="primary" onClick={saveTools} disabled={savingTools || !toolsChanged}>
              {savingTools ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}

      {tab === 'share' && (
        <div className="section-block">
          {shareUrl ? (
            <div className="share-link-row">
              <input className="share-link-input" value={shareUrl} readOnly onFocus={(e) => e.target.select()} />
              <button type="button" className="link-button" onClick={handleCopyLink}>
                {linkCopied ? 'Copied!' : 'Copy'}
              </button>
              <button type="button" className="link-button danger" onClick={handleDisableShare} disabled={sharing}>
                Disable
              </button>
            </div>
          ) : (
            <div className="share-link-row">
              <p className="muted">Let anyone with this link chat with {persona.name} — no login, no system prompt visible.</p>
              <button type="button" className="link-button" onClick={handleEnableShare} disabled={sharing}>
                {sharing ? 'Enabling…' : 'Enable public link'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
