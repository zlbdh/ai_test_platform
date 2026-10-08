/**
 * CI/CD integration service for backend /api/ci/* endpoints
 */
import { API_ENDPOINTS } from '../config';

// ── Types ──
export interface CICDConfig {
    enabled: boolean;
    webhook_secret_masked: string;
    webhook_url: string;
    default_task_template: string;
    notify_on_complete: boolean;
    created_at: string;
}

export interface TriggerRecord {
    id: string;
    triggered_at: string;
    source: string;
    ref: string;
    commit: string;
    task_id: string;
    status: string;
    duration_ms: number;
    test_count: number;
    passed_count: number;
    failed_count: number;
    report_path: string;
}

// ── API Calls ──
export const getCICDConfig = async (): Promise<CICDConfig> => {
    const res = await fetch(API_ENDPOINTS.ci.config);
    const data = await res.json();
    return data.config;
};

export const updateCICDConfig = async (config: Partial<CICDConfig>): Promise<CICDConfig> => {
    const res = await fetch(API_ENDPOINTS.ci.config, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });
    const data = await res.json();
    return data.config;
};

export const getCICDSecret = async (): Promise<string> => {
    const res = await fetch(API_ENDPOINTS.ci.secret);
    const data = await res.json();
    return data.secret;
};

export const getCICDHistory = async (): Promise<TriggerRecord[]> => {
    const res = await fetch(API_ENDPOINTS.ci.history);
    const data = await res.json();
    return data.history || [];
};

export const getCICDTriggerDetail = async (triggerId: string): Promise<TriggerRecord> => {
    const res = await fetch(API_ENDPOINTS.ci.trigger(triggerId));
    const data = await res.json();
    return data.trigger;
};

export const triggerWebhook = async (source: string, ref: string = '', commit: string = ''): Promise<{ trigger_id: string }> => {
    const res = await fetch(API_ENDPOINTS.ci.webhook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, ref, commit }),
    });
    const data = await res.json();
    return data;
};

export const getJunitReportUrl = (triggerId: string): string => API_ENDPOINTS.ci.reportJunit(triggerId);
export const getHtmlReportUrl = (triggerId: string): string => API_ENDPOINTS.ci.reportHtml(triggerId);
