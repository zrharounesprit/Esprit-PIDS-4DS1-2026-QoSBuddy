import PageHeader from '../components/PageHeader'
import { Map } from 'lucide-react'

export default function NetworkCoverageSimulator() {
  return (
    <div>
      <PageHeader
        icon={Map}
        title="Network Coverage Simulator"
        accent="#22C55E"
        subtitle="Simulate and visualize network coverage across regions"
      />
      <div className="card p-8 text-center text-text-muted">
        <Map size={48} className="mx-auto mb-4 opacity-30" />
        <p className="text-sm">Coverage simulator coming soon.</p>
      </div>
    </div>
  )
}
