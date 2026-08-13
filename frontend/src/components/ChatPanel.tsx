import { useEffect, useRef, useState } from 'react'
import { getChatHistory, sendChatMessage } from '../api'
import type { ChatMessage } from '../types'

const HISTORY_POLL_MS = 4000

interface Props {
  personaId: string
  personaName: string
}

export function ChatPanel({ personaId, personaName }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Loads the persona's history right away — notably the seeded
  // first_message (storage/persona_store.py) — instead of showing an empty
  // "say hello" state until the first poll tick catches up.
  useEffect(() => {
    getChatHistory(personaId)
      .then(setMessages)
      .catch((e) => setError(String(e)))
  }, [personaId])

  // Picks up messages the persona sends on its own, e.g. a fired scheduled
  // follow-up (scheduler/dispatcher.py) — those never come back as a
  // sendChatMessage() response, only through polled history.
  useEffect(() => {
    const interval = setInterval(async () => {
      if (sending) return
      try {
        const history = await getChatHistory(personaId)
        setMessages((prev) => (history.length > prev.length ? history : prev))
      } catch {
        // best-effort poll; a transient failure just waits for the next tick
      }
    }, HISTORY_POLL_MS)
    return () => clearInterval(interval)
  }, [personaId, sending])

  async function send() {
    const text = input.trim()
    if (!text || sending) return

    setError(null)
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setSending(true)
    try {
      const { reply } = await sendChatMessage(personaId, text)
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }])
    } catch (err) {
      setError(String(err))
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="muted">Say hello to {personaName} to start the conversation.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
        {sending && <div className="bubble assistant pending">…</div>}
        <div ref={bottomRef} />
      </div>

      {error && <p className="error">{error}</p>}

      <div className="chat-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`Message ${personaName}`}
          disabled={sending}
        />
        <button type="button" className="primary" onClick={send} disabled={sending || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
