import { createContext, useContext, useState, useCallback } from 'react'

const ToastContext = createContext(null)

let nextId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++nextId
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration)
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be inside ToastProvider')
  return ctx.addToast
}

const TYPE_STYLES = {
  success: 'border-l-4 border-accent-green bg-accent-green-dim text-accent-green',
  error:   'border-l-4 border-accent-red bg-accent-red-dim text-accent-red',
  info:    'border-l-4 border-accent-teal bg-accent-teal-dim text-accent-teal',
  warning: 'border-l-4 border-accent-orange bg-accent-orange-dim text-accent-orange',
}

function ToastContainer({ toasts, onRemove }) {
  if (!toasts.length) return null
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`flex items-start justify-between gap-3 px-4 py-3 rounded-sm shadow-lg text-sm font-medium animate-slide-in ${TYPE_STYLES[t.type] || TYPE_STYLES.info}`}
        >
          <span>{t.message}</span>
          <button onClick={() => onRemove(t.id)} className="opacity-60 hover:opacity-100 shrink-0 mt-0.5">✕</button>
        </div>
      ))}
    </div>
  )
}
