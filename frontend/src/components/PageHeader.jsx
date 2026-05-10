export default function PageHeader({ title, subtitle, accent = '#00E8C6', icon: Icon, children }) {
  return (
    <div className="mb-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          {Icon && (
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
              style={{ background: `${accent}12`, border: `1px solid ${accent}20` }}
            >
              <Icon size={18} style={{ color: accent }} />
            </div>
          )}
          <div>
            <h1 className="text-xl font-bold text-text-primary leading-tight">{title}</h1>
            {subtitle && (
              <p className="mt-1 text-sm text-text-muted max-w-xl leading-relaxed">{subtitle}</p>
            )}
          </div>
        </div>
        {children && <div className="flex items-center gap-2">{children}</div>}
      </div>
      <div
        className="mt-5 h-px w-full"
        style={{ background: `linear-gradient(to right, ${accent}30, transparent)` }}
      />
    </div>
  )
}
