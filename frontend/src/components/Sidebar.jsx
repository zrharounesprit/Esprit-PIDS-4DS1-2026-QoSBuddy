import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Upload, AlertTriangle, GitBranch,
  ShieldAlert, Users, TrendingUp, Network, Radio,
  Shield, Leaf, ChevronRight, Zap,
  ChevronsLeft, ChevronsRight
} from 'lucide-react'

const NAV = [
  { to: '/',           label: 'Dashboard',            icon: LayoutDashboard, accent: '#00E8C6' },
  { to: '/upload',     label: 'Upload Dataset',       icon: Upload,          accent: '#34D399' },
  { divider: true, label: 'Analysis' },
  { to: '/anomaly',    label: 'Anomaly Detection',    icon: AlertTriangle,   accent: '#FF5A5A' },
  { to: '/rca',        label: 'Root Cause Analysis',  icon: GitBranch,       accent: '#A78BFA' },
  { to: '/sla',        label: 'SLA Detection',        icon: ShieldAlert,     accent: '#38BDF8' },
  { to: '/persona',    label: 'User Persona',         icon: Users,           accent: '#E879F9' },
  { to: '/forecast',   label: 'Traffic Forecasting',  icon: TrendingUp,      accent: '#60A5FA' },
  { divider: true, label: 'Simulation' },
  { to: '/simulation', label: 'Network Simulation',   icon: Network,         accent: '#00E8C6' },
  { to: '/auto-pilot', label: 'Green Auto-Pilot',     icon: Leaf,            accent: '#34D399' },
  { to: '/mcp',        label: 'MCP Demo',             icon: Radio,           accent: '#38BDF8' },
  { divider: true, label: 'AI Ops' },
  { to: '/noc',        label: 'NOC Autopilot',        icon: Shield,          accent: '#00E8C6' },
]

export default function Sidebar({ collapsed, onToggle }) {
  return (
    <aside
      className={`${collapsed ? 'w-[68px]' : 'w-[240px]'} shrink-0 h-screen sticky top-0 flex flex-col bg-surface/80 backdrop-blur-xl border-r border-border overflow-hidden transition-all duration-300 ease-in-out z-30`}
    >
      {/* Brand */}
      <div className={`px-4 pt-5 pb-4 border-b border-border ${collapsed ? 'flex justify-center' : ''}`}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-gradient-to-br from-accent-teal/20 to-accent-teal/5 border border-accent-teal/30 shrink-0">
            <Zap size={15} className="text-accent-teal" />
          </div>
          {!collapsed && (
            <div className="animate-fade-in">
              <div className="text-sm font-bold text-text-primary tracking-tight leading-none">QoSBuddy</div>
              <div className="text-[10px] text-text-muted mt-0.5">Network Assurance</div>
            </div>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto overflow-x-hidden">
        {NAV.map((item, idx) => {
          if (item.divider) {
            if (collapsed) return <div key={idx} className="my-2 mx-3 border-t border-border-subtle" />
            return (
              <div key={idx} className="px-3 pt-5 pb-1.5">
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
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                `group relative flex items-center gap-2.5 rounded-md transition-all duration-200 mb-0.5
                 ${collapsed ? 'justify-center px-0 py-2.5 mx-1' : 'px-3 py-2'}
                 ${isActive
                    ? 'bg-surface-3 text-text-primary font-medium'
                    : 'text-text-muted hover:text-text-primary hover:bg-surface-2'
                 }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* Active accent bar */}
                  {isActive && (
                    <span
                      className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full transition-all"
                      style={{ background: item.accent }}
                    />
                  )}
                  <Icon
                    size={collapsed ? 18 : 16}
                    style={{ color: isActive ? item.accent : undefined }}
                    className={`shrink-0 transition-colors ${isActive ? '' : 'group-hover:text-text-secondary'}`}
                  />
                  {!collapsed && (
                    <>
                      <span className="flex-1 text-[13px] truncate">{item.label}</span>
                      {isActive && (
                        <ChevronRight size={12} style={{ color: item.accent }} className="opacity-50" />
                      )}
                    </>
                  )}
                </>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="px-4 py-3 border-t border-border animate-fade-in">
          <div className="text-[10px] text-text-faint leading-relaxed">
            <div className="font-semibold text-text-muted mb-0.5">Team VizBiz</div>
            Esprit · 4DS1 · 2026
          </div>
        </div>
      )}
    </aside>
  )
}
