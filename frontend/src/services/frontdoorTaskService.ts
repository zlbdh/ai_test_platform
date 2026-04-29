import { API_BASE_URL } from '../config';
import type { MissionLog } from './commanderService';

const BASE = `${API_BASE_URL}/api/commander`;
const TIMEOUT = 60_000;

async function fetchJSON<T>(url: string, options: RequestInit = {}): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT);
    try {
        const resp = await fetch(url, { ...options, signal: controller.signal });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } finally {
        clearTimeout(timer);
    }
}

export type FrontdoorTaskKind = 'general' | 'prototype' | 'exploration';
export type GateStatus = 'passed' | 'warning' | 'failed';

export interface FrontdoorFinding {
    finding_id?: string;
    evidence_id?: string;
    severity: string;
    title: string;
    summary: string;
    category: string;
    agent_id: string;
    source_type?: string;
    locator?: string;
}

export interface FrontdoorGateSummary {
    status: GateStatus;
    summary: string;
    metrics: Record<string, unknown>;
    decision_reason?: string;
}

export interface FrontdoorEvidenceSummary {
    log_count: number;
    finding_count: number;
    has_report: boolean;
    worker_count?: number;
    execution_group_id: string;
    summary_keys?: string[];
    evidence_ids?: string[];
    latest_log_at?: string | null;
    static_unprovable_count?: number;
}

export interface FrontdoorVerificationState {
    status: 'verified_passed' | 'issues_found' | 'context_unprovable' | 'pending';
    label: string;
    summary: string;
}

export interface FrontdoorTask {
    task_id: string;
    mission_kind: string;
    task_kind: FrontdoorTaskKind;
    user_goal: string;
    status: string;
    created_at?: string;
    started_at?: string | null;
    completed_at?: string | null;
    source_context: Record<string, unknown>;
    strategy: Record<string, unknown>;
    agent_states: Record<string, string>;
    evidence_summary: FrontdoorEvidenceSummary;
    findings: FrontdoorFinding[];
    gate_summary: FrontdoorGateSummary;
    verification_state: FrontdoorVerificationState;
    recommendations: string[];
    result_summary: Record<string, unknown>;
    logs: MissionLog[];
    execution_group_id: string;
    lineage_root_id: string;
    rerun_from_task_id: string;
    execution_center_path: string;
    quality_gate_path: string;
    expert_path: string;
    raw_report: Record<string, unknown>;
}

export interface FrontdoorTaskRequest {
    task_kind: FrontdoorTaskKind;
    user_goal: string;
    source_context: Record<string, unknown>;
    strategy: Record<string, unknown>;
}

export interface FrontdoorTaskListFilters {
    limit?: number;
    taskKind?: FrontdoorTaskKind | '';
    status?: string;
    lineageRootId?: string;
}

export interface FrontdoorTaskActionResult {
    task_id: string;
    cancelled: boolean;
    status: string;
    message: string;
}

function createTaskStream(url: string, onLog: (log: MissionLog) => void, onEnd?: () => void): () => void {
    const evtSource = new EventSource(url);

    evtSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.level === 'end') {
                onEnd?.();
                evtSource.close();
                return;
            }
            onLog(data);
        } catch {
            // ignore parse errors
        }
    };

    evtSource.onerror = () => {
        evtSource.close();
        onEnd?.();
    };

    return () => evtSource.close();
}

export async function createFrontdoorTask(payload: FrontdoorTaskRequest): Promise<FrontdoorTask> {
    return fetchJSON(`${BASE}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export async function listFrontdoorTasks(filters: FrontdoorTaskListFilters = {}): Promise<FrontdoorTask[]> {
    const params = new URLSearchParams();
    params.set('limit', String(filters.limit ?? 20));
    if (filters.taskKind) params.set('task_kind', filters.taskKind);
    if (filters.status) params.set('status', filters.status);
    if (filters.lineageRootId) params.set('lineage_root_id', filters.lineageRootId);
    return fetchJSON(`${BASE}/tasks?${params.toString()}`);
}

export async function getFrontdoorTask(taskId: string): Promise<FrontdoorTask> {
    return fetchJSON(`${BASE}/tasks/${taskId}`);
}

export async function getFrontdoorTaskResult(taskId: string): Promise<FrontdoorTask> {
    return fetchJSON(`${BASE}/tasks/${taskId}/result`);
}

export async function cancelFrontdoorTask(taskId: string): Promise<FrontdoorTaskActionResult> {
    return fetchJSON(`${BASE}/tasks/${taskId}/cancel`, {
        method: 'POST',
    });
}

export async function rerunFrontdoorTask(taskId: string): Promise<FrontdoorTask> {
    return fetchJSON(`${BASE}/tasks/${taskId}/rerun`, {
        method: 'POST',
    });
}

export function streamFrontdoorTask(taskId: string, onLog: (log: MissionLog) => void, onEnd?: () => void): () => void {
    return createTaskStream(`${BASE}/tasks/${taskId}/stream`, onLog, onEnd);
}
