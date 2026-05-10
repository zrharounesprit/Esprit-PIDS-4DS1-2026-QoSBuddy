import { useState, useMemo, useEffect, useRef } from 'react'
import { useDataset } from '../context/DatasetContext'
import { useToast } from '../hooks/useToast'
import { forecastApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Area
} from 'recharts'
import { TrendingUp, TrendingDown, Minus, Zap, Brain, AlertTriangle,
         CheckCircle, ChevronDown, ChevronUp, Activity } from 'lucide-react'

const ACCENT   = '#3B82F6'
const SEQ_LEN  = 24
const HORIZON  = 6

const FEATURES = [
  'n_flows','n_packets','n_bytes','sum_n_dest_asn','average_n_dest_asn',
  'sum_n_dest_ports','average_n_dest_ports','sum_n_dest_ip','average_n_dest_ip',
  'tcp_udp_ratio_packets','tcp_udp_ratio_bytes','dir_ratio_packets','dir_ratio_bytes',
  'avg_duration','avg_ttl',
]

const TREND_META = {
  Rising:   { color: '#F97316', icon: TrendingUp,   label: 'Rising'   },
  Declining:{ color: '#3B82F6', icon: TrendingDown, label: 'Declining'},
  Volatile: { color: '#EF4444', icon: Activity,     label: 'Volatile' },
  Stable:   { color: '#22C55E', icon: Minus,        label: 'Stable'   },
}

function fmt(bytes) {
  if (bytes == null || isNaN(bytes)) return '—'
  const b = Number(bytes)
  if (b >= 1e9) return `${(b/1e9).toFixed(2)} GB`
  if (b >= 1e6) return `${(b/1e6).toFixed(2)} MB`
  if (b >= 1e3) return `${(b/1e3).toFixed(1)} KB`
  return `${Math.round(b)} B`
}

function fmtShort(bytes) {
  const b = Number(bytes)
  if (b >= 1e9) return `${(b/1e9).toFixed(1)}G`
  if (b >= 1e6) return `${(b/1e6).toFixed(1)}M`
  if (b >= 1e3) return `${(b/1e3).toFixed(0)}K`
  return `${Math.round(b)}`
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-border px-3 py-2 rounded-sm text-xs shadow-lg">
      <div className="text-text-muted mb-1 font-mono">{label}</div>
      {payload.map(p => p.value != null && (
        <div key={p.dataKey} style={{ color: p.color }} className="font-mono">
          {p.name}: {fmt(p.value)} ({Number(p.value).toLocaleString()} B)
        </div>
      ))}
    </div>
  )
}

export default function Forecasting() {
  const { dataset }      = useDataset()
  const toast            = useToast()
  const autoRan          = useRef(false)

  const [startIdx,    setStartIdx]    = useState(0)
  const [ipId,        setIpId]        = useState(0)
  const [forecast,    setForecast]    = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [xai,         setXai]         = useState(null)
  const [xaiLoading,  setXaiLoading]  = useState(false)
  const [showAdv,     setShowAdv]     = useState(false)

  const maxStart = dataset ? Math.max(0, dataset.rows - SEQ_LEN) : 0

  const timeCol = useMemo(() => {
    if (!dataset) return null
    return ['time','timestamp','date','datetime'].find(c => dataset.columns.includes(c)) || null
  }, [dataset])

  const missingFeatures = useMemo(() =>
    dataset ? FEATURES.filter(f => !dataset.columns.includes(f)) : [],
  [dataset])

  // ── Auto-resolve IP ID silently ──────────────────────────────────────────────
  useEffect(() => {
    if (!dataset?.name) return
    forecastApi.ipId(dataset.name)
      .then(res => setIpId(res.ip_id))
      .catch(() => setIpId(0))
  }, [dataset?.name])

  // ── Auto-find best window silently on load ───────────────────────────────────
  useEffect(() => {
    if (!dataset || autoRan.current) return
    autoRan.current = true
    let bestIdx = 0, bestAvg = -1
    for (let i = 0; i <= dataset.rows - SEQ_LEN; i++) {
      const win = dataset.data.slice(i, i + SEQ_LEN)
      const avg = win.reduce((s, r) => s + (Number(r.n_bytes) || 0), 0) / SEQ_LEN
      if (avg > bestAvg) { bestAvg = avg; bestIdx = i }
    }
    setStartIdx(bestIdx)
  }, [dataset])

  // ── Run forecast ─────────────────────────────────────────────────────────────
  async function runForecast() {
    if (!dataset) return
    const window = dataset.data.slice(startIdx, startIdx + SEQ_LEN)
    const rows   = window.map(r => Object.fromEntries(FEATURES.map(f => [f, r[f] ?? 0])))
    setLoading(true); setForecast(null); setXai(null)
    try {
      const res = await forecastApi.run(rows, ipId)
      setForecast({ values: res.forecast, startIdx })
      toast('Forecast complete', 'success')
    } catch (e) {
      toast(`Forecast error: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  // ── Explain with AI ──────────────────────────────────────────────────────────
  async function runExplain() {
    if (!dataset || !forecast) return
    const window    = dataset.data.slice(forecast.startIdx, forecast.startIdx + SEQ_LEN)
    const histBytes = window.map(r => Number(r.n_bytes) || 0)
    setXaiLoading(true); setXai(null)
    try {
      const res = await forecastApi.explain(histBytes, forecast.values, dataset.name)
      setXai(res)
    } catch (e) {
      toast(`AI error: ${e.message}`, 'error')
    } finally {
      setXaiLoading(false)
    }
  }

  // ── Chart data ───────────────────────────────────────────────────────────────
  const chartData = useMemo(() => {
    if (!dataset || !forecast) return []
    const win  = dataset.data.slice(forecast.startIdx, forecast.startIdx + SEQ_LEN)
    const hist = win.map((r, i) => ({
      label:      timeCol ? String(r[timeCol]).slice(11,16) : `T-${SEQ_LEN - i}`,
      historical: Number(r.n_bytes) || 0,
      forecast:   null,
      isBoundary: false,
    }))
    // duplicate last historical point as first forecast anchor (no gap)
    const boundary = {
      label:      hist[hist.length - 1].label,
      historical: hist[hist.length - 1].historical,
      forecast:   hist[hist.length - 1].historical,
      isBoundary: true,
    }
    const fc = forecast.values.map((v, i) => ({
      label:      timeCol ? `+${i+1}h` : `T+${i+1}`,
      historical: null,
      forecast:   v,
      isBoundary: false,
    }))
    return [...hist, boundary, ...fc]
  }, [dataset, forecast, timeCol])

  const boundaryLabel = chartData.find(d => d.isBoundary)?.label

  // ── Stats ────────────────────────────────────────────────────────────────────
  const fcValues       = forecast?.values ?? []
  const histWindow     = dataset ? dataset.data.slice(startIdx, startIdx + SEQ_LEN) : []
  const histAvg        = histWindow.length
    ? histWindow.reduce((s,r) => s + (Number(r.n_bytes)||0), 0) / histWindow.length : 0
  const lastActual     = Number(histWindow[histWindow.length-1]?.n_bytes) || 0
  const fcAvg          = fcValues.length ? fcValues.reduce((a,b)=>a+b,0)/fcValues.length : 0
  const peakIdx        = fcValues.indexOf(Math.max(...fcValues))
  const anomalyHours   = fcValues.map((v,i) => ({h:i+1,v,flag: v > histAvg*2.5})).filter(x=>x.flag)
  const nextHourChange = fcValues[0] ? ((fcValues[0]-lastActual)/Math.max(lastActual,1)*100) : null

  if (!dataset) return (
    <div className="max-w-4xl animate-fade-in">
      <PageHeader title="Traffic Forecasting"
        subtitle="6-hour network traffic prediction using LSTM deep learning with IP-specific embeddings."
        accent={ACCENT} />
      <div className="flex flex-col items-center py-20">
        <TrendingUp size={32} className="text-text-faint mb-4" />
        <div className="text-sm text-text-muted">No dataset loaded — go to Upload first.</div>
      </div>
    </div>
  )

  if (missingFeatures.length > 0) return (
    <div className="max-w-4xl animate-fade-in">
      <PageHeader title="Traffic Forecasting"
        subtitle="6-hour network traffic prediction using LSTM deep learning with IP-specific embeddings."
        accent={ACCENT} />
      <div className="card p-5">
        <div className="text-sm font-semibold text-red-400 mb-2">Missing required columns</div>
        <div className="flex flex-wrap gap-1.5">
          {missingFeatures.map(f => (
            <span key={f} className="px-2 py-0.5 bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono rounded-sm">{f}</span>
          ))}
        </div>
      </div>
    </div>
  )

  const trendMeta = xai ? (TREND_META[xai.trend] || TREND_META.Stable) : null

  return (
    <div className="max-w-4xl animate-fade-in">
      <PageHeader
        title="Traffic Forecasting"
        subtitle="6-hour network traffic prediction using LSTM deep learning with IP-specific embeddings."
        accent={ACCENT}
      />

      {/* ── Config card ─────────────────────────────────────────────────────── */}
      <div className="card p-5 mb-6">
        {/* Window info */}
        <div className="text-xs text-text-muted font-mono bg-canvas px-3 py-2 rounded-sm border border-border mb-4">
          Analysing rows {startIdx}–{startIdx+SEQ_LEN-1} &nbsp;·&nbsp;
          Avg traffic in window: <span className="text-text font-semibold">{fmt(histAvg)}/h</span>
          &nbsp;·&nbsp; {dataset.name}
        </div>

        {/* Advanced toggle */}
        <button
          onClick={() => setShowAdv(v => !v)}
          className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text mb-3 transition-colors"
        >
          {showAdv ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
          Advanced options
        </button>

        {showAdv && (
          <div className="mb-4 p-3 bg-canvas rounded-sm border border-border space-y-3">
            <div>
              <label className="label">Lookback window start (row {startIdx})</label>
              <input type="range" min={0} max={maxStart} value={startIdx}
                onChange={e => { setStartIdx(Number(e.target.value)); setForecast(null); setXai(null) }}
                className="w-full accent-blue-500 mt-1" />
              <div className="flex justify-between text-xs text-text-faint mt-1 font-mono">
                <span>Row 0</span><span>Row {maxStart}</span>
              </div>
            </div>
            <div>
              <label className="label">IP Embedding ID</label>
              <input type="number" min={0} max={999} value={ipId}
                onChange={e => setIpId(Number(e.target.value))}
                className="input w-32 mt-1" />
            </div>
          </div>
        )}

        <button onClick={runForecast} disabled={loading}
          className="btn-primary w-full" style={{ background: loading ? undefined : ACCENT }}>
          {loading ? 'Running LSTM Forecast…' : 'Run Forecast'}
        </button>
      </div>

      {/* ── Anomaly warning ──────────────────────────────────────────────────── */}
      {anomalyHours.length > 0 && (
        <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-sm px-4 py-3 mb-5 text-xs text-red-400">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          <span>
            Anomalous spike predicted at {anomalyHours.map(x=>`+${x.h}h`).join(', ')} —
            forecast exceeds 2.5× the historical average ({fmt(histAvg)}/h).
          </span>
        </div>
      )}

      {/* ── Summary cards ───────────────────────────────────────────────────── */}
      {fcValues.length > 0 && (
        <div className="grid grid-cols-2 gap-4 mb-6 sm:grid-cols-4">
          {[
            { label: 'Avg Predicted',   value: fmt(fcAvg),                          sub: `${Math.round(fcAvg).toLocaleString()} B/h`,       accent: ACCENT    },
            { label: 'Peak Hour',       value: `+${peakIdx+1}h — ${fmt(fcValues[peakIdx])}`, sub: `${Math.round(fcValues[peakIdx]).toLocaleString()} B`, accent: '#F97316' },
            { label: 'Min Hour',        value: fmt(Math.min(...fcValues)),           sub: `${Math.round(Math.min(...fcValues)).toLocaleString()} B`, accent: '#22C55E' },
            { label: 'Next-Hour Change',value: nextHourChange != null ? `${nextHourChange>0?'+':''}${nextHourChange.toFixed(1)}%` : '—',
              sub: `${fmt(fcValues[0])} forecast`,  accent: nextHourChange > 0 ? '#F04444' : '#22C55E' },
          ].map(c => (
            <div key={c.label} className="card p-4">
              <div className="text-xs text-text-muted mb-1">{c.label}</div>
              <div className="text-lg font-bold font-mono leading-tight" style={{ color: c.accent }}>{c.value}</div>
              <div className="text-xs text-text-faint font-mono mt-0.5">{c.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Chart ───────────────────────────────────────────────────────────── */}
      {chartData.length > 0 && (
        <div className="card p-5 mb-5">
          <div className="section-title mb-3">Network Traffic — Historical → 6h Forecast</div>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
              <XAxis dataKey="label" stroke="#484F58"
                tick={{ fontSize: 10, fill: '#7D8590' }}
                interval={Math.floor(chartData.length / 8)} />
              <YAxis stroke="#484F58"
                tick={{ fontSize: 10, fill: '#7D8590' }}
                tickFormatter={v => fmtShort(v)} />
              <Tooltip content={<CustomTooltip />} />
              {boundaryLabel && (
                <ReferenceLine x={boundaryLabel} stroke="#484F58"
                  strokeDasharray="4 4" label={{ value: 'now', fill: '#7D8590', fontSize: 10 }} />
              )}
              <Line dataKey="historical" stroke="#1f77b4" strokeWidth={2}
                dot={false} name="Historical" connectNulls={false} />
              <Line dataKey="forecast" stroke={ACCENT} strokeWidth={2.5}
                dot={{ r: 4, fill: ACCENT, strokeWidth: 0 }}
                strokeDasharray="6 3" name="Forecast" connectNulls={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Forecast table ───────────────────────────────────────────────────── */}
      {fcValues.length > 0 && (
        <div className="card overflow-hidden mb-6">
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-header text-left">Hour</th>
                <th className="table-header text-left">Predicted Traffic</th>
                <th className="table-header text-left">Raw (bytes)</th>
                <th className="table-header text-left">vs. Current</th>
                <th className="table-header text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {fcValues.map((v, i) => {
                const delta   = ((v - lastActual) / Math.max(lastActual, 1) * 100)
                const isSpike = v > histAvg * 2.5
                const isLow   = v < histAvg * 0.3
                return (
                  <tr key={i} className="table-row">
                    <td className="table-cell font-mono text-blue-400 font-semibold">+{i+1}h</td>
                    <td className="table-cell font-semibold">{fmt(v)}</td>
                    <td className="table-cell font-mono text-text-muted text-xs">{Math.round(v).toLocaleString()}</td>
                    <td className="table-cell font-mono text-xs">
                      <span className={delta > 0 ? 'text-red-400' : 'text-green-400'}>
                        {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                      </span>
                    </td>
                    <td className="table-cell text-xs">
                      {isSpike
                        ? <span className="flex items-center gap-1 text-red-400"><AlertTriangle size={10}/> Spike</span>
                        : isLow
                        ? <span className="flex items-center gap-1 text-yellow-400"><AlertTriangle size={10}/> Low</span>
                        : <span className="flex items-center gap-1 text-green-400"><CheckCircle size={10}/> Normal</span>
                      }
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── AI Explanation ───────────────────────────────────────────────────── */}
      {fcValues.length > 0 && (
        <div className="card p-5 mb-6">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Brain size={15} className="text-purple-400" />
              <span className="section-title mb-0">AI Analysis</span>
            </div>
            <button onClick={runExplain} disabled={xaiLoading}
              className="flex items-center gap-1.5 text-xs px-4 py-1.5 rounded-sm border border-purple-500/40 text-purple-400 hover:bg-purple-500/10 transition-colors disabled:opacity-50">
              <Zap size={11} />
              {xaiLoading ? 'Analysing…' : xai ? 'Re-analyse' : 'Explain with AI'}
            </button>
          </div>

          {!xai && !xaiLoading && (
            <div className="text-xs text-text-faint text-center py-8">
              Click "Explain with AI" to get a detailed Gemini-powered analysis.
            </div>
          )}

          {xaiLoading && (
            <div className="text-xs text-text-muted text-center py-8 animate-pulse">
              Gemini is analysing your traffic data…
            </div>
          )}

          {xai && (
            <div className="space-y-5">

              {/* Trend + peak */}
              <div className="grid grid-cols-3 gap-4">
                {[
                  {
                    label: 'Traffic Direction',
                    value: xai.trend,
                    sub: `Over the next 6 hours`,
                    color: trendMeta?.color,
                    Icon: trendMeta?.icon,
                  },
                  {
                    label: 'Peak Hour',
                    value: `+${xai.peak_hour}h from now`,
                    sub: `${fmt(fcValues[xai.peak_hour-1])} expected`,
                    color: '#F97316',
                    Icon: TrendingUp,
                  },
                  {
                    label: 'Historical Avg',
                    value: fmt(histAvg),
                    sub: `${Math.round(histAvg).toLocaleString()} B/h`,
                    color: '#7D8590',
                    Icon: Activity,
                  },
                ].map(({ label, value, sub, color, Icon }) => (
                  <div key={label} className="bg-canvas rounded-sm border border-border p-4">
                    <div className="text-xs text-text-muted mb-2">{label}</div>
                    <div className="flex items-center gap-2">
                      {Icon && <Icon size={14} style={{ color }} />}
                      <span className="font-semibold text-sm" style={{ color }}>{value}</span>
                    </div>
                    <div className="text-xs text-text-faint mt-1">{sub}</div>
                  </div>
                ))}
              </div>

              {/* Gemini analysis */}
              <div className="bg-purple-500/5 border border-purple-500/20 rounded-sm p-4">
                <div className="flex items-center gap-1.5 mb-3 text-xs text-purple-400 font-semibold">
                  <Brain size={11} /> Gemini Analysis
                </div>
                <div className="text-sm text-text leading-relaxed whitespace-pre-line">
                  {xai.explanation}
                </div>
              </div>

              {/* Recommendations */}
              <div>
                <div className="text-xs font-semibold text-text-muted mb-2 uppercase tracking-wider">Recommendations</div>
                <div className="space-y-2">
                  {xai.recommendations.map((r, i) => (
                    <div key={i} className="flex items-start gap-2.5 text-sm bg-canvas border border-border rounded-sm px-3 py-2.5">
                      <CheckCircle size={13} className="text-blue-400 mt-0.5 shrink-0" />
                      <span className="text-text">{r}</span>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          )}
        </div>
      )}
    </div>
  )
}
