import { create } from 'zustand';
import { AgentType, AgentStat } from '../types';

// ============================================================================
// Agent store: agent status statistics
// ============================================================================

const DEFAULT_AGENTS: AgentStat[] = [
    { id: AgentType.PLANNER, name: 'Planner Agent', role: "Test strategy planning", status: 'IDLE', tasksCompleted: 0, successRate: 100 },
    { id: AgentType.UI, name: 'UI Agent', role: "Web UI automation", status: 'IDLE', tasksCompleted: 0, successRate: 100 },
    { id: AgentType.API, name: 'API Agent', role: "API testing", status: 'IDLE', tasksCompleted: 0, successRate: 100 },
    { id: AgentType.DATA, name: 'Data Agent', role: "Data validation", status: 'IDLE', tasksCompleted: 0, successRate: 100 },
    { id: AgentType.RCA, name: 'RCA Agent', role: "Root cause analysis", status: 'IDLE', tasksCompleted: 0, successRate: 100 },
];

interface AgentStoreState {
    agents: AgentStat[];
    updateAgentStatus: (agentId: AgentType, status: 'IDLE' | 'BUSY' | 'ERROR' | 'HEALING') => void;
    incrementAgentTasks: (agentId: AgentType, success: boolean) => void;
    resetAgents: () => void;
}

export const useAgentStore = create<AgentStoreState>((set) => ({
    agents: DEFAULT_AGENTS,

    updateAgentStatus: (agentId, status) => set((state) => ({
        agents: state.agents.map(a => a.id === agentId ? { ...a, status } : a),
    })),

    incrementAgentTasks: (agentId, success) => set((state) => ({
        agents: state.agents.map(a => {
            if (a.id !== agentId) return a;
            const total = a.tasksCompleted + 1;
            const successCount = Math.round(a.successRate * a.tasksCompleted / 100) + (success ? 1 : 0);
            return { ...a, tasksCompleted: total, successRate: Math.round(successCount / total * 100) };
        }),
    })),

    resetAgents: () => set({ agents: DEFAULT_AGENTS }),
}));
