import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AccountStats as IAccountStats } from '../types'

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

export default function AccountStats() {
  const [stats, setStats] = useState<IAccountStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    api.getAccountStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [])

  if (loading && !stats) return (
    <div>
      <div className="page-header"><h1 className="page-title">Account</h1></div>
      <div className="stat-grid">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="stat-card">
            <div className="skeleton" style={{ height: 12, width: '60%', marginBottom: 10 }} />
            <div className="skeleton" style={{ height: 28, width: '80%' }} />
          </div>
        ))}
      </div>
    </div>
  )

  if (error) return (
    <div>
      <div className="page-header"><h1 className="page-title">Account</h1></div>
      <p className="error-msg">Could not load account stats: {error}</p>
      <p className="text-muted" style={{ marginTop: 8, fontSize: 12 }}>
        Make sure ACCESS_TOKEN and IG_USER_ID are set in config.py and the backend is running.
      </p>
    </div>
  )

  if (!stats) return null

  const cards = [
    { label: 'Followers',      value: fmt(stats.followers_count), sub: 'total' },
    { label: 'Following',      value: fmt(stats.follows_count),   sub: 'accounts' },
    { label: 'Posts',          value: fmt(stats.media_count),     sub: 'published' },
    { label: 'API Calls Used', value: String(stats.calls_this_hour), sub: 'this hour' },
    { label: 'API Remaining',  value: String(stats.calls_remaining), sub: 'of 150 limit' },
  ]

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">@{stats.username}</h1>
          <p className="text-muted" style={{ fontSize: 13, marginTop: 4 }}>{stats.biography}</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}>Refresh</button>
      </div>

      <div className="stat-grid">
        {cards.map(c => (
          <div key={c.label} className="stat-card">
            <div className="stat-label">{c.label}</div>
            <div className="stat-value">{c.value}</div>
            <div className="stat-sub">{c.sub}</div>
          </div>
        ))}
      </div>

      {stats.website && (
        <div className="card" style={{ display: 'inline-block', marginTop: 4 }}>
          <span className="section-label">Website</span>
          <a href={stats.website} target="_blank" rel="noreferrer">{stats.website}</a>
        </div>
      )}
    </div>
  )
}
