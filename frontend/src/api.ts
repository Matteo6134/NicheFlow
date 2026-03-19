import type {
  AccountStats,
  Creator,
  LeadsResponse,
  HashtagsResponse,
  DiscoveryStatus,
  LeadFilters,
} from './types'

const BASE = import.meta.env.VITE_API_URL || '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export const api = {
  // Account
  getAccountStats: () =>
    request<AccountStats>('/account/stats'),

  // Leads
  getLeads: (filters: LeadFilters, limit = 100, offset = 0) => {
    const p = new URLSearchParams({
      status:  filters.status,
      niche:   filters.niche,
      sort_by: filters.sort_by,
      order:   filters.order,
      limit:   String(limit),
      offset:  String(offset),
    })
    return request<LeadsResponse>(`/leads?${p}`)
  },

  updateLeadStatus: (id: string, status: Creator['status'], notes: string) =>
    request<{ ok: boolean }>(`/leads/${id}/status`, {
      method: 'PATCH',
      body:   JSON.stringify({ status, notes }),
    }),

  exportLeads: () => {
    window.location.href = `${BASE}/leads/export`
  },

  // Hashtags
  getHashtags: () =>
    request<HashtagsResponse>('/hashtags'),

  // Discovery
  startDiscovery: (hashtags: string[], mode: string, media_limit: number) =>
    request<{ run_id: string; status: string }>('/discovery/run', {
      method: 'POST',
      body:   JSON.stringify({ hashtags, mode, media_limit }),
    }),

  getDiscoveryStatus: () =>
    request<DiscoveryStatus>('/discovery/status'),
}
