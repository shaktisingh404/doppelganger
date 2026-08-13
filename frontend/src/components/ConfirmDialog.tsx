import { createContext, useCallback, useContext, useRef, useState } from 'react'

interface ConfirmOptions {
  title?: string
  message: string
  confirmLabel?: string
  danger?: boolean
}

type ConfirmFn = (options: ConfirmOptions | string) => Promise<boolean>

const ConfirmContext = createContext<ConfirmFn | null>(null)

// Replaces every window.confirm() call with a real modal matching the
// design system instead of the browser's native dialog. Usage mirrors
// window.confirm's call-site shape closely (just async now):
//   if (!(await confirm('Delete this? This can't be undone.'))) return
export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used within ConfirmProvider')
  return ctx
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null)
  const resolveRef = useRef<((value: boolean) => void) | null>(null)

  const confirm = useCallback<ConfirmFn>((opts) => {
    setOptions(typeof opts === 'string' ? { message: opts } : opts)
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve
    })
  }, [])

  function close(result: boolean) {
    resolveRef.current?.(result)
    setOptions(null)
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {options && (
        <div className="modal-overlay" onClick={() => close(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            {options.title && <h3>{options.title}</h3>}
            <p>{options.message}</p>
            <div className="modal-actions">
              <button type="button" className="link-button" onClick={() => close(false)}>
                Cancel
              </button>
              <button
                type="button"
                className={options.danger ? 'primary danger-btn' : 'primary'}
                onClick={() => close(true)}
              >
                {options.confirmLabel ?? 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}
