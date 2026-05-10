import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Upload, AlertTriangle, GitBranch,
  ShieldAlert, Users, TrendingUp, Network, Radio,
  Bot, Shield, Map, Leaf, ChevronRight
} from 'lucide-react'

const NAV = [
  { to: '/',           label: 'Dashboard',           icon: LayoutDashboard, accent: '#00FFD5' },
  { to: '/upload',     label: 'Upload Dataset',       icon: Upload,          accent: '#22C55E' },
  { divider: true, label: 'Analysis' },
  { to: '/anomaly',    label: 'Anomaly Detection',    icon: AlertTriangle,   accent: '#F04444' },
  { to: '/rca',        label: 'Root Cause Analysis',  icon: GitBranch,       accent: '#8B7CF8' },
  { to: '/sla',        label: 'SLA Detection',        icon: ShieldAlert,     accent: '#22D3EE' },
  { to: '/persona',    label: 'User Persona',         icon: Users,           accent: '#E040FB' },
  { to: '/forecast',   label: 'Traffic Forecasting',  icon: TrendingUp,      accent: '#3B82F6' },
  { divider: true, label: 'Simulation' },
  { to: '/simulation', label: 'Network Simulation',   icon: Network,         accent: '#00FFD5' },
  { to: '/coverage',   label: 'Coverage Simulator',   icon: Map,             accent: '#22C55E' },
  { to: '/auto-pilot', label: 'Green Auto-Pilot',     icon: Leaf,            accent: '#22C55E' },
  { to: '/mcp',        label: 'MCP Demo',             icon: Radio,           accent: '#0097a7' },
  { divider: true, label: 'AI Intelligence' },
  { to: '/autopilot',  label: 'Autopilot',            icon: Bot,             accent: '#F59E0B' },
  { to: '/noc',        label: 'NOC Autopilot',        icon: Shield,          accent: '#00FFD5' },
]

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 flex flex-col bg-surface border-r border-border overflow-y-auto">
      {/* Brand */}
      <div className="px-5 pt-6 pb-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-sm flex items-center justify-center bg-accent-teal-dim border border-accent-teal-border">
            <span className="text-accent-teal text-xs font-bold font-mono">QB</span>
          </div>
          <div>
            <div className="text-sm font-bold text-text-primary tracking-tight">QoSBuddy</div>
            <div className="text-[10px] text-text-faint uppercase tracking-widest">Network Assurance</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3">
        {NAV.map((item, idx) => {
          if (item.divider) {
            return (
              <div key={idx} className="px-3 pt-4 pb-1">
                <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-text-faint">
                  {item.label}
                </span>
              </div>
            )
          }
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `group flex items-center gap-2.5 px-3 py-2 text-sm rounded-sm transition-all duration-150 mb-0.5 ${
                  isActive
                    ? 'bg-surface-2 text-text-primary font-medium'
                    : 'text-text-muted hover:text-text-primary hover:bg-surface-2'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* Active accent bar */}
                  <span
                    className="absolute left-0 w-0.5 h-5 rounded-r transition-all"
                    style={{ background: isActive ? item.accent : 'transparent' }}
                  />
                  <Icon
                    size={15}
                    style={{ color: isActive ? item.accent : undefined }}
                    className={isActive ? '' : 'group-hover:text-text-primary'}
                  />
                  <span className="flex-1">{item.label}</span>
                  {isActive && (
                    <ChevronRight size={12} style={{ color: item.accent }} className="opacity-60" />
                  )}
                </>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border">
        <div className="text-[10px] text-text-faint leading-relaxed">
          <div className="font-semibold text-text-muted mb-0.5">Team VizBiz</div>
          Esprit · 4DS1 · 2026
        </div>
      </div>
    </aside>
  )
}
