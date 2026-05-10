import { useState, useRef } from 'react'
import { useToast } from '../hooks/useToast'
import { autopilotApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import {
  Bot, Upload, X, FileText, ChevronRight, Loader, CheckCircle,
  AlertTriangle, XCircle, Info, Zap, Brain, TrendingUp, Activity
} from 'lucide-react'

const ACCENT = '#F59E0B'

// ── Severity config ────────────────────────────────────────────────────────
const SEV_CONFIG = {
  CRITICAL: { color: '#EF4444', bg: '#7f1d1d33', label: 'CRITICAL', icon: XCircle },
  HIGH:     { color: '#F97316', bg: '#7c2d1233', label: 'HIGH',     icon: AlertTriangle },
  MEDIUM:   { color: '#EAB308', bg: '#71350033', label: 'MEDIUM',   icon: AlertTriangle },
  LOW:      { color: '#22C55E', bg: '#14532d33', label: 'LOW',      icon: CheckCircle },
}

// ── Step config ────────────────────────────────────────────────────────────
const STEP_META = {
  'Anomaly Detection':     { icon: Activity,  color: '#EF4444', num: 1 },
  'Root Cause Analysis':   { icon: Zap,       color: '#8B7CF8', num: 2 },
  'Persona Classification':{ icon: Brain,     color: '#E040FB', num: 3 },
  'SLA Risk':              { icon: AlertTriangle, color: '#F97316', num: 4 },
  'Traffic Forecast':      { icon: TrendingUp,color: '#3B82F6', num: 5 },
}

// ── Step row ────────────────────────────────────────────────────────────────
function StepRow({ step, index, visible }) {
  const meta = STEP_META[step.step] || { icon: Info, color: '#6B7280', num: index + 1 }
  const Icon = meta.icon

  const statusEl = {
    ok:   <CheckCircle size={13} className="text-green-400 flex-shrink-0 mt-0.5" />,
    warn: <AlertTriangle size={13} className="text-yellow-400 flex-shrink-0 mt-0.5" />,
    error:<XCircle size={13} className="text-red-400 flex-shrink-0 mt-0.5" />,
    info: <Info size={13} className="text-blue-400 flex-shrink-0 mt-0.5" />,
  }[step.status] || <CheckCircle size={13} className="text-green-400 flex-shrink-0 mt-0.5" />

  return (
    <div
      className="flex items-start gap-3 py-2.5 border-b border-border last:border-0 transition-all duration-500"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(10px)',
        transitionDelay: `${index * 120}ms`,
      }}
    >
      <div className="flex-shrink-0 w-7 h-7 rounded flex items-center justify-center text-xs font-bold"
           style={{ background: `${meta.color}18`, border: `1px solid ${meta.color}44`, color: meta.color }}>
        {meta.num}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <Icon size={12} style={{ color: meta.color }} />
          <span className="text-xs font-semibold text-text-primary">{step.icon} {step.step}</span>
        </div>
        <div className="flex items-start gap-1.5">
          {statusEl}
          <p className="text-[11px] text-text-muted leading-relaxed">{step.summary}</p>
        </div>
      </div>
    </div>
  )
}

// ── Report card ─────────────────────────────────────────────────────────────
function ReportCard({ result, visible }) {
  const sev = SEV_CONFIG[result.severity] || SEV_CONFIG.LOW
  const SevIcon = sev.icon
  const synthesis = result.synthesis || {}

  return (
    <div
      className="rounded-sm border border-border bg-surface overflow-hidden transition-all duration-700"
      style={{ opacity: visible ? 1 : 0, transform: visible ? 'translateY(0)' : 'translateY(20px)' }}
    >
      {/* Banner */}
      <div className="px-4 py-3 flex items-center gap-2.5"
           style={{ background: sev.bg, borderBottom: `1px solid ${sev.color}44` }}>
        <SevIcon size={16} style={{ color: sev.color }} />
        <span className="text-sm font-bold tracking-wide" style={{ color: sev.color }}>
          {result.severity} SEVERITY
        </span>
        <span className="ml-auto text-[10px] text-text-faint">
          {result.rows} rows · {result.columns?.length || 0} cols
        </span>
      </div>

      <div className="p-4 grid gap-4">
        {/* Summary */}
        {synthesis.executive_summary && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1">Executive Summary</div>
            <p className="text-sm text-text-primary leading-relaxed">{synthesis.executive_summary}</p>
          </div>
        )}

        {/* Root cause + Impact */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {synthesis.root_cause && (
            <div className="rounded bg-surface-2 border border-border p-3">
              <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1">Root Cause</div>
              <p className="text-[11px] text-text-muted leading-relaxed">{synthesis.root_cause}</p>
            </div>
          )}
          {synthesis.business_impact && (
            <div className="rounded bg-surface-2 border border-border p-3">
              <div className="text-[10px] uppercase tracking-widest text-text-faint mb-1">Business Impact</div>
              <p className="text-[11px] text-text-muted leading-relaxed">{synthesis.business_impact}</p>
            </div>
          )}
        </div>

        {/* Recommendations */}
        {synthesis.recommendations?.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-text-faint mb-2">Recommendations</div>
            <div className="grid gap-1.5">
              {synthesis.recommendations.map((rec, i) => (
                <div key={i} className="flex items-start gap-2 text-[11px] text-text-muted">
                  <ChevronRight size={11} className="mt-0.5 flex-shrink-0" style={{ color: ACCENT }} />
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Source */}
        {synthesis.source && (
          <div className="text-[10px] text-text-faint flex items-center gap-1.5 pt-1 border-t border-border">
            <Brain size={10} />
            Synthesised by {synthesis.source}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function Autopilot() {
  const toast = useToast()
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [stepsVisible, setStepsVisible] = useState(false)
  const fileRef = useRef(null)

  function handleFile(f) {
    if (!f || !f.name.endsWith('.csv')) {
      toast('Please upload a .csv file.', 'error')
      return
    }
    setFile(f)
    setResult(null)
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  async function runAnalysis() {
    if (!file) return
    setLoading(true)
    setResult(null)
    setStepsVisible(false)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await autopilotApi.analyze(fd)
      setResult(res)
      setTimeout(() => setStepsVisible(true), 100)
      if (res.severity === 'CRITICAL' || res.severity === 'HIGH') {
        toast(`${res.severity} severity detected`, 'error')
      } else {
        toast(`Analysis complete — Severity: ${res.severity}`, 'success')
      }
    } catch (e) {
      toast(`Analysis failed: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  // Pipeline strip steps
  const PIPELINE = [
    { label: 'Anomaly', color: '#EF4444' },
    { label: 'Root Cause', color: '#8B7CF8' },
    { label: 'Persona', color: '#E040FB' },
    { label: 'SLA Risk', color: '#F97316' },
    { label: 'Forecast', color: '#3B82F6' },
    { label: 'Kimi K2.6', color: '#00FFD5' },
  ]

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <PageHeader
        icon={<Bot size={20} style={{ color: ACCENT }} />}
        title="Autopilot"
        subtitle="Upload a CESNET traffic CSV for a full AI-powered incident investigation"
        accent={ACCENT}
      />

      {/* Pipeline strip */}
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1">
        {PIPELINE.map((p, i) => (
          <div key={i} className="flex items-center gap-1 flex-shrink-0">
            <div className="rounded px-2.5 py-1 text-[10px] font-medium border"
                 style={{ color: p.color, borderColor: `${p.color}44`, background: `${p.color}10` }}>
              {p.label}
            </div>
            {i < PIPELINE.length - 1 && <ChevronRight size={10} className="text-text-faint" />}
          </div>
        ))}
      </div>

      {/* Upload zone */}
      <div
        className={`mb-5 rounded-sm border-2 border-dashed transition-colors cursor-pointer ${
          dragging ? 'border-amber-400 bg-amber-400/5' : 'border-border hover:border-border-hover'
        }`}
        onClick={() => fileRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={e => handleFile(e.target.files[0])}
        />
        {file ? (
          <div className="flex items-center gap-3 p-4">
            <FileText size={20} style={{ color: ACCENT }} />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-text-primary truncate">{file.name}</div>
              <div className="text-[11px] text-text-faint">
                {(file.size / 1024).toFixed(1)} KB — click to replace
              </div>
            </div>
            <button
              className="p-1 hover:bg-surface-2 rounded"
              onClick={e => { e.stopPropagation(); setFile(null); setResult(null) }}
            >
              <X size={14} className="text-text-faint" />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 py-8">
            <Upload size={22} style={{ color: ACCENT, opacity: 0.7 }} />
            <span className="text-sm text-text-muted">Drop CESNET CSV here or click to browse</span>
            <span className="text-[11px] text-text-faint">
              18-column CESNET format — include id_time for full SLA analysis
            </span>
          </div>
        )}
      </div>

      {/* Run button */}
      <button
        onClick={runAnalysis}
        disabled={!file || loading}
        className="mb-6 flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-sm transition-all disabled:opacity-40"
        style={{
          background: file && !loading ? `${ACCENT}22` : undefined,
          border: `1px solid ${ACCENT}55`,
          color: ACCENT,
        }}
      >
        {loading ? (
          <>
            <Loader size={14} className="animate-spin" />
            Investigating…
          </>
        ) : (
          <>
            <Bot size={14} />
            Run Autopilot Investigation
          </>
        )}
      </button>

      {/* Results */}
      {result && (
        <div className="grid gap-5">
          {/* Step timeline */}
          <div className="rounded-sm border border-border bg-surface overflow-hidden">
            <div className="px-4 py-3 border-b border-border">
              <span className="text-xs font-semibold text-text-primary">Investigation Steps</span>
            </div>
            <div className="px-4 py-2">
              {result.steps?.map((step, i) => (
                <StepRow key={i} step={step} index={i} visible={stepsVisible} />
              ))}
            </div>
          </div>

          {/* Report */}
          <ReportCard result={result} visible={stepsVisible} />
        </div>
      )}
    </div>
  )
}
