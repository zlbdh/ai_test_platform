import { create } from 'zustand';
import type { FrontdoorTask, FrontdoorTaskKind } from '../services/frontdoorTaskService';

export interface FrontdoorDraft {
    taskKind: FrontdoorTaskKind;
    userGoal: string;
    targetUrl: string;
    sourceType: 'url' | 'file' | 'directory';
    source: string;
    compareSource: string;
    playbookId: string;
}

interface FrontdoorTaskStoreState {
    draft: FrontdoorDraft;
    tasks: FrontdoorTask[];
    currentTask: FrontdoorTask | null;
    currentTaskId: string | null;
    filters: {
        taskKind: FrontdoorTaskKind | '';
        status: string;
    };
    streamConnected: boolean;
    setDraft: (patch: Partial<FrontdoorDraft>) => void;
    resetDraft: () => void;
    setTasks: (tasks: FrontdoorTask[]) => void;
    setCurrentTask: (task: FrontdoorTask | null | ((task: FrontdoorTask | null) => FrontdoorTask | null)) => void;
    setCurrentTaskId: (taskId: string | null) => void;
    setFilters: (patch: Partial<FrontdoorTaskStoreState['filters']>) => void;
    setStreamConnected: (connected: boolean) => void;
}

const defaultDraft: FrontdoorDraft = {
    taskKind: 'general',
    userGoal: '',
    targetUrl: '',
    sourceType: 'url',
    source: '',
    compareSource: '',
    playbookId: 'sample-platform-prototype',
};

export const useFrontdoorTaskStore = create<FrontdoorTaskStoreState>((set) => ({
    draft: defaultDraft,
    tasks: [],
    currentTask: null,
    currentTaskId: null,
    filters: {
        taskKind: '',
        status: '',
    },
    streamConnected: false,
    setDraft: (patch) => set((state) => ({ draft: { ...state.draft, ...patch } })),
    resetDraft: () => set({ draft: defaultDraft }),
    setTasks: (tasks) => set({ tasks }),
    setCurrentTask: (task) => set((state) => {
        const nextTask = typeof task === 'function' ? task(state.currentTask) : task;
        return {
            currentTask: nextTask,
            currentTaskId: nextTask?.task_id ?? null,
        };
    }),
    setCurrentTaskId: (taskId) => set({ currentTaskId: taskId }),
    setFilters: (patch) => set((state) => ({ filters: { ...state.filters, ...patch } })),
    setStreamConnected: (connected) => set({ streamConnected: connected }),
}));
