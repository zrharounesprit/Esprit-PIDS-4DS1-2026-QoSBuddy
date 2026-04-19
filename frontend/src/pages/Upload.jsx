import { useState, useRef } from 'react'
import { useDataset } from '../context/DatasetContext'
import { useToast } from '../hooks/useToast'
import PageHeader from '../components/PageHeader'
import { Upload as UploadIcon, FileText, X, CheckCircle, Table } from 'lucide-react'

const ACCENT = '#22C55E'

export default function Upload() {
  const { dataset, setDataset, clearDataset } = useDataset()
  const toast = useToast()
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef()

  function parseCSV(text) {
    const lines = text.trim().split('\n')
    if (lines.length < 2) throw new Error('CSV must have a header row and at least one data row.')
    const columns = lines[0].split(',').map(c => c.trim().replace(/^"|"$/g, ''))
    const data = lines.slice(1).map(line => {
      const vals = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''))
      const row = {}
      columns.forEach((col, i) => { row[col] = isNaN(vals[i]) ? vals[i] : Number(vals[i]) })
      return row
    })
    return { columns, data, rows: data.length }
  }

  async function handleFile(file) {
    if (!file.name.endsWith('.csv')) { toast('Only CSV files are supported.', 'error'); return }
    setLoading(true)
    try {
      const text = await file.text()
      const { columns, data, rows } = parseCSV(text)
      setDataset({ name: file.name, rows, columns, data })
      toast(`${file.name} loaded — ${rows.toLocaleString()} rows`, 'success')
    } catch (e) {
      toast(`Failed to parse CSV: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  function onDrop(e) {
    e.preventDefault(); setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="max-w-3xl animate-fade-in">
      <PageHeader
        title="Upload Dataset"
        subtitle="Upload your CESNET CSV file once. All model pages will read from it automatically."
        accent={ACCENT}
      />

      {dataset ? (
        <div className="card p-6 mb-6" style={{ borderColor: '#22C55E40' }}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <CheckCircle size={20} className="text-accent-green shrink-0" />
              <div>
                <div className="text-sm font-semibold text-text-primary">{dataset.name}</div>
                <div className="text-xs text-text-muted mt-0.5">
                  {dataset.rows.toLocaleString()} rows · {dataset.columns.length} columns
                </div>
              </div>
            </div>
            <button
              onClick={clearDataset}
              className="btn-ghost text-xs flex items-center gap-1"
            >
              <X size={12} /> Remove
            </button>
          </div>

          {/* Column list */}
          <div className="mt-4 pt-4 border-t border-border">
            <div className="label">Detected Columns</div>
            <div className="flex flex-wrap gap-1.5">
              {dataset.columns.map(col => (
                <span key={col} className="px-2 py-0.5 bg-surface-2 border border-border text-xs font-mono text-text-muted rounded-sm">
                  {col}
                </span>
              ))}
            </div>
          </div>

          {/* Preview table */}
          <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center gap-2 mb-3">
              <Table size={13} className="text-text-muted" />
              <span className="label mb-0">Preview (first 5 rows)</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    {dataset.columns.slice(0, 8).map(col => (
                      <th key={col} className="table-header text-left">{col}</th>
                    ))}
                    {dataset.columns.length > 8 && <th className="table-header text-left">+{dataset.columns.length - 8} more</th>}
                  </tr>
                </thead>
                <tbody>
                  {dataset.data.slice(0, 5).map((row, i) => (
                    <tr key={i} className="table-row">
                      {dataset.columns.slice(0, 8).map(col => (
                        <td key={col} className="table-cell">{String(row[col] ?? '—')}</td>
                      ))}
                      {dataset.columns.length > 8 && <td className="table-cell text-text-faint">…</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <button onClick={() => inputRef.current.click()} className="btn-secondary mt-5 w-full">
            Replace with a different file
          </button>
        </div>
      ) : (
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current.click()}
          className={`border-2 border-dashed rounded-sm p-14 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 ${
            dragging
              ? 'border-accent-green bg-accent-green-dim'
              : 'border-border hover:border-accent-green-border hover:bg-surface-2'
          }`}
        >
          <UploadIcon
            size={32}
            className="mb-4"
            style={{ color: dragging ? ACCENT : '#484F58' }}
          />
          <div className="text-sm font-semibold text-text-primary mb-1">
            {dragging ? 'Drop to upload' : 'Drop your CSV here'}
          </div>
          <div className="text-xs text-text-muted">or click to browse</div>
          <div className="mt-4 text-xs text-text-faint font-mono">
            Supported: .csv — CESNET-format network traffic files
          </div>
          {loading && <div className="mt-4 text-xs text-accent-green animate-pulse">Parsing…</div>}
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={e => { if (e.target.files[0]) handleFile(e.target.files[0]) }}
      />

      {/* Help */}
      <div className="mt-6 card p-4">
        <div className="flex items-start gap-3">
          <FileText size={14} className="text-text-muted shrink-0 mt-0.5" />
          <div className="text-xs text-text-muted leading-relaxed">
            <strong className="text-text-primary">Required columns for full functionality:</strong>
            {' '}n_bytes, n_packets, n_flows, tcp_udp_ratio_packets, dir_ratio_packets, sum_n_dest_ip,
            sum_n_dest_ports, avg_duration, avg_ttl, id_ip, id_time / timestamp.{' '}
            Some pages (SLA, Forecasting) may require additional columns — check individual page requirements.
          </div>
        </div>
      </div>
    </div>
  )
}
