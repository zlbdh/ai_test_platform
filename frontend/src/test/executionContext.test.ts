import { beforeEach, describe, expect, it } from 'vitest';
import { useExecutionStore } from '../stores';
import {
    beginExecutionCampaign,
    buildExecutionContextPayload,
    ensureExecutionContextPayload,
    summarizeExecutionTitle,
} from '../utils/executionContext';

describe('executionContext', () => {
    beforeEach(() => {
        localStorage.clear();
        useExecutionStore.setState({
            sessions: [{ id: 'sess_test', name: '会话 1', mode: 'chromium' }],
            activeSessionId: 'sess_test',
            sessionGroups: {},
        });
    });

    it('should create and expose the active execution batch payload', () => {
        const batch = beginExecutionCampaign('对服务商品中心进行全链路测试', { sessionId: 'sess_test' });
        const payload = buildExecutionContextPayload('sess_test');

        expect(batch.title).toBe('对服务商品中心进行全链路测试');
        expect(payload.session_id).toBe('sess_test');
        expect(payload.execution_group_id).toBe(batch.id);
        expect(payload.group_title).toBe(batch.title);
    });

    it('should keep only the first line and trim long titles', () => {
        const title = summarizeExecutionTitle(`第一行标题\n第二行说明${'x'.repeat(80)}`);

        expect(title.startsWith('第一行标题')).toBe(true);
        expect(title.includes('\n')).toBe(false);
        expect(title.length).toBeLessThanOrEqual(51);
    });

    it('should auto-create and reuse a specialized execution batch when missing', () => {
        const firstPayload = ensureExecutionContextPayload('数据库专项测试', {
            sessionId: 'sess_test',
            targetUrl: 'http://127.0.0.1:8020/api/health',
        });
        const secondPayload = ensureExecutionContextPayload('安全专项测试', {
            sessionId: 'sess_test',
            targetUrl: 'http://127.0.0.1:8020/api/health',
        });

        expect(firstPayload.session_id).toBe('sess_test');
        expect(firstPayload.execution_group_id).toBeTruthy();
        expect(firstPayload.group_title).toContain('专项测试');
        expect(secondPayload.execution_group_id).toBe(firstPayload.execution_group_id);
        expect(secondPayload.group_title).toBe(firstPayload.group_title);
    });
});
