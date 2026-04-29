import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch;

import {
    analyzeRequirementDocument,
    fetchRequirementPlaybook,
    generateTestsFromRequirement,
    parseRequirement,
    parseRequirementUpload,
} from '../services/requirementService';

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

describe('requirementService', () => {
    beforeEach(() => {
        mockFetch.mockReset();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('analyzeRequirementDocument should POST to analyze endpoint', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            title: '登录需求',
            summary: 'summary',
            confidence: 0.88,
            rules_count: 1,
            test_cases_count: 1,
            rules: [],
            test_cases: [],
            analysis: {
                document_type: 'requirement_prd',
                document_label: '需求文档',
                quality_score: 0.82,
                completeness_score: 0.81,
                testability_score: 0.84,
                recommended_test_types: ['ui_e2e'],
                issues: [],
                extracted: {
                    actors: ['用户'],
                    flows: ['用户登录'],
                    business_rules: ['支持验证码登录'],
                    data_constraints: ['验证码有效期 5 分钟'],
                    api_endpoints: [],
                    error_codes: [],
                    database_objects: [],
                },
                next_actions: ['建立追溯关系'],
            },
            bundle_analysis: {
                coverage_score: 0.81,
                consistency_score: 0.76,
                involved_document_types: ['requirement_prd', 'development_design'],
                aligned_signals: { data_constraints: 1 },
                uncovered_signals: { data_constraints: 0 },
                findings: [],
                recommended_actions: ['建立联合追溯'],
            },
        }));

        const result = await analyzeRequirementDocument('content', 'title', [
            { title: '开发文档', content: '金额必须大于 0' },
        ]);

        expect(result.analysis.document_type).toBe('requirement_prd');
        expect(result.bundle_analysis?.coverage_score).toBe(0.81);
        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/requirement/analyze');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({
            content: 'content',
            title: 'title',
            references: [{ title: '开发文档', content: '金额必须大于 0' }],
        });
    });

    it('parseRequirement should reuse analyze endpoint', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            title: '需求',
            summary: '',
            confidence: 0.9,
            rules_count: 0,
            test_cases_count: 0,
            rules: [],
            test_cases: [],
            analysis: {
                document_type: 'general_text',
                document_label: '通用文本',
                quality_score: 0.5,
                completeness_score: 0.5,
                testability_score: 0.5,
                recommended_test_types: [],
                issues: [],
                extracted: {
                    actors: [],
                    flows: [],
                    business_rules: [],
                    data_constraints: [],
                    api_endpoints: [],
                    error_codes: [],
                    database_objects: [],
                },
                next_actions: [],
            },
        }));

        await parseRequirement('req', 'doc');

        expect(mockFetch.mock.calls[0][0]).toContain('/api/requirement/analyze');
    });

    it('parseRequirementUpload should POST form data to upload endpoint', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            title: '登录需求',
            summary: 'summary',
            confidence: 0.91,
            rules_count: 1,
            test_cases_count: 1,
            rules: [],
            test_cases: [],
            extracted_text: '文档正文',
            uploaded_filename: 'login.docx',
            analysis: {
                document_type: 'requirement_prd',
                document_label: '需求文档',
                quality_score: 0.82,
                completeness_score: 0.81,
                testability_score: 0.84,
                recommended_test_types: ['ui_e2e'],
                issues: [],
                extracted: {
                    actors: ['用户'],
                    flows: ['用户登录'],
                    business_rules: ['支持验证码登录'],
                    data_constraints: ['验证码有效期 5 分钟'],
                    api_endpoints: [],
                    error_codes: [],
                    database_objects: [],
                },
                next_actions: ['建立追溯关系'],
            },
        }));

        const file = new File(['docx-bytes'], 'login.docx', {
            type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        });
        const result = await parseRequirementUpload(file, '登录需求');

        expect(result.extracted_text).toBe('文档正文');
        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/requirement/parse-upload');
        expect(options.method).toBe('POST');
        expect(options.body).toBeInstanceOf(FormData);
    });

    it('generateTestsFromRequirement should keep analysis payload', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            total_tests: 3,
            confidence: 0.78,
            tests: [
                {
                    id: 'TC-001',
                    name: '登录成功',
                    type: 'ui_e2e',
                    priority: 'high',
                    instruction: '...',
                    tags: ['login'],
                    document_title: '开发文档',
                    document_label: '开发文档',
                    document_type: 'development_design',
                    document_role: 'primary',
                },
                {
                    id: 'API-HAPPY-001',
                    name: '接口主流程: POST /orders',
                    type: 'api_rest',
                    priority: 'high',
                    instruction: '...',
                    tags: ['api'],
                    document_title: '参考文档',
                    document_label: '接口文档',
                    document_type: 'api_spec',
                    document_role: 'reference',
                },
                {
                    id: 'BUNDLE-001',
                    name: '跨文档consistency验证 1',
                    type: 'contract',
                    priority: 'high',
                    instruction: '...',
                    tags: ['bundle'],
                    document_title: '多文档交叉检测',
                    document_label: '交叉检测',
                    document_type: 'document_bundle',
                    document_role: 'bundle',
                },
            ],
            analysis: {
                document_type: 'development_design',
                document_label: '开发文档',
                quality_score: 0.71,
                completeness_score: 0.69,
                testability_score: 0.74,
                recommended_test_types: ['api_rest'],
                issues: [],
                extracted: {
                    actors: [],
                    flows: [],
                    business_rules: [],
                    data_constraints: [],
                    api_endpoints: ['GET /api/orders'],
                    error_codes: ['400'],
                    database_objects: [],
                },
                next_actions: ['补充异常响应断言'],
            },
            generation_summary: {
                title: '开发文档',
                document_type: 'development_design',
                strategy_label: '多文档联合设计',
                rationale: '以主文档为主，并吸收参考文档与交叉检测结果。',
                generated_count: 3,
                counts_by_type: { ui_e2e: 1, api_rest: 1, contract: 1 },
                counts_by_origin: { primary: 1, reference: 1, bundle: 1 },
                focus_areas: ['api_rest', 'contract'],
                traceability: {
                    business_rules: 0,
                    flows: 0,
                    api_endpoints: 2,
                    database_objects: 0,
                    data_constraints: 0,
                },
                document_sources: [
                    {
                        title: '开发文档',
                        document_type: 'development_design',
                        document_label: '开发文档',
                        document_role: 'primary',
                        generated_count: 1,
                    },
                    {
                        title: '参考文档',
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
            bundle_analysis: {
                coverage_score: 0.72,
                consistency_score: 0.68,
                involved_document_types: ['requirement_prd', 'development_design'],
                aligned_signals: { api_endpoints: 1 },
                uncovered_signals: { api_endpoints: 0 },
                findings: [],
                recommended_actions: ['统一接口定义'],
            },
        }));

        const result = await generateTestsFromRequirement('content', '开发文档', [
            { title: '参考文档', content: 'GET /api/orders' },
        ]);

        expect(result.tests).toHaveLength(3);
        expect(result.analysis?.document_type).toBe('development_design');
        expect(result.generation_summary?.strategy_label).toBe('多文档联合设计');
        expect(result.generation_summary?.counts_by_origin?.reference).toBe(1);
        expect(result.tests[1].document_role).toBe('reference');
        expect(result.tests[2].document_role).toBe('bundle');
        expect(result.bundle_analysis?.consistency_score).toBe(0.68);
        expect(mockFetch.mock.calls[0][0]).toContain('/api/requirement/generate-tests');
    });

    it('fetchRequirementPlaybook should load project preset', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            playbook_id: 'sample-first-regression',
            project_name: '示例项目企业平台端',
            title: '示例项目企业平台端首轮真实回归',
            content: '# 回归',
            references: [
                { title: '企业平台端-登录与认证模块', content: '登录文档正文' },
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
            waves: [{ id: 'wave0', name: 'Wave 0', focus: ['登录'] }],
            recommended_test_types: ['ui_e2e', 'business_flow'],
        }));

        const result = await fetchRequirementPlaybook('sample-first-regression');

        expect(result.project_name).toBe('示例项目企业平台端');
        expect(result.references[0].title).toBe('企业平台端-登录与认证模块');
        expect(mockFetch.mock.calls[0][0]).toContain('/api/requirement/playbooks/sample-first-regression');
    });

    it('fetchRequirementPlaybook should keep platform prototype asset metadata', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            playbook_id: 'sample-platform-prototype',
            project_name: '示例项目大平台',
            title: '示例项目大平台原型测试包',
            content: '# 原型测试',
            references: [],
            document_sources: [],
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
            ],
            page_mappings: [
                {
                    mapping_id: 'mp-1',
                    module_name: '登录与认证',
                    page_name: '平台管理员登录',
                    route: '/ptLogin',
                    page_type: '登录页',
                    description: '登录入口',
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
                    recommended_test_types: ['ui_e2e'],
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
            waves: [],
            recommended_test_types: ['ui_e2e', 'visual_regression'],
        }));

        const result = await fetchRequirementPlaybook('sample-platform-prototype');

        expect(result.project_name).toBe('示例项目大平台');
        expect(result.prototype_assets?.[0].relative_path).toContain('示例项目大平台htmlV1.0');
        expect(result.mapping_summary?.module_count).toBe(16);
        expect(result.page_mappings?.[0].mapping_status).toBe('pending_prototype');
        expect(mockFetch.mock.calls[0][0]).toContain('/api/requirement/playbooks/sample-platform-prototype');
    });
});
