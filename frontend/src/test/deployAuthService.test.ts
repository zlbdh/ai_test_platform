import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch;

function mockResponse(body: unknown, ok = true, status = 200): Response {
    return {
        ok,
        status,
        statusText: ok ? 'OK' : 'ERROR',
        json: vi.fn().mockResolvedValue(body),
        text: vi.fn().mockResolvedValue(JSON.stringify(body)),
        headers: new Headers(),
        redirected: false,
        type: 'basic',
        url: '',
        clone: vi.fn(),
        body: null,
        bodyUsed: false,
        arrayBuffer: vi.fn(),
        blob: vi.fn(),
        formData: vi.fn(),
        bytes: vi.fn(),
    } as unknown as Response;
}

import {
    attachDeployToken,
    clearDeployAuthSession,
    getDeployAuthHeaders,
    getStoredDeployAuthToken,
    hasDeployPermission,
    loginDeployControl,
    logoutDeployControl,
} from '../services/deployAuthService';

describe('deployAuthService', () => {
    beforeEach(() => {
        mockFetch.mockReset();
        localStorage.clear();
    });

    it('登录后会保存 token 并拉取当前用户权限', async () => {
        mockFetch
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                token: 'demo-token',
                expires_at: '2026-03-24T12:00:00',
            }))
            .mockResolvedValueOnce(mockResponse({
                status: 'success',
                user: {
                    user_id: 'user_1',
                    username: 'alice',
                    email: 'alice@test.com',
                    role: 'developer',
                    project_ids: ['proj1'],
                },
            }));

        const profile = await loginDeployControl('alice', 'secret');

        expect(profile.username).toBe('alice');
        expect(profile.permissions).toEqual(['deploy_view', 'deploy_request']);
        expect(getStoredDeployAuthToken()).toBe('demo-token');
        expect(hasDeployPermission(profile, 'deploy_request')).toBe(true);
        expect(mockFetch).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining('/api/auth/login'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ username: 'alice', password: 'secret' }),
            }),
        );
        expect(mockFetch).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining('/api/auth/me?token=demo-token'),
        );
    });

    it('附加 token 时会校验并推导管理员权限', async () => {
        mockFetch.mockResolvedValueOnce(mockResponse({
            status: 'success',
            user: {
                user_id: 'user_admin',
                username: 'admin',
                email: 'admin@test.com',
                role: 'admin',
                project_ids: [],
            },
        }));

        const profile = await attachDeployToken('manual-token');

        expect(profile.role).toBe('admin');
        expect(profile.permissions).toContain('deploy_approve');
        expect(getStoredDeployAuthToken()).toBe('manual-token');
    });

    it('请求头会自动注入 Bearer token', () => {
        localStorage.setItem('deploy_control_auth', JSON.stringify({ token: 'demo-token' }));

        const headers = getDeployAuthHeaders({ 'Content-Type': 'application/json' });

        expect(headers.get('Authorization')).toBe('Bearer demo-token');
        expect(headers.get('Content-Type')).toBe('application/json');
    });

    it('登出会提交 token 并清空本地会话', async () => {
        localStorage.setItem('deploy_control_auth', JSON.stringify({ token: 'demo-token' }));
        mockFetch.mockResolvedValueOnce(mockResponse({ status: 'success' }));

        await logoutDeployControl();

        expect(getStoredDeployAuthToken()).toBe('');
        expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/auth/logout'),
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ token: 'demo-token' }),
            }),
        );
    });

    it('清空会话后不再保留 token', () => {
        localStorage.setItem('deploy_control_auth', JSON.stringify({ token: 'demo-token' }));
        clearDeployAuthSession();
        expect(getStoredDeployAuthToken()).toBe('');
    });
});
