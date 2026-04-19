import { useDataset } from '../context/DatasetContext'
import { Database, AlertCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function DatasetBanner() {
  const { dataset } = useDataset()
  const navigate = useNavigate()

  if (dataset) {
    return (
      <div className="flex items-center gap-2.5 px-3 py-1.5 bg-accent-green-dim border border-accent-green-border rounded-sm text-xs">
        <Database size={12} className="text-accent-green shrink-0" />
        <span className="text-accent-green font-semibold truncate max-w-[180px]">{dataset.name}</span>
        <span className="text-text-muted">{dataset.rows.toLocaleString()} rows</span>
      </div>
    )
  }

  return (
    <button
      onClick={() => navigate('/upload')}
      className="flex items-center gap-2 px-3 py-1.5 bg-surface-2 border border-border rounded-sm text-xs text-text-muted hover:border-accent-teal hover:text-accent-teal transition-colors"
    >
      <AlertCircle size={12} />
      <span>No dataset loaded</span>
    </button>
  )
}
