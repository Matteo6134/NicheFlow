import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { DiscoveryStatus, HashtagsResponse } from '../types'

export default function DiscoveryPanel() {
  const [hashtags, setHashtags]       = useState<HashtagsResponse | null>(null)
  const [selected, setSelected]       = useState<string[]>([])
  const [mode, setMode]               = useState('top')
  const [mediaLimit, setMediaLimit]   = useState(50)
  const [status, setStatus]           = useState<DiscoveryStatus | null>(null)
  const [logs, setLogs]               = useState<string[]>([])
  const [error, setError]             = useState('')
  const logRef = useRef<HTMLDivElement>(null)
  const esRef  = useRef<EventSource | null>(null)

  // Load hashtag list on mount
  useEffect(() => {
    api.getHashtags().then(h => {
      setHashtags(h)
      setSelected(h.configured)
    }).catch(() => {})

    // Poll for status every 3s (SSE fallback)
    const poll = setInterval(() => {
      api.getDiscoveryStatus().then(s => {
        setStatus(s)
        if (s.recent_logs.length > 0) setLogs(s.recent_logs)
      }).catch(() => {})
    }, 3000)

    return () => clearInterval(poll)
  }, [])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logs])

  const isRunning = status?.status === 'running'

  const startRun = async () => {
    setError('')
    setLogs([])

    try {
      await api.startDiscovery(selected, mode, mediaLimit)
      setStatus(prev => prev ? { ...prev, status: 'running' } : null)

      // Open SSE stream
      if (esRef.current) esRef.current.close()
      const es = new EventSource('/api/discovery/stream')
      esRef.current = es

      es.onmessage = e => {
        setLogs(prev => [...prev, e.data])
      }
      es.addEventListener('done', () => {
        es.close()
        api.getDiscoveryStatus().then(setStatus)
      })
      es.onerror = () => es.close()

    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    }
  }

  const toggleHashtag = (tag: string) => {
    setSelected(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    )
  }

  const syncedMap = Object.fromEntries(
    (hashtags?.synced ?? []).map(s => [s.name, s.last_synced])
  )

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Discovery</h1>
        {status && (
          <span className={`badge badge-${status.status === 'running' ? 'reviewed' : status.status === 'done' ? 'contacted' : 'new'}`}>
            {status.status}
          </span>
        )}
      </div>

      {/* Hashtag selector */}
      <div className="card mb-4">
        <div className="section-label">Target Hashtags</div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setSelected(hashtags?.configured ?? [])}>
            Select all
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => setSelected([])}>
            Clear
          </button>
          <span className="text-muted" style={{ fontSize: 12, marginLeft: 4, alignSelf: 'center' }}>
            {selected.length} / {hashtags?.configured.length ?? 0} selected
          </span>
        </div>
        <div className="hashtag-grid">
          {(hashtags?.configured ?? []).map(tag => (
            <button
              key={tag}
              className={`ht-chip ${selected.includes(tag) ? 'selected' : ''}`}
              onClick={() => toggleHashtag(tag)}
            >
              #{tag}
              {syncedMap[tag] && (
                <span style={{ fontSize: 10, opacity: 0.6 }}>
                  ✓
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Run options */}
      <div className="card mb-4">
        <div className="section-label">Options</div>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
            Mode
            <select value={mode} onChange={e => setMode(e.target.value)}>
              <option value="top">Top posts</option>
              <option value="recent">Recent posts</option>
              <option value="both">Both</option>
            </select>
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
            Posts per hashtag
            <input
              type="number"
              min={10}
              max={50}
              value={mediaLimit}
              onChange={e => setMediaLimit(Number(e.target.value))}
              style={{ width: 70 }}
            />
          </label>
        </div>
      </div>

      {/* Start button */}
      <div style={{ marginBottom: 20 }}>
        <button
          className="btn btn-primary"
          onClick={startRun}
          disabled={isRunning || selected.length === 0}
        >
          {isRunning ? (
            <><span className="spinner" /> Running…</>
          ) : (
            '▶ Start Discovery'
          )}
        </button>
        {error && <p className="error-msg" style={{ marginTop: 8 }}>{error}</p>}
      </div>

      {/* Live log */}
      <div className="section-label">Live Log</div>
      <div className="live-log" ref={logRef}>
        {logs.length === 0 ? (
          <span className="log-idle">No active run. Start a discovery scan to see output here.</span>
        ) : (
          logs.map((line, i) => (
            <div key={i} className="log-line">{line}</div>
          ))
        )}
      </div>

      {/* Results summary */}
      {status?.status === 'done' && (
        <div className="card mt-4" style={{ borderColor: 'rgba(68,204,136,0.3)' }}>
          <span className="text-accent" style={{ fontWeight: 700 }}>
            ✓ Scan complete
          </span>
          <span className="text-muted" style={{ marginLeft: 12, fontSize: 13 }}>
            {status.results_count} creators saved to Leads
          </span>
        </div>
      )}
    </div>
  )
}
