import { describe, expect, it, beforeEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const mockFetch = vi.fn();
global.fetch = mockFetch;

import ScenarioPage from '../pages/ScenarioPage';

describe('ScenarioPage', () => {
    beforeEach(() => {
        mockFetch.mockReset();
    });

    it('should import sample_platform playbook scenarios', async () => {
        mockFetch.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url.endsWith('/api/scenarios') && (!init || !init.method || init.method === 'GET')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        scenarios: [
                            {
                                id: 'scn-1',
                                name: '[业务运营角色]-登录认证-Wave0基线-测试环境',
                                description: 'desc',
                                stepCount: 3,
                                status: 'draft',
                                tags: ['示例项目', 'wave0'],
                                updated_at: '2026-03-24T12:00:00',
                            },
                        ],
                    }),
                } as unknown as Response;
            }

            if (url.endsWith('/api/scenarios/import-playbook/sample-first-regression')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'success',
                        playbook_id: 'sample-first-regression',
                        playbook_name: '示例项目企业平台端首轮真实回归',
                        playbook_title: '示例项目企业平台端首轮真实回归',
                        project_name: '示例项目企业平台端',
                        imported_count: 2,
                        scenarios: [
                            {
                                id: 'scn-1',
                                name: '[业务运营角色]-登录认证-Wave0基线-测试环境',
                                stepCount: 3,
                                tags: ['示例项目', 'wave0'],
                            },
                            {
                                id: 'scn-2',
                                name: '[业务运营角色]-工单调度-Wave1主流程-测试环境',
                                stepCount: 3,
                                tags: ['示例项目', 'wave1'],
                            },
                        ],
                    }),
                } as unknown as Response;
            }

            throw new Error(`Unhandled fetch: ${url}`);
        });

        render(<ScenarioPage />);

        await waitFor(() => expect(mockFetch).toHaveBeenCalled());
        fireEvent.click(screen.getByRole('button', { name: '导入示例项目场景包' }));

        await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/scenarios/import-playbook/sample-first-regression'),
            expect.objectContaining({ method: 'POST' }),
        ));

        expect(await screen.findByText('示例项目企业平台端首轮真实回归')).toBeInTheDocument();
        expect(screen.getByText('已导入 2 条场景，覆盖 Wave 0 到 Wave 4，可直接逐条执行或二次编辑。')).toBeInTheDocument();
        expect(screen.getByText('[业务运营角色]-工单调度-Wave1主流程-测试环境')).toBeInTheDocument();
    });

    it('should import sample_platform platform prototype scenarios', async () => {
        mockFetch.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url.endsWith('/api/scenarios') && (!init || !init.method || init.method === 'GET')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({ scenarios: [] }),
                } as unknown as Response;
            }

            if (url.endsWith('/api/scenarios/import-playbook/sample-platform-prototype')) {
                return {
                    ok: true,
                    json: vi.fn().mockResolvedValue({
                        status: 'success',
                        playbook_id: 'sample-platform-prototype',
                        playbook_name: '示例项目大平台原型测试包',
                        playbook_title: '示例项目大平台原型测试包',
                        project_name: '示例项目大平台',
                        imported_count: 3,
                        scenarios: [
                            {
                                id: 'pt-1',
                                name: '[平台管理员角色]-企业管理-页面结构检查-原型阶段',
                                stepCount: 1,
                                tags: ['示例项目大平台', '原型测试', '企业管理', 'structure'],
                            },
                        ],
                    }),
                } as unknown as Response;
            }

            throw new Error(`Unhandled fetch: ${url}`);
        });

        render(<ScenarioPage />);

        await waitFor(() => expect(mockFetch).toHaveBeenCalled());
        fireEvent.click(screen.getByRole('button', { name: '导入大平台原型场景包' }));

        await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/scenarios/import-playbook/sample-platform-prototype'),
            expect.objectContaining({ method: 'POST' }),
        ));

        expect(await screen.findByText('示例项目大平台原型测试包')).toBeInTheDocument();
        expect(screen.getByText('已导入 3 条原型场景，覆盖登录、15 个业务模块以及跨模块主链路，可继续补充真实环境后执行。')).toBeInTheDocument();
        expect(screen.getByText('[平台管理员角色]-企业管理-页面结构检查-原型阶段')).toBeInTheDocument();
    });
});
