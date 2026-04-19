export default function PageHeader({ title, subtitle, accent = '#00FFD5', children }) {
  return (
    <div className="mb-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div
            className="text-xs font-semibold uppercase tracking-[0.2em] mb-2"
            style={{ color: accent }}
          >
            QoSBuddy
          </div>
          <h1 className="text-2xl font-bold text-text-primary leading-tight">{title}</h1>
          {subtitle && (
            <p className="mt-1.5 text-sm text-text-muted max-w-xl leading-relaxed">{subtitle}</p>
          )}
        </div>
        {children && <div className="flex items-center gap-2">{children}</div>}
      </div>
      <div
        className="mt-5 h-px w-full"
        style={{ background: `linear-gradient(to right, ${accent}60, transparent)` }}
      />
    </div>
  )
}
