/**
 * Models panel — live view of all local LLM providers and their models.
 *
 * Features:
 *  • Shows Ollama, Qwen-local, Qwen-cloud with online/offline status
 *  • Per-model: size (GB), family, quantization, parameters, context length
 *  • Green "▶ running" badge when the model is loaded in VRAM
 *  • Shows which agents use each model
 *  • Pull a new model from Ollama with live progress bar
 *  • Delete an Ollama model with confirm
 *  • Click any model row → open detail side-panel (modelfile, template, etc.)
 */
import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { wsUrl } from '../api';

// ── Types ────────────────────────────────────────────────────────────────────

interface ModelEntry {
  name: string;
  size_gb?: number | null;
  family?: string | null;
  parameters?: string | null;
  quantization?: string | null;
  format?: string | null;
  modified_at?: string | null;
  running?: boolean;
  used_by_agents?: Array<{ id: string; name: string; preset: string; llm_provider: string }>;
}

interface ProviderData {
  key: string;
  label: string;
  online: boolean;
  base_url: string;
  error?: string;
  models: ModelEntry[];
  running?: Array<{ name: string; size_gb?: number | null; vram_size_gb?: number | null; expires_at?: string }>;
}

interface PullItem {
  name: string;
  status: string;
  completed: number;
  total: number;
  pct: number;
  error?: string;
}

interface Snapshot {
  providers: ProviderData[];
  pull_queue: PullItem[];
  agents_by_model: Record<string, Array<{ id: string; name: string; preset: string }>>;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtGb(gb: number | null | undefined): string {
  if (gb == null) return '—';
  return `${gb.toFixed(1)} GB`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch {
    return '';
  }
}

const PRESET_COLORS: Record<string, string> = {
  boss: '#f5b301',
  sysadmin: '#4ade80',
  vk_watcher: '#60a5fa',
  terminal_helper: '#a78bfa',
  researcher: '#f472b6',
};

function AgentBadge({ agent }: { agent: { name: string; preset: string } }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium"
      style={{
        background: (PRESET_COLORS[agent.preset] ?? '#94a3b8') + '22',
        color: PRESET_COLORS[agent.preset] ?? '#94a3b8',
        border: `1px solid ${(PRESET_COLORS[agent.preset] ?? '#94a3b8')}44`,
      }}
    >
      {agent.name}
    </span>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ProviderStatus({ online, label }: { online: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ background: online ? '#4ade80' : '#ef4444' }}
      />
      <span className="font-semibold text-sm">{label}</span>
      <span className="text-xs text-gray-500">{online ? 'онлайн' : 'недоступен'}</span>
    </div>
  );
}

function PullProgress({ item }: { item: PullItem }) {
  const isErr = item.status === 'error';
  const isDone = item.status === 'success';
  return (
    <div className="bg-[#0f1420] rounded p-2 text-xs">
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-gray-300">{item.name}</span>
        <span className={isErr ? 'text-red-400' : isDone ? 'text-green-400' : 'text-[#60a5fa]'}>
          {isDone ? '✓ готово' : isErr ? '✗ ошибка' : `${item.pct}%`}
        </span>
      </div>
      {!isDone && !isErr && (
        <div className="w-full h-1 bg-[#1f2637] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${item.pct}%`, background: '#60a5fa' }}
          />
        </div>
      )}
      <div className="text-gray-500 mt-0.5">
        {isErr ? item.error : `${item.status}`}
      </div>
    </div>
  );
}

function ModelDetail({ model, providerKey, onClose, onDelete }: {
  model: ModelEntry;
  providerKey: string;
  onClose: () => void;
  onDelete: (name: string) => void;
}) {
  const [info, setInfo] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (providerKey !== 'ollama') return;
    setLoading(true);
    api.ollamaModelInfo(model.name)
      .then(setInfo)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [model.name, providerKey]);

  return (
    <div
      className="absolute inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="panel w-[520px] max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-header">
          <span className="font-mono text-sm">{model.name}</span>
          <button className="btn" style={{ padding: '2px 8px' }} onClick={onClose}>×</button>
        </div>
        <div className="panel-body overflow-auto space-y-3 text-xs">
          {/* Basic facts */}
          <div className="grid grid-cols-2 gap-2">
            {[
              ['Размер', fmtGb(model.size_gb)],
              ['Семейство', model.family ?? '—'],
              ['Параметры', model.parameters ?? '—'],
              ['Квантизация', model.quantization ?? '—'],
              ['Формат', model.format ?? '—'],
              ['Обновлено', fmtDate(model.modified_at)],
            ].map(([k, v]) => (
              <div key={k} className="bg-[#0f1420] rounded p-2">
                <div className="text-gray-500">{k}</div>
                <div className="font-mono text-gray-200">{v}</div>
              </div>
            ))}
          </div>

          {/* Agents using this model */}
          {(model.used_by_agents ?? []).length > 0 && (
            <div>
              <div className="text-gray-400 mb-1">Агенты на этой модели</div>
              <div className="flex flex-wrap gap-1">
                {(model.used_by_agents ?? []).map((a) => (
                  <AgentBadge key={a.id} agent={a} />
                ))}
              </div>
            </div>
          )}

          {/* Ollama-specific info */}
          {providerKey === 'ollama' && loading && (
            <div className="text-gray-500 text-center py-4">загрузка деталей…</div>
          )}

          {info && !loading && (
            <>
              {info.parameters && (
                <div>
                  <div className="text-gray-400 mb-1">Параметры модели</div>
                  <pre className="bg-[#0a0d14] rounded p-2 overflow-auto text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {info.parameters}
                  </pre>
                </div>
              )}
              {info.template && (
                <div>
                  <div className="text-gray-400 mb-1">Шаблон промпта</div>
                  <pre className="bg-[#0a0d14] rounded p-2 overflow-auto text-gray-300 text-[10px] whitespace-pre-wrap max-h-32">
                    {info.template}
                  </pre>
                </div>
              )}
              {info.system && (
                <div>
                  <div className="text-gray-400 mb-1">Системный промпт по умолчанию</div>
                  <div className="bg-[#0a0d14] rounded p-2 text-gray-300 whitespace-pre-wrap max-h-24 overflow-auto">
                    {info.system}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Actions */}
          {providerKey === 'ollama' && (
            <div className="flex gap-2 pt-1 border-t border-white/10">
              <button
                className="btn"
                style={{ color: '#ef4444' }}
                onClick={() => {
                  if (confirm(`Удалить модель «${model.name}»? Это освободит место на диске.`)) {
                    onDelete(model.name);
                    onClose();
                  }
                }}
              >
                🗑 удалить модель
              </button>
              <span className="text-gray-600 text-xs self-center ml-auto">
                {fmtGb(model.size_gb)} · ollama rm {model.name}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ModelsPanel() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [detail, setDetail] = useState<{ model: ModelEntry; providerKey: string } | null>(null);
  const [pullName, setPullName] = useState('');
  const [pulling, setPulling] = useState(false);
  const [pullErr, setPullErr] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Live WS
  useEffect(() => {
    let cancelled = false;
    let retry = 0;

    const connect = () => {
      const ws = new WebSocket(wsUrl('/ws/models'));
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'snapshot') {
            const { type: _t, ...rest } = msg;
            setSnap(rest as Snapshot);
          } else if (msg.type === 'pull_progress') {
            // Force refresh snapshot after pull completes
            if (msg.status === 'success' || msg.status === 'error') {
              api.modelsSnapshot().then((s) => setSnap(s as Snapshot)).catch(() => {});
            }
          }
        } catch { /* ignore */ }
      };
      ws.onclose = () => {
        if (cancelled) return;
        retry = Math.min(retry + 1, 6);
        setTimeout(connect, 600 * retry);
      };
      ws.onerror = () => ws.close();
    };
    connect();

    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  const handleDelete = async (name: string) => {
    try {
      await api.ollamaDelete(name);
      const s = await api.modelsSnapshot();
      setSnap(s as Snapshot);
    } catch (e: any) {
      alert(`Не удалось удалить: ${e.message ?? e}`);
    }
  };

  const handlePull = async () => {
    const name = pullName.trim();
    if (!name) return;
    setPulling(true);
    setPullErr(null);
    try {
      await api.ollamaPull(name);
      setPullName('');
    } catch (e: any) {
      setPullErr(String(e.message ?? e));
    } finally {
      setPulling(false);
    }
  };

  if (!snap) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        подключение к /ws/models…
      </div>
    );
  }

  const totalModels = snap.providers.reduce((n, p) => n + p.models.length, 0);
  const totalRunning = snap.providers
    .filter((p) => p.key === 'ollama')
    .reduce((n, p) => n + (p.running?.length ?? 0), 0);
  const totalSizeGb = snap.providers
    .filter((p) => p.key === 'ollama')
    .flatMap((p) => p.models)
    .reduce((sum, m) => sum + (m.size_gb ?? 0), 0);

  return (
    <div className="flex flex-col gap-3 h-full overflow-auto text-sm">
      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-2 flex-shrink-0">
        {[
          ['Всего моделей', totalModels],
          ['В VRAM сейчас', totalRunning],
          ['Размер на диске', `${totalSizeGb.toFixed(1)} GB`],
        ].map(([label, val]) => (
          <div key={label as string} className="bg-[#0f1420] rounded p-2 text-center">
            <div className="text-xl font-bold text-[#f5b301]">{val}</div>
            <div className="text-xs text-gray-400">{label}</div>
          </div>
        ))}
      </div>

      {/* Pull new model */}
      <div className="flex-shrink-0">
        <div className="text-xs text-gray-400 mb-1">Загрузить новую модель (Ollama)</div>
        <div className="flex gap-2">
          <input
            value={pullName}
            onChange={(e) => setPullName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handlePull()}
            placeholder="qwen2.5:7b, llama3.1:8b, mistral…"
            className="flex-1 font-mono text-xs"
          />
          <button
            className="btn btn-primary"
            onClick={handlePull}
            disabled={pulling || !pullName.trim()}
            title="Запустить ollama pull"
          >
            {pulling ? '…' : '⬇ pull'}
          </button>
        </div>
        {pullErr && <div className="text-red-400 text-xs mt-1">{pullErr}</div>}
      </div>

      {/* Active pulls */}
      {snap.pull_queue.length > 0 && (
        <div className="flex-shrink-0 space-y-1">
          <div className="text-xs text-gray-400">Загрузки</div>
          {snap.pull_queue.map((p) => (
            <PullProgress key={p.name} item={p} />
          ))}
        </div>
      )}

      {/* Providers */}
      <div className="flex-1 space-y-4 min-h-0 overflow-auto">
        {snap.providers.map((prov) => (
          <ProviderSection
            key={prov.key}
            prov={prov}
            onModelClick={(m) => setDetail({ model: m, providerKey: prov.key })}
            onDelete={handleDelete}
          />
        ))}
      </div>

      {/* Detail overlay */}
      {detail && (
        <ModelDetail
          model={detail.model}
          providerKey={detail.providerKey}
          onClose={() => setDetail(null)}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
}

// ── Provider section ──────────────────────────────────────────────────────────

function ProviderSection({
  prov,
  onModelClick,
  onDelete,
}: {
  prov: ProviderData;
  onModelClick: (m: ModelEntry) => void;
  onDelete: (name: string) => void;
}) {
  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <ProviderStatus online={prov.online} label={prov.label} />
        <span className="text-xs text-gray-600 font-mono ml-auto">{prov.base_url}</span>
        <span className="text-xs text-gray-500">{prov.models.length} мод.</span>
      </div>

      {!prov.online && prov.error && (
        <div className="text-xs text-red-400 bg-red-900/20 rounded px-3 py-2 mb-2">
          {prov.error}
        </div>
      )}

      {/* Currently running in VRAM (Ollama only) */}
      {prov.running && prov.running.length > 0 && (
        <div className="flex gap-2 mb-2 flex-wrap">
          {prov.running.map((r) => (
            <div key={r.name} className="flex items-center gap-1.5 bg-green-900/20 border border-green-500/30 rounded px-2 py-1 text-xs">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              <span className="font-mono text-green-300">{r.name}</span>
              {r.vram_size_gb != null && (
                <span className="text-green-600">{fmtGb(r.vram_size_gb)} VRAM</span>
              )}
            </div>
          ))}
        </div>
      )}

      {prov.models.length === 0 && prov.online && (
        <div className="text-xs text-gray-500 italic">нет моделей</div>
      )}

      <div className="space-y-1">
        {prov.models.map((m) => (
          <ModelRow
            key={m.name}
            model={m}
            providerKey={prov.key}
            onClick={() => onModelClick(m)}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
}

// ── Model row ─────────────────────────────────────────────────────────────────

function ModelRow({
  model,
  providerKey,
  onClick,
  onDelete,
}: {
  model: ModelEntry;
  providerKey: string;
  onClick: () => void;
  onDelete: (name: string) => void;
}) {
  return (
    <div
      className="flex items-center gap-2 bg-[#0f1420] hover:bg-[#141e30] rounded px-3 py-2 cursor-pointer transition-colors"
      onClick={onClick}
    >
      {/* Status dot */}
      <div
        className={`w-2 h-2 rounded-full flex-shrink-0 ${model.running ? 'bg-green-400' : 'bg-[#2a3249]'}`}
        title={model.running ? 'загружена в VRAM' : 'не активна'}
      />

      {/* Name */}
      <span className="font-mono text-xs text-gray-200 flex-1 truncate min-w-0">
        {model.name}
      </span>

      {/* Badges */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {model.running && (
          <span className="text-[10px] font-medium text-green-400 bg-green-900/30 px-1.5 py-0.5 rounded">
            ▶ VRAM
          </span>
        )}
        {model.parameters && (
          <span className="text-[10px] text-gray-400 bg-[#1b2235] px-1.5 py-0.5 rounded">
            {model.parameters}
          </span>
        )}
        {model.quantization && (
          <span className="text-[10px] text-gray-500 bg-[#1b2235] px-1.5 py-0.5 rounded">
            {model.quantization}
          </span>
        )}
        {model.size_gb != null && (
          <span className="text-[10px] text-gray-400 w-14 text-right">{fmtGb(model.size_gb)}</span>
        )}
      </div>

      {/* Agents */}
      {(model.used_by_agents ?? []).length > 0 && (
        <div className="flex gap-1 flex-shrink-0">
          {(model.used_by_agents ?? []).slice(0, 3).map((a) => (
            <AgentBadge key={a.id} agent={a} />
          ))}
          {(model.used_by_agents ?? []).length > 3 && (
            <span className="text-[10px] text-gray-500">+{(model.used_by_agents ?? []).length - 3}</span>
          )}
        </div>
      )}

      {/* Delete (Ollama only, shown on hover via group) */}
      {providerKey === 'ollama' && (
        <button
          className="text-[10px] text-gray-600 hover:text-red-400 flex-shrink-0 ml-1"
          title="Удалить модель"
          onClick={(e) => {
            e.stopPropagation();
            if (confirm(`Удалить «${model.name}»?`)) onDelete(model.name);
          }}
        >
          🗑
        </button>
      )}
    </div>
  );
}
