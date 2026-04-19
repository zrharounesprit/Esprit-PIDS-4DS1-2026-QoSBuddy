import { useNavigate } from 'react-router-dom'
import { useDataset } from '../context/DatasetContext'
import {
  AlertTriangle, GitBranch, ShieldAlert, Users,
  TrendingUp, Network, Radio, Upload, ArrowRight, Database
} from 'lucide-react'

const FEATURES = [
  {
    to: '/anomaly', label: 'Anomaly Detection',
    desc: 'Detect network anomalies with Isolation Forest + SHAP explanations. Severity-ranked results with downloadable reports.',
    icon: AlertTriangle, accent: '#F04444', tag: 'ML · Isolation Forest',
  },
  {
    to: '/rca', label: 'Root Cause Analysis',
    desc: 'Diagnose what is driving anomalous traffic. KMeans clustering classifies IPs into four behavioral groups.',
    icon: GitBranch, accent: '#8B7CF8', tag: 'ML · KMeans',
  },
  {
    to: '/sla', label: 'SLA Detection',
    desc: 'Predict SLA breaches before they happen. XGBoost model trained on 30+ engineered time-series features.',
    icon: ShieldAlert, accent: '#22D3EE', tag: 'ML · XGBoost',
  },
  {
    to: '/persona', label: 'User Persona Classification',
    desc: 'Classify users as Gamers, Streamers, or Normal based on traffic patterns. 24h behavioral analysis.',
    icon: Users, accent: '#E040FB', tag: 'ML · XGBoost',
  },
  {
    to: '/forecast', label: 'Traffic Forecasting',
    desc: '6-hour ahead traffic volume prediction using an LSTM model with IP embedding and 24-hour lookback.',
    icon: TrendingUp, accent: '#3B82F6', tag: 'DL · LSTM',
  },
  {
    to: '/simulation', label: 'Network Simulation',
    desc: 'Agent-based simulation of network traffic. Run What-If scenarios with LLM-generated user personas.',
    icon: Network, accent: '#00FFD5', tag: 'Agent · Gemini',
  },
  {
    to: '/mcp', label: 'MCP Demo',
    desc: 'Live demonstration of the MCP bridge. Test the agent orchestration layer with real-time tool calls.',
    icon: Radio, accent: '#0097a7', tag: 'Protocol · MCP',
  },
]

export default function Home() {
  const navigate = useNavigate()
  const { dataset } = useDataset()

  return (
    <div className="max-w-5xl animate-fade-in">
      {/* Hero */}
      <div className="mb-10">
        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-teal mb-3">
          Esprit · PIDS · 4DS1 · 2026
        </div>
        <h1 className="text-4xl font-bold text-text-primary leading-tight mb-3">
          QoSBuddy
        </h1>
        <p className="text-text-muted text-lg max-w-2xl leading-relaxed">
          Intelligent Network Assurance & Autonomous Optimization.<br/>
          Anomaly detection, root cause analysis, SLA monitoring, and simulation — all in one place.
        </p>
        <div className="h-px mt-6 w-full" style={{ background: 'linear-gradient(to right, #00FFD560, transparent)' }} />
      </div>

      {/* Dataset status */}
      {dataset ? (
        <div className="flex items-center gap-3 mb-8 p-4 bg-accent-green-dim border border-accent-green-border rounded-sm">
          <Database size={16} className="text-accent-green shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-semibold text-accent-green">{dataset.name}</span>
            <span className="text-sm text-text-muted ml-3">{dataset.rows.toLocaleString()} rows · {dataset.columns.length} columns</span>
          </div>
          <span className="text-xs text-text-muted">Dataset loaded — all pages ready</span>
        </div>
      ) : (
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-3 mb-8 p-4 w-full text-left bg-surface border border-dashed border-border hover:border-accent-teal-border hover:bg-surface-2 transition-all rounded-sm group"
        >
          <Upload size={16} className="text-text-muted group-hover:text-accent-teal transition-colors shrink-0" />
          <div>
            <div className="text-sm font-semibold text-text-primary group-hover:text-accent-teal transition-colors">
              Upload your dataset to get started
            </div>
            <div className="text-xs text-text-muted mt-0.5">
              Upload a CSV once — all model pages will use it automatically
            </div>
          </div>
          <ArrowRight size={14} className="text-text-faint group-hover:text-accent-teal ml-auto transition-colors" />
        </button>
      )}

      {/* Feature grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {FEATURES.map(f => {
          const Icon = f.icon
          return (
            <button
              key={f.to}
              onClick={() => navigate(f.to)}
              className="card p-5 text-left hover:bg-surface-2 transition-all duration-150 group relative overflow-hidden"
            >
              {/* Accent glow */}
              <div
                className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{ background: `radial-gradient(ellipse at 0% 0%, ${f.accent}08 0%, transparent 60%)` }}
              />
              <div className="flex items-start gap-3 relative">
                <div
                  className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0 mt-0.5"
                  style={{ background: `${f.accent}15`, border: `1px solid ${f.accent}30` }}
                >
                  <Icon size={16} style={{ color: f.accent }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-sm font-semibold text-text-primary group-hover:text-white transition-colors">
                      {f.label}
                    </span>
                    <span
                      className="text-[10px] font-mono font-medium shrink-0"
                      style={{ color: f.accent }}
                    >
                      {f.tag}
                    </span>
                  </div>
                  <p className="text-xs text-text-muted leading-relaxed">{f.desc}</p>
                </div>
              </div>
              <div
                className="absolute bottom-0 left-0 h-0.5 w-0 group-hover:w-full transition-all duration-300"
                style={{ background: f.accent }}
              />
            </button>
          )
        })}
      </div>
    </div>
  )
}
