/**
 * Autonomy Panel — управление автономными задачами агентов.
 *
 * Три вкладки:
 *  📋 Задачи   — создание / редактирование / запуск задач
 *  📡 События  — живой лог событий (cpu_high, tg_message, task_finished, …)
 *  🧠 Роутер   — таблица capability-матрицы ModelRouter
 */
import { useEffect, useRef, useState } from 'react';
import { api, wsUrl } from '../api';
import { useStore } from '../store';

type Tab = 'tasks' | 'events' | 'router';

// ── Типы ─────────────────────────────────────────────────────────────────────

interface Task {
  id: string;
  agent_id: string;
  name: string;
  objective: string;
  trigger_type: 'manual' | 'interval' | 'cron' | 'event';
  trigger_value: string;
  enabled: boolean;
  max_iterations: number;
  last_run_at: number;
}

interface TaskRun {
  id: number;
  task_id: string;
  started_at: number;
  finished_at: number;
  trigger: string;
  status: 'running' | 'ok' | 'error';
  summary: string;
  error: string;
}

interface AutonomyEvent {
  event: string;
  ts: number;
  [key: string]: any;
}

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtTs(ts: number): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString('ru-RU', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function StatusDot({ status }: { status: 'running' | 'ok' | 'error' | string }) {
  const col = status === 'ok' ? '#22c55e' : status === 'error' ? '#ef4444' : '#f5b301';
  return (
    <span
      style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: col, marginRight: 5, boxShadow: `0 0 6px ${col}` }}
    />
  );
}

const TRIGGER_HINTS: Record<string, string> = {
  manual: 'Только вручную (кнопка ▶)',
  interval: 'Каждые N секунд. Значение: число секунд, например 300',
  cron: 'Cron-выражение. Примеры: */15 * * * *  или  @every 30m',
  event: 'Системное событие. Значения: cpu_high | mem_high | tg_message | vk_message | process_new',
};

// ── TaskForm ──────────────────────────────────────────────────────────────────

function TaskForm({
  agents,
  initial,
  onSave,
  onCancel,
}: {
  agents: any[];
  initial?: Partial<Task>;
  onSave: (data: any) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    agent_id: initial?.agent_id ?? (agents[0]?.id ?? ''),
    name: initial?.name ?? '',
    objective: initial?.objective ?? '',
    trigger_type: (initial?.trigger_type ?? 'manual') as Task['trigger_type'],
    trigger_value: initial?.trigger_value ?? '',
    enabled: initial?.enabled ?? true,
    max_iterations: initial?.max_iterations ?? 6,
  });

  return (
    <div className="flex flex-col gap-2 text-sm">
      <label className="flex flex-col gap-1">
        <span className="text-gray-400">Агент</span>
        <select value={form.agent_id} onChange={e => setForm({ ...form, agent_id: e.target.value })}>
          {agents.map(a => <option key={a.id} value={a.id}>{a.name} ({a.title})</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-gray-400">Название задачи</span>
        <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Например: Мониторинг CPU" />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-gray-400">Цель (что сделать)</span>
        <textarea
          value={form.objective}
          onChange={e => setForm({ ...form, objective: e.target.value })}
          placeholder="Проверь список процессов, найди те что грузят CPU больше 50%, и отправь уведомление через notify.toast"
          style={{ minHeight: 90 }}
        />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-gray-400">Триггер</span>
          <select
            value={form.trigger_type}
            onChange={e => setForm({ ...form, trigger_type: e.target.value as Task['trigger_type'], trigger_value: '' })}
          >
            <option value="manual">manual — вручную</option>
            <option value="interval">interval — по времени</option>
            <option value="cron">cron — расписание</option>
            <option value="event">event — по событию</option>
          </select>
        </label>
        {form.trigger_type !== 'manual' && (
          <label className="flex flex-col gap-1">
            <span className="text-gray-400">Значение</span>
            <input
              value={form.trigger_value}
              onChange={e => setForm({ ...form, trigger_value: e.target.value })}
              placeholder={
                form.trigger_type === 'interval' ? '300' :
                form.trigger_type === 'cron' ? '*/15 * * * *' :
                'cpu_high'
              }
            />
          </label>
        )}
      </div>
      {form.trigger_type !== 'manual' && (
        <div className="text-xs text-gray-500 bg-[#0a0d14] rounded px-2 py-1">
          {TRIGGER_HINTS[form.trigger_type]}
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-gray-400">Макс итераций</span>
          <input type="number" min="1" max="20" value={form.max_iterations}
            onChange={e => setForm({ ...form, max_iterations: +e.target.value })} />
        </label>
        <label className="flex items-center gap-2 mt-5 cursor-pointer">
          <input type="checkbox" checked={form.enabled}
            onChange={e => setForm({ ...form, enabled: e.target.checked })} />
          <span className="text-gray-300">Включена</span>
        </label>
      </div>
      <div className="flex gap-2 pt-1">
        <button className="btn btn-primary" onClick={() => onSave(form)}>сохранить</button>
        <button className="btn" onClick={onCancel}>отмена</button>
      </div>
    </div>
  );
}

// ── TaskRow ───────────────────────────────────────────────────────────────────

function TaskRow({
  task,
  agents,
  onEdit,
  onDelete,
  onRun,
  onToggle,
}: {
  task: Task;
  agents: any[];
  onEdit: (t: Task) => void;
  onDelete: (id: string) => void;
  onRun: (id: string) => void;
  onToggle: (id: string, enabled: boolean) => void;
}) {
  const agentName = agents.find(a => a.id === task.agent_id)?.name ?? task.agent_id.slice(0, 8);
  const [runs, setRuns] = useState<TaskRun[]>([]);
  const [showRuns, setShowRuns] = useState(false);

  const loadRuns = async () => {
    const r = await api.taskRuns(task.id, 5);
    setRuns(r);
    setShowRuns(true);
  };

  const triggerBadge = {
    manual: { bg: '#1f2637', col: '#7a8499', text: 'manual' },
    interval: { bg: '#1a2635', col: '#00e5ff', text: `⏱ ${task.trigger_value}s` },
    cron: { bg: '#1a2635', col: '#a855f7', text: `⏰ ${task.trigger_value}` },
    event: { bg: '#1a2635', col: '#f5b301', text: `⚡ ${task.trigger_value}` },
  }[task.trigger_type] ?? { bg: '#1f2637', col: '#7a8499', text: task.trigger_type };

  return (
    <div className={`rounded border ${task.enabled ? 'border-white/10' : 'border-white/5 opacity-60'} bg-[#0f1420] p-3 space-y-2`}>
      <div className="flex items-start gap-2">
        <input type="checkbox" checked={task.enabled}
          onChange={e => onToggle(task.id, e.target.checked)}
          className="mt-1 cursor-pointer" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm truncate">{task.name}</span>
            <span className="text-[10px] rounded px-1.5 py-0.5 font-mono"
              style={{ background: triggerBadge.bg, color: triggerBadge.col, border: `1px solid ${triggerBadge.col}44` }}>
              {triggerBadge.text}
            </span>
            <span className="text-[10px] text-gray-500 ml-auto">{agentName}</span>
          </div>
          <div className="text-xs text-gray-400 mt-0.5 line-clamp-2">{task.objective}</div>
          {task.last_run_at > 0 && (
            <div className="text-[10px] text-gray-600 mt-0.5">последний запуск: {fmtTs(task.last_run_at)}</div>
          )}
        </div>
      </div>

      <div className="flex gap-1.5 flex-wrap">
        <button className="btn btn-primary" style={{ fontSize: 11, padding: '3px 9px' }}
          onClick={() => onRun(task.id)}>
          ▶ запустить
        </button>
        <button className="btn" style={{ fontSize: 11, padding: '3px 9px' }}
          onClick={() => onEdit(task)}>
          ✏ изменить
        </button>
        <button className="btn" style={{ fontSize: 11, padding: '3px 9px' }}
          onClick={() => showRuns ? setShowRuns(false) : loadRuns()}>
          📋 логи
        </button>
        <button className="btn btn-danger" style={{ fontSize: 11, padding: '3px 9px', marginLeft: 'auto' }}
          onClick={() => { if (confirm(`Удалить задачу «${task.name}»?`)) onDelete(task.id); }}>
          🗑
        </button>
      </div>

      {showRuns && runs.length > 0 && (
        <div className="space-y-1 border-t border-white/5 pt-2">
          {runs.map(r => (
            <div key={r.id} className="flex items-start gap-2 text-xs bg-[#0a0d14] rounded px-2 py-1.5">
              <StatusDot status={r.status} />
              <div className="flex-1 min-w-0">
                <div className="flex gap-2 text-gray-500">
                  <span>{fmtTs(r.started_at)}</span>
                  <span className="text-gray-600">·</span>
                  <span className="text-[10px] font-mono">{r.trigger}</span>
                </div>
                {r.summary && <div className="text-gray-300 truncate">{r.summary}</div>}
                {r.error && <div className="text-red-400 truncate">{r.error}</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Events tab ────────────────────────────────────────────────────────────────

const EVENT_ICONS: Record<string, string> = {
  cpu_high: '🔥', mem_high: '💾',
  process_new: '🔵', process_died: '⚫',
  tg_message: '✈️', vk_message: '💙',
  spotify_track: '🎵',
  task_started: '▶', task_finished: '✅',
  agent_finished: '🤖',
};

function EventsTab() {
  const [events, setEvents] = useState<AutonomyEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.recentEvents(50).then(setEvents).catch(() => {});

    const connect = () => {
      const ws = new WebSocket(wsUrl('/ws/events'));
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'history') {
            setEvents(msg.events ?? []);
          } else if (msg.event) {
            setEvents(prev => [msg, ...prev].slice(0, 200));
          }
        } catch { /* ignore */ }
      };
      ws.onclose = () => { if (!cancelled) setTimeout(connect, 1000); };
      ws.onerror = () => ws.close();
    };
    connect();

    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="flex flex-col gap-1 h-full overflow-auto">
      {events.length === 0 && (
        <div className="text-gray-500 text-xs text-center pt-8">
          Событий пока нет. Они появятся когда агенты начнут работать.
        </div>
      )}
      {events.map((e, i) => {
        const icon = EVENT_ICONS[e.event] ?? '📣';
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { event: _ev, ts: _ts, ...payload } = e;
        const payloadStr = Object.entries(payload)
          .filter(([, v]) => v !== undefined && v !== null)
          .map(([k, v]) => `${k}: ${typeof v === 'string' ? v.slice(0, 60) : JSON.stringify(v)}`)
          .join(' · ');

        const eventColor: Record<string, string> = {
          task_finished: '#22c55e', task_started: '#f5b301',
          cpu_high: '#ef4444', mem_high: '#f97316',
          tg_message: '#2ca5e0', vk_message: '#4a76a8',
        };
        const col = eventColor[e.event] ?? '#6b7488';

        return (
          <div key={i} className="flex items-start gap-2 rounded px-2 py-1.5 hover:bg-white/3"
            style={{ borderLeft: `2px solid ${col}` }}>
            <span className="text-sm flex-shrink-0">{icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold font-mono" style={{ color: col }}>{e.event}</span>
                <span className="text-[10px] text-gray-600 ml-auto">{fmtTs(e.ts)}</span>
              </div>
              {payloadStr && (
                <div className="text-[11px] text-gray-400 truncate">{payloadStr}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Router tab ────────────────────────────────────────────────────────────────

function RouterTab() {
  const [caps, setCaps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.routerCapabilities()
      .then(setCaps)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const Bar = ({ value, max = 10, color }: { value: number; max?: number; color: string }) => (
    <div className="flex items-center gap-1">
      <div className="w-16 h-1.5 bg-[#1f2637] rounded-full overflow-hidden">
        <div style={{ width: `${(value / max) * 100}%`, background: color, height: '100%' }} />
      </div>
      <span className="text-[10px] text-gray-400">{value}</span>
    </div>
  );

  return (
    <div className="h-full overflow-auto text-xs">
      <div className="mb-2 text-gray-400">
        ModelRouter выбирает оптимальный провайдер для каждого агента автоматически.
        Больше очки = лучше по критерию.
      </div>
      {loading && <div className="text-gray-500">загрузка…</div>}
      <table className="w-full">
        <thead className="sticky top-0 bg-[#141822]">
          <tr className="text-left text-gray-500">
            <th className="py-1 pr-2">Провайдер / Модель</th>
            <th className="py-1 pr-2">Tools</th>
            <th className="py-1 pr-2">Reason</th>
            <th className="py-1 pr-2">Speed</th>
            <th className="py-1 pr-2">Vision</th>
            <th className="py-1 pr-2">Offline</th>
          </tr>
        </thead>
        <tbody>
          {caps.map((c, i) => (
            <tr key={i} className="border-t border-white/5">
              <td className="py-1 pr-2">
                <div className="font-mono text-[11px]">{c.provider}</div>
                <div className="text-gray-500">{c.model || '(default)'}</div>
              </td>
              <td className="py-1 pr-2"><Bar value={c.tool_calling} color="#00e5ff" /></td>
              <td className="py-1 pr-2"><Bar value={c.reasoning} color="#a855f7" /></td>
              <td className="py-1 pr-2"><Bar value={c.speed} color="#22c55e" /></td>
              <td className="py-1 pr-2"><Bar value={c.vision} color="#f97316" /></td>
              <td className="py-1 pr-2">
                {c.offline
                  ? <span className="badge badge-green">local</span>
                  : <span className="badge badge-cyan">cloud</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function AutonomyPanel() {
  const agents = useStore(s => s.agents);
  const [tab, setTab] = useState<Tab>('tasks');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [editing, setEditing] = useState<Task | null | 'new'>(null);
  const [loading, setLoading] = useState(false);

  const loadTasks = async () => {
    setLoading(true);
    try { setTasks(await api.listTasks()); } finally { setLoading(false); }
  };

  useEffect(() => { loadTasks(); }, []);

  const handleSave = async (data: any) => {
    if (editing === 'new') {
      const t = await api.createTask(data);
      setTasks(prev => [t, ...prev]);
    } else if (editing) {
      const t = await api.updateTask(editing.id, data);
      setTasks(prev => prev.map(x => x.id === t.id ? t : x));
    }
    setEditing(null);
  };

  const handleDelete = async (id: string) => {
    await api.deleteTask(id);
    setTasks(prev => prev.filter(t => t.id !== id));
  };

  const handleRun = async (id: string) => {
    await api.runTask(id);
    // Refresh task list to see updated last_run_at
    setTimeout(loadTasks, 1500);
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    const t = await api.updateTask(id, { enabled });
    setTasks(prev => prev.map(x => x.id === t.id ? t : x));
  };

  return (
    <div className="flex flex-col h-full gap-2">
      {/* tabs */}
      <div className="flex gap-1 border-b border-white/10 flex-shrink-0">
        {([['tasks', '📋 Задачи'], ['events', '📡 События'], ['router', '🧠 Роутер']] as [Tab, string][]).map(
          ([key, label]) => (
            <button
              key={key}
              className="px-3 py-1.5 text-xs rounded-t transition-colors"
              style={{
                background: tab === key ? '#1b2235' : 'transparent',
                color: tab === key ? '#e6e8ef' : '#6b7488',
                borderBottom: tab === key ? '2px solid #f5b301' : '2px solid transparent',
              }}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          )
        )}
      </div>

      {/* tab body */}
      <div className="flex-1 min-h-0 overflow-auto">
        {tab === 'tasks' && (
          <div className="space-y-3">
            {editing ? (
              <div className="rounded border border-white/10 bg-[#0f1420] p-3">
                <div className="text-xs font-semibold text-gray-400 mb-2">
                  {editing === 'new' ? 'Новая задача' : `Редактировать: ${editing.name}`}
                </div>
                <TaskForm
                  agents={agents}
                  initial={editing === 'new' ? undefined : editing}
                  onSave={handleSave}
                  onCancel={() => setEditing(null)}
                />
              </div>
            ) : (
              <button
                className="btn btn-primary w-full"
                style={{ justifyContent: 'center', display: 'flex', gap: 6 }}
                onClick={() => setEditing('new')}
              >
                ＋ создать задачу
              </button>
            )}

            {loading && <div className="text-gray-500 text-xs text-center">загрузка…</div>}

            {tasks.length === 0 && !loading && !editing && (
              <div className="text-center text-gray-500 text-xs py-8">
                <div className="text-3xl mb-2">🤖</div>
                <div>Нет задач. Создай первую — агент будет работать сам.</div>
                <div className="mt-1 text-gray-600">
                  Примеры: проверять CPU каждые 5 мин · отвечать на сообщения VK · мониторить новые процессы
                </div>
              </div>
            )}

            {tasks.map(t => (
              <TaskRow
                key={t.id}
                task={t}
                agents={agents}
                onEdit={task => setEditing(task)}
                onDelete={handleDelete}
                onRun={handleRun}
                onToggle={handleToggle}
              />
            ))}
          </div>
        )}

        {tab === 'events' && <EventsTab />}
        {tab === 'router' && <RouterTab />}
      </div>
    </div>
  );
}
