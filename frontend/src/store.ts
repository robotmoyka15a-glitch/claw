import { create } from 'zustand';
import type { Agent, AgentState, ConnectorStatus, SystemSnapshot } from './api';

export type PanelKey =
  | 'terminal'
  | 'processes'
  | 'system'
  | 'vk'
  | 'telegram'
  | 'discord'
  | 'steam'
  | 'spotify'
  | 'notifications'
  | 'settings'
  | 'about'
  | 'agent-config'
  | 'agent-chat';

interface PanelState {
  key: PanelKey;
  title: string;
  agentId?: string;
}

interface Toast {
  id: number;
  title: string;
  message: string;
  level: 'info' | 'warn' | 'error';
  ts: number;
}

interface Store {
  agents: Agent[];
  selectedAgentId: string | null;
  snapshot: SystemSnapshot | null;
  openPanels: PanelState[];

  connectors: ConnectorStatus[];
  agentStates: Record<string, AgentState>;
  toasts: Toast[];

  setAgents: (a: Agent[]) => void;
  upsertAgent: (a: Agent) => void;
  removeAgent: (id: string) => void;
  selectAgent: (id: string | null) => void;
  setSnapshot: (s: SystemSnapshot) => void;

  setConnectors: (c: ConnectorStatus[]) => void;
  setAgentState: (agentId: string, st: AgentState) => void;

  pushToast: (t: Omit<Toast, 'id'>) => void;
  dismissToast: (id: number) => void;

  openPanel: (p: PanelState) => void;
  closePanel: (key: PanelKey, agentId?: string) => void;
}

let toastSeq = 1;

export const useStore = create<Store>((set) => ({
  agents: [],
  selectedAgentId: null,
  snapshot: null,
  openPanels: [],

  connectors: [],
  agentStates: {},
  toasts: [],

  setAgents: (agents) => set({ agents }),
  upsertAgent: (a) =>
    set((s) => {
      const rest = s.agents.filter((x) => x.id !== a.id);
      return { agents: [...rest, a] };
    }),
  removeAgent: (id) =>
    set((s) => ({
      agents: s.agents.filter((a) => a.id !== id),
      selectedAgentId: s.selectedAgentId === id ? null : s.selectedAgentId,
    })),
  selectAgent: (id) => set({ selectedAgentId: id }),
  setSnapshot: (snapshot) => set({ snapshot }),

  setConnectors: (connectors) => set({ connectors }),
  setAgentState: (agentId, st) =>
    set((s) => ({ agentStates: { ...s.agentStates, [agentId]: st } })),

  pushToast: (t) =>
    set((s) => ({
      toasts: [...s.toasts, { ...t, id: toastSeq++ }],
    })),
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  openPanel: (p) =>
    set((s) => {
      const exists = s.openPanels.find(
        (x) => x.key === p.key && x.agentId === p.agentId,
      );
      if (exists) return s;
      return { openPanels: [...s.openPanels, p] };
    }),
  closePanel: (key, agentId) =>
    set((s) => ({
      openPanels: s.openPanels.filter(
        (x) => !(x.key === key && x.agentId === agentId),
      ),
    })),
}));
