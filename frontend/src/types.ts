export interface Creator {
  id: string
  username: string
  full_name: string | null
  biography: string | null
  followers: number
  following: number
  post_count: number
  avg_likes: number
  avg_comments: number
  engagement_rate: number
  account_type: string | null
  website: string | null
  niche_tags: string | null
  score: number
  status: 'new' | 'reviewed' | 'contacted' | 'skip'
  notes: string | null
  discovered_at: string
  updated_at: string | null
}

export interface AccountStats {
  id: string
  username: string
  name: string
  biography: string
  followers_count: number
  follows_count: number
  media_count: number
  website: string
  calls_this_hour: number
  calls_remaining: number
}

export interface LeadsResponse {
  total: number
  items: Creator[]
}

export interface HashtagsResponse {
  configured: string[]
  synced: { id: string; name: string; last_synced: string | null }[]
}

export interface DiscoveryStatus {
  status: 'idle' | 'running' | 'done' | 'error'
  run_id: string | null
  started_at: string | null
  finished_at: string | null
  results_count: number
  recent_logs: string[]
}

export interface LeadFilters {
  status: string
  niche: string
  sort_by: string
  order: string
}
