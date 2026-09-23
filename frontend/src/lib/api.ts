const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1';

export interface Death {
  id: number;
  file_id: number;
  filename: string;
  original_path: string;
  extension: string;
  size_bytes: number;
  born_at: string;
  last_modified_at: string | null;
  deleted_at: string;
  lifespan_seconds: number;
  lifespan_label: string;
  cause: string;
  cause_label: string;
  epitaph: string | null;
  cemetery_x: number;
  cemetery_y: number;
  created_at: string;
}

export interface DeathListResponse {
  items: Death[];
  total: number;
  limit: number;
  offset: number;
}

export interface StatisticsResponse {
  total_deaths: number;
  total_lifespan_seconds: number;
  average_lifespan_seconds: number;
  by_cause: Record<string, number>;
  by_extension: Record<string, number>;
  oldest_death: string | null;
  newest_death: string | null;
}

export interface TimelineEvent {
  id: number;
  file_id: number;
  filename: string;
  extension: string;
  deleted_at: string;
  cause: string;
  cause_label: string;
  lifespan_label: string;
  cemetery_x: number;
  cemetery_y: number;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface SearchResult {
  id: number;
  file_id: number;
  filename: string;
  original_path: string;
  extension: string;
  deleted_at: string;
  cause: string;
  cause_label: string;
  lifespan_label: string;
  cemetery_x: number;
  cemetery_y: number;
}

export interface SearchResponse {
  items: SearchResult[];
  total: number;
  limit: number;
  offset: number;
  query: string;
}

export interface WatcherStatusResponse {
  running: boolean;
  watched_directories: string[];
}

export interface SettingsResponse {
  watched_directories: string[];
  ignored_directories: string[];
  ai_epitaphs_enabled: boolean;
}

export interface SettingsUpdate {
  watched_directories?: string[];
  ignored_directories?: string[];
  ai_epitaphs_enabled?: boolean;
}

class ApiError extends Error {
  constructor(public status: number, public body: any) {
    super(body?.message || `API error: ${status}`);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

export const api = {
  deaths: {
    list: (params?: { limit?: number; offset?: number; cause?: string; extension?: string; q?: string }) => {
      const searchParams = new URLSearchParams();
      if (params) {
        if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
        if (params.offset !== undefined) searchParams.set('offset', String(params.offset));
        if (params.cause) searchParams.set('cause', params.cause);
        if (params.extension) searchParams.set('extension', params.extension);
        if (params.q) searchParams.set('q', params.q);
      }
      const qs = searchParams.toString();
      return request<DeathListResponse>(`/deaths${qs ? `?${qs}` : ''}`, {
        method: 'GET',
      });
    },

    get: (id: number) => request<Death>(`/deaths/${id}`),
  },

  statistics: {
    get: () => request<StatisticsResponse>('/statistics'),
  },

  timeline: {
    get: (params?: { limit?: number; offset?: number; from?: string; to?: string }) =>
      request<TimelineResponse>('/timeline', {
        method: 'GET',
      }),
  },

  search: {
    get: (q: string, params?: { limit?: number; offset?: number }) =>
      request<SearchResponse>(`/search?q=${encodeURIComponent(q)}`, {
        method: 'GET',
      }),
  },

  watcher: {
    status: () => request<WatcherStatusResponse>('/watcher/status'),
  },

  settings: {
    get: () => request<SettingsResponse>('/settings'),
    update: (data: SettingsUpdate) =>
      request<SettingsResponse>('/settings', {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
  },
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}