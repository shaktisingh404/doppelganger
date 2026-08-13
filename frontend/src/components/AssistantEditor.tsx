import { useEffect, useState } from 'react'
import { createPersona, generateSystemPrompt } from '../api'
import type { ActivatedTool, ArchetypeSpec, AssembledPersona, BusinessInfo, ReferenceFile } from '../types'

interface Props {
  archetype: ArchetypeSpec
  activatedTools: ActivatedTool[]
  onCreated: (persona: AssembledPersona) => void
  onCancel: () => void
}

// Mirrors MAX_REFERENCE_FILE_CHARS in backend/compiler/models.py — checked
// here too so a too-big file fails fast instead of round-tripping to the
// server first, but the backend re-validates regardless of this value.
const MAX_REFERENCE_FILE_CHARS = 20_000

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

export function AssistantEditor({ archetype, activatedTools, onCreated, onCancel }: Props) {
  const [name, setName] = useState(archetype.display_name)
  const [firstMessage, setFirstMessage] = useState('')
  // Starts as just the archetype's short blurb, then upgraded below to the
  // full assembled prompt (common template + guardrails included) — the
  // same shape Generate would produce, so what you see here on open is
  // already the real thing, not a stand-in for it.
  const [systemPrompt, setSystemPrompt] = useState(archetype.persona_text)
  const [loadingPreview, setLoadingPreview] = useState(true)

  const [showGenerate, setShowGenerate] = useState(false)
  const [description, setDescription] = useState('')
  const [workingStyle, setWorkingStyle] = useState('')
  const [language, setLanguage] = useState('English')
  const [tone, setTone] = useState('')
  const [addBusiness, setAddBusiness] = useState(false)
  const [bizName, setBizName] = useState('')
  const [address, setAddress] = useState('')
  const [phone, setPhone] = useState('')
  const [hours, setHours] = useState('')
  const [services, setServices] = useState('')
  const [notes, setNotes] = useState('')
  const [referenceFiles, setReferenceFiles] = useState<ReferenceFile[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>([])

  const [generating, setGenerating] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // An empty description skips the LLM call server-side (nothing to
  // extract), so this is cheap enough to run the instant the editor opens.
  useEffect(() => {
    let cancelled = false
    generateSystemPrompt({
      archetype_id: archetype.id,
      name: archetype.display_name,
      language: 'English',
      tone: null,
      description: '',
      business_info: null,
    })
      .then(({ system_prompt }) => {
        // Don't clobber an edit the user already made while this was in flight.
        if (!cancelled) setSystemPrompt((current) => (current === archetype.persona_text ? system_prompt : current))
      })
      .catch(() => {
        // Falls back to the archetype's short blurb already showing.
      })
      .finally(() => {
        if (!cancelled) setLoadingPreview(false)
      })
    return () => {
      cancelled = true
    }
    // archetype is fixed for this component's lifetime (App.tsx keys it by archetype.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleFilesSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    e.target.value = '' // lets picking the same file again re-trigger onChange
    setFileError(null)

    for (const file of files) {
      const content = await file.text()
      if (content.length > MAX_REFERENCE_FILE_CHARS) {
        setFileError(`${file.name} is too long (${content.length} characters, max ${MAX_REFERENCE_FILE_CHARS}).`)
        continue
      }
      setReferenceFiles((prev) => [...prev, { filename: file.name, content }])
    }
  }

  function removeFile(filename: string) {
    setReferenceFiles((prev) => prev.filter((f) => f.filename !== filename))
  }

  function toggleTool(toolInstanceId: string) {
    setSelectedToolIds((prev) =>
      prev.includes(toolInstanceId) ? prev.filter((id) => id !== toolInstanceId) : [...prev, toolInstanceId]
    )
  }

  async function handleGenerate() {
    setGenerating(true)
    setError(null)

    const business_info: BusinessInfo | null = addBusiness
      ? {
          name: bizName,
          address: address || null,
          phone: phone || null,
          hours: hours || null,
          services: splitList(services),
          notes: splitList(notes),
        }
      : null

    try {
      const { system_prompt } = await generateSystemPrompt({
        archetype_id: archetype.id,
        name,
        language,
        tone: tone || null,
        description,
        business_info,
        conversational_style: workingStyle || null,
        reference_files: referenceFiles,
      })
      setSystemPrompt(system_prompt)
      setShowGenerate(false)
    } catch (err) {
      setError(String(err))
    } finally {
      setGenerating(false)
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      const persona = await createPersona({
        name,
        system_prompt: systemPrompt,
        first_message: firstMessage,
        archetype_id: archetype.id,
        tool_instance_ids: selectedToolIds,
      })
      onCreated(persona)
    } catch (err) {
      setError(String(err))
    } finally {
      setCreating(false)
    }
  }

  return (
    <form className="editor" onSubmit={handleCreate}>
      <div className="editor-top-row">
        <input
          className="editor-name-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          placeholder="Assistant name"
        />
        <div className="editor-top-actions">
          <button type="button" className="link-button" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={creating || !systemPrompt.trim()}>
            {creating ? 'Creating…' : 'Create Assistant'}
          </button>
        </div>
      </div>

      <label>
        First Message <span className="muted">(assistant speaks first — optional)</span>
        <textarea
          value={firstMessage}
          onChange={(e) => setFirstMessage(e.target.value)}
          rows={2}
          placeholder="Hi, this is Riverside Dental. How can I help you today?"
        />
      </label>

      <label>
        <div className="field-label-row">
          <span>System Prompt {loadingPreview && <span className="muted">(loading full prompt…)</span>}</span>
          <button
            type="button"
            className="generate-btn"
            onClick={() => setShowGenerate((v) => !v)}
          >
            ✨ Generate
          </button>
        </div>
        <textarea
          className="system-prompt-input"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          rows={14}
          required
        />
      </label>

      <div className="tools-section">
        <span className="field-label-row-static">Tools</span>
        {activatedTools.length === 0 ? (
          <p className="muted">
            No tools activated yet — activate one from the Tools section in the sidebar, then attach it here.
          </p>
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
      </div>

      {showGenerate && (
        <div className="generate-panel">
          <p className="generate-panel-title">Generate via AI</p>
          <label>
            Description
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="What should this persona specialize in, focus on, or avoid?"
            />
          </label>
          <label>
            Working style <span className="muted">(optional)</span>
            <textarea
              value={workingStyle}
              onChange={(e) => setWorkingStyle(e.target.value)}
              rows={2}
              placeholder="How should it converse — pacing, when to ask clarifying questions, how it handles things it doesn't know?"
            />
          </label>
          <div className="form-row">
            <label>
              Language
              <input value={language} onChange={(e) => setLanguage(e.target.value)} />
            </label>
            <label>
              Tone <span className="muted">(optional)</span>
              <input value={tone} onChange={(e) => setTone(e.target.value)} placeholder="e.g. warm and efficient" />
            </label>
          </div>

          <label>
            Reference files <span className="muted">(.txt or .md — injected verbatim, optional)</span>
            <input type="file" accept=".txt,.md" multiple onChange={handleFilesSelected} />
          </label>
          {fileError && <p className="error">{fileError}</p>}
          {referenceFiles.length > 0 && (
            <div className="file-chip-row">
              {referenceFiles.map((f) => (
                <span key={f.filename} className="file-chip">
                  {f.filename}
                  <button type="button" onClick={() => removeFile(f.filename)} aria-label={`Remove ${f.filename}`}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          <label className="checkbox-row">
            <input type="checkbox" checked={addBusiness} onChange={(e) => setAddBusiness(e.target.checked)} />
            Add business details
          </label>

          {addBusiness && (
            <div className="business-fields">
              <label>
                Business name
                <input value={bizName} onChange={(e) => setBizName(e.target.value)} required />
              </label>
              <div className="form-row">
                <label>
                  Address <span className="muted">(optional)</span>
                  <input value={address} onChange={(e) => setAddress(e.target.value)} />
                </label>
                <label>
                  Phone <span className="muted">(optional)</span>
                  <input value={phone} onChange={(e) => setPhone(e.target.value)} />
                </label>
              </div>
              <label>
                Hours <span className="muted">(optional)</span>
                <input value={hours} onChange={(e) => setHours(e.target.value)} />
              </label>
              <label>
                Services <span className="muted">(comma-separated, optional)</span>
                <input value={services} onChange={(e) => setServices(e.target.value)} />
              </label>
              <label>
                Other facts <span className="muted">(comma-separated, optional)</span>
                <input value={notes} onChange={(e) => setNotes(e.target.value)} />
              </label>
            </div>
          )}

          <button
            type="button"
            className="primary"
            onClick={handleGenerate}
            disabled={generating || !description.trim()}
          >
            {generating ? 'Generating…' : 'Generate System Prompt'}
          </button>
        </div>
      )}

      {error && <p className="error">{error}</p>}
    </form>
  )
}
