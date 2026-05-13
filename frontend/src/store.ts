import { create } from 'zustand';
import type { Agent, SystemSnapshot } from './api';

export type PanelKey =
  | 'terminal'
  | 'processes'
  | 'system'
  | 'vk'
  | 'agent-config'
  | 'agent-chat';

interface PanelState {
  key: PanelKey;
  title: string;
  agentId?: string;
}

interface Store {
  agents: Agent[];
  selectedAgentId: string | null;
  snapshot: SystemSnapshot | null;
  openPanels: PanelState[];

  setAgents: (a: Agent[]) => void;
  upsertAgent: (a: Agent) => void;
  removeAgent: (id: string) => void;
  selectAgent: (id: string | null) => void;
  setSnapshot: (s: SystemSnapshot) => void;

  openPanel: (p: PanelState) => void;
  closePanel: (key: PanelKey, agentId?: string) => void;
}

export const useStore = create<Store>((set) => ({
  agents: [],
  selectedAgentId: null,
  snapshot: null,
  openPanels: [],

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
