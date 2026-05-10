import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function Layout({ children }) {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <div className="flex h-screen overflow-hidden bg-canvas relative">
      {/* ── Video background ── */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="fixed inset-0 w-full h-full object-cover z-0 pointer-events-none"
        style={{ opacity: 0.15 }}
      >
        <source src="/bg-video.mp4" type="video/mp4" />
      </video>

      {/* Dark overlay on top of video for readability */}
      <div className="fixed inset-0 z-0 pointer-events-none bg-canvas/70" />

      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />

      <div className="flex-1 flex flex-col overflow-hidden min-w-0 relative z-10">
        <TopBar collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />

        <main className="flex-1 overflow-y-auto">
          <div className="p-6 lg:p-8 max-w-[1600px] mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
