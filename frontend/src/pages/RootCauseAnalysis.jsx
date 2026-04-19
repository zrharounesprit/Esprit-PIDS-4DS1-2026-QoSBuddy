import { useState } from 'react'
import { useDataset } from '../context/DatasetContext'
import { useToast } from '../hooks/useToast'
import { rcaApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import SeverityBadge from '../components/SeverityBadge'
import { GitBranch, ChevronDown, ChevronUp } from 'lucide-react'

const ACCENT = '#8B7CF8'

const CAUSE_ACCENT = {
  extreme_scanner: '#F04444',
  udp_suspicious:  '#F97316',
  congestion:      '#EAB308',
  normal:          '#22C55E',
}

export default function RootCauseAnalysis() {
  const { dataset } = useDataset()
  const toast = useToast()
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [rawOpen, setRawOpen] = useState(false)

  const RCA_FIELDS = [
    'id_ip','n_flows','n_packets','n_bytes','sum_n_dest_ip','sum_n_dest_ports',
    'std_n_dest_ip','tcp_udp_ratio_packets','tcp_udp_ratio_bytes',
    'dir_ratio_packets','dir_ratio_bytes','avg_duration','avg_ttl',
  ]

  async function analyse() {
    if (!dataset) return
    const row = dataset.data[selectedIdx]
    const payload = {
      id_ip:                   parseInt(row.id_ip ?? 0),
      n_flows:                 parseFloat(row.n_flows ?? 0),
      n_packets:               parseFloat(row.n_packets ?? 0),
      n_bytes:                 parseFloat(row.n_bytes ?? 0),
      sum_n_dest_ip:           parseFloat(row.sum_n_dest_ip ?? 0),
      sum_n_dest_ports:        parseFloat(row.sum_n_dest_ports ?? 0),
      std_n_dest_ip:           parseFloat(row.std_n_dest_ip ?? 0),
      tcp_udp_ratio_packets:   parseFloat(row.tcp_udp_ratio_packets ?? 1),
      tcp_udp_ratio_bytes:     parseFloat(row.tcp_udp_ratio_bytes ?? 1),
      dir_ratio_packets:       parseFloat(row.dir_ratio_packets ?? 0.5),
      dir_ratio_bytes:         parseFloat(row.dir_ratio_bytes ?? 0.5),
      avg_duration:            parseFloat(row.avg_duration ?? 0),
      avg_ttl:                 parseFloat(row.avg_ttl ?? 0),
    }
    setLoading(true); setReport(null)
    try {
      const res = await rcaApi.analyse(payload)
      setReport(res)
      toast('Root cause analysis complete', 'success')
    } catch (e) {
      toast(`RCA API error: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  if (!dataset) return (
    <div className="max-w-3xl animate-fade-in">
      <PageHeader title="Root Cause Analysis" accent={ACCENT} />
      <div className="flex flex-col items-center py-20">
        <GitBranch size={32} className="text-text-faint mb-4" />
        <div className="text-sm text-text-muted">No dataset loaded — go to Upload first.</div>
      </div>
    </div>
  )

  const causeColor = report ? (CAUSE_ACCENT[report.cause_label] || '#7D8590') : ACCENT

  return (
    <div className="max-w-3xl animate-fade-in">
      <PageHeader
        title="Root Cause Analysis"
        subtitle="Select a row from your dataset to diagnose the root cause of its network behaviour using KMeans clustering."
        accent={ACCENT}
      />

      {/* Row selector */}
      <div className="card p-5 mb-6">
        <div className="label">Select row to analyse</div>
        <div className="flex items-center gap-3">
          <select
            value={selectedIdx}
            onChange={e => { setSelectedIdx(Number(e.target.value)); setReport(null) }}
            className="input flex-1"
          >
            {dataset.data.map((row, i) => (
              <option key={i} value={i}>
                Row {i}{row.id_ip != null ? ` — IP ${row.id_ip}` : ''}{row.timestamp ? ` · ${row.timestamp}` : ''}
              </option>
            ))}
          </select>
          <button
            onClick={analyse}
            disabled={loading}
            className="btn-primary min-w-[140px]"
            style={{ background: loading ? undefined : ACCENT }}
          >
            {loading ? 'Analysing…' : 'Analyse Root Cause'}
          </button>
        </div>

        {/* Selected row preview */}
        <div className="mt-4 pt-4 border-t border-border">
          <div className="label">Selected Row Values</div>
          <div className="grid grid-cols-3 gap-2">
            {RCA_FIELDS.filter(f => dataset.columns.includes(f)).map(f => (
              <div key={f} className="flex items-center justify-between px-2 py-1 bg-surface rounded-sm">
                <span className="text-xs text-text-faint font-mono">{f}</span>
                <span className="text-xs text-text-primary font-mono ml-2">
                  {dataset.data[selectedIdx]?.[f] ?? '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Report */}
      {report && (
        <div className="animate-fade-in">
          {/* Header card */}
          <div
            className="rounded-sm p-5 mb-5"
            style={{
              background: `${causeColor}10`,
              borderLeft: `4px solid ${causeColor}`,
              border: `1px solid ${causeColor}30`,
              borderLeftWidth: '4px',
            }}
          >
            <div className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: causeColor }}>
              Root Cause Analysis Report
            </div>
            <div className="text-xl font-bold text-text-primary mb-2">{report.cause_title}</div>
            <div className="flex items-center gap-3 flex-wrap">
              <SeverityBadge label={report.cause_label} />
              <span className="text-xs text-text-muted font-mono">
                IP: {report.id_ip} &nbsp;·&nbsp; {report.generated_at}
              </span>
            </div>
          </div>

          {/* What it means */}
          <div className="card p-5 mb-4">
            <div className="section-title">What This Means</div>
            <p className="text-sm text-text-muted leading-relaxed">{report.what_it_means}</p>
          </div>

          {/* Why we think this */}
          {report.why_we_think_this?.length > 0 && (
            <div className="card p-5 mb-4">
              <div className="section-title">Why We Think This</div>
              <div className="flex flex-col gap-2">
                {report.why_we_think_this.map((obs, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-3 bg-canvas rounded-sm"
                    style={{ borderLeft: `2px solid ${causeColor}` }}
                  >
                    <span className="text-xs font-bold mt-0.5" style={{ color: causeColor }}>{i + 1}.</span>
                    <p className="text-sm text-text-primary leading-relaxed">{obs}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Raw JSON */}
          <div className="card overflow-hidden">
            <button
              onClick={() => setRawOpen(o => !o)}
              className="flex items-center justify-between w-full px-5 py-3 text-sm text-text-muted hover:text-text-primary transition-colors"
            >
              <span>View raw JSON</span>
              {rawOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {rawOpen && (
              <div className="px-5 pb-5 border-t border-border">
                <pre className="text-xs font-mono text-text-muted leading-relaxed overflow-x-auto pt-4">
                  {JSON.stringify(report, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
