import { useEffect, useState } from 'react';
import { api } from '../api';

export function TelegramPanel() {
  const [me, setMe] = useState<any>(null);
  const [updates, setUpdates] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [toSend, setToSend] = useState('');

  const refresh = async () => {
    setErr(null);
    try {
      const [m, u] = await Promise.all([api.tgMe(), api.tgUpdates(20)]);
      setMe(m);
      setUpdates(u);
    } catch (e: any) {
      setErr(String(e.message ?? e));
    }
  };
  useEffect(() => { refresh(); }, []);

  const send = async () => {
    if (!toSend.trim()) return;
    try {
      await api.tgSend(toSend);
      setToSend('');
      refresh();
    } catch (e: any) {
      setErr(String(e.message ?? e));
    }
  };

  if (err) return <div className="text-sm text-red-400">Telegram: {err}</div>;

  return (
    <div className="flex flex-col gap-2 h-full text-sm">
      {me && (
        <div className="bg-[#0f1420] rounded p-2">
          <div className="font-semibold">@{me.username}</div>
          <div className="text-xs text-gray-400">{me.first_name} · bot id {me.id}</div>
        </div>
      )}
      <div className="flex gap-2">
        <input
          placeholder="сообщение в default chat…"
          value={toSend}
          onChange={(e) => setToSend(e.target.value)}
        />
        <button className="btn btn-primary" onClick={send}>→</button>
        <button className="btn" onClick={refresh}>⟳</button>
      </div>
      <div className="flex-1 min-h-0 overflow-auto space-y-2">
        {updates.length === 0 && (
          <div className="text-gray-500 text-xs">нет входящих обновлений</div>
        )}
        {updates.map((u, i) => {
          const m = u.message ?? u.channel_post ?? {};
          return (
            <div key={i} className="bg-[#0f1420] rounded p-2">
              <div className="text-xs text-gray-400">
                {m.from?.username ?? m.from?.first_name ?? 'chat'} · {m.chat?.title ?? m.chat?.id}
              </div>
              <div className="whitespace-pre-wrap">{m.text ?? '(медиа)'}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
