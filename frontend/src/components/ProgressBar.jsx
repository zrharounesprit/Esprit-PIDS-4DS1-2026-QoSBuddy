export default function ProgressBar({ value, max, label, accent = '#00FFD5' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div>
      {label && (
        <div className="flex justify-between text-xs text-text-muted mb-1.5">
          <span>{label}</span>
          <span className="font-mono">{value} / {max}</span>
        </div>
      )}
      <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <div
          className="h-full transition-all duration-300 rounded-full"
          style={{ width: `${pct}%`, background: accent }}
        />
      </div>
    </div>
  )
}
