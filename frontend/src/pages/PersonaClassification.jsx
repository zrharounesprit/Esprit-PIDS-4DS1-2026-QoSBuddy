import { useState } from 'react'
import { useDataset } from '../context/DatasetContext'
import { useToast } from '../hooks/useToast'
import { personaApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import MetricCard from '../components/MetricCard'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Users, Gamepad2, Play, User } from 'lucide-react'
import CsvInfo from '../components/CsvInfo'

const ACCENT = '#E040FB'
const PERSONA_ICON = { Gamer: Gamepad2, Streamer: Play, Normal: User }
const PERSONA_COLOR = { Gamer: '#F04444', Streamer: '#3B82F6', Normal: '#22C55E' }

const REQUIRED = ['n_bytes','tcp_udp_ratio_packets','avg_duration','sum_n_dest_ip']

export default function PersonaClassification() {
  const { dataset } = useDataset()
  const toast = useToast()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  async function runAnalysis() {
    if (!dataset) { toast('No dataset loaded', 'error'); return }
    const missing = REQUIRED.filter(c => !dataset.columns.includes(c))
    if (missing.length) { toast(`Missing columns: ${missing.join(', ')}`, 'error'); return }

    setLoading(true); setResult(null)
    try {
      const payload = dataset.data.map(row =>
        Object.fromEntries(REQUIRED.map(c => [c, row[c]]))
      )
      const res = await personaApi.classify(payload)
      setResult(res)
      toast(`Persona detected: ${res.classification}`, 'success')
    } catch (e) {
      toast(`Classification error: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  // Build 24-hour chart data from dataset
  const chartData = dataset ? (() => {
    const rows = dataset.data.length
    return dataset.data.map((row, i) => {
      const mins = (i / rows) * 1440
      const h = Math.floor(mins / 60).toString().padStart(2,'0')
      const m = Math.floor(mins % 60).toString().padStart(2,'0')
      return { time: `${h}:${m}`, bytes: row.n_bytes ?? 0 }
    })
  })() : []

  const persona = result?.classification
  const PersonaIcon = PERSONA_ICON[persona] || User
  const personaColor = PERSONA_COLOR[persona] || ACCENT
  const profile = result?.profile

  return (
    <div className="max-w-4xl animate-fade-in">
      <PageHeader
        title="User Persona Classification"
        subtitle="Classify network users into behavioral personas — Gamer, Streamer, or Normal — using a 7-feature XGBoost model."
        accent={ACCENT}
      />

      <CsvInfo
        accent={ACCENT}
        columns={['n_bytes','tcp_udp_ratio_packets','avg_duration','sum_n_dest_ip']}
        notes="Upload traffic records for a single user (or subnet). The model aggregates all rows into one set of behavioral features, then classifies. More rows = more accurate burstiness and evening-intensity scores."
      />

      {/* Run */}
      <div className="card p-5 mb-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold text-text-primary">
              {dataset ? `Classify ${dataset.rows.toLocaleString()} traffic records` : 'No dataset loaded'}
            </div>
            <div className="text-xs text-text-muted mt-0.5">
              Requires: {REQUIRED.join(', ')}
            </div>
          </div>
          <button
            onClick={runAnalysis}
            disabled={loading || !dataset}
            className="btn-primary min-w-[160px]"
            style={{ background: loading || !dataset ? undefined : ACCENT }}
          >
            {loading ? 'Classifying…' : 'Run AI Analysis'}
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="animate-fade-in">
          {/* Persona hero */}
          <div
            className="card p-6 mb-6"
            style={{ borderColor: `${personaColor}40`, background: `${personaColor}08` }}
          >
            <div className="flex items-center gap-5">
              <div
                className="w-16 h-16 flex items-center justify-center rounded-sm"
                style={{ background: `${personaColor}15`, border: `2px solid ${personaColor}40` }}
              >
                <PersonaIcon size={28} style={{ color: personaColor }} />
              </div>
              <div>
                <div className="text-xs uppercase tracking-widest font-semibold text-text-muted mb-1">
                  Detected Persona
                </div>
                <div className="text-3xl font-bold" style={{ color: personaColor }}>
                  {persona}
                </div>
              </div>
            </div>
          </div>

          {/* Profile metrics */}
          {profile && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              {[
                { label: 'Avg Traffic Volume', value: profile.avg_traffic_bytes ? `${Number(profile.avg_traffic_bytes).toLocaleString()} B` : '—' },
                { label: 'Burstiness Index',   value: profile.burstiness_score ?? '—' },
                { label: 'Flow Duration (s)',   value: profile.avg_duration ?? '—' },
                { label: 'Unique Destinations', value: profile.destinations_contacted ?? '—' },
                { label: 'Evening Intensity',   value: profile.evening_intensity ?? '—' },
                { label: 'TCP/UDP Ratio',       value: profile.protocol_ratio ?? '—' },
              ].map(m => (
                <MetricCard key={m.label} label={m.label} value={String(m.value)} accent={personaColor} />
              ))}
            </div>
          )}

          {/* 24h traffic chart */}
          <div className="card p-5">
            <div className="section-title">24-Hour Traffic Pattern</div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData.filter((_, i) => i % Math.max(1, Math.floor(chartData.length / 200)) === 0)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                <XAxis dataKey="time" stroke="#484F58" tick={{ fontSize: 10, fill: '#7D8590' }}
                  interval={Math.floor(chartData.length / 8)} />
                <YAxis stroke="#484F58" tick={{ fontSize: 10, fill: '#7D8590' }}
                  tickFormatter={v => v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(0)}K` : v} />
                <Tooltip
                  contentStyle={{ background: '#161B22', border: '1px solid #30363D', borderRadius: 2 }}
                  labelStyle={{ color: '#7D8590', fontSize: 11 }}
                  itemStyle={{ color: personaColor, fontSize: 11 }}
                />
                <Line type="monotone" dataKey="bytes" stroke={personaColor} dot={false}
                  strokeWidth={2} name="n_bytes" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {!dataset && (
        <div className="flex flex-col items-center py-20">
          <Users size={32} className="text-text-faint mb-4" />
          <div className="text-sm text-text-muted">No dataset loaded — go to Upload first.</div>
        </div>
      )}
    </div>
  )
}
