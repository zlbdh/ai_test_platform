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
            title: "Login requirements",
            summary: 'summary',
            confidence: 0.88,
            rules_count: 1,
            test_cases_count: 1,
            rules: [],
            test_cases: [],
            analysis: {
                document_type: 'requirement_prd',
                document_label: "Requirements document",
                quality_score: 0.82,
                completeness_score: 0.81,
                testability_score: 0.84,
                recommended_test_types: ['ui_e2e'],
                issues: [],
                extracted: {
                    actors: ["User"],
                    flows: ["User login"],
                    business_rules: ["Support verification code login"],
                    data_constraints: ["Verification codes expire after 5 minutes"],
                    api_endpoints: [],
                    error_codes: [],
                    database_objects: [],
                },
                next_actions: ["Establish traceability"],
            },
            bundle_analysis: {
                coverage_score: 0.81,
                consistency_score: 0.76,
                involved_document_types: ['requirement_prd', 'development_design'],
                aligned_signals: { data_constraints: 1 },
                uncovered_signals: { data_constraints: 0 },
                findings: [],
                recommended_actions: ["Establish combined traceability"],
            },
        }));

        const result = await analyzeRequirementDocument('content', 'title', [
            { title: "Development document", content: "Amount must be greater than 0" },
        ]);

        expect(result.analysis.document_type).toBe('requirement_prd');
        expect(result.bundle_analysis?.coverage_score).toBe(0.81);
        const [url, options] = mockFetch.mock.calls[0];
        expect(url).toContain('/api/requirement/analyze');
        expect(options.method).toBe('POST');
        expect(JSON.parse(options.body)).toEqual({
            content: 'content',
            title: 'title',
            references: [{ title: "Development document", content: "Amount must be greater than 0" }],
        });
    });

    it('parseRequirement should reuse analyze endpoint', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            status: 'success',
            title: "Requirement",
            summary: '',
            confidence: 0.9,
            rules_count: 0,
            test_cases_count: 0,
            rules: [],
            test_cases: [],
            analysis: {
                document_type: 'general_text',
                document_label: "General text",
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
            title: "Login requirements",
            summary: 'summary',
            confidence: 0.91,
            rules_count: 1,
            test_cases_count: 1,
            rules: [],
            test_cases: [],
            extracted_text: "Document body",
            uploaded_filename: 'login.docx',
            analysis: {
                document_type: 'requirement_prd',
                document_label: "Requirements document",
                quality_score: 0.82,
                completeness_score: 0.81,
                testability_score: 0.84,
                recommended_test_types: ['ui_e2e'],
                issues: [],
                extracted: {
                    actors: ["User"],
                    flows: ["User login"],
                    business_rules: ["Support verification code login"],
                    data_constraints: ["Verification codes expire after 5 minutes"],
                    api_endpoints: [],
                    error_codes: [],
                    database_objects: [],
                },
                next_actions: ["Establish traceability"],
            },
        }));

        const file = new File(['docx-bytes'], 'login.docx', {
            type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        });
        const result = await parseRequirementUpload(file, "Login requirements");

        expect(result.extracted_text).toBe("Document body");
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
                    name: "Login succeeded",
                    type: 'ui_e2e',
                    priority: 'high',
                    instruction: '...',
                    tags: ['login'],
                    document_title: "Development document",
                    document_label: "Development document",
                    document_type: 'development_design',
                    document_role: 'primary',
                },
                {
                    id: 'API-HAPPY-001',
                    name: "Primary API workflow: POST /orders",
                    type: 'api_rest',
                    priority: 'high',
                    instruction: '...',
                    tags: ['api'],
                    document_title: "Reference document",
                    document_label: "API document",
                    document_type: 'api_spec',
                    document_role: 'reference',
                },
                {
                    id: 'BUNDLE-001',
                    name: "Cross-document consistency check 1",
                    type: 'contract',
                    priority: 'high',
                    instruction: '...',
                    tags: ['bundle'],
                    document_title: "Cross-document review",
                    document_label: "Cross-check",
                    document_type: 'document_bundle',
                    document_role: 'bundle',
                },
            ],
            analysis: {
                document_type: 'development_design',
                document_label: "Development document",
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
                next_actions: ["Add exception response assertions"],
            },
            generation_summary: {
                title: "Development document",
                document_type: 'development_design',
                strategy_label: "Combined document design",
                rationale: "Use the primary document as the basis and incorporate reference documents and cross-check results.",
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
                        title: "Development document",
                        document_type: 'development_design',
                        document_label: "Development document",
                        document_role: 'primary',
                        generated_count: 1,
                    },
                    {
                        title: "Reference document",
                        document_type: 'api_spec',
                        document_label: "API document",
                        document_role: 'reference',
                        generated_count: 1,
                    },
                    {
                        title: "Cross-document review",
                        document_type: 'document_bundle',
                        document_label: "Cross-check",
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
                recommended_actions: ["Unify API definitions"],
            },
        }));

        const result = await generateTestsFromRequirement('content', "Development document", [
            { title: "Reference document", content: 'GET /api/orders' },
        ]);

        expect(result.tests).toHaveLength(3);
        expect(result.analysis?.document_type).toBe('development_design');
        expect(result.generation_summary?.strategy_label).toBe("Combined document design");
        expect(result.generation_summary?.counts_by_origin?.reference).toBe(1);
        expect(result.tests[1].document_role).toBe('reference');
        expect(result.tests[2].document_role).toBe('bundle');
        expect(result.bundle_analysis?.consistency_score).toBe(0.68);
        expect(mockFetch.mock.calls[0][0]).toContain('/api/requirement/generate-tests');
    });

    it('fetchRequirementPlaybook should load project preset', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            playbook_id: 'sample-first-regression',
            project_name: "Sample business platform",
            title: "Sample enterprise platform initial live regression",
            content: "# Regression",
            references: [
                { title: "Business platform - Login and authentication", content: "Login document body" },
            ],
            document_sources: [
                {
                    title: "Business platform - Login and authentication",
                    role: 'reference',
                    relative_path: "docx/XQ/Second/business-platform-requirements/01-login-and-authentication.md",
                    local_path: "D:/workspace/ai_test_platform/data/deploy/sample_platform/docx/XQ/Second/business-platform-requirements/01-login-and-authentication.md",
                    exists: true,
                },
            ],
            target_url: 'https://example.com/login',
            repositories: [],
            waves: [{ id: 'wave0', name: 'Wave 0', focus: ["Login"] }],
            recommended_test_types: ['ui_e2e', 'business_flow'],
        }));

        const result = await fetchRequirementPlaybook('sample-first-regression');

        expect(result.project_name).toBe("Sample business platform");
        expect(result.references[0].title).toBe("Business platform - Login and authentication");
        expect(mockFetch.mock.calls[0][0]).toContain('/api/requirement/playbooks/sample-first-regression');
    });

    it('fetchRequirementPlaybook should keep platform prototype asset metadata', async () => {
        mockFetch.mockResolvedValue(mockResponse({
            playbook_id: 'sample-platform-prototype',
            project_name: "Sample platform",
            title: "Sample project platform prototype test package",
            content: "# Prototype testing",
            references: [],
            document_sources: [],
            prototype_assets: [
                {
                    asset_id: 'sample-platform-prototype-docs',
                    title: "Sample platform HTML prototype directory (deployment documentation repository)",
                    role: 'prototype',
                    relative_path: "docx/XQ/Second/html/sample-platform-html-v1.0",
                    local_path: "D:/workspace/ai_test_platform/data/deploy/sample_platform/docx/XQ/Second/html/sample-platform-html-v1.0",
                    exists: false,
                    file_count: 0,
                },
            ],
            asset_checks: [
                {
                    check_id: 'platform_docs_ready',
                    label: "Requirements document synchronization",
                    status: 'success',
                    message: "Synchronized 18/18 platform requirements documents.",
                    value: '18/18',
                },
            ],
            page_mappings: [
                {
                    mapping_id: 'mp-1',
                    module_name: "Login and authentication",
                    page_name: "Platform administrator login",
                    route: '/ptLogin',
                    page_type: "Login page",
                    description: "Login entry",
                    requirement_source: {
                        title: "Sample platform - Login and authentication",
                        role: 'primary',
                        relative_path: "docx/XQ/Second/sample-platform-requirements/01-login-and-authentication.md",
                        local_path: "D:/workspace/ai_test_platform/data/deploy/sample_platform/docx/XQ/Second/sample-platform-requirements/01-login-and-authentication.md",
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
                    key_assertions: ["Complete login form"],
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
            target_url: "Prototype directory awaiting synchronization: docx/XQ/Second/html/sample-platform-html-v1.0",
            repositories: [],
            waves: [],
            recommended_test_types: ['ui_e2e', 'visual_regression'],
        }));

        const result = await fetchRequirementPlaybook('sample-platform-prototype');

        expect(result.project_name).toBe("Sample platform");
        expect(result.prototype_assets?.[0].relative_path).toContain("sample-platform-html-v1.0");
        expect(result.mapping_summary?.module_count).toBe(16);
        expect(result.page_mappings?.[0].mapping_status).toBe('pending_prototype');
        expect(mockFetch.mock.calls[0][0]).toContain('/api/requirement/playbooks/sample-platform-prototype');
    });
});
