import { create } from 'zustand';

// ============================================================================
// Exploratory store: persist exploratory testing execution state
// ============================================================================

interface ExploratoryStoreState {
    running: boolean;
    taskId: string;
    logs: string[];
    status: string;  // 'idle' | 'running' | 'completed' | 'failed' | 'stopped'
    stats: { pages: number; actions: number; anomalies: number };

    // Actions
    start: (taskId: string) => void;
    appendLog: (log: string) => void;
    finish: (status: string) => void;
    updateStats: (stats: { pages: number; actions: number; anomalies: number }) => void;
    reset: () => void;
}

export const useExploratoryStore = create<ExploratoryStoreState>((set) => ({
    running: false,
    taskId: '',
    logs: [],
    status: 'idle',
    stats: { pages: 0, actions: 0, anomalies: 0 },

    start: (taskId) =>
        set({
            running: true,
            taskId,
            logs: [`[Started] Task ${taskId} started`],
            status: 'running',
            stats: { pages: 0, actions: 0, anomalies: 0 },
        }),

    appendLog: (log) =>
        set((state) => ({
            logs: [...state.logs, log],
        })),

    finish: (status) =>
        set({
            running: false,
            status,
        }),

    updateStats: (stats) => set({ stats }),

    reset: () =>
        set({
            running: false,
            taskId: '',
            logs: [],
            status: 'idle',
            stats: { pages: 0, actions: 0, anomalies: 0 },
        }),
}));
