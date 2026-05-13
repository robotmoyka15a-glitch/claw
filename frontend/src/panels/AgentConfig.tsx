import { useEffect, useState } from 'react';
import { api, type Agent, type ProviderInfo } from '../api';
import { useStore } from '../store';

interface Props { agent: Agent }

export function AgentConfig({ agent }: Props) {
  const [draft, setDraft] = useState<Agent>(agent);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [saving, setSaving] = useState(false);
  const upsertAgent = useStore((s) => s.upsertAgent);
  const removeAgent = useStore((s) => s.removeAgent);

  useEffect(() => setDraft(agent), [agent.id]);
  useEffect(() => { api.providers().then(setProviders).catch(() => {}); }, []);

  const providerInfo = providers.find((p) => p.key === draft.llm_provider);

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
              <option key={p.key} value={p.key}>
                {p.key}
              </option>
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
              <option key={m} value={m}>
                {m}
              </option>
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
          style={{ minHeight: 140 }}
        />
      </label>

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
