import Sidebar from './Sidebar'
import DatasetBanner from './DatasetBanner'

export default function Layout({ children }) {
  return (
    <div className="flex h-screen overflow-hidden bg-canvas">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-12 shrink-0 flex items-center justify-end gap-3 px-6 border-b border-border bg-surface">
          <DatasetBanner />
        </header>
        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-7">
          {children}
        </main>
      </div>
    </div>
  )
}
