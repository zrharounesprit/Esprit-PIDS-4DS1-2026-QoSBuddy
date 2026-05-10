import { Routes, Route } from 'react-router-dom'
import { DatasetProvider } from './context/DatasetContext'
import { ToastProvider } from './hooks/useToast'
import Layout from './components/Layout'

import Home                     from './pages/Home'
import Upload                   from './pages/Upload'
import AnomalyDetection         from './pages/AnomalyDetection'
import RootCauseAnalysis        from './pages/RootCauseAnalysis'
import SLADetection             from './pages/SLADetection'
import PersonaClassification    from './pages/PersonaClassification'
import Forecasting              from './pages/Forecasting'
import Simulation               from './pages/Simulation'
import MCPDemo                  from './pages/MCPDemo'
import AutoPilot                from './pages/AutoPilot'
import SLAGuardian              from './pages/SLAGuardian'

export default function App() {
  return (
    <DatasetProvider>
      <ToastProvider>
        <Layout>
          <Routes>
            <Route path="/"             element={<Home />} />
            <Route path="/upload"       element={<Upload />} />
            <Route path="/anomaly"      element={<AnomalyDetection />} />
            <Route path="/rca"          element={<RootCauseAnalysis />} />
            <Route path="/sla"          element={<SLADetection />} />
            <Route path="/persona"      element={<PersonaClassification />} />
            <Route path="/forecast"     element={<Forecasting />} />
            <Route path="/simulation"   element={<Simulation />} />
            <Route path="/mcp"          element={<MCPDemo />} />
            <Route path="/auto-pilot"   element={<AutoPilot />} />
            <Route path="/noc"          element={<SLAGuardian />} />
            <Route path="*"             element={<div className="text-text-muted p-8">404 — Page not found</div>} />
          </Routes>
        </Layout>
      </ToastProvider>
    </DatasetProvider>
  )
}
