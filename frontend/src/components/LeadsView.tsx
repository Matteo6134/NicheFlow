import { useEffect, useState, useCallback } from 'react'
import { api } from '../api'
import type { Creator, LeadFilters } from '../types'

interface Props {
  filters: LeadFilters
  onFiltersChange: (f: LeadFilters) => void
}

const PAGE_SIZE = 100

function StatusBadge({ status }: { status: Creator['status'] }) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

function InlineStatusEditor({
  creator,
  onUpdated,
}: {
  creator: Creator
  onUpdated: () => void
}) {
  const [open, setOpen]   = useState(false)
  const [sel, setSel]     = useState(creator.status)
  const [notes, setNotes] = useState(creator.notes ?? '')
  const [saving, setSaving] = useState(false)

  const save = () => {
    setSaving(true)
    api.updateLeadStatus(creator.id, sel as Creator['status'], notes)
      .then(() => { onUpdated(); setOpen(false) })
      .catch(console.error)
      .finally(() => setSaving(false))
  }

  if (!open) return (
    <span onClick={() => setOpen(true)} title="Click to change status">
      <StatusBadge status={creator.status} />
    </span>
  )

  return (
    <div className="status-editor">
      <select value={sel} onChange={e => setSel(e.target.value)}>
        <option value="new">new</option>
        <option value="reviewed">reviewed</option>
        <option value="contacted">contacted</option>
        <option value="skip">skip</option>
      </select>
      <textarea
        placeholder="Notes (optional)"
        value={notes}
        onChange={e => setNotes(e.target.value)}
      />
      <div className="status-editor-actions">
        <button className="btn btn-primary btn-sm" onClick={save} disabled={saving}>
          {saving ? <span className="spinner" /> : 'Save'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </div>
  )
}

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K'
  return String(n ?? 0)
}

export default function LeadsView({ filters, onFiltersChange }: Props) {
  const [creators, setCreators] = useState<Creator[]>([])
  const [total, setTotal]       = useState(0)
  const [page, setPage]         = useState(0)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const load = useCallback(() => {
    setLoading(true)
    api.getLeads(filters, PAGE_SIZE, page * PAGE_SIZE)
      .then(r => { setCreators(r.items); setTotal(r.total) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [filters, page])

  useEffect(() => { load() }, [load])

  const setFilter = (key: keyof LeadFilters, val: string) => {
    onFiltersChange({ ...filters, [key]: val })
    setPage(0)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Leads</h1>
          <p className="text-muted" style={{ fontSize: 13, marginTop: 4 }}>
            {total.toLocaleString()} creators found
          </p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={api.exportLeads}>
          ↓ Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <select value={filters.status} onChange={e => setFilter('status', e.target.value)}>
          <option value="">All statuses</option>
          <option value="new">new</option>
          <option value="reviewed">reviewed</option>
          <option value="contacted">contacted</option>
          <option value="skip">skip</option>
        </select>

        <input
          placeholder="Filter by niche…"
          value={filters.niche}
          onChange={e => setFilter('niche', e.target.value)}
          style={{ width: 180 }}
        />

        <select value={filters.sort_by} onChange={e => setFilter('sort_by', e.target.value)}>
          <option value="score">Score</option>
          <option value="followers">Followers</option>
          <option value="engagement_rate">Engagement rate</option>
          <option value="discovered_at">Discovered</option>
        </select>

        <select value={filters.order} onChange={e => setFilter('order', e.target.value)}>
          <option value="desc">↓ Desc</option>
          <option value="asc">↑ Asc</option>
        </select>

        <button className="btn btn-ghost btn-sm" onClick={load}>
          {loading ? <span className="spinner" /> : '↺'}
        </button>
      </div>

      {error && <p className="error-msg">{error}</p>}

      <div className="table-wrap card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Username</th>
              <th className="num">Followers</th>
              <th className="num">ER%</th>
              <th className="num">Score</th>
              <th>Niches</th>
              <th>Status</th>
              <th>Notes</th>
              <th>Website</th>
            </tr>
          </thead>
          <tbody>
            {creators.length === 0 && !loading && (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: 32, color: 'var(--muted)' }}>
                  No creators yet — run a discovery scan first.
                </td>
              </tr>
            )}
            {creators.map((c, i) => (
              <tr key={c.id}>
                <td className="text-muted">{page * PAGE_SIZE + i + 1}</td>
                <td>
                  <a
                    href={`https://instagram.com/${c.username}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontWeight: 600 }}
                  >
                    @{c.username}
                  </a>
                  {c.full_name && (
                    <div className="text-muted" style={{ fontSize: 11 }}>{c.full_name}</div>
                  )}
                </td>
                <td className="num">{fmt(c.followers)}</td>
                <td className="num">{(c.engagement_rate ?? 0).toFixed(2)}%</td>
                <td className="num text-accent" style={{ fontWeight: 700 }}>
                  {(c.score ?? 0).toFixed(1)}
                </td>
                <td style={{ maxWidth: 200 }}>
                  <span className="text-muted" style={{ fontSize: 11 }}>
                    {(c.niche_tags ?? '').split(',').map(t => `#${t}`).join(' ')}
                  </span>
                </td>
                <td>
                  <InlineStatusEditor creator={c} onUpdated={load} />
                </td>
                <td style={{ maxWidth: 160, fontSize: 12, color: 'var(--muted)' }}>
                  {c.notes ?? '—'}
                </td>
                <td>
                  {c.website
                    ? <a href={c.website} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>link</a>
                    : <span className="text-muted">—</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setPage(p => Math.max(p - 1, 0))}
            disabled={page === 0}
          >← Prev</button>
          <span>Page {page + 1} of {totalPages}</span>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setPage(p => Math.min(p + 1, totalPages - 1))}
            disabled={page >= totalPages - 1}
          >Next →</button>
        </div>
      )}
    </div>
  )
}
