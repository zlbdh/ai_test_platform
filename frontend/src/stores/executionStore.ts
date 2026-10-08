import { create } from 'zustand';

// ============================================================================
// Execution store: sessions and current test batch context
// ============================================================================

const STORAGE_KEY = 'ai-test-execution-store';

export interface SessionInfo {
    id: string;
    name: string;
    mode: 'chromium' | 'real';
}

export interface ExecutionBatchInfo {
    id: string;
    title: string;
    sessionId: string;
    source: 'orchestrator' | 'specialized';
    targetUrl?: string;
    createdAt: string;
}

interface PersistedExecutionState {
    sessions: SessionInfo[];
    activeSessionId: string;
    sessionGroups: Record<string, ExecutionBatchInfo>;
}

interface StartExecutionGroupOptions {
    groupId?: string;
    source?: ExecutionBatchInfo['source'];
    targetUrl?: string;
}

interface ExecutionStoreState extends PersistedExecutionState {
    addSession: (mode: 'chromium' | 'real') => SessionInfo;
    removeSession: (id: string) => void;
    setActiveSession: (id: string) => void;
    startExecutionGroup: (sessionId: string, title: string, options?: StartExecutionGroupOptions) => ExecutionBatchInfo;
    clearExecutionGroup: (sessionId?: string) => void;
    getExecutionGroup: (sessionId?: string) => ExecutionBatchInfo | null;
}

let sessionCounter = 1;

function createSessionId() {
    return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
}

function createInitialSession(): SessionInfo {
    return { id: createSessionId(), name: "Session 1", mode: 'chromium' };
}

function normalizePersistedState(raw: Partial<PersistedExecutionState> | null | undefined): PersistedExecutionState {
    const sessions = Array.isArray(raw?.sessions) && raw?.sessions.length > 0
        ? raw.sessions.filter((item): item is SessionInfo => Boolean(item?.id && item?.name && item?.mode))
        : [createInitialSession()];
    const activeSessionId = sessions.some((session) => session.id === raw?.activeSessionId)
        ? String(raw?.activeSessionId)
        : sessions[0].id;
    const sessionGroups = Object.fromEntries(
        Object.entries(raw?.sessionGroups || {}).filter(([sessionId, batch]) => {
            return Boolean(
                sessionId
                && batch
                && typeof batch.id === 'string'
                && typeof batch.title === 'string'
            );
        })
    ) as Record<string, ExecutionBatchInfo>;

    sessionCounter = Math.max(sessionCounter, sessions.length);

    return {
        sessions,
        activeSessionId,
        sessionGroups,
    };
}

function loadPersistedState(): PersistedExecutionState {
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            return normalizePersistedState(JSON.parse(saved) as Partial<PersistedExecutionState>);
        }
    } catch {
        // Ignore corrupted persisted data and use defaults
    }
    return normalizePersistedState(null);
}

function persistState(state: PersistedExecutionState) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function buildNextState(
    state: ExecutionStoreState,
    patch: Partial<PersistedExecutionState>
): PersistedExecutionState {
    return {
        sessions: patch.sessions ?? state.sessions,
        activeSessionId: patch.activeSessionId ?? state.activeSessionId,
        sessionGroups: patch.sessionGroups ?? state.sessionGroups,
    };
}

function createExecutionBatchId() {
    return `batch_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const initialState = loadPersistedState();

export const useExecutionStore = create<ExecutionStoreState>((set, get) => ({
    sessions: initialState.sessions,
    activeSessionId: initialState.activeSessionId,
    sessionGroups: initialState.sessionGroups,

    addSession: (mode) => {
        sessionCounter++;
        const newSession: SessionInfo = {
            id: createSessionId(),
            name: `Session ${sessionCounter}`,
            mode,
        };
        set((state) => {
            const next = buildNextState(state, {
                sessions: [...state.sessions, newSession],
                activeSessionId: newSession.id,
            });
            persistState(next);
            return next;
        });
        return newSession;
    },

    removeSession: (id) => {
        const { sessions, activeSessionId, sessionGroups } = get();
        if (sessions.length <= 1) return;
        const filteredSessions = sessions.filter((session) => session.id !== id);
        const nextGroups = { ...sessionGroups };
        delete nextGroups[id];
        const nextActiveSessionId = activeSessionId === id
            ? filteredSessions[filteredSessions.length - 1].id
            : activeSessionId;
        const next = {
            sessions: filteredSessions,
            activeSessionId: nextActiveSessionId,
            sessionGroups: nextGroups,
        };
        persistState(next);
        set(next);
    },

    setActiveSession: (id) => {
        set((state) => {
            const next = buildNextState(state, { activeSessionId: id });
            persistState(next);
            return next;
        });
    },

    startExecutionGroup: (sessionId, title, options) => {
        const batch: ExecutionBatchInfo = {
            id: options?.groupId || createExecutionBatchId(),
            title: title.trim(),
            sessionId,
            source: options?.source || 'specialized',
            targetUrl: options?.targetUrl || '',
            createdAt: new Date().toISOString(),
        };
        set((state) => {
            const next = buildNextState(state, {
                activeSessionId: sessionId,
                sessionGroups: {
                    ...state.sessionGroups,
                    [sessionId]: batch,
                },
            });
            persistState(next);
            return next;
        });
        return batch;
    },

    clearExecutionGroup: (sessionId) => {
        set((state) => {
            const resolvedSessionId = sessionId || state.activeSessionId || state.sessions[0]?.id;
            if (!resolvedSessionId || !state.sessionGroups[resolvedSessionId]) {
                return state;
            }
            const nextGroups = { ...state.sessionGroups };
            delete nextGroups[resolvedSessionId];
            const next = buildNextState(state, { sessionGroups: nextGroups });
            persistState(next);
            return next;
        });
    },

    getExecutionGroup: (sessionId) => {
        const state = get();
        const resolvedSessionId = sessionId || state.activeSessionId || state.sessions[0]?.id;
        if (!resolvedSessionId) {
            return null;
        }
        return state.sessionGroups[resolvedSessionId] || null;
    },
}));
