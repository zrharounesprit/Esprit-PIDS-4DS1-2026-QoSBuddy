import { useState } from 'react'
import { useDataset } from '../context/DatasetContext'
import { useToast } from '../hooks/useToast'
import { anomalyApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import MetricCard from '../components/MetricCard'
import SeverityBadge from '../components/SeverityBadge'
import ProgressBar from '../components/ProgressBar'
import { AlertTriangle, Download, ChevronDown, ChevronUp } from 'lucide-react'

const ACCENT = '#F04444'
const FEATURES = ['n_bytes','n_packets','n_flows','tcp_udp_ratio_packets','dir_ratio_packets']

function NoDataset() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <AlertTriangle size={32} className="text-text-faint mb-4" />
      <div className="text-sm font-semibold text-text-muted mb-1">No dataset loaded</div>
      <div className="text-xs text-text-faint">Go to Upload Dataset in the sidebar first.</div>
    </div>
  )
}

const ROW_BG = { HIGH: 'bg-red-600/10', MEDIUM: 'bg-orange-500/8', LOW: 'bg-yellow-500/5' }

export default function AnomalyDetection() {
  const { dataset } = useDataset()
  const toast = useToast()
  const [results, setResults] = useState([])
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const [onlyAnomalies, setOnlyAnomalies] = useState(false)
  const [severityFilter, setSeverityFilter] = useState(['LOW','MEDIUM','HIGH'])
  const [expanded, setExpanded] = useState(null)

  async function runAnalysis() {
    if (!dataset) return
    const missing = FEATURES.filter(f => !dataset.columns.includes(f))
    if (missing.length) { toast(`Missing columns: ${missing.join(', ')}`, 'error'); return }

    setRunning(true); setResults([]); setProgress({ done: 0, total: dataset.rows })
    const out = []

    for (let i = 0; i < dataset.data.length; i++) {
      const row = dataset.data[i]
      const payload = Object.fromEntries(FEATURES.map(f => [f, row[f]]))
      try {
        const r = await anomalyApi.predict(payload)
        out.push({
          idx: i,
          timestamp: row.timestamp ?? row.time ?? row.id_time ?? i,
          anomaly: r.anomaly,
          severity: r.severity ?? null,
          score: r.score ?? null,
          recommendation: r.recommendation ?? null,
          report: r.report ?? null,
        })
      } catch {
        out.push({ idx: i, timestamp: row.timestamp ?? i, anomaly: false, severity: null, score: null, recommendation: null, report: null })
      }
      setProgress({ done: i + 1, total: dataset.rows })
      if ((i + 1) % 10 === 0) setResults([...out])
    }

    setResults([...out])
    setRunning(false)
    const cnt = out.filter(r => r.anomaly).length
    toast(`Analysis complete — ${cnt} anomalies found`, cnt > 0 ? 'warning' : 'success')
  }

  function downloadCSV() {
    const rows = results.filter(r => r.anomaly)
    const cols = ['timestamp','severity','score','recommendation']
    const csv = [cols.join(','), ...rows.map(r => cols.map(c => r[c] ?? '').join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = 'anomaly_results.csv'; a.click()
  }

  const anomalyCount = results.filter(r => r.anomaly).length
  const anomalyRate = results.length ? ((anomalyCount / results.length) * 100).toFixed(2) : null
  const filtered = results.filter(r => {
    if (onlyAnomalies && !r.anomaly) return false
    if (r.anomaly && !severityFilter.includes(r.severity)) return false
    return true
  })

  return (
    <div className="max-w-5xl animate-fade-in">
      <PageHeader
        title="Anomaly Detection"
        subtitle="Detect anomalies in network traffic using Isolation Forest. Each flagged row includes SHAP-based explanations and actionable recommendations."
        accent={ACCENT}
      >
        {results.length > 0 && (
          <button onClick={downloadCSV} className="btn-secondary flex items-center gap-2">
            <Download size={13} /> Export CSV
          </button>
        )}
      </PageHeader>

      {!dataset ? <NoDataset /> : (
        <>
          {/* Run button + progress */}
          <div className="card p-5 mb-6">
            <div className="flex items-center justify-between gap-4 mb-4">
              <div>
                <div className="text-sm font-semibold text-text-primary">Analyse {dataset.rows.toLocaleString()} rows</div>
                <div className="text-xs text-text-muted mt-0.5">
                  Requires: {FEATURES.join(', ')}
                </div>
              </div>
              <button onClick={runAnalysis} disabled={running} className="btn-primary min-w-[120px]"
                style={{ background: running ? undefined : ACCENT }}>
                {running ? 'Running…' : 'Run Analysis'}
              </button>
            </div>
            {running && (
              <ProgressBar value={progress.done} max={progress.total}
                label="Processing rows" accent={ACCENT} />
            )}
          </div>

          {/* Metrics */}
          {results.length > 0 && (
            <div className="grid grid-cols-3 gap-4 mb-6">
              <MetricCard label="Total Rows" value={results.length.toLocaleString()} accent="#7D8590" />
              <MetricCard label="Anomalies" value={anomalyCount.toLocaleString()} accent={ACCENT} />
              <MetricCard label="Anomaly Rate" value={anomalyRate ? `${anomalyRate}%` : '—'} accent="#F97316" />
            </div>
          )}

          {/* Filters */}
          {results.length > 0 && (
            <div className="flex items-center gap-4 mb-4">
              <label className="flex items-center gap-2 text-sm text-text-muted cursor-pointer select-none">
                <input type="checkbox" checked={onlyAnomalies} onChange={e => setOnlyAnomalies(e.target.checked)}
                  className="accent-red-500" />
                Show only anomalies
              </label>
              {onlyAnomalies && (
                <div className="flex items-center gap-2">
                  {['LOW','MEDIUM','HIGH'].map(s => (
                    <label key={s} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
                      <input type="checkbox" checked={severityFilter.includes(s)}
                        onChange={e => setSeverityFilter(prev =>
                          e.target.checked ? [...prev, s] : prev.filter(x => x !== s))}
                        className="accent-red-500" />
                      <SeverityBadge label={s} />
                    </label>
                  ))}
                </div>
              )}
              <span className="ml-auto text-xs text-text-faint font-mono">{filtered.length} rows shown</span>
            </div>
          )}

          {/* Results table */}
          {filtered.length > 0 && (
            <div className="card overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr>
                    {['#','Timestamp','Anomaly','Severity','Score','Recommendation'].map(h => (
                      <th key={h} className="table-header text-left">{h}</th>
                    ))}
                    <th className="table-header" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(row => (
                    <>
                      <tr
                        key={row.idx}
                        className={`table-row cursor-pointer ${row.anomaly ? (ROW_BG[row.severity] || '') : ''}`}
                        onClick={() => setExpanded(expanded === row.idx ? null : row.idx)}
                      >
                        <td className="table-cell font-mono text-text-faint">{row.idx}</td>
                        <td className="table-cell font-mono">{String(row.timestamp)}</td>
                        <td className="table-cell">
                          {row.anomaly
                            ? <span className="text-red-400 font-semibold text-xs">YES</span>
                            : <span className="text-text-faint text-xs">—</span>}
                        </td>
                        <td className="table-cell">
                          {row.severity ? <SeverityBadge label={row.severity} /> : <span className="text-text-faint">—</span>}
                        </td>
                        <td className="table-cell font-mono text-xs">
                          {row.score != null ? row.score.toFixed(4) : '—'}
                        </td>
                        <td className="table-cell text-xs max-w-xs truncate">
                          {row.recommendation ?? <span className="text-text-faint">—</span>}
                        </td>
                        <td className="table-cell">
                          {row.report && (
                            expanded === row.idx
                              ? <ChevronUp size={14} className="text-text-muted" />
                              : <ChevronDown size={14} className="text-text-muted" />
                          )}
                        </td>
                      </tr>
                      {expanded === row.idx && row.report && (
                        <tr key={`${row.idx}-exp`} className="bg-surface-2">
                          <td colSpan={7} className="px-6 py-4">
                            <div className="text-xs text-text-muted mb-1 font-semibold uppercase tracking-wider">Report</div>
                            <pre className="text-xs font-mono text-text-primary whitespace-pre-wrap leading-relaxed">
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
        </>
      )}
    </div>
  )
}
