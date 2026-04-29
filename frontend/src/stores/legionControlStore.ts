import { create } from 'zustand';

export type LegionTabId = 'command' | 'control' | 'exploration' | 'warroom' | 'skills';

interface CommandRunFilters {
    commandId: string;
    projectKey: string;
    status: string;
    approvalStatus: string;
    source: string;
}

interface ExplorationFilters {
    projectKey: string;
    status: string;
    severity: string;
    reviewOnly: boolean;
    reviewStatus: string;
}

interface LegionControlStoreState {
    activeTab: LegionTabId;
    commandRunFilters: CommandRunFilters;
    explorationFilters: ExplorationFilters;
    selectedRunId: string | null;
    selectedSessionId: string | null;
    selectedAssessmentId: string | null;
    selectedFindingId: string | null;
    lastRefreshedAt: string;
    setActiveTab: (tab: LegionTabId) => void;
    setCommandRunFilters: (patch: Partial<CommandRunFilters>) => void;
    setExplorationFilters: (patch: Partial<ExplorationFilters>) => void;
    setSelectedRunId: (runId: string | null) => void;
    setSelectedSessionId: (sessionId: string | null) => void;
    setSelectedAssessmentId: (assessmentId: string | null) => void;
    setSelectedFindingId: (findingId: string | null) => void;
    markRefreshed: () => void;
}

export const useLegionControlStore = create<LegionControlStoreState>((set) => ({
    activeTab: 'command',
    commandRunFilters: {
        commandId: '',
        projectKey: '',
        status: '',
        approvalStatus: '',
        source: '',
    },
    explorationFilters: {
        projectKey: '',
        status: '',
        severity: '',
        reviewOnly: false,
        reviewStatus: '',
    },
    selectedRunId: null,
    selectedSessionId: null,
    selectedAssessmentId: null,
    selectedFindingId: null,
    lastRefreshedAt: '',
    setActiveTab: (tab) => set({ activeTab: tab }),
    setCommandRunFilters: (patch) => set((state) => ({
        commandRunFilters: {
            ...state.commandRunFilters,
            ...patch,
        },
    })),
    setExplorationFilters: (patch) => set((state) => ({
        explorationFilters: {
            ...state.explorationFilters,
            ...patch,
        },
    })),
    setSelectedRunId: (runId) => set({ selectedRunId: runId }),
    setSelectedSessionId: (sessionId) => set({ selectedSessionId: sessionId }),
    setSelectedAssessmentId: (assessmentId) => set({ selectedAssessmentId: assessmentId }),
    setSelectedFindingId: (findingId) => set({ selectedFindingId: findingId }),
    markRefreshed: () => set({ lastRefreshedAt: new Date().toISOString() }),
}));
