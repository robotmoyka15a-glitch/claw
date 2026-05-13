import { useEffect, useState } from 'react';
import { api, type SystemSnapshot } from './api';
import { useStore, type PanelKey } from './store';
import { Room } from './scene/Room';
import { PanelFrame } from './panels/PanelFrame';
import { Terminal } from './panels/Terminal';
import { SystemStats } from './panels/SystemStats';
import { ProcessList } from './panels/ProcessList';
import { VKFeed } from './panels/VKFeed';
import { TelegramPanel } from './panels/Telegram';
import { DiscordPanel } from './panels/Discord';
import { SteamPanel } from './panels/Steam';
import { SpotifyPanel } from './panels/Spotify';
import { SettingsPanel } from './panels/Settings';
import { AboutPanel } from './panels/About';
import { ModelsPanel } from './panels/Models';
import { ToastLayer } from './panels/Toasts';
import { AgentConfig } from './panels/AgentConfig';
import { AgentChat } from './panels/AgentChat';
import { useWS } from './hooks/useWS';

// ── метаданные панелей ────────────────────────────────────────────
interface PanelMeta {
  key: PanelKey;
  title: string;
  icon: string;
  size: [number, number];
  accent: string;       // hex без #
  glow?: string;        // data-glow CSS-класс
  connector?: string;
  group: 'system' | 'social' | 'tools';
}

const PANELS: PanelMeta[] = [
  // system
  { key: 'system',    title: 'Система',     icon: '📊', size: [520, 360], accent: '00e5ff', glow: 'cyan',   group: 'system' },
  { key: 'processes', title: 'Процессы',    icon: '🔧', size: [620, 480], accent: '4ade80', glow: 'green',  group: 'system' },
  { key: 'models',    title: 'Модели LLM',  icon: '🤖', size: [560, 580], accent: 'a855f7', glow: 'purple', group: 'system' },
  { key: 'terminal',  title: 'Терминал',    icon: '💻', size: [680, 440], accent: '22c55e', glow: 'green',  group: 'system' },
  // social
  { key: 'vk',       title: 'ВКонтакте',   icon: '💙', size: [440, 580], accent: '4a76a8', connector: 'vk',       group: 'social' },
  { key: 'telegram', title: 'Telegram',     icon: '✈️', size: [440, 540], accent: '2ca5e0', connector: 'telegram', group: 'social' },
  { key: 'discord',  title: 'Discord',      icon: '🎮', size: [440, 520], accent: '7289da', connector: 'discord',  group: 'social' },
  { key: 'steam',    title: 'Steam',        icon: '🎯', size: [440, 540], accent: '4a76a8', connector: 'steam',    group: 'social' },
  { key: 'spotify',  title: 'Spotify',      icon: '🎵', size: [360, 320], accent: '1db954', connector: 'spotify',  group: 'social' },
  // tools
  { key: 'settings', title: 'Настройки',   icon: '⚙️', size: [500, 660], accent: 'f5b301', group: 'tools' },
  { key: 'about',    title: 'Помощь',       icon: '❓', size: [520, 660], accent: 'a855f7', group: 'tools' },
];

// карта иконок групп для боковой панели
const GROUP_ICONS: Record<PanelMeta['group'], { icon: string; label: string }> = {
  system: { icon: '🖥', label: 'Система' },
  social: { icon: '🌐', label: 'Соцсети' },
  tools:  { icon: '🔩', label: 'Инструменты' },
};

// Uptime в человекочитаемом виде
function fmtUptime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}ч ${m}м` : `${m}м`;
}

// ── основной компонент ────────────────────────────────────────────
export default function App() {
  const {
    agents, setAgents, upsertAgent,
    openPanels, openPanel, closePanel,
    connectors, setConnectors,
    setAgentState, setSnapshot, pushToast,
  } = useStore();

  const snapshot = useStore((s) => s.snapshot);
  const agentStates = useStore((s) => s.agentStates);

  const [sideGroup, setSideGroup] = useState<PanelMeta['group'] | null>(null);

  // ── инициализация ────────────────────────────────────────────────
  useEffect(() => {
    api.listAgents().then(setAgents).catch(console.error);
    api.connectorStatus().then(setConnectors).catch(() => {});
  }, [setAgents, setConnectors]);

  // WebSocket: состояния агентов
  useWS<{ type?: string; agent_id?: string; state?: any; agents?: any[] }>(
    '/ws/agents-state',
    (msg) => {
      if (msg.type === 'snapshot' && Array.isArray(msg.agents))
        for (const { agent_id, state } of msg.agents) setAgentState(agent_id, state);
      else if (msg.agent_id && msg.state)
        setAgentState(msg.agent_id, msg.state);
    },
  );

  // WebSocket: системные метрики
  useWS<SystemSnapshot>('/ws/system', (snap) => setSnapshot(snap));

  // Пуш-уведомления от агентов
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const list = await api.pendingNotifications();
        for (const n of list)
          pushToast({ title: n.title, message: n.message, level: n.level, ts: n.ts });
      } catch { /* ignore */ }
    }, 3_000);
    return () => clearInterval(t);
  }, [pushToast]);

  // ── хелперы ───────────────────────────────────────────────────────
  const onAgentClick = (agentId: string) => {
    const a = agents.find((x) => x.id === agentId);
    if (!a) return;
    const accentMap: Record<string, string> = {
      boss: 'f5b301', sysadmin: '4ade80', vk_watcher: '60a5fa',
      terminal_helper: 'a78bfa', researcher: 'f472b6',
    };
    openPanel({ key: 'agent-chat',   title: `${a.name} · чат`,       agentId, accent: accentMap[a.preset] ?? 'f5b301' });
    openPanel({ key: 'agent-config', title: `${a.name} · настройки`, agentId, accent: accentMap[a.preset] ?? 'f5b301' });
  };

  const openByKey = (key: PanelKey) => {
    const meta = PANELS.find((p) => p.key === key);
    if (!meta) return;
    openPanel({ key: meta.key, title: meta.title, accent: meta.accent });
  };

  // фильтр групп с учётом коннекторов
  const visiblePanelsInGroup = (group: PanelMeta['group']) =>
    PANELS.filter((p) => p.group === group);

  // ── статус-бар ────────────────────────────────────────────────────
  const cpuPct  = snapshot?.cpu_percent ?? 0;
  const ramPct  = snapshot?.ram_percent ?? 0;
  const cpuWarn = cpuPct > 80;
  const ramWarn = ramPct > 80;
  const ollama  = connectors.length > 0;

  return (
    <div className="relative w-screen h-screen overflow-hidden" style={{ paddingLeft: 56, paddingBottom: 26 }}>
      {/* ── изометрическая комната ────────────────────────────────── */}
      <div className="absolute inset-0" style={{ left: 56, bottom: 26 }}>
        <Room
          agents={agents}
          states={agentStates}
          snapshot={snapshot}
          onSelect={onAgentClick}
        />
      </div>

      {/* ════════════════════════════════════════════════════════════
          БОКОВАЯ НАВИГАЦИЯ
      ════════════════════════════════════════════════════════════ */}
      <nav className="sidebar">
        {/* лого */}
        <div className="sidebar-logo select-none" title="claw">C</div>

        <div className="sidebar-sep" />

        {/* группы */}
        {(Object.entries(GROUP_ICONS) as [PanelMeta['group'], typeof GROUP_ICONS[PanelMeta['group']]][]).map(
          ([group, meta]) => (
            <button
              key={group}
              className={`nav-btn ${sideGroup === group ? 'active' : ''}`}
              data-tip={meta.label}
              data-glow={group === 'system' ? 'cyan' : group === 'social' ? 'green' : undefined}
              onClick={() => setSideGroup(sideGroup === group ? null : group)}
              title={meta.label}
            >
              {meta.icon}
            </button>
          )
        )}

        <div className="sidebar-sep" />

        {/* новый агент */}
        <button
          className="nav-btn"
          data-tip="Новый агент"
          title="Создать агента"
          onClick={() =>
            api.createAgent({ preset: 'researcher', name: 'Новый', desk: 'spare' })
              .then(upsertAgent).catch(() => {})
          }
        >
          ＋
        </button>

        {/* агенты-аватары в сайдбаре */}
        {agents.map((a) => {
          const st = agentStates[a.id];
          const isActive = st && st.status !== 'idle';
          return (
            <button
              key={a.id}
              className="nav-btn"
              data-tip={`${a.name} (${a.title ?? a.preset})`}
              title={a.name}
              onClick={() => onAgentClick(a.id)}
              style={{ position: 'relative' }}
            >
              <span
                style={{
                  width: 26, height: 26, borderRadius: '7px', display: 'flex',
                  alignItems: 'center', justifyContent: 'center',
                  background: a.color + '22',
                  border: `1px solid ${a.color}55`,
                  fontSize: '0.6rem', fontWeight: 700, color: a.color,
                }}
              >
                {a.name.slice(0, 2).toUpperCase()}
              </span>
              {/* зелёная точка когда агент активен */}
              {isActive && (
                <span style={{
                  position: 'absolute', bottom: 2, right: 2,
                  width: 6, height: 6, borderRadius: '50%',
                  background: st.status === 'tool' ? '#00e5ff' : '#f5b301',
                  boxShadow: `0 0 6px ${st.status === 'tool' ? '#00e5ff' : '#f5b301'}`,
                }} />
              )}
            </button>
          );
        })}
      </nav>

      {/* ════════════════════════════════════════════════════════════
          ВЫДВИЖНАЯ ПАНЕЛЬ С КНОПКАМИ ГРУППЫ
      ════════════════════════════════════════════════════════════ */}
      {sideGroup && (
        <div
          className="animate-in"
          style={{
            position: 'fixed',
            left: 56, top: 0, bottom: 26,
            width: 180,
            background: 'rgba(9,12,18,0.94)',
            borderRight: '1px solid rgba(255,255,255,0.07)',
            backdropFilter: 'saturate(180%) blur(14px)',
            display: 'flex', flexDirection: 'column',
            padding: '12px 10px',
            gap: 4,
            zIndex: 90,
          }}
        >
          <div style={{ fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)', textTransform: 'uppercase', paddingLeft: 6, marginBottom: 4 }}>
            {GROUP_ICONS[sideGroup].label}
          </div>

          {visiblePanelsInGroup(sideGroup).map((p) => (
            <button
              key={p.key}
              className="btn"
              style={{ textAlign: 'left', padding: '7px 10px', borderRadius: 8, fontSize: '0.78rem', gap: 8, display: 'flex', alignItems: 'center' }}
              onClick={() => { openByKey(p.key); setSideGroup(null); }}
            >
              <span>{p.icon}</span>
              <span>{p.title}</span>
            </button>
          ))}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
          ОТКРЫТЫЕ ПАНЕЛИ
      ════════════════════════════════════════════════════════════ */}
      {openPanels.map((p, i) => {
        const meta  = PANELS.find((m) => m.key === p.key);
        const isCnt = p.key === 'agent-chat' || p.key === 'agent-config';
        return (
          <PanelFrame
            key={`${p.key}-${p.agentId ?? 'global'}`}
            title={p.title}
            icon={meta?.icon}
            accentColor={p.accent ?? meta?.accent ?? 'f5b301'}
            onClose={() => closePanel(p.key, p.agentId)}
            initial={{
              x: 80 + i * 30,
              y: 60 + i * 30,
              w: isCnt
                ? (p.key === 'agent-chat' ? 520 : 460)
                : (meta?.size[0] ?? 480),
              h: isCnt
                ? (p.key === 'agent-chat' ? 500 : 640)
                : (meta?.size[1] ?? 380),
            }}
          >
            <PanelBody panelKey={p.key} agentId={p.agentId} />
          </PanelFrame>
        );
      })}

      {/* ════════════════════════════════════════════════════════════
          ТОСТЫ
      ════════════════════════════════════════════════════════════ */}
      <ToastLayer />

      {/* ════════════════════════════════════════════════════════════
          СТРОКА СТАТУСА
      ════════════════════════════════════════════════════════════ */}
      <footer className="statusbar">
        {/* CPU */}
        <div className={`statusbar-item ${cpuWarn ? 'warn' : 'ok'}`}>
          <div className="statusbar-dot" />
          <span>CPU</span>
          <strong>{cpuPct.toFixed(0)}%</strong>
        </div>
        {/* RAM */}
        <div className={`statusbar-item ${ramWarn ? 'warn' : 'ok'}`}>
          <div className="statusbar-dot" />
          <span>RAM</span>
          <strong>{ramPct.toFixed(0)}%</strong>
          {snapshot && <span style={{ color: 'var(--text-muted)' }}>({(snapshot.ram_used_mb / 1024).toFixed(1)} GB)</span>}
        </div>
        {/* Net */}
        {snapshot && (
          <div className="statusbar-item ok">
            <div className="statusbar-dot" />
            <span>↓{snapshot.net_recv_mb.toFixed(1)}</span>
            <span>↑{snapshot.net_sent_mb.toFixed(1)}</span>
            <span style={{ color: 'var(--text-muted)' }}>MB/s</span>
          </div>
        )}
        {/* Uptime */}
        {snapshot && (
          <div className="statusbar-item ok">
            <span>uptime</span>
            <strong>{fmtUptime(snapshot.uptime_s)}</strong>
          </div>
        )}

        {/* разделитель */}
        <div style={{ flex: 1 }} />

        {/* число агентов */}
        <div className="statusbar-item ok">
          <div className="statusbar-dot" />
          <strong>{agents.length}</strong>
          <span>агентов</span>
        </div>
        {/* claw brand */}
        <div style={{ color: 'var(--gold)', fontWeight: 700, fontSize: '0.72rem' }}>
          claw v0.1
        </div>
      </footer>
    </div>
  );
}

// ── тело панели ───────────────────────────────────────────────────
function PanelBody({ panelKey, agentId }: { panelKey: PanelKey; agentId?: string }) {
  const agent = useStore((s) => s.agents.find((a) => a.id === agentId));

  switch (panelKey) {
    case 'terminal':      return <Terminal />;
    case 'processes':     return <ProcessList />;
    case 'system':        return <SystemStats />;
    case 'models':        return <ModelsPanel />;
    case 'vk':            return <VKFeed />;
    case 'telegram':      return <TelegramPanel />;
    case 'discord':       return <DiscordPanel />;
    case 'steam':         return <SteamPanel />;
    case 'spotify':       return <SpotifyPanel />;
    case 'settings':      return <SettingsPanel />;
    case 'about':         return <AboutPanel />;
    case 'notifications': return <div className="text-sm" style={{ color: 'var(--text-dim)' }}>Уведомления появляются в правом верхнем углу.</div>;
    case 'agent-config':  return agent ? <AgentConfig agent={agent} /> : <div style={{ color: 'var(--text-dim)' }}>Агент не найден</div>;
    case 'agent-chat':    return agent ? <AgentChat agent={agent} /> : <div style={{ color: 'var(--text-dim)' }}>Агент не найден</div>;
  }
}
