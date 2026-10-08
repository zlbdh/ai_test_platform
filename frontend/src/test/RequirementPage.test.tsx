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
            title: "Login requirements",
            summary: 'summary',
            confidence: 0.92,
            rules_count: 1,
            test_cases_count: 1,
            rules: [],
            test_cases: [],
            analysis: {
                document_type: 'requirement_prd',
                document_label: "Requirements document",
                quality_score: 0.88,
                completeness_score: 0.85,
                testability_score: 0.91,
                recommended_test_types: ['ui_e2e', 'business_flow'],
                issues: [
                    {
                        issue_id: 'ISS-0001',
                        severity: 'warning',
                        category: 'testability',
                        message: "Missing exception flow description",
                        suggestion: "Add failure scenarios",
                    },
                ],
                extracted: {
                    actors: ["User"],
                    flows: ["User login"],
                    business_rules: ["Support verification code login"],
                    data_constraints: ["Verification codes expire after 5 minutes"],
                    api_endpoints: [],
                    api_parameters: ['POST /api/login -> body:password (required)'],
                    response_statuses: ['POST /api/login -> 200'],
                    error_codes: [],
                    database_objects: [],
                },
                next_actions: ["Establish requirements traceability"],
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
                        message: "The primary document contains data constraints, but the reference document lacks corresponding field constraints.",
                        suggestion: "Add database design or API field constraints.",
                    },
                ],
                recommended_actions: ["Establish combined traceability"],
            },
            references_analysis: [
                {
                    title: "Login API OpenAPI",
                    document_type: 'api_spec',
                    document_label: "API document",
                    analysis: {
                        document_type: 'api_spec',
                        document_label: "API document",
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
                        next_actions: ["Add exception response models"],
                    },
                },
            ],
        };
        mockAnalyze.mockResolvedValue(parsedResult);
        mockAnalyzeUpload.mockImplementation(async (file: File) => ({
            ...parsedResult,
            extracted_text: "Uploaded document body",
            uploaded_filename: file.name,
        }));
        mockGenerate.mockResolvedValue({
            total_tests: 3,
            confidence: 0.81,
            tests: [
                {
                    id: 'TC-001',
                    name: "Login succeeded",
                    type: 'ui_e2e',
                    priority: 'high',
                    instruction: "Steps...",
                    tags: ['login'],
                    document_title: "Login requirements",
                    document_label: "Requirements document",
                    document_type: 'requirement_prd',
                    document_role: 'primary',
                },
                {
                    id: 'API-HAPPY-001',
                    name: "Primary API workflow: POST /api/login",
                    type: 'api_rest',
                    priority: 'high',
                    instruction: "Steps...",
                    tags: ['api'],
                    document_title: "Development, API, and database reference documents",
                    document_label: "API document",
                    document_type: 'api_spec',
                    document_role: 'reference',
                },
                {
                    id: 'BUNDLE-001',
                    name: "Cross-document consistency check 1",
                    type: 'contract',
                    priority: 'medium',
                    instruction: "Steps...",
                    tags: ['bundle'],
                    document_title: "Cross-document review",
                    document_label: "Cross-check",
                    document_type: 'document_bundle',
                    document_role: 'bundle',
                },
            ],
            generation_summary: {
                title: "Login requirements",
                document_type: 'requirement_prd',
                strategy_label: "Combined document design",
                rationale: "Prioritize primary business workflows while incorporating reference documents and cross-check results.",
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
                        title: "Login requirements",
                        document_type: 'requirement_prd',
                        document_label: "Requirements document",
                        document_role: 'primary',
                        generated_count: 1,
                    },
                    {
                        title: "Development, API, and database reference documents",
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
            analysis: undefined,
        });
        mockFetchPlaybook.mockImplementation(async (playbookId: string) => {
            if (playbookId === 'sample-platform-prototype') {
                return {
                    playbook_id: 'sample-platform-prototype',
                    project_name: "Sample platform",
                    title: "Sample project platform prototype test package",
                    content: "# Sample platform prototype test package",
                    references: [
                        {
                            title: "Sample platform - Business management",
                            content: "Business management content",
                            relative_path: "docx/XQ/Second/business-requirements/sample-platform/01_business-management_requirements.md",
                        },
                    ],
                    document_sources: [
                        {
                            title: "Sample platform - Business management",
                            role: 'reference',
                            relative_path: "docx/XQ/Second/business-requirements/sample-platform/01_business-management_requirements.md",
                            local_path: "D:/workspace/ai_test_platform/data/deploy/sample_platform/docx/XQ/Second/business-requirements/sample-platform/01_business-management_requirements.md",
                            exists: true,
                        },
                    ],
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
                        {
                            check_id: 'platform_page_mapping_rate',
                            label: "Page mapping rate",
                            status: 'warning',
                            message: "Mapped 0/77 pages.",
                            value: 0,
                        },
                    ],
                    page_mappings: [
                        {
                            mapping_id: 'mp-1',
                            module_name: "Login and authentication",
                            page_name: "Platform administrator login",
                            route: '/ptLogin',
                            page_type: "Login page",
                            description: "Platform administrator login entry",
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
                            recommended_test_types: ['ui_e2e', 'data_validation'],
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
                    waves: [
                        { id: 'wave0', name: "Wave 0 login and entry baseline", focus: ["Login and authentication"] },
                        { id: 'wave1', name: "Wave 1 core governance workflows", focus: ["Business management"] },
                    ],
                    recommended_test_types: ['ui_e2e', 'business_flow', 'data_validation', 'visual_regression'],
                    naming_convention: {
                        scenario: "[role]-[module]-[scenario]-[environment]",
                        test_data_prefix: 'SAMPLE_PLATFORM_PROTO',
                    },
                };
            }

            return {
                playbook_id: 'sample-first-regression',
                project_name: "Sample business platform",
                title: "Sample enterprise platform initial live regression",
                content: "# Sample project regression plan",
                references: [
                    {
                        title: "Business platform - Login and authentication",
                        content: "Login module content",
                        relative_path: "docx/XQ/Second/business-platform-requirements/01-login-and-authentication.md",
                    },
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
                waves: [
                    { id: 'wave0', name: "Wave 0 authentication and session baseline", focus: ["Login and authentication"] },
                    { id: 'wave1', name: "Wave 1 core business workflows", focus: ["Work order dispatch"] },
                ],
                recommended_test_types: ['ui_e2e', 'business_flow', 'api_rest', 'data_validation'],
                naming_convention: {
                    scenario: "[role]-[module]-[scenario]-[environment]",
                    test_data_prefix: 'TEST_SAMPLE',
                },
            };
        });
    });

    it('should show document analysis result after clicking detect', async () => {
        render(<RequirementPage />);

        fireEvent.click(screen.getByRole('button', { name: "Check document" }));

        await waitFor(() => expect(mockAnalyze).toHaveBeenCalledTimes(1));
        expect((await screen.findAllByText("Requirements document")).length).toBeGreaterThan(0);
        expect(screen.getByText("Missing exception flow description")).toBeInTheDocument();
        expect(screen.getByText("Establish requirements traceability")).toBeInTheDocument();
        expect(screen.getByText("API parameters")).toBeInTheDocument();
        expect((await screen.findAllByText("Cross-check")).length).toBeGreaterThan(0);
        expect(screen.getByText("Establish combined traceability")).toBeInTheDocument();
        expect(screen.getByText("Reference document analysis")).toBeInTheDocument();
        expect(screen.getByText("Login API OpenAPI")).toBeInTheDocument();
    });

    it('should auto parse uploaded docx file', async () => {
        const { container } = render(<RequirementPage />);
        const input = container.querySelector('input[type="file"]') as HTMLInputElement;
        const file = new File(['docx'], 'login.docx', {
            type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        });

        fireEvent.change(input, { target: { files: [file] } });

        await waitFor(() => expect(mockAnalyzeUpload).toHaveBeenCalledTimes(1));
        expect(await screen.findByText("Login requirements")).toBeInTheDocument();
        expect(screen.getByDisplayValue("Uploaded document body")).toBeInTheDocument();
        expect(screen.getByText('login.docx')).toBeInTheDocument();
    });

    it('should auto parse uploaded reference file', async () => {
        const { container } = render(<RequirementPage />);
        const inputs = container.querySelectorAll('input[type="file"]');
        const referenceInput = inputs[1] as HTMLInputElement;
        const file = new File(['openapi'], 'login-api.json', { type: 'application/json' });

        fireEvent.change(referenceInput, { target: { files: [file] } });

        await waitFor(() => expect(mockAnalyzeUpload).toHaveBeenCalledTimes(1));
        expect(await screen.findByDisplayValue("Uploaded document body")).toBeInTheDocument();
        expect(screen.getAllByDisplayValue("Login requirements").length).toBeGreaterThan(0);
        expect(screen.getByText('login-api.json')).toBeInTheDocument();
    });

    it('should run analyze and generate workflow with multiple references', async () => {
        render(<RequirementPage />);

        fireEvent.change(screen.getByPlaceholderText("Paste development documents, OpenAPI specifications, or database designs to cross-check against the primary document"), {
            target: { value: 'GET /api/orders' },
        });
        fireEvent.click(screen.getByRole('button', { name: "Add reference document" }));
        fireEvent.change(screen.getAllByPlaceholderText("Paste development documents, OpenAPI specifications, or database designs to cross-check against the primary document")[1], {
            target: { value: 'CREATE TABLE orders (id BIGINT PRIMARY KEY)' },
        });
        fireEvent.click(screen.getByRole('button', { name: "Check, then generate" }));

        await waitFor(() => expect(mockAnalyze).toHaveBeenCalledTimes(1));
        await waitFor(() => expect(mockGenerate).toHaveBeenCalledTimes(1));
        expect(mockAnalyze.mock.calls[0][2]).toEqual([
            { title: "Development, API, and database reference documents", content: 'GET /api/orders' },
            { title: "Reference document 2", content: 'CREATE TABLE orders (id BIGINT PRIMARY KEY)' },
        ]);
        expect(mockGenerate.mock.calls[0][2]).toEqual([
            { title: "Development, API, and database reference documents", content: 'GET /api/orders' },
            { title: "Reference document 2", content: 'CREATE TABLE orders (id BIGINT PRIMARY KEY)' },
        ]);
        expect(await screen.findByText("Login succeeded")).toBeInTheDocument();
        expect(screen.getByText("Combined document design")).toBeInTheDocument();
        expect(screen.getByText("Generation source")).toBeInTheDocument();
        expect(screen.getByText("Document source")).toBeInTheDocument();
        expect(screen.getByText("Development, API, and database reference documents")).toBeInTheDocument();
        expect(screen.getAllByText("Reference document").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Cross-validation").length).toBeGreaterThan(0);
    });

    it('should load sample_platform playbook into editor', async () => {
        render(<RequirementPage />);

        fireEvent.click(screen.getByRole('button', { name: "Load sample project regression package" }));

        await waitFor(() => expect(mockFetchPlaybook).toHaveBeenCalledWith('sample-first-regression'));
        expect(await screen.findByText("Sample business platform")).toBeInTheDocument();
        expect(screen.getByDisplayValue("Sample enterprise platform initial live regression")).toBeInTheDocument();
        expect(screen.getByDisplayValue("# Sample project regression plan")).toBeInTheDocument();
        expect(screen.getByText("Target URL: https://example.com/login")).toBeInTheDocument();
        expect(screen.getByText("Data prefix TEST_SAMPLE")).toBeInTheDocument();
    });

    it('should load sample_platform platform prototype playbook and show mapping summary', async () => {
        render(<RequirementPage />);

        fireEvent.click(screen.getByRole('button', { name: "Load sample project platform prototype package" }));

        await waitFor(() => expect(mockFetchPlaybook).toHaveBeenCalledWith('sample-platform-prototype'));
        expect(await screen.findByText("Sample platform")).toBeInTheDocument();
        expect(screen.getByText("Requirements document synchronization:18/18")).toBeInTheDocument();
        expect(screen.getByText("Page mapping rate:0")).toBeInTheDocument();
        expect(screen.getByText("Modules 16")).toBeInTheDocument();
        expect(screen.getByText("Pages 77")).toBeInTheDocument();
        expect(screen.getByText("Login and authentication / Platform administrator login")).toBeInTheDocument();
        expect(screen.getByText("Awaiting prototype")).toBeInTheDocument();
    });
});
