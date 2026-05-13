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
import { ToastLayer } from './panels/Toasts';
import { AgentConfig } from './panels/AgentConfig';
import { AgentChat } from './panels/AgentChat';
import { useWS } from './hooks/useWS';

// All panels selectable from the top dock. The list is filtered by connector
// status so we never show panels for services that aren't configured.
const ALL_PANELS: { key: PanelKey; title: string; size: [number, number]; connector?: string }[] = [
  { key: 'terminal', title: 'Терминал', size: [640, 420] },
  { key: 'processes', title: 'Процессы', size: [560, 420] },
  { key: 'system', title: 'Система', size: [520, 320] },
  { key: 'vk', title: 'ВКонтакте', size: [420, 520], connector: 'vk' },
  { key: 'telegram', title: 'Telegram', size: [420, 520], connector: 'telegram' },
  { key: 'discord', title: 'Discord', size: [420, 520], connector: 'discord' },
  { key: 'steam', title: 'Steam', size: [420, 520], connector: 'steam' },
  { key: 'spotify', title: 'Spotify', size: [360, 260], connector: 'spotify' },
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

  // Initial fetches
  useEffect(() => {
    api.listAgents().then(setAgents).catch(console.error);
    api.connectorStatus().then(setConnectors).catch(() => {});
  }, [setAgents, setConnectors]);

  // Live agent-state subscription (drives the room animations)
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

  // Live system snapshot — feeds the CPU painting and the Stats panel legend
  useWS<SystemSnapshot>('/ws/system', (snap) => setSnapshot(snap));

  // Poll pending notifications from backend (agents calling notify.toast)
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const list = await api.pendingNotifications();
        for (const n of list) {
          pushToast({ title: n.title, message: n.message, level: n.level, ts: n.ts });
        }
      } catch {/* backend may be down, ignore */}
    }, 3000);
    return () => clearInterval(t);
  }, [pushToast]);

  const onAgentClick = (agentId: string) => {
    const a = agents.find((x) => x.id === agentId);
    if (!a) return;
    openPanel({ key: 'agent-chat', title: `${a.name} · чат`, agentId });
    openPanel({ key: 'agent-config', title: `${a.name} · настройки`, agentId });
  };

  const connectorOk = (key?: string) => {
    if (!key) return true;
    return connectors.find((c) => c.key === key)?.configured ?? true;
    // ^ if the status list hasn't loaded yet, show the button optimistically
  };

  const visiblePanels = ALL_PANELS.filter((p) => connectorOk(p.connector));

  const snapshot = useStore((s) => s.snapshot);
  const agentStates = useStore((s) => s.agentStates);

  return (
    <div className="relative w-screen h-screen">
      <Room
        agents={agents}
        states={agentStates}
        snapshot={snapshot}
        onSelect={onAgentClick}
      />

      {/* top dock */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 flex flex-wrap gap-2 max-w-[75vw] justify-center">
        {visiblePanels.map((p) => (
          <button
            key={p.key}
            className="btn"
            onClick={() => openPanel({ key: p.key, title: p.title })}
          >
            {p.title}
          </button>
        ))}
        <button
          className="btn"
          onClick={() => {
            api
              .createAgent({ preset: 'researcher', name: 'Новый', desk: 'spare' })
              .then(upsertAgent);
          }}
        >
          + агент
        </button>
      </div>

      {/* brand */}
      <div className="absolute top-3 left-4 text-sm text-gray-400 pointer-events-none">
        <span className="text-[#f5b301] font-bold">claw</span> · рабочая комната
      </div>

      {/* toast layer */}
      <ToastLayer />

      {/* draggable panels */}
      {openPanels.map((p, i) => (
        <PanelFrame
          key={`${p.key}-${p.agentId ?? 'global'}`}
          title={p.title}
          onClose={() => closePanel(p.key, p.agentId)}
          initial={{
            x: 60 + i * 24,
            y: 70 + i * 24,
            w:
              p.key === 'agent-chat' ? 520 :
              p.key === 'agent-config' ? 440 :
              ALL_PANELS.find((g) => g.key === p.key)?.size[0] ?? 480,
            h:
              p.key === 'agent-chat' ? 480 :
              p.key === 'agent-config' ? 620 :
              ALL_PANELS.find((g) => g.key === p.key)?.size[1] ?? 360,
          }}
        >
          <PanelBody panelKey={p.key} agentId={p.agentId} />
        </PanelFrame>
      ))}
    </div>
  );
}

function PanelBody({ panelKey, agentId }: { panelKey: PanelKey; agentId?: string }) {
  const agent = useStore((s) => s.agents.find((a) => a.id === agentId));

  switch (panelKey) {
    case 'terminal': return <Terminal />;
    case 'processes': return <ProcessList />;
    case 'system': return <SystemStats />;
    case 'vk': return <VKFeed />;
    case 'telegram': return <TelegramPanel />;
    case 'discord': return <DiscordPanel />;
    case 'steam': return <SteamPanel />;
    case 'spotify': return <SpotifyPanel />;
    case 'notifications': return <div>see top-right toasts</div>;
    case 'agent-config':
      return agent ? <AgentConfig agent={agent} /> : <div>агент не найден</div>;
    case 'agent-chat':
      return agent ? <AgentChat agent={agent} /> : <div>агент не найден</div>;
  }
}
