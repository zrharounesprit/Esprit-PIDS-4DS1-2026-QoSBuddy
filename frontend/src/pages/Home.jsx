import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDataset } from '../context/DatasetContext'
import { nocApi } from '../api/client'
import {
  AlertTriangle, GitBranch, ShieldAlert, Users,
  TrendingUp, Network, Radio, Upload, ArrowRight,
  Database, Shield, Activity, Zap, BarChart3, Leaf,
  CheckCircle, XCircle, Clock, ChevronRight, ArrowUpRight
} from 'lucide-react'

/* ── Feature cards config ──────────────────────────────────────────── */
const FEATURES = [
  {
    to: '/anomaly', label: 'Anomaly Detection',
    desc: 'Isolation Forest + SHAP explanations',
    icon: AlertTriangle, accent: '#FF5A5A', tag: 'ML',
  },
  {
    to: '/rca', label: 'Root Cause Analysis',
    desc: 'KMeans IP behavioral clustering',
    icon: GitBranch, accent: '#A78BFA', tag: 'ML',
  },
  {
    to: '/sla', label: 'SLA Detection',
    desc: 'XGBoost breach prediction',
    icon: ShieldAlert, accent: '#38BDF8', tag: 'ML',
  },
  {
    to: '/persona', label: 'User Persona',
    desc: 'Gamer / Streamer / Normal classification',
    icon: Users, accent: '#E879F9', tag: 'ML',
  },
  {
    to: '/forecast', label: 'Traffic Forecasting',
    desc: 'LSTM 6-hour prediction',
    icon: TrendingUp, accent: '#60A5FA', tag: 'DL',
  },
  {
    to: '/simulation', label: 'Network Simulation',
    desc: 'Agent-based what-if scenarios',
    icon: Network, accent: '#00E8C6', tag: 'Agent',
  },
  {
    to: '/auto-pilot', label: 'Green Auto-Pilot',
    desc: 'Multi-LLM autonomous agent',
    icon: Leaf, accent: '#34D399', tag: 'LLM',
  },
  {
    to: '/noc', label: 'NOC Autopilot',
    desc: 'Autonomous SLA guardian',
    icon: Shield, accent: '#00E8C6', tag: 'AI Ops',
  },
]

/* ── Stat card component ──────────────────────────────────────────── */
function StatCard({ label, value, sub, icon: Icon, accent, delay = 0 }) {
  return (
    <div
      className="card-elevated p-5 animate-fade-up opacity-0"
      style={{ animationDelay: `${delay}ms`, animationFillMode: 'forwards' }}
    >
      <div className="flex items-start justify-between mb-3">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ background: `${accent}12`, border: `1px solid ${accent}20` }}
        >
          <Icon size={16} style={{ color: accent }} />
        </div>
      </div>
      <div className="text-2xl font-bold font-mono text-text-primary">{value}</div>
      <div className="text-[11px] font-medium text-text-muted mt-1 uppercase tracking-wider">{label}</div>
      {sub && <div className="text-xs text-text-faint mt-1">{sub}</div>}
    </div>
  )
}

/* ── NOC Status widget ────────────────────────────────────────────── */
function NocWidget({ nocData }) {
  const navigate = useNavigate()
  if (!nocData) {
    return (
      <div className="card-elevated p-5 col-span-full lg:col-span-2 animate-fade-up opacity-0" style={{ animationDelay: '200ms', animationFillMode: 'forwards' }}>
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-accent-teal-dim border border-accent-teal-border">
            <Shield size={16} className="text-accent-teal" />
          </div>
          <div>
            <div className="text-sm font-semibold text-text-primary">NOC Autopilot</div>
            <div className="text-xs text-text-muted">Connecting...</div>
          </div>
        </div>
        <div className="skeleton h-16 rounded-md" />
      </div>
    )
  }

  const isBreached = nocData.breach_detected
  const statusColor = isBreached ? (nocData.resolved ? '#FBBF24' : '#FF5A5A') : '#34D399'
  const statusText = isBreached ? (nocData.resolved ? 'Resolved' : 'Active Breach') : 'Nominal'
  const StatusIcon = isBreached ? (nocData.resolved ? CheckCircle : XCircle) : CheckCircle

  return (
    <div
      className="card-elevated p-5 col-span-full lg:col-span-2 animate-fade-up opacity-0 cursor-pointer group"
      style={{ animationDelay: '200ms', animationFillMode: 'forwards' }}
      onClick={() => navigate('/noc')}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-accent-teal-dim border border-accent-teal-border">
            <Shield size={16} className="text-accent-teal" />
          </div>
          <div>
            <div className="text-sm font-semibold text-text-primary">NOC Autopilot</div>
            <div className="text-xs text-text-muted">SLA Guardian · Kimi K2.6</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md" style={{ background: `${statusColor}12`, border: `1px solid ${statusColor}25` }}>
            <StatusIcon size={12} style={{ color: statusColor }} />
            <span className="text-[11px] font-semibold" style={{ color: statusColor }}>{statusText}</span>
          </div>
          <ArrowUpRight size={14} className="text-text-faint group-hover:text-accent-teal transition-colors" />
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div>
          <div className="text-lg font-bold font-mono text-text-primary">{nocData.severity || 'OK'}</div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">Severity</div>
        </div>
        <div>
          <div className="text-lg font-bold font-mono text-text-primary">
            {nocData.breach_summary?.max_prob?.toFixed(3) || '0.000'}
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">Max Prob</div>
        </div>
        <div>
          <div className="text-lg font-bold font-mono text-text-primary">{nocData.iterations || 0}</div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">Iterations</div>
        </div>
        <div>
          <div className="text-lg font-bold font-mono text-text-primary">
            {nocData.phases?.length || 0}
          </div>
          <div className="text-[10px] text-text-muted uppercase tracking-wider mt-0.5">Phases</div>
        </div>
      </div>
    </div>
  )
}

/* ── Main Dashboard ───────────────────────────────────────────────── */
export default function Home() {
  const navigate = useNavigate()
  const { dataset } = useDataset()
  const [nocData, setNocData] = useState(null)
  const [nocHistory, setNocHistory] = useState([])

  useEffect(() => {
    nocApi.history(5)
      .then(data => {
        setNocHistory(Array.isArray(data) ? data : [])
        if (Array.isArray(data) && data.length > 0) setNocData(data[0])
      })
      .catch(() => {})
  }, [])

  return (
    <div className="space-y-6">
      {/* ── Hero Banner ────────────────────────────────────────────────── */}
      <div
        className="relative rounded-xl overflow-hidden p-8 lg:p-10 animate-fade-up opacity-0"
        style={{ animationFillMode: 'forwards' }}
      >
        {/* Gradient mesh background */}
        <div className="absolute inset-0 bg-gradient-to-br from-accent-teal/8 via-canvas to-accent-blue-dim" />
        <div className="absolute top-0 right-0 w-96 h-96 bg-accent-teal/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-accent-purple/5 rounded-full blur-[100px]" />

        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent-teal/10 border border-accent-teal/20">
              <Zap size={11} className="text-accent-teal" />
              <span className="text-[11px] font-semibold text-accent-teal">Esprit · PIDS · 4DS1 · 2026</span>
            </div>
          </div>

          <h1 className="text-3xl lg:text-4xl font-bold text-text-primary leading-tight mb-2">
            QoS<span className="text-gradient-teal">Buddy</span>
          </h1>
          <p className="text-text-secondary text-base max-w-xl leading-relaxed">
            Intelligent Network Assurance & Autonomous Optimization.
            Anomaly detection, root cause analysis, SLA monitoring, and AI-driven operations.
          </p>

          {/* Dataset CTA */}
          {!dataset && (
            <button
              onClick={() => navigate('/upload')}
              className="mt-5 inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent-teal/10 border border-accent-teal/25 text-accent-teal text-sm font-medium hover:bg-accent-teal/15 transition-all group"
            >
              <Upload size={15} />
              Upload dataset to get started
              <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
            </button>
          )}

          {dataset && (
            <div className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-green-dim border border-accent-green-border">
              <Database size={14} className="text-accent-green" />
              <span className="text-sm font-medium text-accent-green">{dataset.name}</span>
              <span className="text-xs text-text-muted ml-1">{dataset.rows?.toLocaleString()} rows · {dataset.columns?.length} cols</span>
            </div>
          )}
        </div>
      </div>

      {/* ── Stats Row ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Models" value="5" sub="ML & DL models" icon={BarChart3} accent="#60A5FA" delay={50} />
        <StatCard label="APIs" value="6" sub="Microservices" icon={Activity} accent="#A78BFA" delay={100} />
        <StatCard label="Features" value="55" sub="Engineered features" icon={Zap} accent="#00E8C6" delay={150} />
        <StatCard label="Cycle" value="10m" sub="NOC interval" icon={Clock} accent="#FB923C" delay={200} />
      </div>

      {/* ── NOC + History ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <NocWidget nocData={nocData} />

        {/* Recent Activity */}
        <div
          className="card-elevated p-5 animate-fade-up opacity-0"
          style={{ animationDelay: '250ms', animationFillMode: 'forwards' }}
        >
          <div className="text-sm font-semibold text-text-primary mb-3">Recent NOC Activity</div>
          <div className="space-y-2">
            {nocHistory.length === 0 ? (
              <div className="text-xs text-text-faint py-4 text-center">No cycles recorded yet</div>
            ) : (
              nocHistory.slice(0, 4).map((cycle, i) => {
                const color = cycle.breach_detected
                  ? (cycle.resolved ? '#FBBF24' : '#FF5A5A')
                  : '#34D399'
                return (
                  <div key={i} className="flex items-center gap-2.5 py-1.5 px-2 rounded-md hover:bg-surface-2 transition-colors">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                    <span className="text-xs text-text-secondary flex-1 truncate">
                      {cycle.severity || 'OK'} — {cycle.breach_detected ? `${cycle.breach_summary?.breach_count || 0} breaches` : 'nominal'}
                    </span>
                    <span className="text-[10px] text-text-faint font-mono shrink-0">
                      {cycle.ts_start ? new Date(cycle.ts_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
                    </span>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>

      {/* ── Feature Grid ───────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text-primary">Capabilities</h2>
          <span className="text-xs text-text-faint">{FEATURES.length} modules</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {FEATURES.map((f, i) => {
            const Icon = f.icon
            return (
              <button
                key={f.to}
                onClick={() => navigate(f.to)}
                className="card-elevated p-4 text-left group relative overflow-hidden animate-fade-up opacity-0"
                style={{ animationDelay: `${300 + i * 50}ms`, animationFillMode: 'forwards' }}
              >
                {/* Hover glow */}
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                  style={{ background: `radial-gradient(ellipse at 50% 0%, ${f.accent}08 0%, transparent 70%)` }}
                />

                <div className="relative">
                  <div className="flex items-center justify-between mb-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={{ background: `${f.accent}12`, border: `1px solid ${f.accent}20` }}
                    >
                      <Icon size={15} style={{ color: f.accent }} />
                    </div>
                    <span
                      className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md"
                      style={{ color: f.accent, background: `${f.accent}10` }}
                    >
                      {f.tag}
                    </span>
                  </div>

                  <div className="text-[13px] font-semibold text-text-primary group-hover:text-white transition-colors mb-1">
                    {f.label}
                  </div>
                  <p className="text-[11px] text-text-muted leading-relaxed">{f.desc}</p>
                </div>

                {/* Bottom accent */}
                <div
                  className="absolute bottom-0 left-0 h-[2px] w-0 group-hover:w-full transition-all duration-500"
                  style={{ background: `linear-gradient(to right, ${f.accent}, transparent)` }}
                />
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
