export interface Agent {
  id: string;
  name: string;
  preset: string;
  title: string;
  desk: string;
  color: string;
  llm_provider: string;
  llm_model: string;
  system_prompt: string;
  temperature: number;
}

export interface ProviderInfo {
  key: string;
  default_model: string;
  models: string[];
  error: string | null;
}

export interface Preset {
  key: string;
  name: string;
  title: string;
  desk: string;
  color: string;
}

export interface SystemSnapshot {
  cpu_percent: number;
  cpu_per_core: number[];
  ram_percent: number;
  ram_used_mb: number;
  ram_total_mb: number;
  disk_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
  net_sent_mb: number;
  net_recv_mb: number;
  uptime_s: number;
  ts: number;
}

export interface ProcessRow {
  pid: number;
  ppid: number;
  name: string;
  user: string;
  status: string;
  cpu: number;
  rss_mb: number;
  threads: number;
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  health: () => j<{ status: string }>('/api/health'),

  // system
  snapshot: () => j<SystemSnapshot>('/api/system/snapshot'),
  processes: (sort = 'cpu', limit = 100) =>
    j<ProcessRow[]>(`/api/system/processes?sort_by=${sort}&limit=${limit}`),
  killProcess: (pid: number, force = false) =>
    j<{ ok: boolean }>(`/api/system/processes/${pid}/kill?force=${force}`, { method: 'POST' }),

  // agents
  listAgents: () => j<Agent[]>('/api/agents'),
  createAgent: (data: Partial<Agent>) =>
    j<Agent>('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  updateAgent: (id: string, patch: Partial<Agent>) =>
    j<Agent>(`/api/agents/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  deleteAgent: (id: string) =>
    j<{ ok: boolean }>(`/api/agents/${id}`, { method: 'DELETE' }),
  presets: () => j<Preset[]>('/api/agents/presets'),
  providers: () => j<ProviderInfo[]>('/api/agents/providers'),
  messages: (id: string) =>
    j<{ role: string; content: string; ts: number }[]>(`/api/agents/${id}/messages`),

  // vk
  vkMe: () => j<any>('/api/vk/me'),
  vkFriends: () => j<any>('/api/vk/friends/online'),
  vkFeed: (n = 25) => j<any>(`/api/vk/newsfeed?count=${n}`),
};

export function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}`;
}
