import { useEffect, useState } from 'react';
import { api } from '../api';

export function SteamPanel() {
  const [summary, setSummary] = useState<any>(null);
  const [recent, setRecent] = useState<any[]>([]);
  const [owned, setOwned] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [s, r, o] = await Promise.all([
          api.steamSummary(),
          api.steamRecent(6),
          api.steamOwned(24),
        ]);
        setSummary(s); setRecent(r); setOwned(o);
      } catch (e: any) { setErr(String(e.message ?? e)); }
    })();
  }, []);

  if (err) return <div className="text-sm text-red-400">Steam: {err}</div>;
  return (
    <div className="flex flex-col gap-2 h-full text-sm">
      {summary && (
        <div className="flex items-center gap-3 bg-[#0f1420] rounded p-2">
          {summary.avatarmedium && (
            <img src={summary.avatarmedium} className="w-10 h-10 rounded" />
          )}
          <div>
            <div className="font-semibold">{summary.personaname}</div>
            <div className="text-xs text-gray-400">
              {['offline','online','busy','away','snooze','looking to trade','looking to play'][summary.personastate ?? 0]}
            </div>
          </div>
        </div>
      )}

      <div className="text-xs text-gray-400">недавно играл</div>
      <div className="grid grid-cols-2 gap-1">
        {recent.map((g) => (
          <div key={g.appid} className="bg-[#0f1420] rounded p-2 text-xs">
            <div className="truncate">{g.name}</div>
            <div className="text-gray-500">
              {Math.round((g.playtime_2weeks ?? 0) / 60)}h за 2 нед · всего {Math.round((g.playtime_forever ?? 0) / 60)}h
            </div>
          </div>
        ))}
      </div>

      <div className="text-xs text-gray-400 mt-2">библиотека (по наигранному)</div>
      <div className="flex-1 min-h-0 overflow-auto grid grid-cols-2 gap-1">
        {owned.map((g) => (
          <div key={g.appid} className="bg-[#0f1420] rounded p-1.5 text-xs">
            <div className="truncate">{g.name}</div>
            <div className="text-gray-500">{Math.round((g.playtime_forever ?? 0) / 60)}h</div>
          </div>
        ))}
      </div>
    </div>
  );
}
