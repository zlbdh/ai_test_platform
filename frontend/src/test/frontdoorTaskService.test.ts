import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch;

const eventSources: Array<{
    url: string;
    instance: {
        onmessage: ((event: { data: string }) => void) | null;
        onerror: (() => void) | null;
        close: ReturnType<typeof vi.fn>;
    };
}> = [];

class MockEventSource {
    url: string;
    onmessage: ((event: { data: string }) => void) | null = null;
    onerror: (() => void) | null = null;
    close = vi.fn();

    constructor(url: string) {
        this.url = url;
        eventSources.push({ url, instance: this });
    }
}

vi.stubGlobal('EventSource', MockEventSource as unknown as typeof EventSource);

import {
    cancelFrontdoorTask,
    createFrontdoorTask,
    getFrontdoorTask,
    getFrontdoorTaskResult,
    listFrontdoorTasks,
    rerunFrontdoorTask,
    streamFrontdoorTask,
} from '../services/frontdoorTaskService';

function mockResponse(body: unknown, ok = true): Response {
    return {
        ok,
        status: ok ? 200 : 500,
        statusText: ok ? 'OK' : 'Error',
        json: vi.fn().mockResolvedValue(body),
        text: vi.fn().mockResolvedValue(JSON.stringify(body)),
        headers: new Headers(),
    } as unknown as Response;
}

describe('frontdoorTaskService', () => {
    beforeEach(() => {
        mockFetch.mockReset();
        eventSources.splice(0, eventSources.length);
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('createFrontdoorTask should POST to unified tasks endpoint', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            task_id: 'task001',
            task_kind: 'general',
            status: 'pending',
        }));

        const result = await createFrontdoorTask({
            task_kind: 'general',
            user_goal: "Check the login workflow",
            source_context: { target_url: 'https://demo.example.com' },
            strategy: { parallel: true },
        });

        expect(result.task_id).toBe('task001');
        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/commander/tasks');
        expect(options.method).toBe('POST');
    });

    it('list/get/result should call matching unified task endpoints with filters', async () => {
        mockFetch
            .mockResolvedValueOnce(mockResponse([{ task_id: 'task001', task_kind: 'prototype', status: 'completed' }]))
            .mockResolvedValueOnce(mockResponse({ task_id: 'task001', task_kind: 'prototype', status: 'completed' }))
            .mockResolvedValueOnce(mockResponse({ task_id: 'task001', status: 'completed', findings: [] }));

        const list = await listFrontdoorTasks({ limit: 5, taskKind: 'prototype', status: 'completed', lineageRootId: 'chain_1' });
        const detail = await getFrontdoorTask('task001');
        const result = await getFrontdoorTaskResult('task001');

        expect(list[0].task_id).toBe('task001');
        expect(detail.task_kind).toBe('prototype');
        expect(result.task_id).toBe('task001');
        expect(mockFetch.mock.calls[0][0]).toContain('/api/commander/tasks?limit=5&task_kind=prototype&status=completed&lineage_root_id=chain_1');
        expect(mockFetch.mock.calls[1][0]).toContain('/api/commander/tasks/task001');
        expect(mockFetch.mock.calls[2][0]).toContain('/api/commander/tasks/task001/result');
    });

    it('cancel and rerun should hit action endpoints', async () => {
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                task_id: 'task001',
                cancelled: true,
                status: 'cancelled',
                message: "Task stopped.",
            }))
            .mockResolvedValueOnce(mockResponse({
                task_id: 'task002',
                task_kind: 'general',
                status: 'pending',
            }));

        const cancelResult = await cancelFrontdoorTask('task001');
        const rerunResult = await rerunFrontdoorTask('task001');

        expect(cancelResult.cancelled).toBe(true);
        expect(rerunResult.task_id).toBe('task002');
        expect(mockFetch.mock.calls[0][0]).toContain('/api/commander/tasks/task001/cancel');
        expect(mockFetch.mock.calls[0][1].method).toBe('POST');
        expect(mockFetch.mock.calls[1][0]).toContain('/api/commander/tasks/task001/rerun');
        expect(mockFetch.mock.calls[1][1].method).toBe('POST');
    });

    it('streamFrontdoorTask should forward logs and stop on end event', () => {
        const onLog = vi.fn();
        const onEnd = vi.fn();

        const dispose = streamFrontdoorTask('task002', onLog, onEnd);

        expect(eventSources[0].url).toContain('/api/commander/tasks/task002/stream');
        eventSources[0].instance.onmessage?.({
            data: JSON.stringify({
                timestamp: '2026-04-02T15:00:00',
                level: 'info',
                message: "Start execution",
                data: {},
            }),
        });
        eventSources[0].instance.onmessage?.({
            data: JSON.stringify({
                level: 'end',
                message: "Task ended",
            }),
        });

        expect(onLog).toHaveBeenCalledTimes(1);
        expect(onEnd).toHaveBeenCalledTimes(1);
        expect(eventSources[0].instance.close).toHaveBeenCalledTimes(1);

        dispose();
        expect(eventSources[0].instance.close).toHaveBeenCalledTimes(2);
    });
});
