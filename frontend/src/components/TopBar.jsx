import { useLocation } from 'react-router-dom'
import { useDataset } from '../context/DatasetContext'
import {
  Database, AlertCircle, PanelLeftClose, PanelLeftOpen,
  Search, Bell, Wifi
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const PAGE_TITLES = {
  '/':           'Dashboard',
  '/upload':     'Upload Dataset',
  '/anomaly':    'Anomaly Detection',
  '/rca':        'Root Cause Analysis',
  '/sla':        'SLA Detection',
  '/persona':    'User Persona',
  '/forecast':   'Traffic Forecasting',
  '/simulation': 'Network Simulation',
  '/mcp':        'MCP Demo',
  '/auto-pilot': 'Green Auto-Pilot',
  '/noc':        'NOC Autopilot',
}

export default function TopBar({ collapsed, onToggle }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { dataset } = useDataset()
  const title = PAGE_TITLES[location.pathname] || 'QoSBuddy'

  return (
    <header className="h-14 shrink-0 flex items-center gap-4 px-4 lg:px-6 border-b border-border bg-surface/80 backdrop-blur-xl z-20">
      {/* Toggle */}
      <button
        onClick={onToggle}
        className="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
      >
        {collapsed
          ? <PanelLeftOpen size={18} />
          : <PanelLeftClose size={18} />
        }
      </button>

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-sm font-semibold text-text-primary truncate">{title}</span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Status indicators */}
      <div className="hidden md:flex items-center gap-3">
        {/* Live indicator */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-accent-green-dim border border-accent-green-border">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-green opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-green" />
          </span>
          <span className="text-[11px] font-medium text-accent-green">Live</span>
        </div>

        {/* Dataset chip */}
        {dataset ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-accent-teal-dim border border-accent-teal-border">
            <Database size={11} className="text-accent-teal" />
            <span className="text-[11px] font-medium text-accent-teal truncate max-w-[140px]">{dataset.name}</span>
          </div>
        ) : (
          <button
            onClick={() => navigate('/upload')}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-2 border border-border text-[11px] text-text-muted hover:border-accent-teal-border hover:text-accent-teal transition-colors"
          >
            <AlertCircle size={11} />
            No dataset
          </button>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        <button className="p-2 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors">
          <Bell size={16} />
        </button>
      </div>
    </header>
  )
}
