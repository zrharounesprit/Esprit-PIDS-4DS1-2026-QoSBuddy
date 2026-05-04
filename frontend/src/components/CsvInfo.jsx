import { useState } from 'react'
import { Info, ChevronDown, ChevronUp } from 'lucide-react'

/**
 * CsvInfo — collapsible "what CSV do I need?" tooltip card.
 *
 * Props:
 *   columns  – string[]   required column names
 *   notes    – string     optional extra guidance
 *   accent   – string     hex accent colour (matches page theme)
 */
export default function CsvInfo({ columns = [], notes, accent = '#00FFD5' }) {
  const [open, setOpen] = useState(false)

  return (
    <div
      className="card mb-5 overflow-hidden"
      style={{ borderColor: `${accent}30` }}
    >
      {/* Header row — always visible */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-surface-2 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Info size={13} style={{ color: accent }} />
          <span className="text-xs font-semibold text-text-muted">What CSV columns does this model need?</span>
        </div>
        {open
          ? <ChevronUp size={13} className="text-text-faint" />
          : <ChevronDown size={13} className="text-text-faint" />}
      </button>

      {/* Expanded body */}
      {open && (
        <div className="px-4 pb-4 border-t border-border-subtle">
          <div className="flex flex-wrap gap-1.5 mt-3">
            {columns.map(col => (
              <span
                key={col}
                className="px-2 py-0.5 bg-canvas border border-border text-xs font-mono rounded-sm"
                style={{ color: accent }}
              >
                {col}
              </span>
            ))}
          </div>
          {notes && (
            <p className="mt-3 text-xs text-text-faint leading-relaxed">
              {notes}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
