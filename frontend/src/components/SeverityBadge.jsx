const SEVERITY = {
  HIGH:             { bg: 'bg-red-500/15',     text: 'text-red-400',     dot: 'bg-red-500' },
  MEDIUM:           { bg: 'bg-orange-500/15',  text: 'text-orange-400',  dot: 'bg-orange-500' },
  LOW:              { bg: 'bg-yellow-500/15',  text: 'text-yellow-400',  dot: 'bg-yellow-500' },
  CRITICAL:         { bg: 'bg-red-700/20',     text: 'text-red-300',     dot: 'bg-red-600' },
  NORMAL:           { bg: 'bg-green-500/15',   text: 'text-green-400',   dot: 'bg-green-500' },
  OK:               { bg: 'bg-green-500/15',   text: 'text-green-400',   dot: 'bg-green-500' },
  extreme_scanner:  { bg: 'bg-red-700/20',     text: 'text-red-300',     dot: 'bg-red-600' },
  udp_suspicious:   { bg: 'bg-orange-500/15',  text: 'text-orange-400',  dot: 'bg-orange-500' },
  congestion:       { bg: 'bg-yellow-500/15',  text: 'text-yellow-400',  dot: 'bg-yellow-500' },
  normal:           { bg: 'bg-green-500/15',   text: 'text-green-400',   dot: 'bg-green-500' },
}

export default function SeverityBadge({ label }) {
  const key = (label || '').toUpperCase()
  const style = SEVERITY[key] || SEVERITY[label] || { bg: 'bg-surface-2', text: 'text-text-muted', dot: 'bg-text-faint' }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider rounded-md ${style.bg} ${style.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {label}
    </span>
  )
}
