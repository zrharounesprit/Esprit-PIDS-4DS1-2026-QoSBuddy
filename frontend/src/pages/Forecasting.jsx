import { useState, useMemo } from 'react'
import { useDataset } from '../context/DatasetContext'
import { useToast } from '../hooks/useToast'
import { forecastApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import MetricCard from '../components/MetricCard'
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import { TrendingUp } from 'lucide-react'

const ACCENT = '#3B82F6'
const SEQ_LEN = 24
const HORIZON = 6

const FEATURES = [
  'n_flows','n_packets','n_bytes','sum_n_dest_asn','average_n_dest_asn',
  'sum_n_dest_ports','average_n_dest_ports','sum_n_dest_ip','average_n_dest_ip',
  'tcp_udp_ratio_packets','tcp_udp_ratio_bytes','dir_ratio_packets','dir_ratio_bytes',
  'avg_duration','avg_ttl',
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-border px-3 py-2 rounded-sm text-xs">
      <div className="text-text-muted mb-1">{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color }} className="font-mono">
          {p.name}: {Number(p.value).toLocaleString()}
        </div>
      ))}
    </div>
  )
}

export default function Forecasting() {
  const { dataset } = useDataset()
  const toast = useToast()
  const [startIdx, setStartIdx] = useState(0)
  const [ipId, setIpId] = useState(0)
  const [forecast, setForecast] = useState(null)
  const [loading, setLoading] = useState(false)

  const maxStart = dataset ? Math.max(0, dataset.rows - SEQ_LEN) : 0

  // Detect time column
  const timeCol = useMemo(() => {
    if (!dataset) return null
    return ['time','timestamp','date','datetime'].find(c => dataset.columns.includes(c)) || null
  }, [dataset])

  // Missing features check
  const missingFeatures = useMemo(() =>
    dataset ? FEATURES.filter(f => !dataset.columns.includes(f)) : [],
  [dataset])

  async function runForecast() {
    if (!dataset) return
    const window = dataset.data.slice(startIdx, startIdx + SEQ_LEN)
    const rows = window.map(r => Object.fromEntries(FEATURES.map(f => [f, r[f] ?? 0])))
    setLoading(true); setForecast(null)
    try {
      const res = await forecastApi.run(rows, ipId)
      setForecast({ values: res.forecast, startIdx })
      toast('Forecast complete', 'success')
    } catch (e) {
      toast(`Forecast API error: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  // Build chart data
  const chartData = useMemo(() => {
    if (!dataset || !forecast) return []
    const window = dataset.data.slice(forecast.startIdx, forecast.startIdx + SEQ_LEN)
    const hist = window.map((r, i) => ({
      label: timeCol ? String(r[timeCol]) : `T-${SEQ_LEN - i}`,
      historical: r.n_bytes ?? 0,
      forecast: null,
    }))
    const lastTime = timeCol ? window[window.length - 1]?.[timeCol] : null
    const fc = forecast.values.map((v, i) => ({
      label: lastTime ? `+${i+1}h` : `T+${i+1}`,
      historical: null,
      forecast: v,
    }))
    return [...hist, ...fc]
  }, [dataset, forecast, timeCol])

  const fcValues = forecast?.values ?? []
  const lastHistorical = dataset?.data[startIdx + SEQ_LEN - 1]?.n_bytes ?? 0
  const trend = fcValues[0] != null
    ? ((fcValues[0] - lastHistorical) / Math.max(lastHistorical, 1) * 100)
    : null

  return (
    <div className="max-w-4xl animate-fade-in">
      <PageHeader
        title="Traffic Forecasting"
        subtitle="Predict future network traffic using an LSTM model with IP embedding. Uses a 24-hour lookback to forecast the next 6 hours."
        accent={ACCENT}
      />

      {!dataset ? (
        <div className="flex flex-col items-center py-20">
          <TrendingUp size={32} className="text-text-faint mb-4" />
          <div className="text-sm text-text-muted">No dataset loaded — go to Upload first.</div>
        </div>
      ) : missingFeatures.length > 0 ? (
        <div className="card p-5">
          <div className="text-sm font-semibold text-red-400 mb-2">Missing required columns</div>
          <div className="flex flex-wrap gap-1.5">
            {missingFeatures.map(f => (
              <span key={f} className="px-2 py-0.5 bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono rounded-sm">{f}</span>
            ))}
          </div>
        </div>
      ) : (
        <>
          {/* Config */}
          <div className="card p-5 mb-6">
            <div className="grid grid-cols-2 gap-5 mb-5">
              <div>
                <label className="label">Lookback window start (row {startIdx})</label>
                <input
                  type="range" min={0} max={maxStart} value={startIdx}
                  onChange={e => { setStartIdx(Number(e.target.value)); setForecast(null) }}
                  className="w-full accent-blue-500"
                />
                <div className="flex justify-between text-xs text-text-faint mt-1 font-mono">
                  <span>Row 0</span><span>Row {maxStart}</span>
                </div>
              </div>
              <div>
                <label className="label">IP Embedding ID (0 = default)</label>
                <input
                  type="number" min={0} max={999} value={ipId}
                  onChange={e => setIpId(Number(e.target.value))}
                  className="input"
                />
              </div>
            </div>
            <div className="text-xs text-text-muted mb-5 font-mono bg-canvas px-3 py-2 rounded-sm border border-border">
              Window: rows {startIdx}–{startIdx + SEQ_LEN - 1} &nbsp;·&nbsp;
              Forecasting rows {startIdx + SEQ_LEN}–{startIdx + SEQ_LEN + HORIZON - 1}
            </div>
            <button
              onClick={runForecast}
              disabled={loading}
              className="btn-primary w-full"
              style={{ background: loading ? undefined : ACCENT }}
            >
              {loading ? 'Running LSTM Forecast…' : 'Run Forecast'}
            </button>
          </div>

          {/* Metrics */}
          {fcValues.length > 0 && (
            <div className="grid grid-cols-4 gap-4 mb-6">
              <MetricCard label="Avg Predicted" value={`${Math.round(fcValues.reduce((a,b)=>a+b,0)/fcValues.length).toLocaleString()} B`} accent={ACCENT} />
              <MetricCard label="Peak Hour" value={`${Math.round(Math.max(...fcValues)).toLocaleString()} B`} accent="#F97316" />
              <MetricCard label="Min Hour" value={`${Math.round(Math.min(...fcValues)).toLocaleString()} B`} accent="#22C55E" />
              <MetricCard label="Next-Hour Trend" value={trend != null ? `${trend > 0 ? '+' : ''}${trend.toFixed(1)}%` : '—'} accent={trend > 0 ? '#F04444' : '#22C55E'} />
            </div>
          )}

          {/* Chart */}
          {chartData.length > 0 && (
            <div className="card p-5 mb-5">
              <div className="section-title">n_bytes: Historical → Forecast</div>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                  <XAxis dataKey="label" stroke="#484F58" tick={{ fontSize: 10, fill: '#7D8590' }}
                    interval={Math.floor(chartData.length / 8)} />
                  <YAxis stroke="#484F58" tick={{ fontSize: 10, fill: '#7D8590' }}
                    tickFormatter={v => v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(0)}K` : v} />
                  <Tooltip content={<CustomTooltip />} />
                  <ReferenceLine x={`T-1`} stroke="#30363D" strokeDasharray="4 4" />
                  <Line dataKey="historical" stroke="#1f77b4" strokeWidth={2} dot={false} name="Historical" connectNulls={false} />
                  <Line dataKey="forecast" stroke={ACCENT} strokeWidth={2.5} dot={{ r: 5, fill: ACCENT }}
                    strokeDasharray="6 3" name="Forecast" connectNulls={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Forecast table */}
          {fcValues.length > 0 && (
            <div className="card overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="table-header text-left">Horizon</th>
                    <th className="table-header text-left">Predicted n_bytes</th>
                    <th className="table-header text-left">vs. Last Actual</th>
                  </tr>
                </thead>
                <tbody>
                  {fcValues.map((v, i) => {
                    const delta = ((v - lastHistorical) / Math.max(lastHistorical, 1) * 100)
                    return (
                      <tr key={i} className="table-row">
                        <td className="table-cell font-mono text-blue-400">+{i+1}h</td>
                        <td className="table-cell font-mono">{Math.round(v).toLocaleString()}</td>
                        <td className="table-cell font-mono text-xs">
                          <span className={delta > 0 ? 'text-red-400' : 'text-green-400'}>
                            {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
