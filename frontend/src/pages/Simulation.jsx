import { useState } from 'react'
import { useToast } from '../hooks/useToast'
import { simulationApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import MetricCard from '../components/MetricCard'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts'
import { Network, Upload as UploadIcon, Plus, X, AlertTriangle, CheckCircle } from 'lucide-react'

const ACCENT = '#00FFD5'

function MetricDelta({ label, value, threshold, unit = '' }) {
  const isHigh = Math.abs(value) > threshold
  const color = value > 0 ? (isHigh ? '#F04444' : '#F97316') : '#22C55E'
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wider text-text-muted mb-2">{label}</div>
      <div className="text-xl font-bold font-mono" style={{ color }}>
        {value > 0 ? '+' : ''}{value.toFixed(2)}{unit}
      </div>
    </div>
  )
}

export default function Simulation() {
  const toast = useToast()
  const [agentFiles, setAgentFiles] = useState([])
  const [capacity, setCapacity] = useState(4)
  const [simCount, setSimCount] = useState(1)
  const [baseResult, setBaseResult] = useState(null)
  const [whatifResult, setWhatifResult] = useState(null)
  const [personaInput, setPersonaInput] = useState('')
  const [runningBase, setRunningBase] = useState(false)
  const [runningWhatif, setRunningWhatif] = useState(false)

  async function runBase() {
    if (!agentFiles.length) { toast('Upload at least one agent CSV first', 'error'); return }
    setRunningBase(true); setBaseResult(null); setWhatifResult(null)

    try {
      const filesData = await Promise.all(
        agentFiles.map(async f => {
          const text = await f.text()
          return { name: f.name, csv: text }
        })
      )
      const res = await simulationApi.runAgents({
        files: filesData,
        capacity_gb: capacity,
        n_simulations: simCount,
      })
      setBaseResult(res)
      toast('Simulation complete', 'success')
    } catch (e) {
      toast(`Simulation error: ${e.message}`, 'error')
    } finally {
      setRunningBase(false)
    }
  }

  async function runWhatif() {
    if (!personaInput.trim()) { toast('Describe a persona first', 'error'); return }
    setRunningWhatif(true); setWhatifResult(null)
    try {
      const res = await simulationApi.agentRun({
        prompt: personaInput,
        capacity_gb: capacity,
        n_simulations: simCount,
      })
      setWhatifResult(res)
      toast('What-If scenario complete', 'success')
    } catch (e) {
      toast(`What-If error: ${e.message}`, 'error')
    } finally {
      setRunningWhatif(false)
    }
  }

  const trafficData = baseResult?.history
    ? baseResult.history.map((row, i) => ({
        t: row.time ?? i,
        traffic: row.traffic,
        load: row.load,
        latency: row.latency,
      }))
    : []

  const compareData = (baseResult && whatifResult)
    ? baseResult.history?.map((row, i) => ({
        t: row.time ?? i,
        before: row.traffic,
        after: whatifResult.simulation_result?.history?.[i]?.traffic ?? null,
      })) ?? []
    : []

  const baseStats = baseResult?.history
    ? {
        avgLoad:    (baseResult.history.reduce((a,r) => a + (r.load||0), 0) / baseResult.history.length).toFixed(2),
        avgLatency: (baseResult.history.reduce((a,r) => a + (r.latency||0), 0) / baseResult.history.length).toFixed(1),
        avgLoss:    (baseResult.history.reduce((a,r) => a + (r.packet_loss||0), 0) / baseResult.history.length * 100).toFixed(2),
      }
    : null

  const maxLoad = baseResult?.history ? Math.max(...baseResult.history.map(r => r.load || 0)) : 0

  return (
    <div className="max-w-5xl animate-fade-in">
      <PageHeader
        title="Network Simulation"
        subtitle="Agent-based network simulation. Upload user traffic CSVs to create agents, configure network capacity, and run What-If scenarios with LLM-generated personas."
        accent={ACCENT}
      />

      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Agent upload */}
        <div className="card p-5">
          <div className="section-title">Agent CSVs</div>
          <div
            className="border-2 border-dashed border-border hover:border-accent-teal-border rounded-sm p-5 text-center cursor-pointer transition-colors mb-3"
            onClick={() => document.getElementById('agent-upload').click()}
          >
            <UploadIcon size={18} className="text-text-faint mx-auto mb-2" />
            <div className="text-xs text-text-muted">Click to add agent CSV files</div>
          </div>
          <input id="agent-upload" type="file" accept=".csv" multiple className="hidden"
            onChange={e => setAgentFiles(prev => [...prev, ...Array.from(e.target.files)])} />

          {agentFiles.length > 0 && (
            <div className="flex flex-col gap-1.5">
              {agentFiles.map((f, i) => (
                <div key={i} className="flex items-center justify-between px-3 py-2 bg-canvas rounded-sm border border-border">
                  <span className="text-xs font-mono text-text-muted truncate">{f.name}</span>
                  <button onClick={() => setAgentFiles(prev => prev.filter((_,j) => j !== i))}
                    className="text-text-faint hover:text-red-400 transition-colors ml-2">
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Network config */}
        <div className="card p-5">
          <div className="section-title">Network Configuration</div>
          <div className="space-y-4">
            <div>
              <label className="label">Capacity: {capacity} Mb/s</label>
              <input type="range" min={1} max={10} value={capacity}
                onChange={e => setCapacity(Number(e.target.value))}
                className="w-full accent-teal-400" />
              <div className="flex justify-between text-xs text-text-faint mt-1 font-mono">
                <span>1 Mb</span><span>10 Mb</span>
              </div>
            </div>
            <div>
              <label className="label">Number of Simulations: {simCount}</label>
              <input type="range" min={1} max={20} value={simCount}
                onChange={e => setSimCount(Number(e.target.value))}
                className="w-full accent-teal-400" />
              <div className="flex justify-between text-xs text-text-faint mt-1 font-mono">
                <span>1</span><span>20</span>
              </div>
            </div>
            <button
              onClick={runBase}
              disabled={runningBase || !agentFiles.length}
              className="btn-primary w-full"
              style={{ background: runningBase || !agentFiles.length ? undefined : ACCENT, color: '#0D1117' }}
            >
              {runningBase ? 'Running…' : 'Run Simulation'}
            </button>
          </div>
        </div>
      </div>

      {/* Base results */}
      {baseStats && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-5">
            <MetricCard label="Avg Load" value={baseStats.avgLoad} accent={ACCENT} />
            <MetricCard label="Avg Latency (ms)" value={baseStats.avgLatency} accent="#F97316" />
            <MetricCard label="Avg Packet Loss (%)" value={baseStats.avgLoss} accent="#F04444" />
          </div>

          <div className="card p-5 mb-6">
            <div className="section-title">Traffic Timeline</div>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={trafficData.filter((_, i) => i % Math.max(1, Math.floor(trafficData.length/300)) === 0)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                <XAxis dataKey="t" stroke="#484F58" tick={{ fontSize: 10, fill: '#7D8590' }} />
                <YAxis stroke="#484F58" tick={{ fontSize: 10, fill: '#7D8590' }}
                  tickFormatter={v => v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(0)}K` : v} />
                <Tooltip contentStyle={{ background: '#161B22', border: '1px solid #30363D' }}
                  labelStyle={{ color: '#7D8590', fontSize: 11 }} itemStyle={{ fontSize: 11 }} />
                <Line dataKey="traffic" stroke={ACCENT} strokeWidth={2} dot={false} name="Traffic" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* What-if */}
      {baseResult && (
        <div className="card p-5 mb-6">
          <div className="section-title">What-If: Add a New User</div>
          <div className="flex gap-3 mb-4">
            <input
              className="input flex-1"
              placeholder="e.g., a gamer who plays at night, a 4K streamer on weekends…"
              value={personaInput}
              onChange={e => { setPersonaInput(e.target.value); setWhatifResult(null) }}
            />
            <button
              onClick={runWhatif}
              disabled={runningWhatif || !personaInput.trim()}
              className="btn-primary flex items-center gap-2 min-w-[160px]"
              style={{ background: runningWhatif ? undefined : '#8B7CF8' }}
            >
              <Plus size={14} />
              {runningWhatif ? 'Running…' : 'Run What-If'}
            </button>
          </div>

          {whatifResult && (
            <div className="animate-fade-in">
              {whatifResult.summary && (
                <div className="bg-canvas border border-border px-4 py-3 rounded-sm text-sm text-text-muted mb-4 leading-relaxed">
                  {whatifResult.summary}
                </div>
              )}

              {compareData.length > 0 && (
                <>
                  <div className="section-title">Before vs. After</div>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={compareData.filter((_, i) => i % Math.max(1, Math.floor(compareData.length/200)) === 0)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                      <XAxis dataKey="t" stroke="#484F58" tick={{ fontSize: 10, fill: '#7D8590' }} />
                      <YAxis stroke="#484F58" tick={{ fontSize: 10, fill: '#7D8590' }} />
                      <Tooltip contentStyle={{ background: '#161B22', border: '1px solid #30363D' }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line dataKey="before" stroke="#7D8590" strokeWidth={2} dot={false} name="Before" />
                      <Line dataKey="after" stroke={ACCENT} strokeWidth={2} dot={false} name="After" />
                    </LineChart>
                  </ResponsiveContainer>
                </>
              )}

              {/* QoS verdict */}
              <div className="mt-4">
                {whatifResult.simulation_result?.max_load > 0.85
                  ? <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-sm">
                      <AlertTriangle size={14} /> Adding this user violates QoS thresholds (load &gt; 85%)
                    </div>
                  : <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/30 text-green-400 text-sm rounded-sm">
                      <CheckCircle size={14} /> This user can be added without violating QoS thresholds
                    </div>
                }
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
