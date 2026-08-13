import { useState } from 'react'
import { login, register, setAuthToken } from '../api'
import type { UserPublic } from '../types'

interface Props {
  onAuthenticated: (user: UserPublic) => void
}

export function AuthView({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const token = mode === 'login' ? await login(email, password) : await register(email, password)
      setAuthToken(token.access_token)
      onAuthenticated(token.user)
    } catch (err) {
      setError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="form auth-form" onSubmit={handleSubmit}>
        <h1 className="brand">Doppelganger</h1>
        <p className="muted">{mode === 'login' ? 'Sign in to your assistants.' : 'Create an account to get started.'}</p>

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            minLength={8}
            required
          />
        </label>

        {error && <p className="error">{error}</p>}

        <button type="submit" className="primary" disabled={submitting}>
          {submitting ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>

        <button
          type="button"
          className="link-button"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError(null)
          }}
        >
          {mode === 'login' ? "Don't have an account? Register" : 'Already have an account? Sign in'}
        </button>
      </form>
    </div>
  )
}
