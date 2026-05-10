import { useState, useEffect, useRef } from 'react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import {
  Play, Pause, RotateCcw, AlertTriangle, CheckCircle,
  Activity, Wifi, ShieldCheck, Leaf, Sparkles,
  Stethoscope, Gavel, Clock, TrendingUp, X, Zap,
} from 'lucide-react'
import PageHeader from '../components/PageHeader'

const API    = 'http://127.0.0.1:8004'
const ACCENT = '#22C55E'

const AGENT_CFG = {
  ECO:         { color: '#22C55E', desc: 'Energy Optimizer' },
  RELIABILITY: { color: '#3B82F6', desc: 'QoS Guardian'    },
  COST:        { color: '#F59E0B', desc: 'FinOps Analyst'   },
}

function fmt(b) {
  if (!b && b !== 0) return '—'
  if (b >= 1e9) return `${(b/1e9).toFixed(2)} GB`
  if (b >= 1e6) return `${(b/1e6).toFixed(1)} MB`
  if (b >= 1e3) return `${(b/1e3).toFixed(1)} KB`
  return `${Math.round(b)} B`
}
const loadColor = p => p > 85 ? '#EF4444' : p > 60 ? '#F59E0B' : '#22C55E'
const loadLabel = p => p > 85 ? 'Critical' : p > 60 ? 'Warning' : 'Healthy'

const CSS = `
  @keyframes ap-blink   { 0%,100%{opacity:1} 50%{opacity:.25} }
  @keyframes ap-float   { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)} }
  @keyframes ap-in      { from{opacity:0;transform:translateY(18px)} to{opacity:1;transform:translateY(0)} }
  @keyframes ap-shimmer { 0%{background-position:-300% center} 100%{background-position:300% center} }
  @keyframes ap-orbit   { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
  @keyframes ap-slide   { from{opacity:0;transform:translateY(-10px)} to{opacity:1;transform:translateY(0)} }

  .ap-blink   { animation: ap-blink 1.4s ease-in-out infinite; }
  .ap-float   { animation: ap-float 3s ease-in-out infinite; }
  .ap-card-in { animation: ap-in .55s cubic-bezier(.16,1,.3,1) both; }
  .ap-slide   { animation: ap-slide .4s ease both; }
  .ap-shimmer {
    background: linear-gradient(90deg,transparent 0%,rgba(255,255,255,.07) 50%,transparent 100%);
    background-size: 300% 100%;
    animation: ap-shimmer 2s linear infinite;
  }
`

export default function AutoPilot() {
  const [meta, setMeta]               = useState(null)
  const [fullSeries, setFullSeries]   = useState([])
  const [bySegSeries, setBySegSeries] = useState([])

  const [cursor, setCursor]   = useState(24)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed]     = useState(1)
  const tickRef               = useRef(null)

  const [capacityMbph] = useState(2000)
  const [numNodes]     = useState(8)
  const [sleepCount, setSleepCount] = useState(0)
  const activeNodes = numNodes - sleepCount

  const [decision, setDecision]           = useState(null)
  const [decideLoading, setDecideLoading] = useState(false)
  const lastDecideAt                      = useRef(-999)

  const [sentinel, setSentinel] = useState({ delta_pct: 0, status: 'normal', consecutive_bad: 0 })
  const lastForecast            = useRef([])

  const [medic, setMedic]             = useState(null)
  const [medicActive, setMedicActive] = useState(false)
  const medicCooldownRef              = useRef(false)

  const [kwhSaved, setKwhSaved]               = useState(0)
  const [injectedEvents, setInjectedEvents]   = useState({})
  const [decisionHistory, setDecisionHistory] = useState([])
  const [loadProgress, setLoadProgress]       = useState(0)

  useEffect(() => {
    ;(async () => {
      const init = await fetch(`${API}/autopilot/init`).then(r => r.json())
      setMeta(init)
      const total = init.history_hours
      const all   = new Array(total)
      let done    = 0
      await Promise.all(Array.from({ length: total }, (_, h) =>
        fetch(`${API}/autopilot/tick?hour=${h}`)
          .then(r => r.json())
          .then(j => { all[h] = j; done++; setLoadProgress(Math.round(done/total*100)) })
      ))
      setFullSeries(all.map(t => t.total_bytes))
      setBySegSeries(all.map((t, i) => ({ hour: i, ...t.by_segment })))
    })()
  }, [])

  useEffect(() => {
    clearInterval(tickRef.current)
    if (!playing || !meta) return
    tickRef.current = setInterval(() => {
      setCursor(c => {
        const next = c + 1
        if (next >= (meta?.history_hours || 168)) { setPlaying(false); return c }
        return next
      })
    }, 2000 / speed)
    return () => clearInterval(tickRef.current)
  }, [playing, speed, meta])

  useEffect(() => {
    if (!fullSeries.length) return
    if (Math.abs(cursor - lastDecideAt.current) < 12) return
    lastDecideAt.current = cursor
    runDecision()
    // eslint-disable-next-line
  }, [cursor, fullSeries])

  useEffect(() => {
    if (!fullSeries.length || cursor < 6) return
    runSentinel()
    // eslint-disable-next-line
  }, [cursor])

  useEffect(() => {
    if (!playing) return
    setKwhSaved(s => s + sleepCount * 1.5 / (3600 / 2))
  }, [cursor, playing, sleepCount])

  async function runDecision() {
    if (cursor < 24 || !fullSeries.length) return
    const history = fullSeries.slice(Math.max(0, cursor - 24), cursor)
    setDecideLoading(true)
    try {
      const fcRes  = await fetch(`${API}/autopilot/lstm-forecast?cursor=${cursor}`)
      const fcData = await fcRes.json()
      const forecast = fcData.forecast || []
      lastForecast.current = forecast

      const res  = await fetch(`${API}/autopilot/decide`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history_24h: history, forecast_6h: forecast, capacity_mbph: capacityMbph, num_nodes: numNodes, failed_nodes_count: 0 }),
      })
      const data = await res.json()
      setDecision(data)
      setSleepCount(typeof data.judge_choice === 'number' ? data.judge_choice : 0)
      setDecisionHistory(prev => [{
        hour: cursor, judge_choice: data.judge_choice,
        agents: data.agents || [], judge_reasoning: data.judge_reasoning || '',
        timestamp: new Date().toLocaleTimeString(),
      }, ...prev].slice(0, 12))
    } catch (e) { console.warn('decide', e) }
    finally { setDecideLoading(false) }
  }

  async function runSentinel() {
    if (!lastForecast.current.length) return
    const actualRecent = fullSeries.slice(Math.max(0, cursor-3), cursor).map(v => v * (injectedEvents[cursor]||1))
    const forecastBack = lastForecast.current.slice(0, actualRecent.length)
    try {
      const res  = await fetch(`${API}/autopilot/sentinel`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actual_recent: actualRecent, predicted_recent: forecastBack, threshold_pct: 30 }),
      })
      const data = await res.json()
      setSentinel(data)
      if (data.status === 'anomaly' && !medicActive && !medicCooldownRef.current) triggerMedic()
    } catch (_) {}
  }

  async function triggerMedic() {
    medicCooldownRef.current = true
    setMedicActive(true)
    const cap = capacityMbph * 1_000_000
    const currentLoad = (fullSeries[cursor]||0) * (injectedEvents[cursor]||1)
    const fcPeak = lastForecast.current.length ? Math.max(...lastForecast.current) : currentLoad
    try {
      const res  = await fetch(`${API}/autopilot/medic`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_load_pct: (currentLoad/cap)*100,
          forecast_peak_pct: (fcPeak/cap)*100,
          nodes_active: activeNodes, nodes_total: numNodes,
        }),
      })
      const data = await res.json()
      setMedic(data)
      setSleepCount(0)
    } catch (_) {}
    setTimeout(() => { medicCooldownRef.current = false }, 90_000)
  }

  function reset() {
    setPlaying(false); setCursor(24); setKwhSaved(0)
    setSentinel({ delta_pct: 0, status: 'normal', consecutive_bad: 0 })
    setDecision(null); setMedic(null); setMedicActive(false)
    setSleepCount(0); setInjectedEvents({}); setDecisionHistory([])
    lastDecideAt.current = -999; lastForecast.current = []
    medicCooldownRef.current = false
  }

  const capacityBytes     = capacityMbph * 1_000_000
  const effectiveCapacity = capacityBytes * (activeNodes / numNodes)
  const currentLoadBytes  = (fullSeries[cursor]||0) * (injectedEvents[cursor]||1)
  const currentLoadPct    = effectiveCapacity > 0 ? (currentLoadBytes / effectiveCapacity) * 100 : 0
  const currentColor      = loadColor(currentLoadPct)

  const chartData = (() => {
    if (!fullSeries.length || cursor < 24) return []
    const out = []
    for (let i = 0; i < 24; i++) {
      const h = cursor - 24 + i
      out.push({ label: `-${24-i}h`, actual: (fullSeries[h]||0)*(injectedEvents[h]||1), capacity: effectiveCapacity })
    }
    const fc = lastForecast.current
    for (let i = 0; i < 6; i++) out.push({ label: `+${i+1}h`, forecast: fc[i]||null, capacity: effectiveCapacity })
    return out
  })()

  if (!meta || !fullSeries.length) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[65vh] gap-6">
        <style>{CSS}</style>
        <div className="relative w-20 h-20">
          <svg viewBox="0 0 80 80" style={{ width: 80, height: 80, animation: 'ap-orbit 2s linear infinite', transformOrigin: '40px 40px' }}>
            <style>{'@keyframes ap-orbit{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}'}</style>
            <circle cx="40" cy="40" r="36" fill="none" stroke="#22C55E20" strokeWidth="1.5"/>
            <circle cx="40" cy="4" r="5" fill="#22C55E" style={{ filter: 'drop-shadow(0 0 6px #22C55E)' }}/>
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <Leaf size={20} className="ap-float" style={{ color: '#22C55E' }}/>
          </div>
        </div>
        <div className="text-center">
          <div className="text-sm font-bold text-text-primary mb-1">Initializing NEXUS Stream</div>
          <div className="text-[11px] text-text-faint">{loadProgress}% · {meta?.history_hours||'…'}h · {meta?.ips_count||'…'} real IPs</div>
        </div>
        <div className="w-56 h-px overflow-hidden" style={{ background: '#21262d' }}>
          <div className="h-full transition-all duration-300" style={{ width: `${loadProgress}%`, background: 'linear-gradient(90deg,#166534,#22C55E)' }}/>
        </div>
      </div>
    )
  }

  const sentColor = sentinel.status === 'anomaly' ? '#EF4444' : sentinel.status === 'warning' ? '#F59E0B' : '#22C55E'

  return (
    <div className="space-y-5 relative pb-10">
      <style>{CSS}</style>

      <PageHeader
        title="Green Auto-Pilot"
        subtitle={`4 LLM agents (Gemini 2.0 Flash) · LangGraph fan-out · LSTM 5.88% MAPE · ${meta.ips_count} real IPs`}
        accent={ACCENT}
      />

      {/* Status strip */}
      <div className="flex items-center gap-3 -mt-3 text-[10px] uppercase tracking-widest font-mono" style={{ color: '#6e7681' }}>
        <span className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${playing ? 'ap-blink' : ''}`} style={{ background: playing ? '#22C55E' : '#30363d' }}/>
          {playing ? 'LIVE' : 'PAUSED'}
        </span>
        · <span>H {cursor} / {meta.history_hours}</span>
        · <span>{speed}×</span>
        · <span style={{ color: sentColor }}>{sentinel.status.toUpperCase()} δ{sentinel.delta_pct}%</span>
        {decideLoading && <> · <span className="text-purple-400 ap-blink">COUNCIL IN SESSION</span></>}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap px-4 py-3 rounded-sm" style={{ background: '#0d1117', border: '1px solid #21262d' }}>
        <button onClick={() => setPlaying(p => !p)}
          className="flex items-center gap-2 px-4 py-2 rounded-sm text-sm font-bold transition-all"
          style={{ background: playing ? 'transparent' : ACCENT, color: playing ? '#8b949e' : '#000', border: playing ? '1px solid #30363d' : 'none' }}>
          {playing ? <Pause size={13}/> : <Play size={13}/>}
          {playing ? 'Pause' : 'Play'}
        </button>
        <button onClick={reset} title="Reset" className="p-2 rounded-sm transition-colors" style={{ border: '1px solid #30363d', color: '#6e7681' }}>
          <RotateCcw size={13}/>
        </button>
        <div className="flex items-center gap-1">
          <span className="text-[10px] mr-1" style={{ color: '#6e7681' }}>Speed</span>
          {[1,2,5,10].map(s => (
            <button key={s} onClick={() => setSpeed(s)}
              className="px-2.5 py-1 text-[11px] rounded-sm font-mono transition-all"
              style={{ background: speed===s ? '#22C55E' : 'transparent', color: speed===s ? '#000' : '#6e7681', border: speed===s ? 'none' : '1px solid #30363d', fontWeight: speed===s ? 700 : 400 }}>
              {s}×
            </button>
          ))}
        </div>
        <div className="flex-1 flex items-center gap-2.5 min-w-[140px]">
          <TrendingUp size={11} style={{ color: '#6e7681' }}/>
          <input type="range" min={24} max={meta.history_hours-6} value={cursor}
            onChange={e => { setPlaying(false); setCursor(+e.target.value) }}
            className="flex-1 accent-green-500" style={{ height: 4 }}/>
          <span className="text-[10px] font-mono w-12 text-right" style={{ color: '#6e7681' }}>{cursor}h</span>
        </div>
        <button onClick={() => setInjectedEvents(p => ({ ...p, [cursor+1]: 4.0 }))}
          className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold rounded-sm transition-all"
          style={{ border: '1px solid rgba(239,68,68,.4)', color: '#f87171' }}>
          <AlertTriangle size={11}/> Inject Anomaly
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { label: 'Network Load',  value: `${currentLoadPct.toFixed(0)}%`,  sub: loadLabel(currentLoadPct),                     color: currentColor,  fill: currentLoadPct/100 },
          { label: 'Active Nodes',  value: `${activeNodes}/${numNodes}`,      sub: sleepCount ? `${sleepCount} eco-sleep` : 'all active', color: sleepCount ? '#22C55E' : '#3B82F6', fill: activeNodes/numNodes },
          { label: 'Energy Saved',  value: `${kwhSaved.toFixed(2)} kWh`,     sub: 'this session',                                color: '#22C55E',     fill: Math.min(kwhSaved/15,1) },
          { label: 'Sentinel',      value: sentinel.status.toUpperCase(),    sub: `δ ${sentinel.delta_pct}%`,                   color: sentColor,     fill: Math.min(sentinel.delta_pct/60,1) },
          { label: 'Last Ruling',   value: decision ? `sleep ${decision.judge_choice}` : '—', sub: `${decisionHistory.length} rounds`, color: '#A855F7', fill: decision ? decision.judge_choice/numNodes : 0 },
        ].map(k => <KPICard key={k.label} {...k}/>)}
      </div>

      {/* 3D NEXUS TOPOLOGY */}
      <NexusTopology
        numNodes={numNodes}
        activeNodes={activeNodes}
        currentColor={currentColor}
        currentLoadPct={currentLoadPct}
        sleepCount={sleepCount}
      />

      {/* AGENT COUNCIL CHAMBER */}
      <AgentCouncil decision={decision} loading={decideLoading} decisionCount={decisionHistory.length}/>

      {/* CHART + SENTINEL */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 260px' }}>
        <div className="rounded-sm p-4" style={{ background: '#0d1117', border: '1px solid #21262d' }}>
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-2" style={{ color: '#6e7681' }}>
              <Activity size={11} style={{ color: '#3B82F6' }}/> Traffic · 24h History + 6h LSTM Forecast
            </span>
            <span className="text-[10px] font-mono" style={{ color: currentColor }}>{fmt(currentLoadBytes)}/h</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={chartData} margin={{ top:4, right:8, left:8, bottom:0 }}>
              <defs>
                <linearGradient id="gA" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3B82F6" stopOpacity={.35}/>
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={.02}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#21262d"/>
              <XAxis dataKey="label" tick={{ fontSize:9, fill:'#6e7681' }} interval={3}/>
              <YAxis tickFormatter={fmt} tick={{ fontSize:9, fill:'#6e7681' }} width={60}/>
              <Tooltip content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null
                return (
                  <div style={{ background:'#0d1117', border:'1px solid #30363d', padding:'7px 11px', fontSize:11, borderRadius:4 }}>
                    <div style={{ color:'#8b949e', marginBottom:3 }}>{label}</div>
                    {payload.map((p,i) => <div key={i} style={{ color:p.color }}>{p.name}: {fmt(p.value)}</div>)}
                  </div>
                )
              }}/>
              <ReferenceLine y={effectiveCapacity} stroke="#EF4444" strokeDasharray="5 3"
                label={{ value:'Cap', fill:'#EF4444', fontSize:9, position:'insideTopRight' }}/>
              <Area type="monotone" dataKey="actual" name="Actual" stroke="#3B82F6" fill="url(#gA)" strokeWidth={2} dot={false}/>
              <Line type="monotone" dataKey="forecast" name="LSTM" stroke="#A855F7" strokeDasharray="5 3" strokeWidth={2} dot={false}/>
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Sentinel gauge */}
        <div className="rounded-sm p-4 flex flex-col items-center justify-center gap-4" style={{ background: '#0d1117', border: '1px solid #21262d' }}>
          <div className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-2" style={{ color: '#6e7681' }}>
            <ShieldCheck size={11} style={{ color: sentColor }}/> Sentinel
          </div>
          <div className="relative w-28 h-28">
            <svg viewBox="0 0 120 120" style={{ width:'100%', height:'100%' }}>
              <circle cx="60" cy="60" r="52" fill="none" stroke="#21262d" strokeWidth="10"/>
              <circle cx="60" cy="60" r="52" fill="none" stroke={sentColor} strokeWidth="10"
                strokeDasharray={`${Math.min(sentinel.delta_pct/80*327,327)} 327`}
                strokeLinecap="round" transform="rotate(-90 60 60)"
                style={{ filter:`drop-shadow(0 0 8px ${sentColor})`, transition:'stroke-dasharray .7s ease' }}/>
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-[9px] font-bold uppercase" style={{ color: sentColor }}>{sentinel.status}</span>
              <span className="text-2xl font-black font-mono" style={{ color: sentColor }}>δ{sentinel.delta_pct}%</span>
            </div>
          </div>
          <div className="text-center text-[10px]" style={{ color: '#6e7681' }}>
            LSTM vs Actual deviation<br/>
            {sentinel.consecutive_bad > 0 && <span style={{ color:'#F59E0B' }}>{sentinel.consecutive_bad} consecutive deviance{sentinel.consecutive_bad>1?'s':''}</span>}
          </div>
        </div>
      </div>

      {/* DECISION LOG */}
      {decisionHistory.length > 0 && <DecisionLog history={decisionHistory}/>}

      {/* MEDIC — inline, non-blocking */}
      {medicActive && medic && (
        <MedicAlert medic={medic} onDismiss={() => setMedicActive(false)}/>
      )}
    </div>
  )
}

// ─── KPI CARD ─────────────────────────────────────────────────────────────────
function KPICard({ label, value, sub, color, fill=0 }) {
  return (
    <div className="rounded-sm p-3" style={{ background:'#0d1117', border:'1px solid #21262d', borderTop:`2px solid ${color}` }}>
      <div className="text-[9px] uppercase tracking-widest mb-1" style={{ color:'#6e7681' }}>{label}</div>
      <div className="text-xl font-bold leading-none mb-1" style={{ color }}>{value}</div>
      <div className="text-[9px] mb-2" style={{ color:'#6e7681' }}>{sub}</div>
      <div className="h-0.5 rounded-full overflow-hidden" style={{ background:'#21262d' }}>
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width:`${Math.min(fill*100,100)}%`, background:`linear-gradient(90deg,${color},${color}70)` }}/>
      </div>
    </div>
  )
}

// ─── NEXUS 3D TOPOLOGY ────────────────────────────────────────────────────────
// NO CSS animations inside SVG — only static SVG with gradients/filters
function NexusTopology({ numNodes, activeNodes, currentColor, currentLoadPct, sleepCount }) {
  const CX = 400, CY = 175, R = 135, NR = 20

  const nodes = Array(numNodes).fill(0).map((_, i) => {
    const a = (i / numNodes) * 2 * Math.PI - Math.PI / 2
    return {
      x: Math.round(CX + R * Math.cos(a)),
      y: Math.round(CY + R * Math.sin(a)),
      active: i < activeNodes,
      i,
    }
  })

  const conns = [
    ...nodes.map((n, i) => {
      const nx = nodes[(i + 1) % numNodes]
      return { x1: n.x, y1: n.y, x2: nx.x, y2: nx.y, active: n.active && nx.active, id: `r${i}` }
    }),
    ...nodes.map((n, i) => ({ x1: n.x, y1: n.y, x2: CX, y2: CY, active: n.active, id: `s${i}` })),
  ]

  const arcLen = 2 * Math.PI * 31
  const arcFill = Math.min((currentLoadPct / 100) * arcLen, arcLen)

  return (
    <div className="rounded-sm overflow-hidden" style={{ background: 'radial-gradient(ellipse at 50% 0%, #0a1628, #080c12)', border: '1px solid #21262d' }}>
      <div className="px-5 pt-3 pb-1 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-2" style={{ color: '#6e7681' }}>
          <Wifi size={11} style={{ color: currentColor }} /> NEXUS — Live Network State
        </span>
        <span className="text-[10px] font-mono" style={{ color: '#6e7681' }}>
          <span style={{ color: currentColor }}>{activeNodes} active</span> · {sleepCount} eco-sleep
        </span>
      </div>

      <svg viewBox="0 0 800 350" style={{ width: '100%', height: 'auto', display: 'block' }}>
        <defs>
          {/* Glow filter */}
          <filter id="svgGlow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b1" />
            <feGaussianBlur in="SourceGraphic" stdDeviation="10" result="b2" />
            <feMerge>
              <feMergeNode in="b2" />
              <feMergeNode in="b1" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="svgNodeGlow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Per-node sphere gradient */}
          {nodes.map(n => (
            <radialGradient key={`rg${n.i}`} id={`rg${n.i}`} cx="35%" cy="28%" r="68%">
              <stop offset="0%"   stopColor="white"                               stopOpacity={n.active ? '0.55' : '0.06'} />
              <stop offset="45%"  stopColor={n.active ? currentColor : '#2a3040'} stopOpacity={n.active ? '0.9'  : '0.5'} />
              <stop offset="100%" stopColor="#060b14"                              stopOpacity="0.9" />
            </radialGradient>
          ))}
          {/* Hub gradient */}
          <radialGradient id="hubGrad" cx="35%" cy="28%" r="68%">
            <stop offset="0%"   stopColor="white"        stopOpacity="0.6" />
            <stop offset="40%"  stopColor={currentColor} stopOpacity="0.95" />
            <stop offset="100%" stopColor="#060b14"       stopOpacity="0.9" />
          </radialGradient>
        </defs>

        {/* Orbit ring guide */}
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="#1c2333" strokeWidth="0.8" strokeDasharray="4 10" />

        {/* Dim inactive connections */}
        {conns.filter(c => !c.active).map(c => (
          <line key={c.id} x1={c.x1} y1={c.y1} x2={c.x2} y2={c.y2}
            stroke="#1d2535" strokeWidth="0.8" />
        ))}

        {/* Active connections — glowing solid line, NO CSS animation */}
        {conns.filter(c => c.active).map(c => (
          <line key={c.id} x1={c.x1} y1={c.y1} x2={c.x2} y2={c.y2}
            stroke={currentColor} strokeWidth="1.5" strokeOpacity="0.55"
            filter="url(#svgGlow)" />
        ))}

        {/* Node spheres */}
        {nodes.map(n => (
          <g key={n.i}>
            {/* Outer glow halo — static, no animation */}
            {n.active && (
              <circle cx={n.x} cy={n.y} r={NR + 9}
                fill="none" stroke={currentColor} strokeWidth="1"
                strokeOpacity="0.18" />
            )}
            {/* Sphere body */}
            <circle cx={n.x} cy={n.y} r={NR}
              fill={`url(#rg${n.i})`}
              stroke={n.active ? currentColor : '#2a3040'}
              strokeWidth={n.active ? 1.5 : 0.8}
              filter={n.active ? 'url(#svgNodeGlow)' : undefined}
            />
            {/* Label */}
            <text x={n.x} y={n.y + 4}
              textAnchor="middle" fontSize={8} fontWeight="700"
              fill={n.active ? '#e6edf3' : '#4a5568'}
              fontFamily="monospace">
              {n.active ? `N${n.i + 1}` : 'zz'}
            </text>
            {/* Active status dot */}
            {n.active && (
              <circle cx={n.x + NR - 4} cy={n.y - NR + 4} r={3}
                fill={currentColor} stroke="#080c12" strokeWidth="1"
                filter="url(#svgGlow)" />
            )}
          </g>
        ))}

        {/* CORE hub */}
        <circle cx={CX} cy={CY} r={28}
          fill="none" stroke={currentColor} strokeWidth="0.8" strokeOpacity="0.15" />
        <circle cx={CX} cy={CY} r={24}
          fill="url(#hubGrad)" stroke={currentColor} strokeWidth="2"
          filter="url(#svgNodeGlow)" />
        {/* Load arc — static, updates via strokeDasharray re-render */}
        <circle cx={CX} cy={CY} r={31}
          fill="none" stroke={currentColor} strokeWidth="4"
          strokeDasharray={`${arcFill.toFixed(1)} ${arcLen.toFixed(1)}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${CX} ${CY})`}
          strokeOpacity="0.8"
          filter="url(#svgGlow)" />
        <text x={CX} y={CY - 3}
          textAnchor="middle" fontSize={7} fontWeight="900"
          fill="white" fontFamily="monospace">CORE</text>
        <text x={CX} y={CY + 7}
          textAnchor="middle" fontSize={7}
          fill={currentColor} fontFamily="monospace">
          {currentLoadPct.toFixed(0)}%
        </text>
      </svg>
    </div>
  )
}

// ─── AGENT COUNCIL CHAMBER ────────────────────────────────────────────────────
function AgentCouncil({ decision, loading, decisionCount }) {
  const agents      = decision?.agents || []
  const judgeChoice = decision?.judge_choice
  const names       = ['ECO','RELIABILITY','COST']

  return (
    <div className="rounded-sm overflow-hidden" style={{ background:'#080c12', border:'1px solid #21262d' }}>
      {/* Header */}
      <div className="px-5 py-3 flex items-center justify-between"
        style={{ borderBottom:'1px solid #21262d', background:'linear-gradient(90deg,rgba(168,85,247,.06),transparent)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm flex items-center justify-center"
            style={{ background:'rgba(168,85,247,.15)', border:'1px solid rgba(168,85,247,.3)' }}>
            <Gavel size={15} style={{ color:'#A855F7' }}/>
          </div>
          <div>
            <div className="text-sm font-bold text-text-primary">Agent Council Chamber</div>
            <div className="text-[10px]" style={{ color:'#6e7681' }}>4 × Gemini 2.0 Flash · LangGraph fan-out · 3 specialist LLMs → 1 judge LLM</div>
          </div>
        </div>
        {loading
          ? <div className="flex items-center gap-2 text-[10px] font-mono ap-blink" style={{ color:'#A855F7' }}>
              <span className="w-1.5 h-1.5 rounded-full" style={{ background:'#A855F7' }}/>
              AGENTS DELIBERATING
            </div>
          : decision && <div className="text-[10px] font-mono" style={{ color:'#22C55E' }}>
              ROUND {decisionCount} COMPLETE · sleep {decision.judge_choice} nodes
            </div>
        }
      </div>

      <div className="p-5">
        {/* 3 agent terminals — key includes decisionCount so cards re-animate on new round */}
        <div className="grid grid-cols-3 gap-4 mb-5">
          {loading && !agents.length
            ? names.map((n,i) => <AgentTerminalLoading key={n} name={n} delay={i*0.1}/>)
            : agents.length > 0
              ? agents.map((a,i) => (
                  <AgentTerminal
                    key={`${decisionCount}-${a.name}`}
                    agent={a} judgeChoice={judgeChoice} delay={i*0.13}
                  />
                ))
              : names.map(n => <AgentTerminalEmpty key={n} name={n}/>)
          }
        </div>

        {/* Judge verdict */}
        <JudgeVerdict decision={decision} loading={loading} decisionCount={decisionCount}/>
      </div>
    </div>
  )
}

// ─── AGENT TERMINAL ───────────────────────────────────────────────────────────
function AgentTerminal({ agent, judgeChoice, delay }) {
  const cfg   = AGENT_CFG[agent.name] || { color:'#8b949e', desc:'Agent' }
  const color = agent.color || cfg.color
  const isWinner = agent.sleep_count === judgeChoice

  return (
    <div className="rounded-sm ap-card-in"
      style={{
        animationDelay: `${delay}s`,
        background: `radial-gradient(ellipse at top left,${color}12,#0d1117 55%)`,
        border: `1px solid ${color}${isWinner?'55':'20'}`,
        borderTop: `3px solid ${color}`,
        boxShadow: isWinner ? `0 0 28px ${color}28,inset 0 0 28px ${color}06` : 'none',
      }}>
      {/* macOS-style title bar */}
      <div className="flex items-center gap-1.5 px-3 py-2" style={{ borderBottom:`1px solid ${color}20` }}>
        <span className="w-2.5 h-2.5 rounded-full" style={{ background:'#ef4444' }}/>
        <span className="w-2.5 h-2.5 rounded-full" style={{ background:'#f59e0b' }}/>
        <span className="w-2.5 h-2.5 rounded-full" style={{ background:'#22c55e' }}/>
        <span className="flex-1 text-center text-[9px] font-mono" style={{ color:`${color}99` }}>
          {agent.name} AGENT · {cfg.desc}
        </span>
        {isWinner
          ? <span className="text-[8px] px-1.5 py-0.5 rounded-full font-bold"
              style={{ background:`${color}25`, color, border:`1px solid ${color}50` }}>ADOPTED</span>
          : judgeChoice !== undefined && <span className="text-[8px]" style={{ color:'#6e7681' }}>overruled</span>
        }
      </div>

      {/* Big proposal number */}
      <div className="px-4 pt-4 pb-2">
        <div className="text-[9px] uppercase tracking-widest mb-1" style={{ color:`${color}70` }}>PROPOSES</div>
        <div className="flex items-end gap-2">
          <div className="font-black leading-none font-mono"
            style={{ fontSize:60, color, textShadow:`0 0 24px ${color}70,0 0 48px ${color}30`, lineHeight:1 }}>
            {agent.sleep_count}
          </div>
          <div className="mb-1.5 text-[11px]" style={{ color:'#6e7681' }}>
            node{agent.sleep_count!==1?'s':''}<br/>to sleep
          </div>
        </div>
      </div>

      {/* Terminal reasoning */}
      <div className="px-4 pb-3">
        <div className="text-[10px] font-mono mb-1.5" style={{ color:`${color}55` }}>$ reasoning</div>
        <div className="text-[11px] leading-relaxed font-mono" style={{ color:'#c9d1d9', minHeight:72 }}>
          {agent.reasoning}
        </div>
      </div>

      {/* Confidence bar */}
      <div className="px-4 pb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] uppercase tracking-wider" style={{ color:`${color}55` }}>confidence</span>
          <span className="text-[11px] font-bold font-mono" style={{ color }}>{((agent.confidence||0)*100).toFixed(0)}%</span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background:'#21262d' }}>
          <div className="h-full rounded-full transition-all duration-1000"
            style={{ width:`${(agent.confidence||0)*100}%`, background:`linear-gradient(90deg,${color},${color}80)`, boxShadow:`0 0 8px ${color}` }}/>
        </div>
      </div>
    </div>
  )
}

function AgentTerminalLoading({ name, delay }) {
  const cfg = AGENT_CFG[name] || { color:'#8b949e' }
  return (
    <div className="rounded-sm relative overflow-hidden" style={{ background:'#0d1117', border:`1px solid ${cfg.color}18`, borderTop:`3px solid ${cfg.color}40`, minHeight:240 }}>
      <div className="absolute inset-0 ap-shimmer"/>
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
        <div className="text-3xl font-mono ap-blink" style={{ color:`${cfg.color}50` }}>···</div>
        <div className="text-[10px] uppercase tracking-widest" style={{ color:`${cfg.color}50` }}>{name} ANALYZING</div>
      </div>
    </div>
  )
}

function AgentTerminalEmpty({ name }) {
  const cfg = AGENT_CFG[name] || { color:'#8b949e' }
  return (
    <div className="rounded-sm flex flex-col items-center justify-center gap-2" style={{ background:'#0d1117', border:`1px solid ${cfg.color}12`, borderTop:`3px solid ${cfg.color}25`, minHeight:240 }}>
      <div className="text-4xl" style={{ color:`${cfg.color}20` }}>○</div>
      <div className="text-[10px] uppercase tracking-widest font-mono" style={{ color:`${cfg.color}40` }}>{name}</div>
      <div className="text-[9px]" style={{ color:'#6e7681' }}>awaiting first cycle</div>
    </div>
  )
}

// ─── JUDGE VERDICT ────────────────────────────────────────────────────────────
// eslint-disable-next-line no-unused-vars
function JudgeVerdict({ decision, loading, decisionCount }) {
  return (
    <div className="rounded-sm"
      style={{
        background:'radial-gradient(ellipse at 50% -20%,rgba(168,85,247,.18),#080c12 55%)',
        border:'2px solid rgba(168,85,247,.35)',
        boxShadow:'0 0 50px rgba(168,85,247,.18),inset 0 0 50px rgba(168,85,247,.04)',
      }}>
      {loading ? (
        <div className="flex items-center justify-center gap-4 py-8">
          <Gavel size={20} className="ap-float" style={{ color:'#A855F7' }}/>
          <div>
            <div className="text-sm font-bold ap-blink" style={{ color:'#d8b4fe' }}>JUDGE DELIBERATING</div>
            <div className="text-[10px]" style={{ color:'#6e7681' }}>Gemini 2.0 Flash weighing agent proposals…</div>
          </div>
        </div>
      ) : decision ? (
        <div className="p-5">
          <div className="flex items-start justify-between gap-6">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-3">
                <Gavel size={13} style={{ color:'#A855F7' }}/>
                <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color:'#c084fc' }}>
                  JUDGE · Gemini 2.0 Flash · Final Ruling
                </span>
              </div>
              <p className="text-sm text-text-primary leading-relaxed">{decision.judge_reasoning}</p>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color:'#6e7681' }}>RULING</div>
              <div className="font-black font-mono leading-none"
                style={{ fontSize:68, color:'#A855F7', textShadow:'0 0 40px rgba(168,85,247,.7),0 0 80px rgba(168,85,247,.3)', lineHeight:1 }}>
                {decision.judge_choice}
              </div>
              <div className="text-[10px]" style={{ color:'#6e7681' }}>nodes to sleep</div>
            </div>
          </div>

          {/* Vote tally */}
          {decision.agents?.length > 0 && (
            <div className="mt-4 pt-4 flex items-center gap-3 flex-wrap"
              style={{ borderTop:'1px solid rgba(168,85,247,.2)' }}>
              <span className="text-[9px] uppercase tracking-wider" style={{ color:'#6e7681' }}>Agent votes:</span>
              {decision.agents.map(a => {
                const color   = a.color || AGENT_CFG[a.name]?.color || '#8b949e'
                const isAlign = a.sleep_count === decision.judge_choice
                const isClose = Math.abs((a.sleep_count||0)-(decision.judge_choice||0)) === 1
                return (
                  <div key={a.name} className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-mono font-semibold"
                    style={{ background:isAlign?`${color}20`:'rgba(255,255,255,.04)', border:`1px solid ${isAlign?color+'60':'#30363d'}`, color:isAlign?color:'#6e7681' }}>
                    {a.name} → {a.sleep_count} {isAlign?'✓':isClose?'≈':'✗'}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-center justify-center gap-2 py-6 text-xs" style={{ color:'#6e7681' }}>
          <Sparkles size={13} style={{ color:'#A855F7' }}/> Awaiting first deliberation cycle…
        </div>
      )}
    </div>
  )
}

// ─── DECISION LOG ─────────────────────────────────────────────────────────────
function DecisionLog({ history }) {
  return (
    <div className="rounded-sm overflow-hidden" style={{ background:'#0d1117', border:'1px solid #21262d' }}>
      <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom:'1px solid #21262d' }}>
        <div className="flex items-center gap-2">
          <Clock size={12} style={{ color:'#A855F7' }}/>
          <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color:'#6e7681' }}>Decision History</span>
        </div>
        <span className="text-[9px]" style={{ color:'#6e7681' }}>{history.length} rounds</span>
      </div>
      <div style={{ borderColor:'#21262d' }}>
        {history.map((entry, i) => {
          const agents = entry.agents || []
          return (
            <div key={i} className="px-5 py-3 grid gap-4 items-start"
              style={{ gridTemplateColumns:'72px 96px auto 1fr', borderBottom:'1px solid #21262d', background:i===0?'rgba(168,85,247,.05)':'transparent', borderLeft:i===0?'3px solid rgba(168,85,247,.5)':'3px solid transparent' }}>
              <div>
                <div className="text-[10px] font-mono font-bold" style={{ color:'#c084fc' }}>h.{entry.hour}</div>
                <div className="text-[9px]" style={{ color:'#6e7681' }}>{entry.timestamp}</div>
              </div>
              <div>
                <div className="text-[12px] font-bold font-mono" style={{ color:'#d8b4fe' }}>sleep {entry.judge_choice}</div>
                <div className="text-[9px]" style={{ color:'#6e7681' }}>judged</div>
              </div>
              <div className="flex gap-1.5 flex-wrap">
                {agents.map(a => {
                  const color   = a.color || AGENT_CFG[a.name]?.color || '#8b949e'
                  const isAlign = a.sleep_count === entry.judge_choice
                  return (
                    <div key={a.name} className="text-[9px] px-1.5 py-0.5 rounded-sm font-mono"
                      style={{ background:isAlign?`${color}18`:'transparent', border:`1px solid ${isAlign?color+'50':'#30363d'}`, color:isAlign?color:'#6e7681' }}>
                      {a.name[0]}:{a.sleep_count} {isAlign?'✓':'✗'}
                    </div>
                  )
                })}
              </div>
              <p className="text-[10px] truncate" style={{ color:'#6e7681' }}>{entry.judge_reasoning}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── MEDIC ALERT (inline) ─────────────────────────────────────────────────────
function MedicAlert({ medic, onDismiss }) {
  return (
    <div className="rounded-sm ap-slide"
      style={{ background:'radial-gradient(ellipse at top,rgba(239,68,68,.14),#0d1117)', border:'1px solid rgba(239,68,68,.5)', boxShadow:'0 0 40px rgba(239,68,68,.18)' }}>
      <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom:'1px solid rgba(239,68,68,.2)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center"
            style={{ background:'rgba(239,68,68,.15)', border:'1px solid rgba(239,68,68,.4)' }}>
            <Stethoscope size={15} style={{ color:'#f87171' }}/>
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest" style={{ color:'#f87171' }}>MEDIC ACTIVATED</div>
            <div className="text-sm font-semibold text-text-primary">Auto-Recovery Protocol</div>
          </div>
          <span className="w-2 h-2 rounded-full ap-blink" style={{ background:'#ef4444' }}/>
        </div>
        <button onClick={onDismiss} className="p-1.5 rounded-sm transition-colors hover:bg-red-500/10"
          style={{ color:'#6e7681' }}>
          <X size={14}/>
        </button>
      </div>
      <div className="p-5">
        <p className="text-sm text-text-primary mb-4">{medic.diagnosis}</p>
        <div className="grid grid-cols-3 gap-3 mb-3">
          {medic.actions?.map((a,i) => (
            <div key={i} className="flex items-start gap-2 text-xs p-3 rounded-sm"
              style={{ background:'#161b22', border:'1px solid #30363d', color:'#8b949e' }}>
              <CheckCircle size={11} className="text-green-400 mt-0.5 shrink-0"/>
              {a}
            </div>
          ))}
        </div>
        <div className="text-[10px]" style={{ color:'#6e7681' }}>ETA ~{medic.eta_seconds}s · All nodes woken</div>
      </div>
    </div>
  )
}
