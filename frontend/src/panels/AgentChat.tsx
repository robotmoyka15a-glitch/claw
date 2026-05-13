import { useEffect, useRef, useState } from 'react';
import { api, wsUrl, type Agent } from '../api';

interface Msg { role: string; content: string; ts: number }

interface Props { agent: Agent }

export function AgentChat({ agent }: Props) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const streamBufRef = useRef('');
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.messages(agent.id).then(setMessages).catch(() => {});
  }, [agent.id]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl(`/ws/agents/${agent.id}`));
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'start') {
        streamBufRef.current = '';
        setStreaming(true);
        setMessages((prev) => [...prev, { role: 'assistant', content: '', ts: Date.now() / 1000 }]);
      } else if (m.type === 'delta') {
        streamBufRef.current += m.text;
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = { ...copy[copy.length - 1], content: streamBufRef.current };
          return copy;
        });
      } else if (m.type === 'end') {
        setStreaming(false);
      }
    };
    return () => ws.close();
  }, [agent.id]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  const send = () => {
    const text = input.trim();
    if (!text || streaming) return;
    setMessages((prev) => [...prev, { role: 'user', content: text, ts: Date.now() / 1000 }]);
    wsRef.current?.send(JSON.stringify({ type: 'user', text }));
    setInput('');
  };

  return (
    <div className="flex flex-col h-full gap-2">
      <div
        ref={listRef}
        className="flex-1 min-h-0 overflow-auto space-y-2 pr-1"
      >
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded p-2 text-sm whitespace-pre-wrap ${
              m.role === 'user' ? 'bg-[#1b2235]' : 'bg-[#0f1420]'
            }`}
          >
            <div className="text-xs text-gray-400 mb-1">
              {m.role === 'user' ? 'Вы' : agent.name}
            </div>
            {m.content || (streaming && i === messages.length - 1 ? '…' : '')}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={`написать ${agent.name}…`}
          style={{ minHeight: 48 }}
        />
        <button className="btn btn-primary" onClick={send} disabled={streaming}>
          {streaming ? '…' : '↵'}
        </button>
      </div>
    </div>
  );
}
