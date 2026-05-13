import { useState, useCallback } from 'react';
import { api, type ProcessRow } from '../api';
import { useWS } from '../hooks/useWS';

type SortKey = 'cpu' | 'rss_mb' | 'pid' | 'name';

interface ProcessDetail {
  pid: number;
  name: string;
  exe: string;
  cwd: string;
  cmdline: string[];
  status: string;
  username: string;
  created: number;
  num_threads: number;
  cpu_percent: number;
  memory_mb: number;
  open_files: string[];
  connections: Array<{ laddr: string; raddr: string; status: string; family: string }>;
  error?: string;
}

export function ProcessList() {
  const [rows, setRows] = useState<ProcessRow[]>([]);
  const [q, setQ] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('cpu');
  const [sortAsc, setSortAsc] = useState(false);
  const [detail, setDetail] = useState<ProcessDetail | null>(null);
  const [loadingPid, setLoadingPid] = useState<number | null>(null);

  useWS<{ rows: ProcessRow[] }>('/ws/processes', ({ rows }) => setRows(rows));

  // ── filtering + sorting ───────────────────────────────────────────────────
  const filtered = (
    q ? rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q.toLowerCase()) ||
        String(r.pid).includes(q) ||
        (r.user || '').toLowerCase().includes(q.toLowerCase()),
    ) : rows
  ).slice().sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    const cmp =
      typeof av === 'string' && typeof bv === 'string'
        ? av.localeCompare(bv)
        : (av as number) - (bv as number);
    return sortAsc ? cmp : -cmp;
  });

  const setSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((p) => !p);
    else { setSortKey(key); setSortAsc(false); }
  };

  // ── detail ────────────────────────────────────────────────────────────────
  const openDetail = useCallback(async (pid: number) => {
    setLoadingPid(pid);
    try {
      const d = await api.processDetail(pid);
      setDetail(d as ProcessDetail);
    } catch {
      /* ignore */
    } finally {
      setLoadingPid(null);
    }
  }, []);

  const th = (label: string, key?: SortKey) => (
    <th
      className={`py-1 pr-2 text-left select-none ${key ? 'cursor-pointer hover:text-white' : ''}`}
      onClick={key ? () => setSort(key) : undefined}
    >
      {label}
      {key && sortKey === key && (sortAsc ? ' ↑' : ' ↓')}
    </th>
  );

  return (
    <div className="flex flex-col gap-2 h-full">
      <input
        placeholder="поиск по имени, PID или пользователю"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      <div className="flex-1 min-h-0 overflow-auto font-mono text-xs">
        <table className="w-full">
          <thead className="sticky top-0 bg-[#141822] text-gray-400">
            <tr>
              {th('PID', 'pid')}
              {th('Name', 'name')}
              {th('CPU%', 'cpu')}
              {th('RAM MB', 'rss_mb')}
              {th('User')}
              <th />
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr
                key={r.pid}
                className="border-t border-white/5 hover:bg-white/5 cursor-pointer"
                onClick={() => openDetail(r.pid)}
              >
                <td className="py-1 pr-2 text-gray-400">{r.pid}</td>
                <td className="py-1 pr-2 truncate max-w-[180px]">{r.name}</td>
                <td
                  className="py-1 pr-2 text-right"
                  style={{ color: r.cpu > 30 ? '#ef4444' : r.cpu > 10 ? '#f5b301' : undefined }}
                >
                  {r.cpu.toFixed(1)}
                </td>
                <td
                  className="py-1 pr-2 text-right"
                  style={{ color: r.rss_mb > 500 ? '#f5b301' : undefined }}
                >
                  {r.rss_mb.toFixed(0)}
                </td>
                <td className="py-1 pr-2 truncate max-w-[120px] text-gray-400">{r.user}</td>
                <td className="py-1">
                  <button
                    className="btn"
                    style={{ padding: '1px 6px', fontSize: 10, color: '#ef4444' }}
                    onClick={(e) => {
                      e.stopPropagation();
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
        <div className="text-gray-500 text-center py-1">
          {filtered.length} / {rows.length} процессов
        </div>
      </div>

      {/* Detail modal */}
      {(detail || loadingPid !== null) && (
        <div
          className="absolute inset-0 bg-black/70 flex items-center justify-center z-50"
          onClick={() => setDetail(null)}
        >
          <div
            className="panel w-[480px] max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-header">
              <span>
                {loadingPid !== null
                  ? `загрузка PID ${loadingPid}…`
                  : `${detail!.name} · PID ${detail!.pid}`}
              </span>
              <button className="btn" style={{ padding: '2px 8px' }} onClick={() => setDetail(null)}>
                ×
              </button>
            </div>

            {detail && !detail.error && (
              <div className="panel-body overflow-auto text-xs font-mono space-y-2">
                <Row k="Exe" v={detail.exe || '—'} />
                <Row k="CWD" v={detail.cwd || '—'} />
                <Row k="Cmdline" v={(detail.cmdline || []).join(' ') || '—'} />
                <Row k="Status" v={detail.status} />
                <Row k="User" v={detail.username} />
                <Row k="Threads" v={String(detail.num_threads)} />
                <Row k="CPU%" v={detail.cpu_percent?.toFixed(1) + '%'} />
                <Row k="RAM" v={detail.memory_mb?.toFixed(1) + ' MB'} />

                {detail.connections?.length > 0 && (
                  <div>
                    <div className="text-gray-400 mb-1">Сетевые соединения ({detail.connections.length})</div>
                    {detail.connections.slice(0, 10).map((c, i) => (
                      <div key={i} className="text-gray-300 pl-2">
                        {c.laddr} → {c.raddr || '—'} [{c.status}]
                      </div>
                    ))}
                  </div>
                )}

                {detail.open_files?.length > 0 && (
                  <div>
                    <div className="text-gray-400 mb-1">Открытые файлы ({detail.open_files.length})</div>
                    {detail.open_files.slice(0, 8).map((f, i) => (
                      <div key={i} className="text-gray-300 pl-2 truncate">{f}</div>
                    ))}
                    {detail.open_files.length > 8 && (
                      <div className="text-gray-500 pl-2">…и ещё {detail.open_files.length - 8}</div>
                    )}
                  </div>
                )}

                <div className="flex gap-2 pt-2">
                  <button
                    className="btn"
                    style={{ color: '#f5b301' }}
                    onClick={() => {
                      if (confirm(`Завершить ${detail.name} (PID ${detail.pid})?`)) {
                        api.killProcess(detail.pid).then(() => setDetail(null));
                      }
                    }}
                  >
                    terminate
                  </button>
                  <button
                    className="btn"
                    style={{ color: '#ef4444' }}
                    onClick={() => {
                      if (confirm(`FORCE KILL ${detail.name} (PID ${detail.pid})?`)) {
                        api.killProcess(detail.pid, true).then(() => setDetail(null));
                      }
                    }}
                  >
                    force kill
                  </button>
                </div>
              </div>
            )}

            {detail?.error && (
              <div className="panel-body text-red-400 text-xs">{detail.error}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2 min-w-0">
      <span className="text-gray-400 w-20 flex-shrink-0">{k}</span>
      <span className="text-gray-200 truncate flex-1">{v}</span>
    </div>
  );
}
