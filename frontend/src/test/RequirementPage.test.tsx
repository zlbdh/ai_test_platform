import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const { mockAnalyze, mockAnalyzeUpload, mockGenerate, mockFetchPlaybook } = vi.hoisted(() => ({
    mockAnalyze: vi.fn(),
    mockAnalyzeUpload: vi.fn(),
    mockGenerate: vi.fn(),
    mockFetchPlaybook: vi.fn(),
}));

vi.mock('../services/requirementService', () => ({
    analyzeRequirementDocument: mockAnalyze,
    parseRequirement: mockAnalyze,
    parseRequirementUpload: mockAnalyzeUpload,
    generateTestsFromRequirement: mockGenerate,
    fetchRequirementPlaybook: mockFetchPlaybook,
}));

import RequirementPage from '../pages/RequirementPage';

describe('RequirementPage', () => {
    beforeEach(() => {
        mockAnalyze.mockReset();
        mockAnalyzeUpload.mockReset();
        mockGenerate.mockReset();
        mockFetchPlaybook.mockReset();
        const parsedResult = {
            title: '登录需求',
            summary: 'summary',
            confidence: 0.92,
            rules_count: 1,
            test_cases_count: 1,
            rules: [],
            test_cases: [],
            analysis: {
                document_type: 'requirement_prd',
                document_label: '需求文档',
                quality_score: 0.88,
                completeness_score: 0.85,
                testability_score: 0.91,
                recommended_test_types: ['ui_e2e', 'business_flow'],
                issues: [
                    {
                        issue_id: 'ISS-0001',
                        severity: 'warning',
                        category: 'testability',
                        message: '缺少异常流程说明',
                        suggestion: '补充失败场景',
                    },
                ],
                extracted: {
                    actors: ['用户'],
                    flows: ['用户登录'],
                    business_rules: ['支持验证码登录'],
                    data_constraints: ['验证码有效期 5 分钟'],
                    api_endpoints: [],
                    api_parameters: ['POST /api/login -> body:password (required)'],
                    response_statuses: ['POST /api/login -> 200'],
                    error_codes: [],
                    database_objects: [],
                },
                next_actions: ['建立需求追溯'],
            },
            bundle_analysis: {
                coverage_score: 0.84,
                consistency_score: 0.73,
                involved_document_types: ['requirement_prd', 'development_design'],
                aligned_signals: {
                    data_constraints: 1,
                    api_endpoints: 0,
                },
                uncovered_signals: {
                    data_constraints: 0,
                    api_endpoints: 1,
                },
                findings: [
                    {
                        finding_id: 'BND-0001',
                        severity: 'warning',
                        category: 'coverage',
                        message: '主文档包含数据约束，但参考文档未体现对应字段约束。',
                        suggestion: '补充数据库设计或接口字段约束。',
                    },
                ],
                recommended_actions: ['建立联合追溯'],
            },
            references_analysis: [
                {
                    title: '登录接口 OpenAPI',
                    document_type: 'api_spec',
                    document_label: '接口文档',
                    analysis: {
                        document_type: 'api_spec',
                        document_label: '接口文档',
                        quality_score: 0.83,
                        completeness_score: 0.8,
                        testability_score: 0.85,
                        recommended_test_types: ['api_rest', 'contract'],
                        issues: [],
                        extracted: {
                            actors: [],
                            flows: [],
                            business_rules: [],
                            data_constraints: [],
                            api_endpoints: ['POST /api/login'],
                            api_parameters: ['POST /api/login -> body:password (required)'],
                            response_statuses: ['POST /api/login -> 200'],
                            error_codes: [],
                            database_objects: [],
                        },
                        next_actions: ['补充异常响应模型'],
                    },
                },
            ],
        };
        mockAnalyze.mockResolvedValue(parsedResult);
        mockAnalyzeUpload.mockImplementation(async (file: File) => ({
            ...parsedResult,
            extracted_text: '上传后的文档正文',
            uploaded_filename: file.name,
        }));
        mockGenerate.mockResolvedValue({
            total_tests: 3,
            confidence: 0.81,
            tests: [
                {
                    id: 'TC-001',
                    name: '登录成功',
                    type: 'ui_e2e',
                    priority: 'high',
                    instruction: '步骤...',
                    tags: ['login'],
                    document_title: '登录需求',
                    document_label: '需求文档',
                    document_type: 'requirement_prd',
                    document_role: 'primary',
                },
                {
                    id: 'API-HAPPY-001',
                    name: '接口主流程: POST /api/login',
                    type: 'api_rest',
                    priority: 'high',
                    instruction: '步骤...',
                    tags: ['api'],
                    document_title: '开发 / 接口 / 数据库参考文档',
                    document_label: '接口文档',
                    document_type: 'api_spec',
                    document_role: 'reference',
                },
                {
                    id: 'BUNDLE-001',
                    name: '跨文档consistency验证 1',
                    type: 'contract',
                    priority: 'medium',
                    instruction: '步骤...',
                    tags: ['bundle'],
                    document_title: '多文档交叉检测',
                    document_label: '交叉检测',
                    document_type: 'document_bundle',
                    document_role: 'bundle',
                },
            ],
            generation_summary: {
                title: '登录需求',
                document_type: 'requirement_prd',
                strategy_label: '多文档联合设计',
                rationale: '优先覆盖业务主流程，同时吸收参考文档和交叉检测结果。',
                generated_count: 3,
                counts_by_type: { ui_e2e: 1, api_rest: 1, contract: 1 },
                counts_by_origin: { primary: 1, reference: 1, bundle: 1 },
                focus_areas: ['ui_e2e', 'api_rest', 'contract'],
                traceability: {
                    business_rules: 1,
                    flows: 1,
                    api_endpoints: 1,
                    api_parameters: 1,
                    response_statuses: 1,
                    database_objects: 0,
                    data_constraints: 1,
                },
                document_sources: [
                    {
                        title: '登录需求',
                        document_type: 'requirement_prd',
                        document_label: '需求文档',
                        document_role: 'primary',
                        generated_count: 1,
                    },
                    {
                        title: '开发 / 接口 / 数据库参考文档',
                        document_type: 'api_spec',
                        document_label: '接口文档',
                        document_role: 'reference',
                        generated_count: 1,
                    },
                    {
                        title: '多文档交叉检测',
                        document_type: 'document_bundle',
                        document_label: '交叉检测',
                        document_role: 'bundle',
                        generated_count: 1,
                    },
                ],
                bundle_findings_count: 1,
            },
            analysis: undefined,
        });
        mockFetchPlaybook.mockImplementation(async (playbookId: string) => {
            if (playbookId === 'sample-platform-prototype') {
                return {
                    playbook_id: 'sample-platform-prototype',
                    project_name: '示例项目大平台',
                    title: '示例项目大平台原型测试包',
                    content: '# 示例项目大平台原型测试包',
                    references: [
                        {
                            title: '示例项目大平台-企业管理',
                            content: '企业管理正文',
                            relative_path: 'docx/XQ/Second/业务需求/示例项目大平台/01_企业管理_需求.md',
                        },
                    ],
                    document_sources: [
                        {
                            title: '示例项目大平台-企业管理',
                            role: 'reference',
                            relative_path: 'docx/XQ/Second/业务需求/示例项目大平台/01_企业管理_需求.md',
                            local_path: 'D:/workspace/ai_test_platform/data/deploy/sample_platform/docx/XQ/Second/业务需求/示例项目大平台/01_企业管理_需求.md',
                            exists: true,
                        },
                    ],
                    prototype_assets: [
                        {
                            asset_id: 'sample-platform-prototype-docs',
                            title: '示例项目大平台 HTML 原型目录（部署文档仓）',
                            role: 'prototype',
                            relative_path: 'docx/XQ/Second/html/示例项目大平台htmlV1.0',
                            local_path: 'D:/workspace/ai_test_platform/data/deploy/sample_platform/docx/XQ/Second/html/示例项目大平台htmlV1.0',
                            exists: false,
                            file_count: 0,
                        },
                    ],
                    asset_checks: [
                        {
                            check_id: 'platform_docs_ready',
                            label: '需求文档同步',
                            status: 'success',
                            message: '已同步 18/18 份大平台需求文档。',
                            value: '18/18',
                        },
                        {
                            check_id: 'platform_page_mapping_rate',
                            label: '页面映射率',
                            status: 'warning',
                            message: '已映射 0/77 个页面。',
                            value: 0,
                        },
                    ],
                    page_mappings: [
                        {
                            mapping_id: 'mp-1',
                            module_name: '登录与认证',
                            page_name: '平台管理员登录',
                            route: '/ptLogin',
                            page_type: '登录页',
                            description: '大平台管理员登录入口',
                            requirement_source: {
                                title: '示例项目大平台-登录与认证',
                                role: 'primary',
                                relative_path: 'docx/XQ/Second/示例项目大平台需求/01-登录与认证模块.md',
                                local_path: 'D:/workspace/ai_test_platform/data/deploy/sample_platform/docx/XQ/Second/示例项目大平台需求/01-登录与认证模块.md',
                                exists: true,
                            },
                            prototype_source: {
                                title: '',
                                relative_path: '',
                                local_path: '',
                                exists: false,
                            },
                            mapping_status: 'pending_prototype',
                            recommended_test_types: ['ui_e2e', 'data_validation'],
                            key_assertions: ['登录表单完整'],
                            baseline_candidate: true,
                            critical: true,
                        },
                    ],
                    mapping_summary: {
                        module_count: 16,
                        total_pages: 77,
                        mapped_pages: 0,
                        mapping_rate: 0,
                        critical_pages: 32,
                        critical_missing_pages: 32,
                        baseline_candidates: 48,
                    },
                    target_url: '待同步原型目录：docx/XQ/Second/html/示例项目大平台htmlV1.0',
                    repositories: [],
                    waves: [
                        { id: 'wave0', name: 'Wave 0 登录与入口基线', focus: ['登录与认证'] },
                        { id: 'wave1', name: 'Wave 1 核心治理链路', focus: ['企业管理'] },
                    ],
                    recommended_test_types: ['ui_e2e', 'business_flow', 'data_validation', 'visual_regression'],
                    naming_convention: {
                        scenario: '[角色]-[模块]-[场景]-[环境]',
                        test_data_prefix: 'SAMPLE_PLATFORM_PROTO',
                    },
                };
            }

            return {
                playbook_id: 'sample-first-regression',
                project_name: '示例项目企业平台端',
                title: '示例项目企业平台端首轮真实回归',
                content: '# 示例项目回归计划',
                references: [
                    {
                        title: '企业平台端-登录与认证模块',
                        content: '登录模块正文',
                        relative_path: 'docx/XQ/Second/企业平台端需求/01-登录与认证模块.md',
                    },
                ],
                document_sources: [
                    {
                        title: '企业平台端-登录与认证模块',
                        role: 'reference',
                        relative_path: 'docx/XQ/Second/企业平台端需求/01-登录与认证模块.md',
                        local_path: 'D:/workspace/ai_test_platform/data/deploy/sample_platform/docx/XQ/Second/企业平台端需求/01-登录与认证模块.md',
                        exists: true,
                    },
                ],
                target_url: 'https://example.com/login',
                repositories: [],
                waves: [
                    { id: 'wave0', name: 'Wave 0 认证与会话基线', focus: ['登录与认证'] },
                    { id: 'wave1', name: 'Wave 1 核心业务流', focus: ['工单调度'] },
                ],
                recommended_test_types: ['ui_e2e', 'business_flow', 'api_rest', 'data_validation'],
                naming_convention: {
                    scenario: '[角色]-[模块]-[场景]-[环境]',
                    test_data_prefix: 'TEST_SAMPLE',
                },
            };
        });
    });

    it('should show document analysis result after clicking detect', async () => {
        render(<RequirementPage />);

        fireEvent.click(screen.getByRole('button', { name: '文档检测' }));

        await waitFor(() => expect(mockAnalyze).toHaveBeenCalledTimes(1));
        expect((await screen.findAllByText('需求文档')).length).toBeGreaterThan(0);
        expect(screen.getByText('缺少异常流程说明')).toBeInTheDocument();
        expect(screen.getByText('建立需求追溯')).toBeInTheDocument();
        expect(screen.getByText('接口参数')).toBeInTheDocument();
        expect((await screen.findAllByText('交叉检测')).length).toBeGreaterThan(0);
        expect(screen.getByText('建立联合追溯')).toBeInTheDocument();
        expect(screen.getByText('参考文档解析')).toBeInTheDocument();
        expect(screen.getByText('登录接口 OpenAPI')).toBeInTheDocument();
    });

    it('should auto parse uploaded docx file', async () => {
        const { container } = render(<RequirementPage />);
        const input = container.querySelector('input[type="file"]') as HTMLInputElement;
        const file = new File(['docx'], 'login.docx', {
            type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        });

        fireEvent.change(input, { target: { files: [file] } });

        await waitFor(() => expect(mockAnalyzeUpload).toHaveBeenCalledTimes(1));
        expect(await screen.findByText('登录需求')).toBeInTheDocument();
        expect(screen.getByDisplayValue('上传后的文档正文')).toBeInTheDocument();
        expect(screen.getByText('login.docx')).toBeInTheDocument();
    });

    it('should auto parse uploaded reference file', async () => {
        const { container } = render(<RequirementPage />);
        const inputs = container.querySelectorAll('input[type="file"]');
        const referenceInput = inputs[1] as HTMLInputElement;
        const file = new File(['openapi'], 'login-api.json', { type: 'application/json' });

        fireEvent.change(referenceInput, { target: { files: [file] } });

        await waitFor(() => expect(mockAnalyzeUpload).toHaveBeenCalledTimes(1));
        expect(await screen.findByDisplayValue('上传后的文档正文')).toBeInTheDocument();
        expect(screen.getAllByDisplayValue('登录需求').length).toBeGreaterThan(0);
        expect(screen.getByText('login-api.json')).toBeInTheDocument();
    });

    it('should run analyze and generate workflow with multiple references', async () => {
        render(<RequirementPage />);

        fireEvent.change(screen.getByPlaceholderText('可粘贴开发文档、OpenAPI、数据库设计等内容，用于与主文档做交叉检测'), {
            target: { value: 'GET /api/orders' },
        });
        fireEvent.click(screen.getByRole('button', { name: '新增参考文档' }));
        fireEvent.change(screen.getAllByPlaceholderText('可粘贴开发文档、OpenAPI、数据库设计等内容，用于与主文档做交叉检测')[1], {
            target: { value: 'CREATE TABLE orders (id BIGINT PRIMARY KEY)' },
        });
        fireEvent.click(screen.getByRole('button', { name: '检测后生成' }));

        await waitFor(() => expect(mockAnalyze).toHaveBeenCalledTimes(1));
        await waitFor(() => expect(mockGenerate).toHaveBeenCalledTimes(1));
        expect(mockAnalyze.mock.calls[0][2]).toEqual([
            { title: '开发 / 接口 / 数据库参考文档', content: 'GET /api/orders' },
            { title: '参考文档 2', content: 'CREATE TABLE orders (id BIGINT PRIMARY KEY)' },
        ]);
        expect(mockGenerate.mock.calls[0][2]).toEqual([
            { title: '开发 / 接口 / 数据库参考文档', content: 'GET /api/orders' },
            { title: '参考文档 2', content: 'CREATE TABLE orders (id BIGINT PRIMARY KEY)' },
        ]);
        expect(await screen.findByText('登录成功')).toBeInTheDocument();
        expect(screen.getByText('多文档联合设计')).toBeInTheDocument();
        expect(screen.getByText('生成来源')).toBeInTheDocument();
        expect(screen.getByText('文档来源')).toBeInTheDocument();
        expect(screen.getByText('开发 / 接口 / 数据库参考文档')).toBeInTheDocument();
        expect(screen.getAllByText('参考文档').length).toBeGreaterThan(0);
        expect(screen.getAllByText('交叉验证').length).toBeGreaterThan(0);
    });

    it('should load sample_platform playbook into editor', async () => {
        render(<RequirementPage />);

        fireEvent.click(screen.getByRole('button', { name: '加载示例项目回归包' }));

        await waitFor(() => expect(mockFetchPlaybook).toHaveBeenCalledWith('sample-first-regression'));
        expect(await screen.findByText('示例项目企业平台端')).toBeInTheDocument();
        expect(screen.getByDisplayValue('示例项目企业平台端首轮真实回归')).toBeInTheDocument();
        expect(screen.getByDisplayValue('# 示例项目回归计划')).toBeInTheDocument();
        expect(screen.getByText('目标地址：https://example.com/login')).toBeInTheDocument();
        expect(screen.getByText('数据前缀 TEST_SAMPLE')).toBeInTheDocument();
    });

    it('should load sample_platform platform prototype playbook and show mapping summary', async () => {
        render(<RequirementPage />);

        fireEvent.click(screen.getByRole('button', { name: '加载示例项目大平台原型包' }));

        await waitFor(() => expect(mockFetchPlaybook).toHaveBeenCalledWith('sample-platform-prototype'));
        expect(await screen.findByText('示例项目大平台')).toBeInTheDocument();
        expect(screen.getByText('需求文档同步:18/18')).toBeInTheDocument();
        expect(screen.getByText('页面映射率:0')).toBeInTheDocument();
        expect(screen.getByText('模块 16')).toBeInTheDocument();
        expect(screen.getByText('页面 77')).toBeInTheDocument();
        expect(screen.getByText('登录与认证 / 平台管理员登录')).toBeInTheDocument();
        expect(screen.getByText('待原型')).toBeInTheDocument();
    });
});
