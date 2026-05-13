import { useEffect, useMemo, useState } from 'react';
import { api, type SettingRow } from '../api';

// Link to VK implicit flow — opens instructions in the panel instead of
// taking the user away mid-configuration.
const VK_OAUTH_URL =
  'https://oauth.vk.com/authorize?client_id=YOUR_APP_ID' +
  '&display=page&redirect_uri=https://oauth.vk.com/blank.html' +
  '&scope=friends,wall,offline&response_type=token&v=5.199';

export function SettingsPanel() {
  const [rows, setRows] = useState<SettingRow[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [envPath, setEnvPath] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [settings, pathInfo] = await Promise.all([
        api.getSettings(),
        api.envPath(),
      ]);
      setRows(settings);
      setEnvPath(pathInfo.path);
      // Seed draft with current (unmasked-if-empty) values
      const initial: Record<string, string> = {};
      for (const r of settings) {
        // Don't pre-fill masked values — user must retype to update
        initial[r.key] = r.masked ? '' : r.value;
      }
      setDraft(initial);
    } catch (e: any) {
      setError(String(e.message ?? e));
    }
  };

  useEffect(() => { load(); }, []);

  const groups = useMemo(() => {
    const m: Record<string, SettingRow[]> = {};
    for (const r of rows) (m[r.group] ??= []).push(r);
    return m;
  }, [rows]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      // Only send keys that the user has actually typed something into.
      const updates: Record<string, string> = {};
      for (const [k, v] of Object.entries(draft)) {
        if (v !== '') updates[k] = v;
      }
      await api.updateSettings(updates);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      await load(); // refresh masked indicators
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setSaving(false);
    }
  };

  const groupColors: Record<string, string> = {
    LLM: '#a78bfa',
    VK: '#60a5fa',
    Telegram: '#34d399',
    Discord: '#818cf8',
    Steam: '#4ade80',
    Spotify: '#1db954',
  };

  return (
    <div className="flex flex-col gap-3 h-full overflow-auto text-sm">

      {/* env file path */}
      <div className="bg-[#0f1420] rounded px-3 py-2 text-xs text-gray-400 flex items-center gap-2">
        <span className="shrink-0">📄 .env:</span>
        <span className="font-mono truncate flex-1">{envPath || '…'}</span>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-500/40 rounded px-3 py-2 text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* groups */}
      {Object.entries(groups).map(([group, list]) => (
        <div key={group} className="flex flex-col gap-1">
          <div
            className="text-xs font-semibold uppercase tracking-wide px-1"
            style={{ color: groupColors[group] ?? '#94a3b8' }}
          >
            {group}
          </div>

          {/* VK oauth helper */}
          {group === 'VK' && (
            <div className="bg-[#0f1420] rounded p-2 text-xs text-gray-400 mb-1">
              Для получения токена:{' '}
              <a
                href={VK_OAUTH_URL}
                target="_blank"
                rel="noreferrer"
                className="text-[#60a5fa] underline"
              >
                открыть Implicit Flow ВКонтакте
              </a>{' '}
              (замени YOUR_APP_ID на id своего приложения из vk.com/apps).
              После входа токен появится в URL после <code>#access_token=</code>.
            </div>
          )}

          {list.map((r) => (
            <div key={r.key} className="flex flex-col gap-0.5">
              <div className="flex items-center justify-between px-1">
                <label className="text-gray-300 font-medium">{r.label}</label>
                {r.configured && (
                  <span className="text-[10px] text-green-400 bg-green-900/30 px-1.5 py-0.5 rounded">
                    ✓ задан
                  </span>
                )}
              </div>
              <input
                type={r.sensitive ? 'password' : 'text'}
                value={draft[r.key] ?? ''}
                onChange={(e) => setDraft({ ...draft, [r.key]: e.target.value })}
                placeholder={
                  r.masked
                    ? '(задан, оставь пустым чтобы не менять)'
                    : r.hint
                }
                className="font-mono text-xs"
              />
              <div className="text-[11px] text-gray-500 px-1">{r.hint}</div>
            </div>
          ))}
        </div>
      ))}

      {/* save bar */}
      <div className="flex items-center gap-3 pt-2 border-t border-white/10 sticky bottom-0 bg-[#141822] pb-1">
        <button
          className="btn btn-primary"
          onClick={save}
          disabled={saving}
        >
          {saving ? 'сохраняю…' : 'сохранить'}
        </button>
        {saved && (
          <span className="text-green-400 text-xs">
            ✓ сохранено — некоторые изменения вступят в силу сразу,
            остальные — после перезапуска claw
          </span>
        )}
        <span className="ml-auto text-xs text-gray-500">
          Изменения пишутся в .env файл на диске
        </span>
      </div>

    </div>
  );
}
