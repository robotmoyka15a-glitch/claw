import { useEffect, useMemo, useState } from 'react';
import { api, type Agent, type ProviderInfo, type ToolInfo } from '../api';
import { useStore } from '../store';

interface Props { agent: Agent }

export function AgentConfig({ agent }: Props) {
  const [draft, setDraft] = useState<Agent>(agent);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [saving, setSaving] = useState(false);
  const upsertAgent = useStore((s) => s.upsertAgent);
  const removeAgent = useStore((s) => s.removeAgent);

  // FIX #5: зависимость agent (весь объект), а не только agent.id.
  // Если поля агента обновятся без смены id (upsertAgent) — draft синхронизируется.
  useEffect(() => setDraft(agent), [agent]);
  useEffect(() => {
    api.providers().then(setProviders).catch(() => {});
    api.tools().then(setTools).catch(() => {});
  }, []);

  const providerInfo = providers.find((p) => p.key === draft.llm_provider);

  const byCategory = useMemo(() => {
    const m: Record<string, ToolInfo[]> = {};
    for (const t of tools) (m[t.category] ??= []).push(t);
    return m;
  }, [tools]);

  const toggleTool = (name: string) => {
    const allowed = new Set(draft.allowed_tools ?? []);
    if (allowed.has(name)) allowed.delete(name);
    else allowed.add(name);
    setDraft({ ...draft, allowed_tools: [...allowed] });
  };

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateAgent(agent.id, {
        name: draft.name,
        llm_provider: draft.llm_provider,
        llm_model: draft.llm_model,
        system_prompt: draft.system_prompt,
        temperature: draft.temperature,
        color: draft.color,
        allowed_tools: draft.allowed_tools,
      });
      upsertAgent(updated);
    } finally {
      setSaving(false);
    }
  };

  const del = async () => {
    if (!confirm(`Удалить агента ${agent.name}?`)) return;
    await api.deleteAgent(agent.id);
    removeAgent(agent.id);
  };

  return (
    <div className="flex flex-col gap-2 text-sm h-full overflow-auto">
      <label className="flex flex-col gap-1">
        <span className="text-gray-400">Имя</span>
        <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
      </label>

      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-gray-400">Провайдер LLM</span>
          <select
            value={draft.llm_provider}
            onChange={(e) => setDraft({ ...draft, llm_provider: e.target.value, llm_model: '' })}
          >
            {providers.map((p) => (
              <option key={p.key} value={p.key}>{p.key}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-gray-400">Модель</span>
          <select
            value={draft.llm_model || ''}
            onChange={(e) => setDraft({ ...draft, llm_model: e.target.value })}
          >
            <option value="">{providerInfo?.default_model ?? 'default'} (по умолчанию)</option>
            {providerInfo?.models.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </label>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-gray-400">Температура: {draft.temperature.toFixed(2)}</span>
        <input
          type="range"
          min="0"
          max="1.5"
          step="0.05"
          value={draft.temperature}
          onChange={(e) => setDraft({ ...draft, temperature: Number(e.target.value) })}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-gray-400">Системный промпт</span>
        <textarea
          value={draft.system_prompt}
          onChange={(e) => setDraft({ ...draft, system_prompt: e.target.value })}
          style={{ minHeight: 120 }}
        />
      </label>

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <span className="text-gray-400">Инструменты ({draft.allowed_tools?.length ?? 0})</span>
          <span className="text-xs text-gray-500">
            отмечай, что можно вызывать LLM-у
          </span>
        </div>
        <div className="border border-white/10 rounded p-2 max-h-48 overflow-auto space-y-2">
          {Object.entries(byCategory).map(([cat, list]) => (
            <div key={cat}>
              <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">{cat}</div>
              {list.map((t) => {
                const on = (draft.allowed_tools ?? []).includes(t.name);
                return (
                  <label
                    key={t.name}
                    className="flex items-start gap-2 py-0.5 cursor-pointer hover:bg-white/5 rounded px-1"
                    title={t.description}
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggleTool(t.name)}
                      className="mt-1"
                    />
                    <div>
                      <div className="font-mono text-xs">
                        {t.name}
                        {t.dangerous && (
                          <span className="ml-1 text-[10px] text-red-400">DANGER</span>
                        )}
                      </div>
                      <div className="text-[11px] text-gray-400 leading-tight">
                        {t.description}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-gray-400">Цвет</span>
        <input
          type="color"
          value={draft.color}
          onChange={(e) => setDraft({ ...draft, color: e.target.value })}
          style={{ padding: 0, height: 32 }}
        />
      </label>

      <div className="flex gap-2 mt-auto pt-2">
        <button className="btn btn-primary" disabled={saving} onClick={save}>
          {saving ? 'сохраняю…' : 'сохранить'}
        </button>
        <button className="btn" onClick={del} style={{ marginLeft: 'auto', color: '#ef4444' }}>
          удалить агента
        </button>
      </div>

      {providerInfo?.error && (
        <div className="text-xs text-red-400 mt-1">
          {draft.llm_provider}: {providerInfo.error}
        </div>
      )}
    </div>
  );
}
