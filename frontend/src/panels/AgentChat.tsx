import { useEffect, useRef, useState } from 'react';
import { api, wsUrl, type Agent } from '../api';

type MsgKind = 'user' | 'assistant' | 'tool';

interface ChatEntry {
  kind: MsgKind;
  text: string;
  /** For tool entries: tool name + result preview */
  tool?: { name: string; args?: string; result?: string; error?: string };
}

interface Props { agent: Agent }

/** Truncate a JSON-looking string for display. */
function short(s: string, n = 240): string {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

export function AgentChat({ agent }: Props) {
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const streamBufRef = useRef('');
  const listRef = useRef<HTMLDivElement>(null);

  // Rehydrate from stored history.
  useEffect(() => {
    api.messages(agent.id).then((msgs) => {
      const rebuilt: ChatEntry[] = [];
      for (const m of msgs) {
        const c = m.content || '';
        if (m.role === 'assistant' && c.startsWith('::tool_calls::')) {
          try {
            const payload = JSON.parse(c.slice('::tool_calls::'.length));
            if (payload.text) rebuilt.push({ kind: 'assistant', text: payload.text });
            for (const tc of payload.tool_calls ?? []) {
              rebuilt.push({
                kind: 'tool',
                text: '',
                tool: { name: tc.name, args: tc.arguments },
              });
            }
          } catch {
            rebuilt.push({ kind: 'assistant', text: c });
          }
        } else if (m.role === 'tool' && c.startsWith('::tool_result::')) {
          try {
            const payload = JSON.parse(c.slice('::tool_result::'.length));
            // find the most recent open tool entry without a result
            const idx = [...rebuilt]
              .map((e, i) => ({ e, i }))
              .reverse()
              .find(({ e }) => e.kind === 'tool' && !e.tool?.result && !e.tool?.error);
            if (idx && idx.e.tool) {
              idx.e.tool.result = payload.content;
            }
          } catch {
            /* ignore */
          }
        } else if (m.role === 'user' || m.role === 'assistant') {
          rebuilt.push({ kind: m.role as MsgKind, text: c });
        }
      }
      setEntries(rebuilt);
    }).catch(() => {});
  }, [agent.id]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl(`/ws/agents/${agent.id}`));
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'start') {
        streamBufRef.current = '';
        setStreaming(true);
        setEntries((prev) => [...prev, { kind: 'assistant', text: '' }]);
      } else if (m.type === 'delta') {
        streamBufRef.current += m.text;
        setEntries((prev) => {
          const copy = [...prev];
          // update the latest assistant entry (if the last one is a tool, push new assistant)
          let last = copy[copy.length - 1];
          if (!last || last.kind !== 'assistant') {
            copy.push({ kind: 'assistant', text: streamBufRef.current });
          } else {
            copy[copy.length - 1] = { ...last, text: streamBufRef.current };
          }
          return copy;
        });
      } else if (m.type === 'tool_call') {
        streamBufRef.current = '';
        setEntries((prev) => [
          ...prev,
          { kind: 'tool', text: '', tool: { name: m.name, args: m.arguments } },
        ]);
      } else if (m.type === 'tool_result' || m.type === 'tool_error') {
        setEntries((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            const e = copy[i];
            if (e.kind === 'tool' && e.tool && !e.tool.result && !e.tool.error) {
              const updated = { ...e, tool: { ...e.tool } };
              if (m.type === 'tool_result') {
                updated.tool.result = JSON.stringify(m.value);
              } else {
                updated.tool.error = m.error;
              }
              copy[i] = updated;
              break;
            }
          }
          return copy;
        });
      } else if (m.type === 'status') {
        // decorative only; the room handles visuals
      } else if (m.type === 'end') {
        setStreaming(false);
      } else if (m.type === 'error') {
        setEntries((prev) => [...prev, { kind: 'assistant', text: `[error: ${m.error}]` }]);
        setStreaming(false);
      }
    };
    return () => ws.close();
  }, [agent.id]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [entries]);

  const send = () => {
    const text = input.trim();
    if (!text || streaming) return;
    setEntries((prev) => [...prev, { kind: 'user', text }]);
    wsRef.current?.send(JSON.stringify({ type: 'user', text }));
    setInput('');
  };

  return (
    <div className="flex flex-col h-full gap-2">
      <div ref={listRef} className="flex-1 min-h-0 overflow-auto space-y-2 pr-1">
        {entries.map((e, i) =>
          e.kind === 'tool' ? (
            <div
              key={i}
              className="rounded border border-[#2a3249] bg-[#0a0d14] p-2 text-xs font-mono"
            >
              <div className="flex items-center gap-2">
                <span className="text-[#60a5fa]">🛠 {e.tool?.name}</span>
                {e.tool?.args && e.tool.args !== '{}' && (
                  <span className="text-gray-500 truncate">{short(e.tool.args, 120)}</span>
                )}
              </div>
              {e.tool?.result && (
                <div className="mt-1 text-gray-300 whitespace-pre-wrap break-all">
                  {short(e.tool.result, 480)}
                </div>
              )}
              {e.tool?.error && (
                <div className="mt-1 text-red-400">{e.tool.error}</div>
              )}
            </div>
          ) : (
            <div
              key={i}
              className={`rounded p-2 text-sm whitespace-pre-wrap ${
                e.kind === 'user' ? 'bg-[#1b2235]' : 'bg-[#0f1420]'
              }`}
            >
              <div className="text-xs text-gray-400 mb-1">
                {e.kind === 'user' ? 'Вы' : agent.name}
              </div>
              {e.text || (streaming && i === entries.length - 1 ? '…' : '')}
            </div>
          ),
        )}
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
