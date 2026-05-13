import { useState } from 'react';
import { api, type ProcessRow } from '../api';
import { useWS } from '../hooks/useWS';

export function ProcessList() {
  const [rows, setRows] = useState<ProcessRow[]>([]);
  const [q, setQ] = useState('');

  useWS<{ rows: ProcessRow[] }>('/ws/processes', ({ rows }) => setRows(rows));

  const filtered = q
    ? rows.filter((r) => r.name.toLowerCase().includes(q.toLowerCase()) || String(r.pid).includes(q))
    : rows;

  return (
    <div className="flex flex-col gap-2 h-full">
      <input
        placeholder="поиск по имени или PID"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="flex-1 min-h-0 overflow-auto font-mono text-xs">
        <table className="w-full">
          <thead className="sticky top-0 bg-[#141822]">
            <tr className="text-left text-gray-400">
              <th className="py-1 pr-2">PID</th>
              <th className="py-1 pr-2">Name</th>
              <th className="py-1 pr-2 text-right">CPU%</th>
              <th className="py-1 pr-2 text-right">RAM MB</th>
              <th className="py-1 pr-2">User</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.pid} className="border-t border-white/5 hover:bg-white/5">
                <td className="py-1 pr-2">{r.pid}</td>
                <td className="py-1 pr-2 truncate max-w-[200px]">{r.name}</td>
                <td className="py-1 pr-2 text-right">{r.cpu.toFixed(1)}</td>
                <td className="py-1 pr-2 text-right">{r.rss_mb.toFixed(0)}</td>
                <td className="py-1 pr-2 truncate max-w-[140px]">{r.user}</td>
                <td className="py-1">
                  <button
                    className="btn"
                    style={{ padding: '1px 6px', fontSize: 10 }}
                    onClick={() => {
                      if (confirm(`Завершить ${r.name} (PID ${r.pid})?`)) {
                        api.killProcess(r.pid).catch(() => {});
                      }
                    }}
                  >
                    kill
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
