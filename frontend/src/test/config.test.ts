/**
 * config.ts 单元测试 (P2-2)
 * 
 * 验证 API 端点配置的完整性和正确性
 */
import { describe, it, expect } from 'vitest';
import { API_ENDPOINTS, WS_ENDPOINTS, DEFAULT_CONFIG, resolveImageUrl, API_BASE_URL } from '../config';

describe('config.ts', () => {
    describe('API_BASE_URL', () => {
        it('should be a valid URL string', () => {
            expect(API_BASE_URL).toBeDefined();
            expect(typeof API_BASE_URL).toBe('string');
            expect(API_BASE_URL).toMatch(/^https?:\/\//);
        });
    });

    describe('API_ENDPOINTS', () => {
        it('should have core endpoints', () => {
            expect(typeof API_ENDPOINTS.status).toBe('function');
            expect(API_ENDPOINTS.status('session-1')).toContain('/api/status');
            expect(API_ENDPOINTS.start).toContain('/api/start');
            expect(typeof API_ENDPOINTS.stop).toBe('function');
            expect(API_ENDPOINTS.stop('session-1')).toContain('/api/stop');
            expect(typeof API_ENDPOINTS.stream).toBe('function');
            expect(API_ENDPOINTS.stream('session-1')).toContain('/api/stream');
        });

        it('should have config endpoints', () => {
            expect(API_ENDPOINTS.config.ai).toContain('/api/config/ai');
        });

        it('should have control endpoints', () => {
            expect(typeof API_ENDPOINTS.control.pause).toBe('function');
            expect(API_ENDPOINTS.control.pause('session-1')).toContain('/api/control/pause');
            expect(typeof API_ENDPOINTS.control.resume).toBe('function');
            expect(API_ENDPOINTS.control.resume('session-1')).toContain('/api/control/resume');
            expect(API_ENDPOINTS.control.suspend).toContain('/api/control/suspend');
            expect(typeof API_ENDPOINTS.control.stop).toBe('function');
            expect(API_ENDPOINTS.control.stop('session-1')).toContain('/api/control/stop');
        });

        it('should have history endpoints with dynamic delete', () => {
            expect(API_ENDPOINTS.history.list).toContain('/api/history');
            expect(API_ENDPOINTS.history.clear).toContain('/api/history');
            expect(typeof API_ENDPOINTS.history.delete).toBe('function');
            expect(API_ENDPOINTS.history.delete('task-123')).toContain('/api/history/task-123');
        });

        it('should have gallery endpoint as function', () => {
            expect(typeof API_ENDPOINTS.gallery).toBe('function');
            expect(API_ENDPOINTS.gallery('task-456')).toContain('/api/gallery/task-456');
        });

        it('should have knowledge endpoints', () => {
            expect(API_ENDPOINTS.knowledge.status).toContain('/api/knowledge/status');
            expect(API_ENDPOINTS.knowledge.add).toContain('/api/knowledge/add');
            expect(API_ENDPOINTS.knowledge.query).toContain('/api/knowledge/query');
            expect(API_ENDPOINTS.knowledge.list).toContain('/api/knowledge/list');
            expect(API_ENDPOINTS.knowledge.upload).toContain('/api/knowledge/upload');
            expect(API_ENDPOINTS.knowledge.content('doc-1')).toContain('/api/knowledge/doc-1/content');
            expect(API_ENDPOINTS.knowledge.delete('doc-1')).toContain('/api/knowledge/doc-1');
            expect(API_ENDPOINTS.knowledge.clear).toContain('/api/knowledge/clear');
        });

        it('should have performance endpoints', () => {
            expect(API_ENDPOINTS.performance.run).toContain('/api/performance/run');
            expect(API_ENDPOINTS.performance.status).toContain('/api/performance/status');
            expect(API_ENDPOINTS.performance.stop).toContain('/api/performance/stop');
            expect(API_ENDPOINTS.performance.delete('perf-1')).toContain('/api/performance/history/perf-1');
        });

        it('should have security endpoints', () => {
            expect(API_ENDPOINTS.security.scan).toContain('/api/security/scan');
            expect(API_ENDPOINTS.security.report('scan-1')).toContain('/api/security/report/scan-1');
        });

        it('should have workbench endpoints with nested functions', () => {
            expect(API_ENDPOINTS.workbench.collections).toContain('/api/workbench/collections');
            expect(API_ENDPOINTS.workbench.collection('c1')).toContain('/api/workbench/collections/c1');
            expect(API_ENDPOINTS.workbench.collectionRequests('c1')).toContain('/api/workbench/collections/c1/requests');
            expect(API_ENDPOINTS.workbench.request('c1', 'r1')).toContain('/api/workbench/collections/c1/requests/r1');
        });

        it('should have CI/CD endpoints', () => {
            expect(API_ENDPOINTS.ci.config).toContain('/api/ci/config');
            expect(API_ENDPOINTS.ci.trigger('run-1')).toContain('/api/ci/trigger/run-1');
            expect(API_ENDPOINTS.ci.reportJunit('run-1')).toContain('/junit.xml');
        });

        it('should have database endpoints', () => {
            expect(API_ENDPOINTS.db.connections).toContain('/api/db/connections');
            expect(API_ENDPOINTS.db.connection('db-1')).toContain('/api/db/connections/db-1');
            expect(API_ENDPOINTS.db.test('db-1')).toContain('/api/db/connections/db-1/test');
            expect(API_ENDPOINTS.db.query('db-1')).toContain('/api/db/connections/db-1/query');
        });

        it('should have all endpoint categories', () => {
            const categories = [
                'config', 'control', 'history', 'knowledge', 'data', 'batch',
                'performance', 'security', 'workbench', 'graphql', 'wsTest',
                'grpc', 'report', 'ci', 'db', 'accessibility', 'i18n',
                'compliance', 'requirement', 'chaos', 'mobile', 'dataFactory', 'system',
            ];
            for (const cat of categories) {
                expect(API_ENDPOINTS).toHaveProperty(cat);
            }
        });

        it('should expose commander prototype endpoints', () => {
            expect(API_ENDPOINTS.commander.prototype.run).toContain('/api/commander/prototype/run');
            expect(API_ENDPOINTS.commander.prototype.status('proto-1')).toContain('/api/commander/prototype/status/proto-1');
            expect(API_ENDPOINTS.commander.prototype.missions).toContain('/api/commander/prototype/missions');
            expect(API_ENDPOINTS.commander.prototype.stream('proto-1')).toContain('/api/commander/prototype/stream/proto-1');
        });

        it('should expose requirement analyze endpoint', () => {
            expect(API_ENDPOINTS.requirement.analyze).toContain('/api/requirement/analyze');
            expect(API_ENDPOINTS.requirement.parse).toContain('/api/requirement/parse');
            expect(API_ENDPOINTS.requirement.parseUpload).toContain('/api/requirement/parse-upload');
            expect(API_ENDPOINTS.requirement.generateTests).toContain('/api/requirement/generate-tests');
        });

        it('should prefix all static endpoints with API_BASE_URL', () => {
            // Sample check on various static endpoints
            const staticEndpoints = [
                API_ENDPOINTS.status('session-1'),
                API_ENDPOINTS.start,
                API_ENDPOINTS.config.ai,
                API_ENDPOINTS.control.pause('session-1'),
                API_ENDPOINTS.history.list,
                API_ENDPOINTS.knowledge.status,
                API_ENDPOINTS.batch.run,
            ];
            for (const ep of staticEndpoints) {
                expect(ep).toMatch(new RegExp(`^${API_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
            }
        });
    });

    describe('WS_ENDPOINTS', () => {
        it('should have sandbox WebSocket endpoint', () => {
            expect(WS_ENDPOINTS.sandbox).toContain('/ws/sandbox');
            expect(WS_ENDPOINTS.sandbox).toMatch(/^wss?:\/\//);
        });
    });

    describe('resolveImageUrl', () => {
        it('should return absolute HTTP URLs unchanged', () => {
            expect(resolveImageUrl('https://example.com/img.png')).toBe('https://example.com/img.png');
            expect(resolveImageUrl('http://example.com/img.png')).toBe('http://example.com/img.png');
        });

        it('should return data URLs unchanged', () => {
            expect(resolveImageUrl('data:image/png;base64,abc')).toBe('data:image/png;base64,abc');
        });

        it('should prefix relative paths with API_BASE_URL', () => {
            expect(resolveImageUrl('/screenshots/1.png')).toBe(`${API_BASE_URL}/screenshots/1.png`);
        });
    });

    describe('DEFAULT_CONFIG', () => {
        it('should have default URL values', () => {
            expect(DEFAULT_CONFIG.performanceTestUrl).toBeDefined();
            expect(DEFAULT_CONFIG.securityScanUrl).toBeDefined();
        });
    });
});
