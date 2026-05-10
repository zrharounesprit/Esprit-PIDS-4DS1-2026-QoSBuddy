import { useState, useEffect, useRef } from 'react'
import { useToast } from '../hooks/useToast'
import { nocApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import {
  Shield, Activity, Play, RefreshCw, Clock, CheckCircle, AlertTriangle,
  XCircle, Loader, ChevronRight, Zap, BarChart2, Eye, Search,
  ClipboardList, Cpu, GitBranch, Brain, SkipForward
} from 'lucide-react'

const ACCENT = '#00E8C6'
const POLL_MS = 3000

// ── Severity config ──────────────────────────────────────────────────────────
const SEV_CONFIG = {
  CRITICAL: { color: '#EF4444', bg: '#7f1d1d33', label: 'CRITICAL', icon: XCircle },
  HIGH:     { color: '#F97316', bg: '#7c2d1233', label: 'HIGH',     icon: AlertTriangle },
  MEDIUM:   { color: '#EAB308', bg: '#71350033', label: 'MEDIUM',   icon: AlertTriangle },
  LOW:      { color: '#22C55E', bg: '#14532d33', label: 'LOW',      icon: CheckCircle },
  OK:       { color: '#00E8C6', bg: '#00E8C611', label: 'NOMINAL',  icon: CheckCircle },
}

// ── Phase config ─────────────────────────────────────────────────────────────
const PHASE_META = {
  OBSERVE:    { icon: Eye,          color: '#00E8C6', label: 'Observe' },
  ATTRIBUTE:  { icon: Search,       color: '#8B7CF8', label: 'Attribute' },
  PLAN:       { icon: ClipboardList,color: '#3B82F6', label: 'Plan' },
  SIMULATE:   { icon: Cpu,          color: '#F59E0B', label: 'Simulate' },
  VERIFY:     { icon: CheckCircle,  color: '#22C55E', label: 'Verify' },
  ITERATE:    { icon: RefreshCw,    color: '#F97316', label: 'Iterate' },
  SYNTHESIZE: { icon: Brain,        color: '#E040FB', label: 'Synthesize' },
}

function getPhaseKey(name = '') {
  const upper = name.toUpperCase()
  for (const key of Object.keys(PHASE_META)) {
    if (upper.includes(key)) return key
  }
  return null
}

// ── Status dot ────────────────────────────────────────────────────────────────
function StatusDot({ status }) {
  const color = status === 'running' ? ACCENT : status === 'error' ? '#EF4444' : '#6B7280'
  return (
    <span
      className="inline-block w-2 h-2 rounded-full mr-1.5"
      style={{
        background: color,
        boxShadow: status === 'running' ? `0 0 6px ${color}` : 'none',
        animation: status === 'running' ? 'pulse 1.5s ease-in-out infinite' : 'none',
      }}
    />
  )
}

// ── Phase row ─────────────────────────────────────────────────────────────────
function PhaseRow({ phase, index, visible }) {
  const key = getPhaseKey(phase.name)
  const meta = key ? PHASE_META[key] : { icon: GitBranch, color: '#6B7280', label: phase.name }
  const Icon = meta.icon
  const statusIcon = {
    done:    <CheckCircle size={13} className="text-green-400" />,
    warn:    <AlertTriangle size={13} className="text-yellow-400" />,
    error:   <XCircle size={13} className="text-red-400" />,
    running: <Loader size={13} className="animate-spin" style={{ color: ACCENT }} />,
    skipped: <SkipForward size={13} className="text-text-faint" />,
  }[phase.status] || <CheckCircle size={13} className="text-green-400" />

  return (
    <div
      className="flex items-start gap-3 py-2.5 border-b border-border last:border-0 transition-all duration-500"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateX(0)' : 'translateX(-12px)',
        transitionDelay: `${index * 80}ms`,
      }}
    >
      <div className="mt-0.5 flex-shrink-0 w-6 h-6 rounded flex items-center justify-center"
           style={{ background: `${meta.color}18`, border: `1px solid ${meta.color}44` }}>
        <Icon size={13} style={{ color: meta.color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          {statusIcon}
          <span className="text-xs font-medium text-text-primary">{phase.name}</span>
        </div>
        {phase.detail && (
          <p className="text-[11px] text-text-muted leading-relaxed line-clamp-3">{phase.detail}</p>
        )}
      </div>
    </div>
  )
}

// ── Report card ───────────────────────────────────────────────────────────────
function ReportCard({ cycle }) {
  if (!cycle) return null
  const sevKey = cycle.severity === 'OK' ? 'OK' : (cycle.severity || 'LOW')
  const sev = SEV_CONFIG[sevKey] || SEV_CONFIG.LOW
  const SevIcon = sev.icon
  const report = cycle.report || {}

  return (
    <div className="rounded-sm border border-border bg-surface overflow-hidden">
      {/* Banner */}
      <div className="px-4 py-3 flex items-center gap-2.5"
           style={{ background: sev.bg, borderBottom: `1px solid ${sev.color}44` }}>
        <SevIcon size={16} style={{ color: sev.color }} />
        <span className="text-sm font-bold tracking-wide" style={{ color: sev.color }}>
          {sev.label}
        </span>
        {cycle.breach_detected ? (
          <span className="ml-auto text-[10px] font-medium px-2 py-0.5 rounded"
                style={{ background: `${sev.color}22`, color: sev.color, border: `1px solid ${sev.color}44` }}>
            BREACH DETECTED
          </span>
        ) : (
          <span className="ml-auto text-[10px] font-medium px-2 py-0.5 rounded text-green-400 border border-green-400/30 bg-green-400/10">
            SLA NOMINAL
          </span>
        )}
      </div>

      <div className="p-4 grid gap-4">
        {/* Executive summary */}
        {report.executive_summary && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1">Executive Summary</div>
            <p className="text-sm text-text-primary leading-relaxed">{report.executive_summary}</p>
          </div>
        )}

        {/* Root cause + Impact */}
        <div className="grid grid-cols-2 gap-3">
          {report.root_cause && (
            <div className="rounded bg-surface-2 border border-border p-2.5">
              <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1">Root Cause</div>
              <p className="text-[11px] text-text-muted leading-relaxed">{report.root_cause}</p>
            </div>
          )}
          {report.business_impact && (
            <div className="rounded bg-surface-2 border border-border p-2.5">
              <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1">Business Impact</div>
              <p className="text-[11px] text-text-muted leading-relaxed">{report.business_impact}</p>
            </div>
          )}
        </div>

        {/* Recommendations */}
        {report.recommendations && report.recommendations.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-text-faint mb-2">
              Recommendations
            </div>
            <div className="grid gap-1.5">
              {report.recommendations.map((rec, i) => (
                <div key={i} className="flex items-start gap-2 text-[11px] text-text-muted">
                  <ChevronRight size={11} className="mt-0.5 flex-shrink-0 text-accent-teal" />
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Metadata row */}
        <div className="flex flex-wrap gap-4 pt-2 border-t border-border">
          {cycle.ts_end && (
            <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
              <Clock size={11} />
              {new Date(cycle.ts_end).toLocaleString()}
            </div>
          )}
          {cycle.iterations > 0 && (
            <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
              <RefreshCw size={11} />
              {cycle.iterations} mitigation iteration{cycle.iterations !== 1 ? 's' : ''}
            </div>
          )}
          {cycle.mitigation_scenario && (
            <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
              <Zap size={11} />
              {cycle.mitigation_scenario.replace('_', ' ')}
            </div>
          )}
          {report.source && (
            <div className="flex items-center gap-1.5 text-[10px] text-text-faint ml-auto">
              <Brain size={11} />
              {report.source}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── History list ──────────────────────────────────────────────────────────────
function HistoryItem({ cycle, onClick, active }) {
  const sevKey = cycle.severity === 'OK' ? 'OK' : (cycle.severity || 'LOW')
  const sev = SEV_CONFIG[sevKey] || SEV_CONFIG.LOW
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded transition-colors border mb-1 ${
        active ? 'border-border bg-surface-2' : 'border-transparent hover:bg-surface-2'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: sev.color }} />
        <span className="text-xs text-text-primary flex-1 truncate">
          {cycle.breach_detected ? '⚠ Breach' : '✓ Nominal'}
        </span>
        <span className="text-[10px] text-text-faint">
          {cycle.ts_end ? new Date(cycle.ts_end).toLocaleTimeString() : '—'}
        </span>
      </div>
      <div className="flex gap-2 mt-0.5 ml-3.5">
        <span className="text-[10px]" style={{ color: sev.color }}>{sev.label}</span>
        {cycle.resolved !== undefined && (
          <span className="text-[10px] text-text-faint">
            {cycle.resolved ? '· resolved' : '· unresolved'}
          </span>
        )}
      </div>
    </button>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function SLAGuardian() {
  const toast = useToast()
  const [status, setStatus]       = useState(null)
  const [history, setHistory]     = useState([])
  const [selectedCycle, setSelectedCycle] = useState(null)
  const [triggering, setTriggering] = useState(false)
  const [phasesVisible, setPhasesVisible] = useState(false)
  const pollRef = useRef(null)
  const prevRunRef = useRef(null)

  // ── Polling ────────────────────────────────────────────────────────────────
  async function fetchStatus() {
    try {
      const s = await nocApi.status()
      setStatus(s)
      // Auto-select latest cycle
      if (s.latest_cycle && s.latest_cycle.ts_end !== prevRunRef.current) {
        prevRunRef.current = s.latest_cycle.ts_end
        setSelectedCycle(s.latest_cycle)
        setPhasesVisible(false)
        setTimeout(() => setPhasesVisible(true), 50)
      }
    } catch (e) {
      // NOC API not reachable — silent
    }
  }

  async function fetchHistory() {
    try {
      const h = await nocApi.history(10)
      setHistory(h.cycles || [])
    } catch (e) {}
  }

  useEffect(() => {
    fetchStatus()
    fetchHistory()
    pollRef.current = setInterval(() => {
      fetchStatus()
      fetchHistory()
    }, POLL_MS)
    return () => clearInterval(pollRef.current)
  }, [])

  // When cycle changes, animate phases
  useEffect(() => {
    if (selectedCycle?.phases?.length) {
      setPhasesVisible(false)
      setTimeout(() => setPhasesVisible(true), 100)
    }
  }, [selectedCycle?.ts_end])

  // ── Manual trigger ─────────────────────────────────────────────────────────
  async function handleTrigger(injectBreach = false) {
    setTriggering(true)
    try {
      await nocApi.trigger(injectBreach)
      toast('NOC cycle started — polling for results…', 'success')
    } catch (e) {
      toast(`Trigger failed: ${e.message}`, 'error')
    } finally {
      setTimeout(() => setTriggering(false), 1500)
    }
  }

  const isRunning = status?.status === 'running'
  const latestCycle = status?.latest_cycle
  const displayCycle = selectedCycle || latestCycle

  // Severity of the displayed cycle
  const sevKey = displayCycle?.severity === 'OK' ? 'OK' : (displayCycle?.severity || 'OK')
  const sev = SEV_CONFIG[sevKey] || SEV_CONFIG.OK

  return (
    <div className="max-w-7xl mx-auto">
      <PageHeader
        icon={Shield}
        title="NOC Autopilot"
        subtitle="Autonomous SLA Guardian — observe, attribute, plan, simulate, verify, iterate, synthesize"
        accent={ACCENT}
      />

      {/* ── Top status bar ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {/* Scheduler status */}
        <div className="rounded-sm border border-border bg-surface p-3">
          <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1.5">Scheduler</div>
          <div className="flex items-center gap-1.5">
            <StatusDot status={status?.status || 'idle'} />
            <span className="text-sm font-medium text-text-primary capitalize">
              {status?.status || '—'}
            </span>
          </div>
          {status?.current_phase && (
            <div className="text-[10px] text-text-faint mt-1 truncate">{status.current_phase}</div>
          )}
        </div>

        {/* Current severity */}
        <div className="rounded-sm border bg-surface p-3" style={{ borderColor: `${sev.color}44` }}>
          <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1.5">Risk Level</div>
          <div className="text-sm font-bold" style={{ color: sev.color }}>{sev.label}</div>
          {displayCycle?.breach_summary?.max_prob != null && (
            <div className="text-[10px] text-text-faint mt-1">
              prob: {displayCycle.breach_summary.max_prob.toFixed(3)}
            </div>
          )}
        </div>

        {/* Last run */}
        <div className="rounded-sm border border-border bg-surface p-3">
          <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1.5">Last Cycle</div>
          <div className="text-sm text-text-primary">
            {status?.last_run ? new Date(status.last_run).toLocaleTimeString() : '—'}
          </div>
          <div className="text-[10px] text-text-faint mt-1">
            {status?.cycle_count || 0} cycle{status?.cycle_count !== 1 ? 's' : ''} total
          </div>
        </div>

        {/* Next run */}
        <div className="rounded-sm border border-border bg-surface p-3">
          <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1.5">Next Cycle</div>
          <div className="text-sm text-text-primary">
            {status?.next_run ? new Date(status.next_run).toLocaleTimeString() : '—'}
          </div>
          <div className="text-[10px] text-text-faint mt-1 flex items-center gap-1">
            <Activity size={10} />
            Auto every 5 min
          </div>
        </div>
      </div>

      {/* ── Action buttons ── */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => handleTrigger(false)}
          disabled={isRunning || triggering}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-sm border border-border hover:bg-surface-2 transition-colors disabled:opacity-40"
        >
          {isRunning ? <Loader size={12} className="animate-spin" /> : <Play size={12} />}
          {isRunning ? 'Running…' : 'Run Cycle'}
        </button>
        <button
          onClick={() => handleTrigger(true)}
          disabled={isRunning || triggering}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-sm border border-yellow-500/40 text-yellow-400 hover:bg-yellow-400/10 transition-colors disabled:opacity-40"
        >
          <Zap size={12} />
          Inject Breach
        </button>
        <button
          onClick={() => { fetchStatus(); fetchHistory() }}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-muted rounded-sm border border-border hover:bg-surface-2 transition-colors ml-auto"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      {/* ── Main content ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Left: Phase timeline */}
        <div className="lg:col-span-1">
          <div className="rounded-sm border border-border bg-surface overflow-hidden">
            <div className="px-4 py-3 border-b border-border">
              <span className="text-xs font-semibold text-text-primary">Agent Loop</span>
              {displayCycle && (
                <span className="ml-2 text-[10px] text-text-faint">
                  {(displayCycle.phases || []).length} phases
                </span>
              )}
            </div>
            <div className="px-4 py-2">
              {/* Live phase indicator when running */}
              {isRunning && status?.current_phase && (
                <div className="flex items-center gap-2 py-2 mb-2 border-b border-border">
                  <Loader size={12} className="animate-spin" style={{ color: ACCENT }} />
                  <span className="text-xs font-medium" style={{ color: ACCENT }}>
                    {status.current_phase}
                  </span>
                  {status.phase_detail && (
                    <span className="text-[10px] text-text-faint truncate">{status.phase_detail}</span>
                  )}
                </div>
              )}
              {displayCycle?.phases?.length ? (
                displayCycle.phases.map((ph, i) => (
                  <PhaseRow key={i} phase={ph} index={i} visible={phasesVisible} />
                ))
              ) : (
                <div className="py-6 text-center text-text-faint text-xs">
                  {isRunning ? (
                    <div className="flex flex-col items-center gap-2">
                      <Loader size={18} className="animate-spin" style={{ color: ACCENT }} />
                      <span>Agent running…</span>
                    </div>
                  ) : (
                    'No cycle data yet. Click "Run Cycle" to start.'
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Report + history */}
        <div className="lg:col-span-2 flex flex-col gap-5">
          {/* Incident report */}
          {displayCycle ? (
            <ReportCard cycle={displayCycle} />
          ) : (
            <div className="rounded-sm border border-border bg-surface p-8 text-center text-text-faint text-sm">
              {isRunning ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader size={22} className="animate-spin" style={{ color: ACCENT }} />
                  <span>Running autonomous investigation…</span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Shield size={28} style={{ color: ACCENT, opacity: 0.4 }} />
                  <span>Waiting for first cycle. Click "Run Cycle" to begin.</span>
                </div>
              )}
            </div>
          )}

          {/* History sidebar */}
          {history.length > 0 && (
            <div className="rounded-sm border border-border bg-surface overflow-hidden">
              <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                <span className="text-xs font-semibold text-text-primary">Cycle History</span>
                <span className="text-[10px] text-text-faint">{history.length} recent</span>
              </div>
              <div className="px-3 py-2 max-h-52 overflow-y-auto">
                {history.map((c, i) => (
                  <HistoryItem
                    key={c.ts_end || i}
                    cycle={c}
                    active={selectedCycle?.ts_end === c.ts_end}
                    onClick={() => {
                      setSelectedCycle(c)
                      setPhasesVisible(false)
                      setTimeout(() => setPhasesVisible(true), 50)
                    }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── How it works ── */}
      <div className="mt-6 rounded-sm border border-border bg-surface p-4">
        <div className="text-xs font-semibold text-text-primary mb-3">How NOC Autopilot Works</div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
          {Object.entries(PHASE_META).map(([key, meta]) => {
            const Icon = meta.icon
            return (
              <div key={key} className="flex flex-col items-center gap-1 p-2 rounded bg-surface-2 border border-border">
                <Icon size={14} style={{ color: meta.color }} />
                <span className="text-[10px] font-medium" style={{ color: meta.color }}>{meta.label}</span>
              </div>
            )
          })}
        </div>
        <p className="text-[11px] text-text-faint mt-3 leading-relaxed">
          Every 5 minutes the agent generates a 48-hour synthetic traffic window, predicts SLA risk,
          attributes anomalies, plans mitigations, simulates interventions, verifies resolution, and
          synthesises a report using <strong className="text-text-muted">Kimi K2.6</strong>.
        </p>
      </div>
    </div>
  )
}
