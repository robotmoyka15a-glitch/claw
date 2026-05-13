import { useEffect } from 'react';
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
import { AutonomyPanel } from './panels/Autonomy';
import { ToastLayer } from './panels/Toasts';
import { AgentConfig } from './panels/AgentConfig';
import { AgentChat } from './panels/AgentChat';
import { useWS } from './hooks/useWS';

const ALL_PANELS: {
  key: PanelKey;
  title: string;
  size: [number, number];
  connector?: string;
  always?: boolean;
}[] = [
  { key: 'terminal',  title: '💻 Терминал',   size: [640, 420], always: true },
  { key: 'processes', title: '🔧 Процессы',   size: [600, 460], always: true },
  { key: 'system',    title: '📊 Система',    size: [520, 340], always: true },
  { key: 'autonomy',  title: '🤖 Автономия',  size: [620, 580], always: true },
  { key: 'vk',        title: '💙 ВКонтакте', size: [440, 560], connector: 'vk' },
  { key: 'telegram',  title: '✈️ Telegram',   size: [420, 520], connector: 'telegram' },
  { key: 'discord',   title: '🎮 Discord',    size: [420, 520], connector: 'discord' },
  { key: 'steam',     title: '🎯 Steam',      size: [420, 520], connector: 'steam' },
  { key: 'spotify',   title: '🎵 Spotify',    size: [360, 300], connector: 'spotify' },
  { key: 'settings',  title: '⚙️ Настройки', size: [500, 640], always: true },
  { key: 'about',     title: '❓ Помощь',     size: [520, 640], always: true },
];

export default function App() {
  const {
    agents,
    setAgents,
    upsertAgent,
    openPanels,
    openPanel,
    closePanel,
    connectors,
    setConnectors,
    setAgentState,
    setSnapshot,
    pushToast,
  } = useStore();

  useEffect(() => {
    api.listAgents().then(setAgents).catch(console.error);
    api.connectorStatus().then(setConnectors).catch(() => {});
  }, [setAgents, setConnectors]);

  useWS<{ type?: string; agent_id?: string; state?: any; agents?: any[] }>(
    '/ws/agents-state',
    (msg) => {
      if (msg.type === 'snapshot' && Array.isArray(msg.agents)) {
        for (const { agent_id, state } of msg.agents) setAgentState(agent_id, state);
      } else if (msg.agent_id && msg.state) {
        setAgentState(msg.agent_id, msg.state);
      }
    },
  );

  useWS<SystemSnapshot>('/ws/system', (snap) => setSnapshot(snap));

  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const list = await api.pendingNotifications();
        for (const n of list)
          pushToast({ title: n.title, message: n.message, level: n.level, ts: n.ts });
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(t);
  }, [pushToast]);

  const onAgentClick = (agentId: string) => {
    const a = agents.find((x) => x.id === agentId);
    if (!a) return;
    openPanel({ key: 'agent-chat', title: `${a.name} · чат`, agentId });
    openPanel({ key: 'agent-config', title: `${a.name} · настройки`, agentId });
  };

  const connectorOk = (p: typeof ALL_PANELS[0]) => {
    if (p.always) return true;
    if (!p.connector) return true;
    // Show connector panels always — panel itself will show error if not configured
    return true;
  };

  const snapshot = useStore((s) => s.snapshot);
  const agentStates = useStore((s) => s.agentStates);

  // Split dock into two rows if too many buttons
  const visiblePanels = ALL_PANELS.filter(connectorOk);

  return (
    <div className="relative w-screen h-screen overflow-hidden">
      <Room
        agents={agents}
        states={agentStates}
        snapshot={snapshot}
        onSelect={onAgentClick}
      />

      {/* top dock — two rows */}
      <div className="absolute top-2 left-1/2 -translate-x-1/2 flex flex-wrap gap-1.5 justify-center max-w-[90vw] z-10">
        {visiblePanels.map((p) => (
          <button
            key={p.key}
            className="btn text-xs px-2.5 py-1"
            onClick={() => openPanel({ key: p.key, title: p.title })}
          >
            {p.title}
          </button>
        ))}
        <button
          className="btn text-xs px-2.5 py-1"
          onClick={() =>
            api.createAgent({ preset: 'researcher', name: 'Новый', desk: 'spare' })
              .then(upsertAgent)
              .catch(() => {})
          }
        >
          ➕ агент
        </button>
      </div>

      {/* brand — bottom left */}
      <div className="absolute bottom-3 left-4 text-xs text-gray-500 pointer-events-none select-none">
        <span className="text-[#f5b301] font-bold">claw</span>
        {' '}·{' '}
        <span>{agents.length} агентов</span>
        {snapshot && (
          <span className="ml-2">
            CPU {snapshot.cpu_percent.toFixed(0)}%{' '}
            RAM {snapshot.ram_percent.toFixed(0)}%
          </span>
        )}
      </div>

      <ToastLayer />

      {openPanels.map((p, i) => {
        const def = ALL_PANELS.find((g) => g.key === p.key);
        return (
          <PanelFrame
            key={`${p.key}-${p.agentId ?? 'global'}`}
            title={p.title}
            onClose={() => closePanel(p.key, p.agentId)}
            initial={{
              x: 60 + i * 28,
              y: 70 + i * 28,
              w: p.key === 'agent-chat' ? 520 : p.key === 'agent-config' ? 460 : def?.size[0] ?? 480,
              h: p.key === 'agent-chat' ? 500 : p.key === 'agent-config' ? 640 : def?.size[1] ?? 380,
            }}
          >
            <PanelBody panelKey={p.key} agentId={p.agentId} />
          </PanelFrame>
        );
      })}
    </div>
  );
}

function PanelBody({ panelKey, agentId }: { panelKey: PanelKey; agentId?: string }) {
  const agent = useStore((s) => s.agents.find((a) => a.id === agentId));

  switch (panelKey) {
    case 'terminal':     return <Terminal />;
    case 'processes':    return <ProcessList />;
    case 'system':       return <SystemStats />;
    case 'autonomy':     return <AutonomyPanel />;
    case 'vk':           return <VKFeed />;
    case 'telegram':     return <TelegramPanel />;
    case 'discord':      return <DiscordPanel />;
    case 'steam':        return <SteamPanel />;
    case 'spotify':      return <SpotifyPanel />;
    case 'settings':     return <SettingsPanel />;
    case 'about':        return <AboutPanel />;
    case 'notifications': return <div className="text-sm text-gray-400">Уведомления появятся в правом верхнем углу.</div>;
    case 'agent-config': return agent ? <AgentConfig agent={agent} /> : <div className="text-sm text-gray-400">Агент не найден</div>;
    case 'agent-chat':   return agent ? <AgentChat agent={agent} /> : <div className="text-sm text-gray-400">Агент не найден</div>;
  }
}
