import { useMemo } from 'react';
import { useExecutionStore } from '../stores';
import type { ExecutionBatchInfo } from '../stores/executionStore';

export interface ExecutionContextPayload {
    session_id: string;
    execution_group_id?: string;
    group_title?: string;
}

interface EnsureExecutionContextOptions {
    sessionId?: string;
    targetUrl?: string;
    source?: ExecutionBatchInfo['source'];
}

interface ActiveExecutionContext {
    sessionId: string;
    batch: ExecutionBatchInfo | null;
    payload: ExecutionContextPayload;
}

function resolveSessionId() {
    const state = useExecutionStore.getState();
    return state.activeSessionId || state.sessions[0]?.id || 'default_session';
}

export function summarizeExecutionTitle(input: string, fallback: string = '未命名测试批次') {
    const firstLine = input
        .split('\n')
        .map((item) => item.trim())
        .find(Boolean);
    const title = firstLine || fallback;
    return title.length > 48 ? `${title.slice(0, 48)}...` : title;
}

export function summarizeExecutionTarget(input?: string, fallback: string = '专项测试批次') {
    const raw = (input || '').trim();
    if (!raw) return fallback;
    try {
        if (raw.startsWith('http://') || raw.startsWith('https://')) {
            const parsed = new URL(raw);
            const compact = `${parsed.host}${parsed.pathname === '/' ? '' : parsed.pathname}`;
            return summarizeExecutionTitle(compact, fallback);
        }
    } catch {
        // ignore and fall back to plain text summarization
    }
    return summarizeExecutionTitle(raw, fallback);
}

export function buildSpecializedExecutionTitle(seedTitle: string, targetUrl?: string) {
    const targetLabel = summarizeExecutionTarget(targetUrl, '');
    if (targetLabel) {
        return summarizeExecutionTitle(`专项测试 · ${targetLabel}`, '专项测试批次');
    }
    return summarizeExecutionTitle(seedTitle || '专项测试批次', '专项测试批次');
}

export function buildExecutionContextPayload(sessionId?: string): ExecutionContextPayload {
    const state = useExecutionStore.getState();
    const resolvedSessionId = sessionId || resolveSessionId();
    const batch = state.getExecutionGroup(resolvedSessionId);
    return {
        session_id: resolvedSessionId,
        execution_group_id: batch?.id,
        group_title: batch?.title,
    };
}

export function beginExecutionCampaign(
    title: string,
    options?: { sessionId?: string; targetUrl?: string; source?: ExecutionBatchInfo['source'] }
) {
    const state = useExecutionStore.getState();
    const resolvedSessionId = options?.sessionId || resolveSessionId();
    return state.startExecutionGroup(
        resolvedSessionId,
        summarizeExecutionTitle(title),
        {
            source: options?.source || 'orchestrator',
            targetUrl: options?.targetUrl,
        }
    );
}

export function ensureExecutionContextPayload(
    seedTitle: string,
    options?: EnsureExecutionContextOptions
): ExecutionContextPayload {
    const state = useExecutionStore.getState();
    const resolvedSessionId = options?.sessionId || resolveSessionId();
    let batch = state.getExecutionGroup(resolvedSessionId);

    if (!batch) {
        batch = state.startExecutionGroup(
            resolvedSessionId,
            buildSpecializedExecutionTitle(seedTitle, options?.targetUrl),
            {
                source: options?.source || 'specialized',
                targetUrl: options?.targetUrl,
            }
        );
    }

    return {
        session_id: resolvedSessionId,
        execution_group_id: batch.id,
        group_title: batch.title,
    };
}

export function clearExecutionCampaign(sessionId?: string) {
    useExecutionStore.getState().clearExecutionGroup(sessionId || resolveSessionId());
}

export function useActiveExecutionContext(): ActiveExecutionContext {
    const sessionId = useExecutionStore((state) => state.activeSessionId || state.sessions[0]?.id || 'default_session');
    const batch = useExecutionStore((state) => {
        const resolvedSessionId = state.activeSessionId || state.sessions[0]?.id || 'default_session';
        return resolvedSessionId ? state.sessionGroups[resolvedSessionId] || null : null;
    });

    return useMemo(() => ({
        sessionId,
        batch,
        payload: {
            session_id: sessionId,
            execution_group_id: batch?.id,
            group_title: batch?.title,
        },
    }), [batch, sessionId]);
}
