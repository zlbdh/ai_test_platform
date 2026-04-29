/**
 * Requirement Parsing Service — 对接后端 /api/requirement/* 接口
 */
import { API_ENDPOINTS } from '../config';

// ── Types ──
export interface BusinessRule {
    rule_id: string;
    type: string;            // functional | validation | business | ui | performance | security
    description: string;
    priority: string;        // critical | high | medium | low
}

export interface TestCaseItem {
    case_id: string;
    title: string;
    test_type: string;
    priority: string;
    steps: string[];
    expected_results: string[];
}

export interface DocumentIssue {
    issue_id: string;
    severity: string;
    category: string;
    message: string;
    suggestion: string;
}

export interface ExtractedSignals {
    actors: string[];
    flows: string[];
    business_rules: string[];
    data_constraints: string[];
    api_endpoints: string[];
    error_codes: string[];
    database_objects: string[];
    api_parameters?: string[];
    response_statuses?: string[];
    schema_entities?: string[];
    database_columns?: string[];
    database_indexes?: string[];
    database_relations?: string[];
    [key: string]: string[] | undefined;
}

export interface DocumentAnalysis {
    document_type: string;
    document_label: string;
    quality_score: number;
    completeness_score: number;
    testability_score: number;
    recommended_test_types: string[];
    issues: DocumentIssue[];
    extracted: ExtractedSignals;
    next_actions: string[];
}

export interface DocumentReferenceInput {
    title: string;
    content: string;
    role?: string;
    relative_path?: string;
    local_path?: string;
    exists?: boolean;
}

export interface BundleFinding {
    finding_id: string;
    severity: string;
    category: string;
    message: string;
    suggestion: string;
}

export interface BundleAnalysis {
    coverage_score: number;
    consistency_score: number;
    involved_document_types: string[];
    aligned_signals: Record<string, number>;
    uncovered_signals: Record<string, number>;
    findings: BundleFinding[];
    recommended_actions: string[];
}

export interface ReferenceAnalysisItem {
    title: string;
    document_type: string;
    document_label: string;
    analysis: DocumentAnalysis;
}

export interface ParseResult {
    title: string;
    summary: string;
    confidence: number;
    rules_count: number;
    test_cases_count: number;
    rules: BusinessRule[];
    test_cases: TestCaseItem[];
    analysis: DocumentAnalysis;
    extracted_text?: string;
    uploaded_filename?: string;
    bundle_analysis?: BundleAnalysis;
    references_analysis?: ReferenceAnalysisItem[];
}

export interface ExecutableTest {
    id: string;
    name: string;
    type: string;
    priority: string;
    instruction: string;
    tags: string[];
    basis?: string[];
    source?: string;
    document_title?: string;
    document_type?: string;
    document_label?: string;
    document_role?: string;
}

export interface GeneratedDocumentSource {
    title: string;
    document_type: string;
    document_label: string;
    document_role: string;
    generated_count: number;
}

export interface GenerationSummary {
    title: string;
    document_type: string;
    strategy_label: string;
    rationale: string;
    generated_count: number;
    counts_by_type: Record<string, number>;
    counts_by_origin?: Record<string, number>;
    focus_areas: string[];
    traceability: {
        business_rules: number;
        flows: number;
        api_endpoints: number;
        database_objects: number;
        data_constraints: number;
        api_parameters?: number;
        response_statuses?: number;
        schema_entities?: number;
        database_columns?: number;
        database_indexes?: number;
        database_relations?: number;
        [key: string]: number | undefined;
    };
    document_sources?: GeneratedDocumentSource[];
    bundle_findings_count?: number;
}

export interface GenerateTestsResult {
    total_tests: number;
    confidence: number;
    tests: ExecutableTest[];
    analysis?: DocumentAnalysis;
    generation_summary?: GenerationSummary;
    bundle_analysis?: BundleAnalysis;
    references_analysis?: ReferenceAnalysisItem[];
}

export interface RequirementPlaybookDocumentSource {
    title: string;
    role: string;
    relative_path: string;
    local_path: string;
    exists: boolean;
}

export interface RequirementPlaybookPrototypeAsset {
    asset_id: string;
    title: string;
    role: string;
    relative_path: string;
    local_path: string;
    exists: boolean;
    asset_scope?: string;
    file_count?: number;
}

export interface RequirementPlaybookAssetCheck {
    check_id: string;
    label: string;
    status: string;
    message: string;
    value: string | number;
}

export interface RequirementPlaybookPageMapping {
    mapping_id: string;
    module_name: string;
    page_name: string;
    route: string;
    page_type: string;
    description: string;
    requirement_source: RequirementPlaybookDocumentSource;
    prototype_source: {
        title: string;
        relative_path: string;
        local_path: string;
        file_uri?: string;
        exists: boolean;
    };
    mapping_status: string;
    recommended_test_types: string[];
    key_assertions: string[];
    baseline_candidate: boolean;
    critical: boolean;
}

export interface RequirementPlaybookMappingSummary {
    module_count: number;
    total_pages: number;
    mapped_pages: number;
    mapping_rate: number;
    critical_pages: number;
    critical_missing_pages: number;
    baseline_candidates: number;
}

export interface RequirementPlaybookRepository {
    label: string;
    url: string;
    local_path: string;
}

export interface RequirementPlaybookWave {
    id: string;
    name: string;
    focus: string[];
}

export interface RequirementPlaybook {
    playbook_id: string;
    project_name: string;
    title: string;
    content: string;
    references: DocumentReferenceInput[];
    document_sources: RequirementPlaybookDocumentSource[];
    prototype_assets?: RequirementPlaybookPrototypeAsset[];
    asset_checks?: RequirementPlaybookAssetCheck[];
    page_mappings?: RequirementPlaybookPageMapping[];
    mapping_summary?: RequirementPlaybookMappingSummary;
    target_url: string;
    repositories: RequirementPlaybookRepository[];
    waves: RequirementPlaybookWave[];
    recommended_test_types: string[];
    naming_convention?: {
        scenario: string;
        test_data_prefix: string;
    };
    notes?: string[];
}

// ── API Calls ──
export const analyzeRequirementDocument = async (
    content: string,
    title: string = '',
    references: DocumentReferenceInput[] = [],
): Promise<ParseResult> => {
    const res = await fetch(API_ENDPOINTS.requirement.analyze, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, title, references }),
    });
    if (!res.ok) throw new Error('解析失败');
    const data = await res.json();
    return data;
};

export const parseRequirement = analyzeRequirementDocument;

export const parseRequirementUpload = async (file: File, title: string = ''): Promise<ParseResult> => {
    const formData = new FormData();
    formData.append('file', file);
    if (title.trim()) {
        formData.append('title', title.trim());
    }

    const res = await fetch(API_ENDPOINTS.requirement.parseUpload, {
        method: 'POST',
        body: formData,
    });
    if (!res.ok) throw new Error('文件解析失败');
    return res.json();
};

export const generateTestsFromRequirement = async (
    content: string,
    title: string = '',
    references: DocumentReferenceInput[] = [],
): Promise<GenerateTestsResult> => {
    const res = await fetch(API_ENDPOINTS.requirement.generateTests, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, title, references }),
    });
    if (!res.ok) throw new Error('生成失败');
    return res.json();
};

export const fetchRequirementPlaybook = async (playbookId: string): Promise<RequirementPlaybook> => {
    const res = await fetch(API_ENDPOINTS.requirement.playbook(playbookId));
    if (!res.ok) throw new Error('加载回归包失败');
    return res.json();
};
