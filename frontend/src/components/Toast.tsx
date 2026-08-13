import { createContext, useCallback, useContext, useState } from 'react'

type ToastType = 'info' | 'success' | 'error'

interface ToastItem {
  id: number
  message: string
  type: ToastType
}

type ShowToastFn = (message: string, type?: ToastType) => void

const ToastContext = createContext<ShowToastFn | null>(null)

// Replaces inline <p className="error"> for transient failures (delete
// failed, save failed) app-wide. Form-level validation errors stay
// inline where they already are — those aren't transient, they're "fix
// this field before submitting."
export function useToast(): ShowToastFn {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

let nextId = 0
const TOAST_DURATION_MS = 4000

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  function dismiss(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  const showToast = useCallback<ShowToastFn>((message, type = 'error') => {
    const id = nextId++
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), TOAST_DURATION_MS)
  }, [])

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      <div className="toast-stack">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>
            <span>{t.message}</span>
            <button type="button" className="toast-dismiss" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
