import { create } from 'zustand';
import type { MissionResult, MissionLog } from '../services/commanderService';

// ============================================================================
// Commander store: persist Commander execution state
// ============================================================================

interface CommanderStoreState {
    // Execution state
    isRunning: boolean;
    activeMission: MissionResult | null;
    streamLogs: MissionLog[];
    missions: MissionResult[];

    // SSE cleanup
    _sseCleanup: (() => void) | null;

    // Actions
    startMission: (mission: MissionResult) => void;
    appendStreamLog: (log: MissionLog) => void;
    finishMission: (final: MissionResult | null, missions: MissionResult[]) => void;
    setActiveMission: (mission: MissionResult | null) => void;
    setMissions: (missions: MissionResult[] | ((prev: MissionResult[]) => MissionResult[])) => void;
    setIsRunning: (v: boolean) => void;
    setSseCleanup: (cleanup: (() => void) | null) => void;
    clearStreamLogs: () => void;
}

export const useCommanderStore = create<CommanderStoreState>((set) => ({
    isRunning: false,
    activeMission: null,
    streamLogs: [],
    missions: [],
    _sseCleanup: null,

    startMission: (mission) =>
        set({
            isRunning: true,
            activeMission: mission,
            streamLogs: [],
        }),

    appendStreamLog: (log) =>
        set((state) => ({
            streamLogs: [...state.streamLogs, log],
        })),

    finishMission: (final, missions) =>
        set({
            isRunning: false,
            activeMission: final,
            missions,
        }),

    setActiveMission: (mission) => set({ activeMission: mission }),
    setMissions: (missions) => set((state) => ({
        missions: typeof missions === 'function' ? missions(state.missions) : missions,
    })),
    setIsRunning: (v) => set({ isRunning: v }),
    setSseCleanup: (cleanup) => set({ _sseCleanup: cleanup }),
    clearStreamLogs: () => set({ streamLogs: [] }),
}));
