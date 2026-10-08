/**
 * Commander service: Commander API client
 */

import { API_BASE_URL } from '../config';

const TIMEOUT = 60_000; // Commander tasks can take longer to complete

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

// Types

export interface MissionLog {
    timestamp: string;
    level: string;
    message: string;
    data: Record<string, unknown>;
}

export interface MissionBugSummaryItem {
    test_type: string;
    title: string;
    status: string;
    summary: string;
    execution_record_id?: string | null;
}

export interface MissionResult {
    mission_id: string;
    user_input: string;
    target_url: string;
    status: string;
    created_at: string;
    started_at: string | null;
    completed_at: string | null;
    strategy: Record<string, unknown> | null;
    test_tasks_count: number;
    test_results_count: number;
    report: Record<string, unknown> | null;
    logs: MissionLog[];
    trace_id: string | null;
    execution_group_id: string;
    execution_center_path?: string;
    bug_summary?: MissionBugSummaryItem[];
}

export interface ArchitectPlan {
    plan_id: string;
    discovery_mode: string;
    test_needs: Array<{
        title: string;
        description: string;
        source: string;
        priority: string;
        target_url: string;
        test_types: string[];
    }>;
    summary: string;
    created_at: string;
}

export interface AgentInfo {
    name: string;
    type: string;
    test_types: string[];
    active: boolean;
}

export interface TracingSummary {
    trace_id: string | null;
    total_calls: number;
    total_tokens: number;
    total_cost_usd: number;
    avg_duration_ms: number;
    max_duration_ms: number;
    error_count: number;
    by_agent: Array<{ agent: string; calls: number; tokens: number; cost_usd: number }>;
}

export interface PrototypeWorkerSwitches {
    visual: boolean;
    flow: boolean;
    ab: boolean;
    a11y: boolean;
    perf: boolean;
}

export interface PrototypeProviders {
    visual?: string;
    flow?: string;
    ab?: string;
    a11y?: string;
    perf?: string;
}

export interface PrototypeFinding {
    finding_id?: string;
    agent_id: string;
    severity: string;
    title: string;
    summary: string;
    category: string;
    provider: string;
    evidence?: Record<string, unknown>;
    execution_record_id?: string | null;
}

export interface PrototypeWorkerResult {
    agent_id: string;
    status: string;
    provider: string;
    started_at: string;
    finished_at: string;
    payload: Record<string, unknown>;
    normalized_findings: PrototypeFinding[];
    execution_record_id?: string | null;
}

export interface PrototypeReport extends Record<string, unknown> {
    summary: Record<string, unknown>;
    findings: PrototypeFinding[];
    recommendations: string[];
    worker_results: PrototypeWorkerResult[];
    quality_gate_metrics: Record<string, number>;
}

export interface PrototypeRunRequest {
    source_type: 'url' | 'file' | 'directory';
    source: string;
    compare_source?: string;
    playbook_id?: string;
    worker_switches?: Partial<PrototypeWorkerSwitches>;
    providers?: PrototypeProviders;
    wcag_level?: 'A' | 'AA' | 'AAA';
}

export interface PrototypeMissionResult extends MissionResult {
    mission_kind?: string;
    source_type?: string;
    source?: string;
    compare_source?: string;
    playbook_id?: string;
    worker_switches?: PrototypeWorkerSwitches;
    providers?: PrototypeProviders;
    wcag_level?: string;
    agent_states?: Record<string, string>;
    worker_results?: PrototypeWorkerResult[];
    report: PrototypeReport | null;
    source_context?: Record<string, unknown> | null;
}

// ── API ─────────────────────────────────────────────────────

const BASE = `${API_BASE_URL}/api/commander`;

function createMissionStream(url: string, onLog: (log: MissionLog) => void, onEnd?: () => void): () => void {
    const evtSource = new EventSource(url);

    evtSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.level === 'end') {
                onEnd?.();
                evtSource.close();
            } else {
                onLog(data);
            }
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

/** Start comprehensive testing with one sentence*/
export async function commanderRun(
    userInput: string,
    targetUrl: string = '',
    parallel: boolean = true,
): Promise<MissionResult> {
    return fetchJSON(`${BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: userInput, target_url: targetUrl, parallel }),
    });
}

/** Query task status*/
export async function commanderStatus(missionId: string): Promise<MissionResult> {
    return fetchJSON(`${BASE}/status/${missionId}`);
}

/** Cancel a task*/
export async function commanderCancel(missionId: string): Promise<{ mission_id: string; cancelled: boolean }> {
    return fetchJSON(`${BASE}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mission_id: missionId }),
    });
}

/** Get all tasks*/
export async function commanderMissions(limit = 20): Promise<MissionResult[]> {
    return fetchJSON(`${BASE}/missions?limit=${limit}`);
}

/** Delete a single task*/
export async function commanderDeleteMission(missionId: string): Promise<{ deleted: boolean }> {
    return fetchJSON(`${BASE}/missions/${missionId}`, { method: 'DELETE' });
}

/** Clear all tasks*/
export async function commanderClearMissions(): Promise<{ cleared: boolean; count: number }> {
    return fetchJSON(`${BASE}/missions`, { method: 'DELETE' });
}

/** Test architect analysis*/
export async function commanderArchitect(
    inputText: string,
    targetUrl: string = '',
    mode?: string,
    diffText: string = '',
): Promise<ArchitectPlan> {
    return fetchJSON(`${BASE}/architect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input_text: inputText, target_url: targetUrl, mode, diff_text: diffText }),
    });
}

/** Get the agent list*/
export async function commanderAgents(): Promise<{ agents: AgentInfo[]; statistics: Record<string, unknown> }> {
    return fetchJSON(`${BASE}/agents`);
}

/** Get a trace*/
export async function commanderTracing(traceId?: string): Promise<TracingSummary> {
    const url = traceId ? `${BASE}/tracing?trace_id=${traceId}` : `${BASE}/tracing`;
    return fetchJSON(url);
}

/** Stream logs over SSE*/
export function commanderStream(missionId: string, onLog: (log: MissionLog) => void, onEnd?: () => void): () => void {
    return createMissionStream(`${BASE}/stream/${missionId}`, onLog, onEnd);
}

export async function commanderPrototypeRun(payload: PrototypeRunRequest): Promise<PrototypeMissionResult> {
    return fetchJSON(`${BASE}/prototype/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export async function commanderPrototypeStatus(missionId: string): Promise<PrototypeMissionResult> {
    return fetchJSON(`${BASE}/prototype/status/${missionId}`);
}

export async function commanderPrototypeMissions(limit = 20): Promise<PrototypeMissionResult[]> {
    return fetchJSON(`${BASE}/prototype/missions?limit=${limit}`);
}

export function commanderPrototypeStream(
    missionId: string,
    onLog: (log: MissionLog) => void,
    onEnd?: () => void,
): () => void {
    return createMissionStream(`${BASE}/prototype/stream/${missionId}`, onLog, onEnd);
}

// Extended agent APIs

export interface AgentHealth {
    name: string;
    type: string;
    active: boolean;
    profile_id: string;
    last_heartbeat_ago: number;
    healthy: boolean;
}

export interface AgentProfile {
    agent_id: string;
    name: string;
    role: string;
    supported_types: string[];
    report_to: string | null;
    members: string[];
}

/** 🐝 Start swarm mode*/
export async function commanderSwarm(
    userInput: string,
    targetUrl: string = '',
    mode?: string,
    diffText: string = '',
): Promise<{ message: string; mode: string; user_input: string }> {
    return fetchJSON(`${BASE}/swarm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: userInput, target_url: targetUrl, mode, diff_text: diffText }),
    });
}

/** 🏥 Agent health*/
export async function commanderHealth(): Promise<{ agents: AgentHealth[]; statistics: Record<string, unknown> }> {
    return fetchJSON(`${BASE}/health`);
}

/** 📋 Agent profile list*/
export async function commanderProfiles(): Promise<{ profiles: AgentProfile[]; total: number }> {
    return fetchJSON(`${BASE}/profiles`);
}

