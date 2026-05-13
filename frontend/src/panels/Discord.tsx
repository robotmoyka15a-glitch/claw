import { useEffect, useState } from 'react';
import { api } from '../api';

export function DiscordPanel() {
  const [me, setMe] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [toSend, setToSend] = useState('');

  const refresh = async () => {
    setErr(null);
    try {
      const [m, msgs] = await Promise.all([api.dcMe(), api.dcMessages(30)]);
      setMe(m);
      setMessages(msgs);
    } catch (e: any) {
      setErr(String(e.message ?? e));
    }
  };
  useEffect(() => { refresh(); }, []);

  const send = async () => {
    if (!toSend.trim()) return;
    try {
      await api.dcSend(toSend);
      setToSend('');
      refresh();
    } catch (e: any) {
      setErr(String(e.message ?? e));
    }
  };

  if (err) return <div className="text-sm text-red-400">Discord: {err}</div>;

  return (
    <div className="flex flex-col gap-2 h-full text-sm">
      {me && (
        <div className="bg-[#0f1420] rounded p-2">
          <div className="font-semibold">{me.username}</div>
          <div className="text-xs text-gray-400">bot id {me.id}</div>
        </div>
      )}
      <div className="flex gap-2">
        <input
          placeholder="сообщение в default channel…"
          value={toSend}
          onChange={(e) => setToSend(e.target.value)}
        />
        <button className="btn btn-primary" onClick={send}>→</button>
        <button className="btn" onClick={refresh}>⟳</button>
      </div>
      <div className="flex-1 min-h-0 overflow-auto space-y-2">
        {messages.length === 0 && (
          <div className="text-gray-500 text-xs">канал пуст</div>
        )}
        {messages.map((m) => (
          <div key={m.id} className="bg-[#0f1420] rounded p-2">
            <div className="text-xs text-gray-400">{m.author}</div>
            <div className="whitespace-pre-wrap">{m.content || '(embed)'}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
