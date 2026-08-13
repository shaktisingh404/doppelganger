import { useEffect, useRef, useState } from 'react'
import { createPublicSession, getPublicChatHistory, getPublicPersona, sendPublicChatMessage } from '../api'
import type { ChatMessage } from '../types'

const HISTORY_POLL_MS = 4000

interface Props {
  shareToken: string
}

function sessionStorageKey(shareToken: string) {
  return `doppelganger_public_session_${shareToken}`
}

export function PublicChat({ shareToken }: Props) {
  const [personaName, setPersonaName] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Distinct from "error while chatting" -- this is "the link itself
  // doesn't work" (unshared/disabled/never existed), a different,
  // terminal state with no retry affordance.
  const [linkInvalid, setLinkInvalid] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    let cancelled = false

    async function init() {
      try {
        const info = await getPublicPersona(shareToken)
        if (cancelled) return
        setPersonaName(info.name)

        let sid = localStorage.getItem(sessionStorageKey(shareToken))
        if (!sid) {
          const created = await createPublicSession(shareToken)
          sid = created.session_id
          localStorage.setItem(sessionStorageKey(shareToken), sid)
        }
        if (cancelled) return
        setSessionId(sid)

        const history = await getPublicChatHistory(shareToken, sid)
        if (!cancelled) setMessages(history)
      } catch {
        if (!cancelled) setLinkInvalid(true)
      }
    }

    init()
    return () => {
      cancelled = true
    }
  }, [shareToken])

  useEffect(() => {
    if (!sessionId) return
    const interval = setInterval(async () => {
      if (sending) return
      try {
        const history = await getPublicChatHistory(shareToken, sessionId)
        setMessages((prev) => (history.length > prev.length ? history : prev))
      } catch {
        // best-effort poll; a transient failure just waits for the next tick
      }
    }, HISTORY_POLL_MS)
    return () => clearInterval(interval)
  }, [shareToken, sessionId, sending])

  async function send() {
    const text = input.trim()
    if (!text || sending || !sessionId) return

    setError(null)
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setSending(true)
    try {
      const { reply } = await sendPublicChatMessage(shareToken, sessionId, text)
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

  if (linkInvalid) {
    return (
      <div className="public-chat-shell">
        <div className="public-chat-invalid">
          <p>This chat link isn't available anymore.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="public-chat-shell">
      <header className="public-chat-header">
        <div className="public-chat-avatar">{personaName ? personaName[0] : '…'}</div>
        <span className="public-chat-name">{personaName ?? 'Loading…'}</span>
      </header>

      <div className="chat-panel public-chat-panel">
        <div className="chat-messages">
          {personaName && messages.length === 0 && (
            <p className="muted">Say hello to {personaName} to start the conversation.</p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.content}
            </div>
          ))}
          {sending && (
            <div className="bubble assistant pending">
              <span />
              <span />
              <span />
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && <p className="error">{error}</p>}

        <div className="chat-input-row">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={personaName ? `Message ${personaName}` : 'Message'}
            disabled={sending || !sessionId}
          />
          <button type="button" className="primary" onClick={send} disabled={sending || !sessionId || !input.trim()}>
            Send
          </button>
        </div>
      </div>

      <footer className="public-chat-footer">
        <span className="muted">Powered by Doppelganger</span>
      </footer>
    </div>
  )
}
