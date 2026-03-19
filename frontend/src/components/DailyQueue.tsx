import { useEffect, useState } from 'react'

interface ActionPlan {
  profile_url:    string
  post_url:       string | null
  post_likes:     number
  post_caption:   string
  comment:        string
  dm:             string
  matched_niches: string[]
}

interface QueueItem {
  queue_id:     number
  queue_status: 'pending' | 'done' | 'skipped'
  contacted_at: string | null
  creator: {
    id:              string
    username:        string
    full_name:       string | null
    biography:       string | null
    followers:       number
    engagement_rate: number
    score:           number
    niche_tags:      string | null
    website:         string | null
  }
  action: ActionPlan
}

interface QueueStats {
  total_contacted: number
  streak_days:     number
  today_done:      number
  today_total:     number
}

interface QueueResponse {
  date:  string
  items: QueueItem[]
  stats: QueueStats
}

function fmt(n: number) {
  if (n >= 1_000_000) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1_000)     return (n / 1e3).toFixed(1) + 'K'
  return String(n ?? 0)
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }
  return (
    <button className="copy-btn" onClick={copy}>
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

function QueueCard({ item, onDone, onSkip }: {
  item:   QueueItem
  onDone: (id: number) => void
  onSkip: (id: number) => void
}) {
  const { creator, action, queue_status, queue_id } = item
  const done    = queue_status === 'done'
  const skipped = queue_status === 'skipped'

  return (
    <div className={`queue-card ${done ? 'queue-card--done' : skipped ? 'queue-card--skipped' : ''}`}>
      {/* Header */}
      <div className="qc-header">
        <div className="qc-avatar">
          {creator.username.charAt(0).toUpperCase()}
        </div>
        <div className="qc-meta">
          <a
            href={action.profile_url}
            target="_blank"
            rel="noreferrer"
            className="qc-username"
          >
            @{creator.username}
          </a>
          {creator.full_name && (
            <span className="qc-fullname">{creator.full_name}</span>
          )}
          <div className="qc-stats">
            <span>{fmt(creator.followers)} followers</span>
            <span>·</span>
            <span>{(creator.engagement_rate ?? 0).toFixed(1)}% ER</span>
            <span>·</span>
            <span className="text-accent">score {(creator.score ?? 0).toFixed(0)}</span>
          </div>
        </div>
        {done && <span className="done-check">✓</span>}
      </div>

      {/* Bio */}
      {creator.biography && (
        <p className="qc-bio">{creator.biography}</p>
      )}

      {/* Niches */}
      <div className="qc-niches">
        {(creator.niche_tags ?? '').split(',').filter(Boolean).map(t => (
          <span key={t} className="niche-pill">#{t}</span>
        ))}
      </div>

      {/* Step 1 — Follow */}
      <div className="qc-step">
        <div className="step-label">
          <span className="step-num">1</span>
          Open profile &amp; follow
        </div>
        <a
          href={action.profile_url}
          target="_blank"
          rel="noreferrer"
          className="btn btn-ghost btn-sm"
        >
          Open Instagram ↗
        </a>
      </div>

      {/* Step 2 — Comment */}
      {action.post_url && (
        <div className="qc-step">
          <div className="step-label">
            <span className="step-num">2</span>
            Comment on their top post
            <span className="step-sub">({fmt(action.post_likes)} likes)</span>
          </div>
          {action.post_caption && (
            <p className="post-caption">"{action.post_caption}{action.post_caption.length >= 120 ? '…' : ''}"</p>
          )}
          <a
            href={action.post_url}
            target="_blank"
            rel="noreferrer"
            className="btn btn-ghost btn-sm"
            style={{ marginBottom: 8 }}
          >
            Open post ↗
          </a>
          <div className="suggestion-box">
            <p className="suggestion-text">{action.comment}</p>
            <CopyButton text={action.comment} />
          </div>
        </div>
      )}

      {/* Step 3 — DM */}
      <div className="qc-step">
        <div className="step-label">
          <span className="step-num">{action.post_url ? '3' : '2'}</span>
          Send a DM
        </div>
        <div className="suggestion-box">
          <p className="suggestion-text">{action.dm}</p>
          <CopyButton text={action.dm} />
        </div>
      </div>

      {/* Actions */}
      {!done && !skipped && (
        <div className="qc-actions">
          <button
            className="btn btn-primary"
            onClick={() => onDone(queue_id)}
          >
            ✓ Done — I contacted them
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => onSkip(queue_id)}
          >
            Skip
          </button>
        </div>
      )}

      {done && (
        <div className="qc-done-msg">Contacted ✓</div>
      )}
    </div>
  )
}

export default function DailyQueue() {
  const [data, setData]       = useState<QueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  const load = () => {
    setLoading(true)
    fetch('/api/queue/today')
      .then(r => r.json())
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleDone = (id: number) => {
    fetch(`/api/queue/${id}/done`, { method: 'POST' })
      .then(load)
      .catch(console.error)
  }

  const handleSkip = (id: number) => {
    fetch(`/api/queue/${id}/skip`, { method: 'POST' })
      .then(load)
      .catch(console.error)
  }

  if (loading && !data) return (
    <div>
      <div className="page-header"><h1 className="page-title">Daily Queue</h1></div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 180, borderRadius: 12 }} />
        ))}
      </div>
    </div>
  )

  if (error) return (
    <div>
      <div className="page-header"><h1 className="page-title">Daily Queue</h1></div>
      <p className="error-msg">{error}</p>
      <p className="text-muted" style={{ fontSize: 12, marginTop: 8 }}>
        Make sure you've run at least one discovery scan first.
      </p>
    </div>
  )

  if (!data) return null

  const { stats, items } = data
  const pending = items.filter(i => i.queue_status === 'pending')
  const done    = items.filter(i => i.queue_status === 'done')

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Daily Queue</h1>
          <p className="text-muted" style={{ fontSize: 13, marginTop: 4 }}>
            {data.date}
          </p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}>↺</button>
      </div>

      {/* Stats strip */}
      <div className="queue-stats-strip">
        <div className="qs-item">
          <span className="qs-value">{stats.today_done}/{stats.today_total}</span>
          <span className="qs-label">Today</span>
        </div>
        <div className="qs-item">
          <span className="qs-value">{stats.total_contacted}</span>
          <span className="qs-label">Total contacted</span>
        </div>
        <div className="qs-item">
          <span className="qs-value">{stats.streak_days}</span>
          <span className="qs-label">Days active</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="progress-bar-wrap">
        <div
          className="progress-bar-fill"
          style={{ width: `${stats.today_total > 0 ? (stats.today_done / stats.today_total) * 100 : 0}%` }}
        />
      </div>

      {/* Cards */}
      {items.length === 0 ? (
        <div className="empty-state">
          <p>No creators in queue yet.</p>
          <p className="text-muted" style={{ fontSize: 13, marginTop: 6 }}>
            Run a discovery scan first to populate your leads.
          </p>
        </div>
      ) : (
        <div className="queue-list">
          {pending.map(item => (
            <QueueCard key={item.queue_id} item={item} onDone={handleDone} onSkip={handleSkip} />
          ))}
          {done.length > 0 && (
            <>
              <div className="section-label" style={{ marginTop: 24 }}>Completed today</div>
              {done.map(item => (
                <QueueCard key={item.queue_id} item={item} onDone={handleDone} onSkip={handleSkip} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
