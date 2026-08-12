import { useState } from 'react'
import { createPersona } from '../api'
import type { ArchetypeSpec, AssembledPersona, BusinessInfo } from '../types'

interface Props {
  archetype: ArchetypeSpec
  onCreated: (persona: AssembledPersona) => void
  onBack: () => void
}

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

export function PersonaForm({ archetype, onCreated, onBack }: Props) {
  const [name, setName] = useState('')
  const [language, setLanguage] = useState('English')
  const [tone, setTone] = useState('')
  const [description, setDescription] = useState('')

  const [addBusiness, setAddBusiness] = useState(false)
  const [bizName, setBizName] = useState('')
  const [address, setAddress] = useState('')
  const [phone, setPhone] = useState('')
  const [hours, setHours] = useState('')
  const [services, setServices] = useState('')
  const [notes, setNotes] = useState('')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
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
      const persona = await createPersona({
        archetype_id: archetype.id,
        name,
        language,
        tone: tone || null,
        description,
        business_info,
      })
      onCreated(persona)
    } catch (err) {
      setError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="stage">
      <button className="link-button" onClick={onBack} type="button">
        ← Back to archetypes
      </button>
      <h1>Build your {archetype.display_name.toLowerCase()}</h1>

      <form onSubmit={handleSubmit} className="form">
        <label>
          Persona name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>

        <div className="form-row">
          <label>
            Language
            <input value={language} onChange={(e) => setLanguage(e.target.value)} required />
          </label>
          <label>
            Tone <span className="muted">(optional)</span>
            <input value={tone} onChange={(e) => setTone(e.target.value)} placeholder="e.g. warm and efficient" />
          </label>
        </div>

        <label>
          Description
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            required
            placeholder="What should this persona specialize in, focus on, or avoid?"
          />
        </label>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={addBusiness}
            onChange={(e) => setAddBusiness(e.target.checked)}
          />
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

        {error && <p className="error">{error}</p>}

        <button type="submit" className="primary" disabled={submitting}>
          {submitting ? 'Building persona…' : 'Build persona'}
        </button>
      </form>
    </div>
  )
}
