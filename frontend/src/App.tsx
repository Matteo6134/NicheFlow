import { useState, useEffect } from 'react'
import AccountStats from './components/AccountStats'
import LeadsView from './components/LeadsView'
import DiscoveryPanel from './components/DiscoveryPanel'
import DailyQueue from './components/DailyQueue'
import type { LeadFilters } from './types'
import './App.css'

type View = 'queue' | 'stats' | 'leads' | 'discovery'

const NAV: { id: View; label: string; icon: string }[] = [
  { id: 'queue',     label: 'Queue',     icon: '✦' },
  { id: 'leads',     label: 'Leads',     icon: '⊞' },
  { id: 'discovery', label: 'Scan',      icon: '⊕' },
  { id: 'stats',     label: 'Account',   icon: '◎' },
]

export default function App() {
  const [view, setView] = useState<View>('queue')
  const [connected, setConnected] = useState<boolean | null>(null)
  const [filters, setFilters] = useState<LeadFilters>({
    status: '', niche: '', sort_by: 'score', order: 'desc',
  })

  useEffect(() => {
    fetch('/api/account/stats')
      .then(r => setConnected(r.ok))
      .catch(() => setConnected(false))
  }, [])

  return (
    <div className="app">
      {/* Desktop sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-dot" data-connected={String(connected)} />
          Discovery
        </div>
        <nav className="sidebar-nav">
          {NAV.map(n => (
            <button
              key={n.id}
              className={`nav-item ${view === n.id ? 'active' : ''}`}
              onClick={() => setView(n.id)}
            >
              <span className="nav-icon">{n.icon}</span>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className={`conn-dot ${connected === true ? 'conn-dot--on' : connected === false ? 'conn-dot--off' : ''}`} />
          <span className="conn-label">
            {connected === null ? 'Connecting…' : connected ? 'API connected' : 'No API key'}
          </span>
        </div>
      </aside>

      {/* Main content */}
      <main className="content">
        <div className="content-inner">
          {view === 'queue'     && <DailyQueue />}
          {view === 'stats'     && <AccountStats />}
          {view === 'leads'     && <LeadsView filters={filters} onFiltersChange={setFilters} />}
          {view === 'discovery' && <DiscoveryPanel />}
        </div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="bottom-nav">
        {NAV.map(n => (
          <button
            key={n.id}
            className={`bottom-nav-item ${view === n.id ? 'active' : ''}`}
            onClick={() => setView(n.id)}
          >
            <span className="bottom-nav-icon">{n.icon}</span>
            <span className="bottom-nav-label">{n.label}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}
