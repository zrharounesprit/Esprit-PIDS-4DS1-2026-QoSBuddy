export default function MetricCard({ label, value, sub, accent = '#7D8590', icon: Icon }) {
  return (
    <div className="card p-5 flex flex-col gap-1">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">{label}</span>
        {Icon && <Icon size={14} style={{ color: accent }} />}
      </div>
      <div className="text-2xl font-bold font-mono" style={{ color: accent }}>
        {value ?? '—'}
      </div>
      {sub && <div className="text-xs text-text-faint mt-0.5">{sub}</div>}
    </div>
  )
}
