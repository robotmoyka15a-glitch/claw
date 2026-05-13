import { useEffect } from 'react';
import { api } from './api';
import { useStore, type PanelKey } from './store';
import { Room } from './scene/Room';
import { PanelFrame } from './panels/PanelFrame';
import { Terminal } from './panels/Terminal';
import { SystemStats } from './panels/SystemStats';
import { ProcessList } from './panels/ProcessList';
import { VKFeed } from './panels/VKFeed';
import { AgentConfig } from './panels/AgentConfig';
import { AgentChat } from './panels/AgentChat';

const GLOBAL_PANELS: { key: PanelKey; title: string; size: [number, number] }[] = [
  { key: 'terminal', title: 'Терминал', size: [640, 420] },
  { key: 'processes', title: 'Процессы', size: [560, 420] },
  { key: 'system', title: 'Система', size: [520, 320] },
  { key: 'vk', title: 'ВКонтакте', size: [420, 520] },
];

export default function App() {
  const { agents, setAgents, openPanels, openPanel, closePanel } = useStore();

  useEffect(() => {
    api.listAgents().then(setAgents).catch(console.error);
  }, [setAgents]);

  const onAgentClick = (agentId: string) => {
    const a = agents.find((x) => x.id === agentId);
    if (!a) return;
    openPanel({ key: 'agent-chat', title: `${a.name} · чат`, agentId });
    openPanel({ key: 'agent-config', title: `${a.name} · настройки`, agentId });
  };

  return (
    <div className="relative w-screen h-screen">
      {/* 1. isometric room */}
      <Room agents={agents} onSelect={onAgentClick} />

      {/* 2. top dock */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 flex gap-2">
        {GLOBAL_PANELS.map((p) => (
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
              .createAgent({
                preset: 'researcher',
                name: 'Новый',
                desk: 'spare',
              })
              .then((a) => {
                useStore.getState().upsertAgent(a);
              });
          }}
        >
          + агент
        </button>
      </div>

      {/* 3. title / brand */}
      <div className="absolute top-3 left-4 text-sm text-gray-400 pointer-events-none">
        <span className="text-[#f5b301] font-bold">claw</span> · рабочая комната
      </div>

      {/* 4. open panels */}
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
              p.key === 'agent-config' ? 420 :
              GLOBAL_PANELS.find((g) => g.key === p.key)?.size[0] ?? 480,
            h:
              p.key === 'agent-chat' ? 480 :
              p.key === 'agent-config' ? 520 :
              GLOBAL_PANELS.find((g) => g.key === p.key)?.size[1] ?? 360,
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
    case 'agent-config':
      return agent ? <AgentConfig agent={agent} /> : <div>агент не найден</div>;
    case 'agent-chat':
      return agent ? <AgentChat agent={agent} /> : <div>агент не найден</div>;
  }
}
