import { create } from 'zustand';
import { AgentType, AgentStat } from '../types';

// ============================================================================
// Agent Store — Agent 状态统计管理
// ============================================================================

const DEFAULT_AGENTS: AgentStat[] = [
    { id: AgentType.PLANNER, name: 'Planner Agent', role: '测试策略规划', status: 'IDLE', tasksCompleted: 0, successRate: 100 },
    { id: AgentType.UI, name: 'UI Agent', role: 'Web UI 自动化', status: 'IDLE', tasksCompleted: 0, successRate: 100 },
    { id: AgentType.API, name: 'API Agent', role: 'API 接口测试', status: 'IDLE', tasksCompleted: 0, successRate: 100 },
    { id: AgentType.DATA, name: 'Data Agent', role: '数据验证', status: 'IDLE', tasksCompleted: 0, successRate: 100 },
    { id: AgentType.RCA, name: 'RCA Agent', role: '根因分析', status: 'IDLE', tasksCompleted: 0, successRate: 100 },
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
