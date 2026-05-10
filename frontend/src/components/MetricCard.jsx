export default function MetricCard({ label, value, sub, accent = '#6B7280', icon: Icon }) {
  return (
    <div className="card-elevated p-5 flex flex-col gap-1">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">{label}</span>
        {Icon && (
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center"
            style={{ background: `${accent}12`, border: `1px solid ${accent}20` }}
          >
            <Icon size={13} style={{ color: accent }} />
          </div>
        )}
      </div>
      <div className="text-2xl font-bold font-mono" style={{ color: accent }}>
        {value ?? '—'}
      </div>
      {sub && <div className="text-xs text-text-faint mt-0.5">{sub}</div>}
    </div>
  )
}
