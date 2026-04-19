import { useState } from 'react'
import { useDataset } from '../context/DatasetContext'
import { useToast } from '../hooks/useToast'
import { slaApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import MetricCard from '../components/MetricCard'
import SeverityBadge from '../components/SeverityBadge'
import { ShieldAlert, Upload as UploadIcon, Download, ChevronDown, ChevronUp } from 'lucide-react'

const ACCENT = '#22D3EE'
const ROW_BG = { HIGH: 'bg-red-600/10', MEDIUM: 'bg-orange-500/8', LOW: 'bg-yellow-500/5' }

export default function SLADetection() {
  const { dataset } = useDataset()
  const toast = useToast()
  const [timesFile, setTimesFile] = useState(null)
  const [results, setResults] = useState([])
  const [running, setRunning] = useState(false)
  const [onlyViolations, setOnlyViolations] = useState(false)
  const [severityFilter, setSeverityFilter] = useState(['LOW','MEDIUM','HIGH'])
  const [expanded, setExpanded] = useState(null)
  const [meta, setMeta] = useState(null)
  const [metaError, setMetaError] = useState(null)

  async function fetchMeta() {
    try {
      const m = await slaApi.metadata()
      setMeta(m); setMetaError(null)
    } catch (e) {
      setMetaError(e.message)
    }
  }

  async function runAnalysis() {
    if (!dataset) { toast('No dataset loaded', 'error'); return }
    setRunning(true); setResults([])
    try {
      const rows = dataset.data.map((row, i) => ({ ...row, __row_id: i }))
      const res = await slaApi.predict({ rows, input_row_count: rows.length })
      const built = (res.results || []).map(item => {
        const src = dataset.data[item.row_id] ?? {}
        const ts = src.datetime ?? src.timestamp ?? src.time ?? src.id_time ?? item.row_id
        if (item.skipped) return { timestamp: ts, anomaly: null }
        if (item.sla_violation) return {
          timestamp: ts, anomaly: true,
          severity: item.severity, score: item.probability,
          recommendation: item.recommendation, report: item.report,
        }
        return { timestamp: ts, anomaly: false, score: item.probability }
      })
      setResults(built)
      const cnt = built.filter(r => r.anomaly).length
      toast(`Analysis complete — ${cnt} SLA violations`, cnt > 0 ? 'warning' : 'success')
    } catch (e) {
      toast(`SLA API error: ${e.message}`, 'error')
    } finally {
      setRunning(false)
    }
  }

  function downloadCSV() {
    const rows = results.filter(r => r.anomaly)
    const cols = ['timestamp','severity','score','recommendation']
    const csv = [cols.join(','), ...rows.map(r => cols.map(c => r[c] ?? '').join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = 'sla_results.csv'; a.click()
  }

  const violationCount = results.filter(r => r.anomaly === true).length
  const violationRate = results.length ? ((violationCount / results.length) * 100).toFixed(2) : null
  const filtered = results.filter(r => {
    if (onlyViolations && !r.anomaly) return false
    if (r.anomaly && !severityFilter.includes(r.severity)) return false
    return true
  })

  return (
    <div className="max-w-5xl animate-fade-in">
      <PageHeader
        title="SLA Detection"
        subtitle="Detect SLA violations using an XGBoost model trained on 30+ engineered time-series features. Requires a dataset with timestamp information."
        accent={ACCENT}
      >
        {results.length > 0 && (
          <button onClick={downloadCSV} className="btn-secondary flex items-center gap-2">
            <Download size={13} /> Export CSV
          </button>
        )}
      </PageHeader>

      {/* API Status */}
      <div className="card p-4 mb-5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <ShieldAlert size={14} style={{ color: ACCENT }} />
          <span className="text-sm text-text-muted">SLA API (port 8003)</span>
          {meta && <span className="text-xs text-accent-green font-semibold">● Ready</span>}
          {metaError && <span className="text-xs text-red-400 font-semibold">● Unreachable</span>}
        </div>
        <button onClick={fetchMeta} className="btn-ghost text-xs">Check Status</button>
      </div>

      {/* Times CSV uploader */}
      <div className="card p-5 mb-5">
        <div className="label">Timestamps file (times_1_hour.csv) — optional</div>
        <div className="flex items-center gap-3">
          <div className="flex-1 input flex items-center gap-2 cursor-pointer"
            onClick={() => document.getElementById('times-upload').click()}>
            <UploadIcon size={13} className="text-text-faint shrink-0" />
            <span className="text-text-faint text-sm">
              {timesFile ? timesFile.name : 'Click to upload times_1_hour.csv'}
            </span>
          </div>
          {timesFile && (
            <button onClick={() => setTimesFile(null)} className="btn-ghost text-xs">Clear</button>
          )}
        </div>
        <input id="times-upload" type="file" accept=".csv" className="hidden"
          onChange={e => setTimesFile(e.target.files[0] || null)} />
        <p className="text-xs text-text-faint mt-2">
          Required only if your CSV uses id_time instead of real timestamps.
        </p>
      </div>

      {/* Run */}
      <div className="card p-5 mb-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold text-text-primary">
              {dataset ? `Analyse ${dataset.rows.toLocaleString()} rows` : 'No dataset loaded'}
            </div>
            <div className="text-xs text-text-muted mt-0.5">
              Uses dataset from Upload page or the file uploaded above
            </div>
          </div>
          <button
            onClick={runAnalysis}
            disabled={running || !dataset}
            className="btn-primary min-w-[140px]"
            style={{ background: running || !dataset ? undefined : ACCENT, color: running || !dataset ? undefined : '#0D1117' }}
          >
            {running ? 'Running…' : 'Run Analysis'}
          </button>
        </div>
      </div>

      {/* Metrics */}
      {results.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <MetricCard label="Total Rows" value={results.length.toLocaleString()} accent="#7D8590" />
          <MetricCard label="SLA Violations" value={violationCount.toLocaleString()} accent={ACCENT} />
          <MetricCard label="Violation Rate" value={violationRate ? `${violationRate}%` : '—'} accent="#F97316" />
        </div>
      )}

      {/* Filters */}
      {results.length > 0 && (
        <div className="flex items-center gap-4 mb-4 flex-wrap">
          <label className="flex items-center gap-2 text-sm text-text-muted cursor-pointer">
            <input type="checkbox" checked={onlyViolations} onChange={e => setOnlyViolations(e.target.checked)}
              className="accent-cyan-500" />
            Show only violations
          </label>
          {onlyViolations && (
            <div className="flex items-center gap-2">
              {['LOW','MEDIUM','HIGH'].map(s => (
                <label key={s} className="flex items-center gap-1.5 text-xs cursor-pointer">
                  <input type="checkbox" checked={severityFilter.includes(s)}
                    onChange={e => setSeverityFilter(p => e.target.checked ? [...p, s] : p.filter(x => x !== s))}
                    className="accent-cyan-500" />
                  <SeverityBadge label={s} />
                </label>
              ))}
            </div>
          )}
          <span className="ml-auto text-xs text-text-faint font-mono">{filtered.length} rows</span>
        </div>
      )}

      {/* Table */}
      {filtered.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr>
                {['#','Timestamp','Violation','Severity','Probability','Recommendation'].map(h => (
                  <th key={h} className="table-header text-left">{h}</th>
                ))}
                <th className="table-header" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <>
                  <tr key={i}
                    className={`table-row ${row.anomaly ? (ROW_BG[row.severity] || '') : ''} ${row.report ? 'cursor-pointer' : ''}`}
                    onClick={() => row.report && setExpanded(expanded === i ? null : i)}
                  >
                    <td className="table-cell font-mono text-text-faint">{i}</td>
                    <td className="table-cell font-mono text-xs">{String(row.timestamp ?? '—')}</td>
                    <td className="table-cell">
                      {row.anomaly === true
                        ? <span className="text-cyan-400 font-semibold text-xs">YES</span>
                        : row.anomaly === false
                        ? <span className="text-text-faint text-xs">NO</span>
                        : <span className="text-text-faint text-xs">SKIP</span>}
                    </td>
                    <td className="table-cell">{row.severity ? <SeverityBadge label={row.severity} /> : <span className="text-text-faint">—</span>}</td>
                    <td className="table-cell font-mono text-xs">{row.score != null ? (row.score * 100).toFixed(1) + '%' : '—'}</td>
                    <td className="table-cell text-xs max-w-xs truncate">{row.recommendation ?? <span className="text-text-faint">—</span>}</td>
                    <td className="table-cell">{row.report && (expanded === i ? <ChevronUp size={14} className="text-text-muted" /> : <ChevronDown size={14} className="text-text-muted" />)}</td>
                  </tr>
                  {expanded === i && row.report && (
                    <tr key={`${i}-exp`} className="bg-surface-2">
                      <td colSpan={7} className="px-6 py-4">
                        <pre className="text-xs font-mono text-text-muted whitespace-pre-wrap">
                          {typeof row.report === 'string' ? row.report : JSON.stringify(row.report, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
