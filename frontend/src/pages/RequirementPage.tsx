import React, { useState, useCallback, useRef } from 'react';
import {
    FileText, Sparkles, Upload, ClipboardList, CheckCircle2,
    AlertTriangle, ShieldCheck, Gauge, ChevronRight, RefreshCw, BookOpen, FileUp, X
} from '../components/icons';
import Badge from '../components/ui/Badge';
import Tabs from '../components/ui/Tabs';
import {
    parseRequirement, parseRequirementUpload, generateTestsFromRequirement, fetchRequirementPlaybook,
    type ParseResult, type ExecutableTest, type GenerationSummary, type RequirementPlaybook,
} from '../services/requirementService';
import PageHeader from '../components/ui/PageHeader';

// ── Priority badge ──
const priorityBadge = (p: string) => {
    const map: Record<string, { variant: 'error' | 'warning' | 'info' | 'neutral'; label: string }> = {
        critical: { variant: 'error', label: "Critical" },
        high: { variant: 'warning', label: "High" },
        medium: { variant: 'info', label: "Medium" },
        low: { variant: 'neutral', label: "Low" },
    };
    const item = map[p] || { variant: 'neutral' as const, label: p };
    return <Badge variant={item.variant} size="sm">{item.label}</Badge>;
};

const ruleTypeIcon = (t: string) => {
    const icons: Record<string, React.ReactNode> = {
        functional: <ClipboardList className="w-3.5 h-3.5 text-blue-500" />,
        validation: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />,
        business: <BookOpen className="w-3.5 h-3.5 text-indigo-500" />,
        ui: <FileText className="w-3.5 h-3.5 text-violet-500" />,
        performance: <Gauge className="w-3.5 h-3.5 text-amber-500" />,
        security: <ShieldCheck className="w-3.5 h-3.5 text-red-500" />,
    };
    return icons[t] || <AlertTriangle className="w-3.5 h-3.5 text-slate-400" />;
};

const severityBadge = (severity: string) => {
    const map: Record<string, { variant: 'error' | 'warning' | 'info' | 'neutral'; label: string }> = {
        error: { variant: 'error', label: "High risk" },
        warning: { variant: 'warning', label: "Reminder" },
        info: { variant: 'info', label: "Notice" },
    };
    const item = map[severity] || { variant: 'neutral' as const, label: severity };
    return <Badge variant={item.variant} size="sm">{item.label}</Badge>;
};

const scoreTone = (score: number) => {
    if (score >= 0.8) return 'text-emerald-500';
    if (score >= 0.6) return 'text-amber-500';
    return 'text-red-500';
};

const analysisGroupLabels: Record<string, string> = {
    actors: "Participating roles",
    flows: "Flow segments",
    business_rules: "Business rules",
    data_constraints: "Data constraints",
    api_endpoints: "API endpoints",
    api_parameters: "API parameters",
    response_statuses: "Response statuses",
    schema_entities: "Data models",
    error_codes: "Error codes",
    database_objects: "Database objects",
    database_columns: "Database fields",
    database_indexes: "Database indexes",
    database_relations: "Database relationships",
};

const generationTypeLabels: Record<string, string> = {
    ui_e2e: 'UI E2E',
    business_flow: "Business flow",
    api_rest: 'API',
    contract: "Contract",
    data_validation: "Data validation",
    visual_regression: "Visual regression",
    performance: "Performance",
    security: "Security",
};

const documentRoleLabels: Record<string, string> = {
    primary: "Primary document",
    reference: "Reference document",
    bundle: "Cross-validation",
};

const documentRoleVariants: Record<string, 'neutral' | 'info' | 'warning'> = {
    primary: 'neutral',
    reference: 'info',
    bundle: 'warning',
};

const playbookCheckVariant = (status: string): 'success' | 'warning' | 'error' | 'neutral' => {
    if (status === 'success' || status === 'passed') return 'success';
    if (status === 'warning' || status === 'pending') return 'warning';
    if (status === 'error' || status === 'failed') return 'error';
    return 'neutral';
};

const mappingStatusMeta = (status: string) => {
    if (status === 'mapped') {
        return { variant: 'success' as const, label: "Mapped" };
    }
    if (status === 'pending_prototype') {
        return { variant: 'warning' as const, label: "Awaiting prototype" };
    }
    return { variant: 'neutral' as const, label: status || "Unknown" };
};

const SUPPORTED_DOCUMENT_EXTENSIONS = ['md', 'txt', 'docx', 'pdf', 'json', 'sql', 'yaml', 'yml'];
const DOCUMENT_ACCEPT = SUPPORTED_DOCUMENT_EXTENSIONS.map(ext => `.${ext}`).join(',');

type ReferenceDraft = {
    id: string;
    title: string;
    content: string;
    uploadedFilename?: string;
    uploading?: boolean;
};

let referenceDraftSequence = 0;

const createReferenceDraft = (title: string = "Reference document"): ReferenceDraft => ({
    id: `reference-${referenceDraftSequence++}`,
    title,
    content: '',
    uploadedFilename: '',
    uploading: false,
});

const isSupportedDocument = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    return !!ext && SUPPORTED_DOCUMENT_EXTENSIONS.includes(ext);
};

const buildReferences = (references: ReferenceDraft[]) => references
    .map(reference => ({
        title: reference.title.trim() || "Reference document",
        content: reference.content.trim(),
    }))
    .filter(reference => reference.content);

// ── Sample content ──
const SAMPLE_REQUIREMENT = `# User Login Module PRD

## Functional Requirements
1. Users can sign in with a phone number and verification code.
2. Users can sign in with an email address and password.
3. Lock the account for 15 minutes after three failed login attempts.
4. Passwords must contain at least eight characters, including uppercase letters, lowercase letters, and numbers.
5. Verification codes expire after five minutes.

## Security Requirements
- Store all passwords securely using bcrypt.
- Sessions expire after 30 minutes.
- Support two-factor authentication (2FA).

## Performance Requirements
- Login API response time < 500 ms.
- Support 1,000 transactions per second.
`;

// ============================================================================
const RequirementPage: React.FC = () => {
    const [content, setContent] = useState(SAMPLE_REQUIREMENT);
    const [title, setTitle] = useState("User login module");
    const [references, setReferences] = useState<ReferenceDraft[]>([
        createReferenceDraft("Development, API, and database reference documents"),
    ]);
    const [result, setResult] = useState<ParseResult | null>(null);
    const [execTests, setExecTests] = useState<ExecutableTest[]>([]);
    const [generationSummary, setGenerationSummary] = useState<GenerationSummary | null>(null);
    const [parsing, setParsing] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [workflowRunning, setWorkflowRunning] = useState(false);
    const [activeTab, setActiveTab] = useState('analysis');
    const [uploadedFile, setUploadedFile] = useState<File | null>(null);
    const [isDragOver, setIsDragOver] = useState(false);
    const [loadingPlaybook, setLoadingPlaybook] = useState(false);
    const [playbook, setPlaybook] = useState<RequirementPlaybook | null>(null);
    const fileRef = useRef<HTMLInputElement>(null);
    const hasReferenceUploading = references.some(reference => reference.uploading);

    const applyPlaybook = useCallback((payload: RequirementPlaybook) => {
        setPlaybook(payload);
        setTitle(payload.title);
        setContent(payload.content);
        const nextReferences = payload.references.length > 0
            ? payload.references.map(reference => ({
                id: `reference-${referenceDraftSequence++}`,
                title: reference.title,
                content: reference.content,
                uploadedFilename: reference.relative_path?.split('/').pop() || '',
                uploading: false,
            }))
            : [createReferenceDraft("Development, API, and database reference documents")];
        setReferences(nextReferences);
        setUploadedFile(null);
        if (fileRef.current) {
            fileRef.current.value = '';
        }
        setResult(null);
        setExecTests([]);
        setGenerationSummary(null);
        setActiveTab('analysis');
    }, []);

    const readFile = useCallback(async (file: File) => {
        if (!isSupportedDocument(file.name)) {
            alert(`Supported formats: ${DOCUMENT_ACCEPT}`);
            return;
        }
        setUploadedFile(file);
        setUploading(true);
        try {
            const fallbackTitle = title && title !== "User login module" ? title : file.name.replace(/\.[^.]+$/, '');
            const parsed = await parseRequirementUpload(file, fallbackTitle);
            setContent(parsed.extracted_text || '');
            setTitle(parsed.title || fallbackTitle);
            setResult(parsed);
            setExecTests([]);
            setGenerationSummary(null);
            setActiveTab('analysis');
        } catch {
            alert("Failed to parse the file. Check its format or try again later.");
        } finally {
            setUploading(false);
        }
    }, [title]);

    const updateReference = useCallback((referenceId: string, patch: Partial<ReferenceDraft>) => {
        setReferences(prev => prev.map(reference => (
            reference.id === referenceId ? { ...reference, ...patch } : reference
        )));
    }, []);

    const addReference = useCallback(() => {
        setReferences(prev => [
            ...prev,
            createReferenceDraft(`Reference document ${prev.length + 1}`),
        ]);
    }, []);

    const removeReference = useCallback((referenceId: string) => {
        setReferences(prev => {
            const next = prev.filter(reference => reference.id !== referenceId);
            return next.length > 0 ? next : [createReferenceDraft("Development, API, and database reference documents")];
        });
    }, []);

    const readReferenceFile = useCallback(async (referenceId: string, file: File) => {
        if (!isSupportedDocument(file.name)) {
            alert(`Supported formats: ${DOCUMENT_ACCEPT}`);
            return;
        }

        const currentReference = references.find(reference => reference.id === referenceId);
        const fallbackTitle = currentReference?.title.trim()
            ? currentReference.title.trim()
            : file.name.replace(/\.[^.]+$/, '');

        updateReference(referenceId, { uploading: true, uploadedFilename: file.name });
        try {
            const parsed = await parseRequirementUpload(file, fallbackTitle);
            setReferences(prev => prev.map(reference => (
                reference.id === referenceId
                    ? {
                        ...reference,
                        title: parsed.title || fallbackTitle,
                        content: parsed.extracted_text || reference.content,
                        uploadedFilename: parsed.uploaded_filename || file.name,
                        uploading: false,
                    }
                    : reference
            )));
        } catch {
            updateReference(referenceId, { uploading: false });
            alert("Failed to parse the reference document. Check its format or try again later.");
        }
    }, [references, updateReference]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) void readFile(file);
    }, [readFile]);

    const clearFile = () => {
        setUploadedFile(null);
        if (fileRef.current) fileRef.current.value = '';
    };

    const loadPlaybook = useCallback(async (playbookId: string, failureLabel: string) => {
        setLoadingPlaybook(true);
        try {
            const payload = await fetchRequirementPlaybook(playbookId);
            applyPlaybook(payload);
        } catch {
            alert(`${failureLabel}Failed to load. Try again later.`);
        } finally {
            setLoadingPlaybook(false);
        }
    }, [applyPlaybook]);

    const loadSamplePlaybook = useCallback(async () => {
        await loadPlaybook('sample-first-regression', "Sample project regression package");
    }, [loadPlaybook]);

    const loadSamplePlatformPrototypePlaybook = useCallback(async () => {
        await loadPlaybook('sample-platform-prototype', "Sample project platform prototype package");
    }, [loadPlaybook]);

    const handleParse = useCallback(async () => {
        setParsing(true);
        try {
            setGenerationSummary(null);
            const r = await parseRequirement(content, title, buildReferences(references));
            setResult(r);
            setActiveTab('analysis');
        } catch { /* */ }
        setParsing(false);
    }, [content, title, references]);

    const handleGenerate = useCallback(async () => {
        setGenerating(true);
        try {
            const normalizedReferences = buildReferences(references);
            const r = await generateTestsFromRequirement(content, title, normalizedReferences);
            setExecTests(r.tests);
            setGenerationSummary(r.generation_summary || null);
            if (!result && r.analysis) {
                const analyzed = await parseRequirement(content, title, normalizedReferences);
                setResult(analyzed);
            }
            setActiveTab('executable');
        } catch { /* */ }
        setGenerating(false);
    }, [content, title, references, result]);

    const handleAnalyzeAndGenerate = useCallback(async () => {
        setWorkflowRunning(true);
        try {
            const normalizedReferences = buildReferences(references);
            const analyzed = await parseRequirement(content, title, normalizedReferences);
            setResult(analyzed);
            const generated = await generateTestsFromRequirement(content, title, normalizedReferences);
            setExecTests(generated.tests);
            setGenerationSummary(generated.generation_summary || null);
            setActiveTab('executable');
        } catch { /* */ }
        setWorkflowRunning(false);
    }, [content, title, references]);

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            <PageHeader
                icon={<FileText className="w-5 h-5" />}
                title={"Requirements analysis"}
                description={"Upload PRD or development documents. AI checks document quality before generating test cases."}
                accent="violet"
            />

            <div className="grid lg:grid-cols-5 gap-6">
                {/* ── Left: Input ── */}
                <div className="lg:col-span-2 space-y-4">
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                                <Upload className="w-4 h-4 text-violet-500" />
                                Requirements document
                            </h3>
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={loadSamplePlaybook}
                                    disabled={loadingPlaybook || parsing || generating || workflowRunning}
                                    className="inline-flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-2.5 py-1.5 text-[11px] font-medium text-violet-700 transition hover:bg-violet-100 disabled:opacity-50 disabled:cursor-not-allowed dark:border-violet-800/60 dark:bg-violet-900/20 dark:text-violet-200 dark:hover:bg-violet-900/30"
                                >
                                    {loadingPlaybook ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <BookOpen className="w-3.5 h-3.5" />}
                                    {loadingPlaybook ? "Loading..." : "Load sample project regression package"}
                                </button>
                                <button
                                    type="button"
                                    onClick={loadSamplePlatformPrototypePlaybook}
                                    disabled={loadingPlaybook || parsing || generating || workflowRunning}
                                    className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1.5 text-[11px] font-medium text-blue-700 transition hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed dark:border-blue-800/60 dark:bg-blue-900/20 dark:text-blue-200 dark:hover:bg-blue-900/30"
                                >
                                    {loadingPlaybook ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <BookOpen className="w-3.5 h-3.5" />}
                                    {loadingPlaybook ? "Loading..." : "Load sample project platform prototype package"}
                                </button>
                            </div>
                        </div>

                        {playbook && (
                            <div className="rounded-lg border border-violet-200 bg-violet-50/70 p-3 space-y-3 dark:border-violet-800/50 dark:bg-violet-900/10">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <p className="text-xs uppercase tracking-wide text-violet-500">Project regression package</p>
                                        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                                            {playbook.project_name}
                                        </h4>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                            Target URL: {playbook.target_url}
                                        </p>
                                    </div>
                                    {playbook.naming_convention?.test_data_prefix && (
                                        <Badge variant="info" size="sm">
                                            Data prefix {playbook.naming_convention.test_data_prefix}
                                        </Badge>
                                    )}
                                </div>
                                <div className="flex gap-1.5 flex-wrap">
                                    {playbook.recommended_test_types.map(item => (
                                        <Badge key={item} variant="neutral" size="sm">{generationTypeLabels[item] || item}</Badge>
                                    ))}
                                </div>
                                <div className="grid gap-2">
                                    <div>
                                        <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Recommended wave</p>
                                        <div className="flex gap-1.5 flex-wrap">
                                            {playbook.waves.map(wave => (
                                                <Badge key={wave.id} variant="warning" size="sm">{wave.name}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Document source</p>
                                        <div className="flex gap-1.5 flex-wrap">
                                            {playbook.document_sources.filter(source => source.exists).slice(0, 6).map(source => (
                                                <Badge key={source.relative_path} variant="info" size="sm">{source.title}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                    {playbook.asset_checks && playbook.asset_checks.length > 0 && (
                                        <div>
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Asset checks</p>
                                            <div className="flex gap-1.5 flex-wrap">
                                                {playbook.asset_checks.map(check => (
                                                    <Badge key={check.check_id} variant={playbookCheckVariant(check.status)} size="sm">
                                                        {check.label}:{typeof check.value === 'number' ? check.value : String(check.value)}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {playbook.mapping_summary && (
                                        <div className="grid sm:grid-cols-2 gap-2">
                                            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/40 p-2.5">
                                                <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Mapping summary</p>
                                                <div className="flex gap-1.5 flex-wrap">
                                                    <Badge variant="neutral" size="sm">Modules {playbook.mapping_summary.module_count}</Badge>
                                                    <Badge variant="neutral" size="sm">Pages {playbook.mapping_summary.total_pages}</Badge>
                                                    <Badge variant="success" size="sm">Mapped {playbook.mapping_summary.mapped_pages}</Badge>
                                                    <Badge variant="warning" size="sm">Critical gaps {playbook.mapping_summary.critical_missing_pages}</Badge>
                                                </div>
                                            </div>
                                            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/40 p-2.5">
                                                <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Prototype assets</p>
                                                <div className="flex gap-1.5 flex-wrap">
                                                    {(playbook.prototype_assets || []).slice(0, 2).map(asset => (
                                                        <Badge key={asset.asset_id} variant={asset.exists ? 'success' : 'warning'} size="sm">
                                                            {asset.title}:{asset.file_count ?? 0}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                    {playbook.page_mappings && playbook.page_mappings.length > 0 && (
                                        <div>
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Page mapping examples</p>
                                            <div className="grid gap-2">
                                                {playbook.page_mappings.slice(0, 6).map(mapping => {
                                                    const statusMeta = mappingStatusMeta(mapping.mapping_status);
                                                    return (
                                                        <div key={mapping.mapping_id} className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/40 p-2.5">
                                                            <div className="flex items-start justify-between gap-2">
                                                                <div>
                                                                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                                                                        {mapping.module_name} / {mapping.page_name}
                                                                    </p>
                                                                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                                                                        {mapping.route || "No route"} · {mapping.page_type}
                                                                    </p>
                                                                </div>
                                                                <div className="flex gap-1.5 flex-wrap justify-end">
                                                                    {mapping.critical && <Badge variant="warning" size="sm">Critical pages</Badge>}
                                                                    {mapping.baseline_candidate && <Badge variant="info" size="sm">Baseline candidate</Badge>}
                                                                    <Badge variant={statusMeta.variant} size="sm">{statusMeta.label}</Badge>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        <input
                            type="text"
                            value={title}
                            onChange={e => setTitle(e.target.value)}
                            placeholder={"Document title"}
                            className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-violet-500/30"
                        />

                        {/* File Upload Area */}
                        <div
                            onDragOver={e => { e.preventDefault(); setIsDragOver(true); }}
                            onDragLeave={() => setIsDragOver(false)}
                            onDrop={handleDrop}
                            onClick={() => fileRef.current?.click()}
                            className={`border-2 border-dashed rounded-lg p-3 text-center cursor-pointer transition-all ${isDragOver
                                ? 'border-violet-400 bg-violet-50 dark:bg-violet-900/20'
                                : uploadedFile
                                    ? 'border-emerald-300 bg-emerald-50 dark:bg-emerald-900/10'
                                    : 'border-slate-200 dark:border-slate-700 hover:border-violet-300 bg-slate-50/50 dark:bg-slate-800/50'
                                }`}
                        >
                            <input
                                ref={fileRef}
                                type="file"
                                accept={DOCUMENT_ACCEPT}
                                className="hidden"
                                onChange={e => { const f = e.target.files?.[0]; if (f) void readFile(f); }}
                            />
                            {uploadedFile ? (
                                <div className="flex items-center justify-center gap-2">
                                    <FileUp className="w-4 h-4 text-emerald-500" />
                                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                                        {uploading ? `Parsing: ${uploadedFile.name}` : uploadedFile.name}
                                    </span>
                                    <span className="text-[10px] text-slate-400">({(uploadedFile.size / 1024).toFixed(1)} KB)</span>
                                    <button onClick={e => { e.stopPropagation(); clearFile(); }}
                                        className="p-0.5 hover:bg-red-100 dark:hover:bg-red-900/20 rounded transition">
                                        <X className="w-3 h-3 text-red-500" />
                                    </button>
                                </div>
                            ) : (
                                <div>
                                    <FileUp className="w-5 h-5 text-slate-400 mx-auto mb-1" />
                                    <p className="text-[11px] text-slate-400">Drop a file here or click to browse</p>
                                    <p className="text-[10px] text-slate-300 dark:text-slate-500">Supports .md, .txt, .docx, .pdf, .json, .sql, .yaml, and .yml with automatic text extraction</p>
                                </div>
                            )}
                        </div>

                        <textarea
                            value={content}
                            onChange={e => setContent(e.target.value)}
                            rows={16}
                            placeholder={"Paste PRD or requirements document content..."}
                            className="w-full text-xs leading-relaxed rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2.5 outline-none focus:ring-2 focus:ring-violet-500/30 resize-none font-mono"
                        />

                        <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3 space-y-3">
                            <div className="flex items-center justify-between">
                                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Reference documents (optional)
                                </h4>
                                <div className="flex items-center gap-2">
                                    <Badge variant="neutral" size="sm">Cross-check</Badge>
                                    <button
                                        type="button"
                                        onClick={addReference}
                                        className="text-[11px] font-medium text-violet-600 hover:text-violet-500 dark:text-violet-300 dark:hover:text-violet-200"
                                    >
                                        Add reference document
                                    </button>
                                </div>
                            </div>
                            <div className="space-y-3">
                                {references.map((reference, index) => (
                                    <div key={reference.id} className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3 space-y-2.5">
                                        <div className="flex items-center justify-between gap-3">
                                            <div>
                                                <p className="text-xs font-semibold text-slate-600 dark:text-slate-200">
                                                    Reference document {index + 1}
                                                </p>
                                                <p className="text-[11px] text-slate-400">
                                                    Upload or paste development documents, OpenAPI specifications, database designs, and similar content
                                                </p>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {reference.uploadedFilename && (
                                                    <Badge variant="info" size="sm">{reference.uploadedFilename}</Badge>
                                                )}
                                                <button
                                                    type="button"
                                                    onClick={() => removeReference(reference.id)}
                                                    className="p-1 rounded transition hover:bg-red-100 dark:hover:bg-red-900/20"
                                                    aria-label={`Remove reference document ${index + 1}`}
                                                >
                                                    <X className="w-3.5 h-3.5 text-red-500" />
                                                </button>
                                            </div>
                                        </div>
                                        <input
                                            type="text"
                                            value={reference.title}
                                            onChange={e => updateReference(reference.id, { title: e.target.value })}
                                            placeholder={"Reference document title"}
                                            className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 outline-none focus:ring-2 focus:ring-violet-500/30"
                                        />
                                        <label className="flex items-center justify-between rounded-lg border border-dashed border-slate-200 dark:border-slate-700 px-3 py-2 text-xs text-slate-500 hover:border-violet-300 dark:hover:border-violet-500 cursor-pointer transition">
                                            <span className="flex items-center gap-2">
                                                <FileUp className="w-3.5 h-3.5 text-violet-500" />
                                                {reference.uploading ? "Extracting reference document..." : "Upload reference document"}
                                            </span>
                                            <span className="text-[10px] text-slate-400">Supports {DOCUMENT_ACCEPT}</span>
                                            <input
                                                type="file"
                                                accept={DOCUMENT_ACCEPT}
                                                className="hidden"
                                                onChange={e => {
                                                    const file = e.target.files?.[0];
                                                    if (file) void readReferenceFile(reference.id, file);
                                                }}
                                            />
                                        </label>
                                        <textarea
                                            value={reference.content}
                                            onChange={e => updateReference(reference.id, { content: e.target.value })}
                                            rows={6}
                                            placeholder={"Paste development documents, OpenAPI specifications, or database designs to cross-check against the primary document"}
                                            className="w-full text-xs leading-relaxed rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2.5 outline-none focus:ring-2 focus:ring-violet-500/30 resize-none font-mono"
                                        />
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="grid grid-cols-3 gap-2">
                            <button
                                onClick={handleParse}
                                disabled={parsing || uploading || hasReferenceUploading || workflowRunning || !content.trim()}
                                className="flex items-center justify-center gap-2 rounded-lg bg-violet-500 hover:bg-violet-600 text-white text-xs font-medium py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {parsing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                                {parsing ? "Checking..." : "Check document"}
                            </button>
                            <button
                                onClick={handleGenerate}
                                disabled={generating || uploading || hasReferenceUploading || workflowRunning || !content.trim()}
                                className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-medium py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {generating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <ClipboardList className="w-3.5 h-3.5" />}
                                {generating ? "Generating..." : "Generate test cases"}
                            </button>
                            <button
                                onClick={handleAnalyzeAndGenerate}
                                disabled={parsing || generating || uploading || hasReferenceUploading || workflowRunning || !content.trim()}
                                className="flex items-center justify-center gap-2 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white text-white text-xs font-medium py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {workflowRunning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                                {workflowRunning ? "Processing..." : "Check, then generate"}
                            </button>
                        </div>
                    </div>
                </div>

                {/* ── Right: Results ── */}
                <div className="lg:col-span-3 space-y-4">
                    {/* Summary */}
                    {result && (
                        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">{result.title}</h3>
                                <div className="flex items-center gap-2">
                                    <Badge variant="neutral" size="sm">{result.analysis.document_label}</Badge>
                                    <Badge variant="info" size="sm">{result.rules_count} rules</Badge>
                                    <Badge variant="success" size="sm">{result.test_cases_count} test cases</Badge>
                                    {result.references_analysis && result.references_analysis.length > 0 && (
                                        <Badge variant="warning" size="sm">{result.references_analysis.length} reference documents</Badge>
                                    )}
                                    <Badge variant={result.confidence > 0.7 ? 'success' : 'warning'} size="sm">
                                        Confidence {Math.round(result.confidence * 100)}%
                                    </Badge>
                                </div>
                            </div>
                            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{result.summary}</p>
                        </div>
                    )}

                    {/* Tabs */}
                    {(result || execTests.length > 0) && (
                        <Tabs
                            activeKey={activeTab}
                            onChange={setActiveTab}
                            items={[
                                { key: 'analysis', label: "Check document", content: <></> },
                                { key: 'rules', label: `Business rules (${result?.rules_count || 0})`, content: <></> },
                                { key: 'cases', label: `Test cases (${result?.test_cases_count || 0})`, content: <></> },
                                { key: 'executable', label: `Executable test cases (${execTests.length})`, content: <></> },
                            ]}
                            variant="underline"
                        />
                    )}

                    {activeTab === 'analysis' && result && (
                        <div className="space-y-4">
                            <div className="grid md:grid-cols-3 gap-3">
                                <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Completeness</p>
                                    <p className={`text-2xl font-semibold ${scoreTone(result.analysis.completeness_score)}`}>
                                        {Math.round(result.analysis.completeness_score * 100)}%
                                    </p>
                                </div>
                                <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Testability</p>
                                    <p className={`text-2xl font-semibold ${scoreTone(result.analysis.testability_score)}`}>
                                        {Math.round(result.analysis.testability_score * 100)}%
                                    </p>
                                </div>
                                <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                                    <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Overall quality</p>
                                    <p className={`text-2xl font-semibold ${scoreTone(result.analysis.quality_score)}`}>
                                        {Math.round(result.analysis.quality_score * 100)}%
                                    </p>
                                </div>
                            </div>

                            <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                                <div className="flex items-center justify-between">
                                    <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Findings</h4>
                                    <div className="flex gap-2 flex-wrap">
                                        {result.analysis.recommended_test_types.map(item => (
                                            <Badge key={item} variant="info" size="sm">{item}</Badge>
                                        ))}
                                    </div>
                                </div>
                                {result.analysis.issues.length > 0 ? (
                                    <div className="space-y-2">
                                        {result.analysis.issues.map(issue => (
                                            <div key={issue.issue_id} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/50 p-3">
                                                <div className="flex items-center gap-2 mb-1">
                                                    {severityBadge(issue.severity)}
                                                    <Badge variant="neutral" size="sm">{issue.category}</Badge>
                                                </div>
                                                <p className="text-sm text-slate-700 dark:text-slate-200">{issue.message}</p>
                                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Suggestion: {issue.suggestion}</p>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="rounded-lg border border-emerald-200 bg-emerald-50/80 dark:border-emerald-800/50 dark:bg-emerald-900/10 p-3 text-sm text-emerald-700 dark:text-emerald-300">
                                        No obvious structural gaps were found. You can generate test cases directly.
                                    </div>
                                )}
                            </div>

                            {result.bundle_analysis && (
                                <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Cross-check</h4>
                                        <div className="flex gap-2 flex-wrap">
                                            {result.bundle_analysis.involved_document_types.map(type => (
                                                <Badge key={type} variant="neutral" size="sm">{type}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="grid md:grid-cols-2 gap-3">
                                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Coverage</p>
                                            <p className={`text-2xl font-semibold ${scoreTone(result.bundle_analysis.coverage_score)}`}>
                                                {Math.round(result.bundle_analysis.coverage_score * 100)}%
                                            </p>
                                        </div>
                                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-1">Consistency</p>
                                            <p className={`text-2xl font-semibold ${scoreTone(result.bundle_analysis.consistency_score)}`}>
                                                {Math.round(result.bundle_analysis.consistency_score * 100)}%
                                            </p>
                                        </div>
                                    </div>
                                    <div className="grid md:grid-cols-2 gap-3">
                                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-2">Signal alignment</p>
                                            <div className="flex gap-1.5 flex-wrap">
                                                {Object.entries(result.bundle_analysis.aligned_signals).map(([type, count]) => (
                                                    <Badge key={type} variant="neutral" size="sm">
                                                        {(analysisGroupLabels[type] || type)}:{count}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-2">Not covered</p>
                                            <div className="flex gap-1.5 flex-wrap">
                                                {Object.entries(result.bundle_analysis.uncovered_signals).map(([type, count]) => (
                                                    <Badge key={type} variant={count > 0 ? 'warning' : 'neutral'} size="sm">
                                                        {(analysisGroupLabels[type] || type)}:{count}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                    {result.bundle_analysis.findings.length > 0 && (
                                        <div className="space-y-2">
                                            {result.bundle_analysis.findings.map(finding => (
                                                <div key={finding.finding_id} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/50 p-3">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        {severityBadge(finding.severity)}
                                                        <Badge variant="neutral" size="sm">{finding.category}</Badge>
                                                    </div>
                                                    <p className="text-sm text-slate-700 dark:text-slate-200">{finding.message}</p>
                                                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Suggestion: {finding.suggestion}</p>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {result.bundle_analysis.recommended_actions.length > 0 && (
                                        <div className="rounded-lg border border-indigo-200 dark:border-indigo-800/50 bg-indigo-50/70 dark:bg-indigo-900/10 p-3">
                                            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-500 mb-2">Combined recommendations</p>
                                            <ul className="space-y-1">
                                                {result.bundle_analysis.recommended_actions.map(action => (
                                                    <li key={action} className="text-sm text-slate-600 dark:text-slate-300 flex items-start gap-2">
                                                        <ChevronRight className="w-3 h-3 mt-1 text-indigo-500 shrink-0" />
                                                        {action}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            )}

                            {result.references_analysis && result.references_analysis.length > 0 && (
                                <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Reference document analysis</h4>
                                        <Badge variant="info" size="sm">{result.references_analysis.length} documents</Badge>
                                    </div>
                                    <div className="grid gap-3">
                                        {result.references_analysis.map(reference => {
                                            const extractedEntries = Object.entries(reference.analysis.extracted)
                                                .filter(([, items]) => (items ?? []).length > 0)
                                                .slice(0, 4);
                                            return (
                                                <div key={reference.title} className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3 space-y-2">
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div>
                                                            <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{reference.title}</p>
                                                            <div className="flex gap-1.5 flex-wrap mt-1">
                                                                <Badge variant="neutral" size="sm">{reference.document_label}</Badge>
                                                                <Badge variant="neutral" size="sm">{reference.document_type}</Badge>
                                                            </div>
                                                        </div>
                                                        <div className="flex gap-1.5 flex-wrap justify-end">
                                                            <Badge variant="neutral" size="sm">Completeness {Math.round(reference.analysis.completeness_score * 100)}%</Badge>
                                                            <Badge variant="neutral" size="sm">Testability {Math.round(reference.analysis.testability_score * 100)}%</Badge>
                                                        </div>
                                                    </div>
                                                    {reference.analysis.recommended_test_types.length > 0 && (
                                                        <div className="flex gap-1.5 flex-wrap">
                                                            {reference.analysis.recommended_test_types.slice(0, 5).map(item => (
                                                                <Badge key={item} variant="info" size="sm">{item}</Badge>
                                                            ))}
                                                        </div>
                                                    )}
                                                    {extractedEntries.length > 0 && (
                                                        <div className="flex gap-1.5 flex-wrap">
                                                            {extractedEntries.map(([key, items]) => (
                                                                <Badge key={`${reference.title}-${key}`} variant="neutral" size="sm">
                                                                    {(analysisGroupLabels[key] || key)}:{(items ?? []).length}
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    )}
                                                    {reference.analysis.issues.length > 0 && (
                                                        <p className="text-xs text-slate-500 dark:text-slate-400">
                                                            Found {reference.analysis.issues.length} issues. First suggestion: {reference.analysis.issues[0].suggestion}
                                                        </p>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                                <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Structured extraction</h4>
                                <div className="grid md:grid-cols-2 gap-3">
                                    {Object.entries(result.analysis.extracted).map(([key, items]) => (
                                        <div key={key} className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            {(() => {
                                                const normalizedItems = items ?? [];
                                                return (
                                                    <>
                                                        <div className="flex items-center justify-between mb-2">
                                                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                                                                {analysisGroupLabels[key] || key}
                                                            </span>
                                                            <Badge variant="neutral" size="sm">{normalizedItems.length}</Badge>
                                                        </div>
                                                        {normalizedItems.length > 0 ? (
                                                            <div className="flex gap-1.5 flex-wrap">
                                                                {normalizedItems.slice(0, 6).map(item => (
                                                                    <Badge key={item} variant="info" size="sm">{item}</Badge>
                                                                ))}
                                                                {normalizedItems.length > 6 && <span className="text-xs text-slate-400">+{normalizedItems.length - 6}</span>}
                                                            </div>
                                                        ) : (
                                                            <p className="text-xs text-slate-400">Unrecognized</p>
                                                        )}
                                                    </>
                                                );
                                            })()}
                                        </div>
                                    ))}
                                </div>
                                {result.analysis.next_actions.length > 0 && (
                                    <div className="mt-4 rounded-lg border border-indigo-200 dark:border-indigo-800/50 bg-indigo-50/70 dark:bg-indigo-900/10 p-3">
                                        <p className="text-xs font-semibold uppercase tracking-wide text-indigo-500 mb-2">Suggested next step</p>
                                        <ul className="space-y-1">
                                            {result.analysis.next_actions.map(action => (
                                                <li key={action} className="text-sm text-slate-600 dark:text-slate-300 flex items-start gap-2">
                                                    <ChevronRight className="w-3 h-3 mt-1 text-indigo-500 shrink-0" />
                                                    {action}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Rules Tab */}
                    {activeTab === 'rules' && result && (
                        <div className="space-y-2">
                            {result.rules.map(rule => (
                                <div key={rule.rule_id} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3 flex items-start gap-3 hover:shadow-sm transition-shadow">
                                    <div className="mt-0.5">{ruleTypeIcon(rule.type)}</div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <code className="text-[10px] text-slate-400 font-mono">{rule.rule_id}</code>
                                            <Badge variant="neutral" size="sm">{rule.type}</Badge>
                                            {priorityBadge(rule.priority)}
                                        </div>
                                        <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">{rule.description}</p>
                                    </div>
                                </div>
                            ))}
                            {result.rules.length === 0 && (
                                <p className="text-center text-sm text-slate-400 py-8">No business rules detected</p>
                            )}
                        </div>
                    )}

                    {/* Test Cases Tab */}
                    {activeTab === 'cases' && result && (
                        <div className="space-y-2">
                            {result.test_cases.map(tc => (
                                <div key={tc.case_id} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">
                                    <div className="flex items-center gap-2 mb-2">
                                        <code className="text-[10px] text-slate-400 font-mono">{tc.case_id}</code>
                                        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{tc.title}</span>
                                        <Badge variant="neutral" size="sm">{tc.test_type}</Badge>
                                        {priorityBadge(tc.priority)}
                                    </div>
                                    <div className="grid md:grid-cols-2 gap-3">
                                        <div>
                                            <p className="text-[10px] font-semibold uppercase text-slate-400 mb-1">Test steps</p>
                                            <ol className="text-xs text-slate-600 dark:text-slate-300 space-y-0.5 list-decimal list-inside">
                                                {tc.steps.map((s, i) => <li key={i}>{s}</li>)}
                                            </ol>
                                        </div>
                                        <div>
                                            <p className="text-[10px] font-semibold uppercase text-slate-400 mb-1">Expected result</p>
                                            <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-0.5">
                                                {tc.expected_results.map((r, i) => (
                                                    <li key={i} className="flex items-start gap-1">
                                                        <ChevronRight className="w-3 h-3 mt-0.5 text-emerald-500 shrink-0" />{r}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {result.test_cases.length === 0 && (
                                <p className="text-center text-sm text-slate-400 py-8">No test cases generated</p>
                            )}
                        </div>
                    )}

                    {/* Executable Tests Tab */}
                    {activeTab === 'executable' && (
                        <div className="space-y-2">
                            {generationSummary && (
                                <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                                    <div className="flex items-center justify-between gap-3">
                                        <div>
                                            <p className="text-xs uppercase tracking-wide text-slate-400">Generation strategy</p>
                                            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                                                {generationSummary.strategy_label}
                                            </h4>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {typeof generationSummary.bundle_findings_count === 'number' && generationSummary.bundle_findings_count > 0 && (
                                                <Badge variant="warning" size="sm">Cross-check findings {generationSummary.bundle_findings_count}</Badge>
                                            )}
                                            <Badge variant="success" size="sm">{generationSummary.generated_count} entries</Badge>
                                        </div>
                                    </div>
                                    <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                                        {generationSummary.rationale}
                                    </p>
                                    <div className="flex gap-2 flex-wrap">
                                        {generationSummary.focus_areas.map(area => (
                                            <Badge key={area} variant="info" size="sm">{generationTypeLabels[area] || area}</Badge>
                                        ))}
                                    </div>
                                    <div className="grid md:grid-cols-2 gap-3">
                                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-2">Test case distribution</p>
                                            <div className="flex gap-1.5 flex-wrap">
                                                {Object.entries(generationSummary.counts_by_type).map(([type, count]) => (
                                                    <Badge key={type} variant="neutral" size="sm">
                                                        {(generationTypeLabels[type] || type)}:{count}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-2">Generation source</p>
                                            <div className="flex gap-1.5 flex-wrap">
                                                {Object.entries(generationSummary.counts_by_origin || {}).map(([origin, count]) => (
                                                    <Badge key={origin} variant={documentRoleVariants[origin] || 'neutral'} size="sm">
                                                        {(documentRoleLabels[origin] || origin)}:{count}
                                                    </Badge>
                                                ))}
                                                {(!generationSummary.counts_by_origin || Object.keys(generationSummary.counts_by_origin).length === 0) && (
                                                    <Badge variant="neutral" size="sm">Primary document: {generationSummary.generated_count}</Badge>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    {generationSummary.document_sources && generationSummary.document_sources.length > 0 && (
                                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-2">Document source</p>
                                            <div className="grid md:grid-cols-2 gap-2">
                                                {generationSummary.document_sources.map(source => (
                                                    <div key={`${source.title}-${source.document_role}`} className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/40 p-2.5">
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <Badge variant={documentRoleVariants[source.document_role] || 'neutral'} size="sm">
                                                                {documentRoleLabels[source.document_role] || source.document_role}
                                                            </Badge>
                                                            <Badge variant="neutral" size="sm">{source.document_label}</Badge>
                                                        </div>
                                                        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{source.title}</p>
                                                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                                            Contributed {source.generated_count} test cases
                                                        </p>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    <div className="grid md:grid-cols-2 gap-3">
                                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 p-3">
                                            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-2">Traceability coverage</p>
                                            <div className="flex gap-1.5 flex-wrap">
                                                {Object.entries(generationSummary.traceability).map(([type, count]) => (
                                                    <Badge key={type} variant="neutral" size="sm">
                                                        {(analysisGroupLabels[type] || type)}:{count}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                            {execTests.map(t => (
                                <div key={t.id} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">
                                    <div className="flex items-center gap-2 mb-1.5">
                                        <code className="text-[10px] text-slate-400 font-mono">{t.id}</code>
                                        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{t.name}</span>
                                        <Badge variant="neutral" size="sm">{t.type}</Badge>
                                        {t.document_role && (
                                            <Badge variant={documentRoleVariants[t.document_role] || 'neutral'} size="sm">
                                                {documentRoleLabels[t.document_role] || t.document_role}
                                            </Badge>
                                        )}
                                        {priorityBadge(t.priority)}
                                    </div>
                                    {(t.document_title || t.document_label) && (
                                        <p className="text-[11px] text-slate-400 dark:text-slate-500 mb-1.5">
                                            Source: {t.document_title || "Unnamed document"}
                                            {t.document_label ? ` · ${t.document_label}` : ''}
                                        </p>
                                    )}
                                    <p className="text-xs text-slate-500 dark:text-slate-400 whitespace-pre-line leading-relaxed">{t.instruction}</p>
                                    {t.tags.length > 0 && (
                                        <div className="flex gap-1 mt-2 flex-wrap">
                                            {t.tags.map(tag => <Badge key={tag} variant="info" size="sm">{tag}</Badge>)}
                                        </div>
                                    )}
                                    {t.basis && t.basis.length > 0 && (
                                        <div className="mt-2">
                                            <p className="text-[10px] font-semibold uppercase text-slate-400 mb-1">Generation rationale</p>
                                            <div className="flex gap-1 flex-wrap">
                                                {t.basis.slice(0, 4).map(item => <Badge key={item} variant="neutral" size="sm">{item}</Badge>)}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                            {execTests.length === 0 && (
                                <p className="text-center text-sm text-slate-400 py-8">
                                    Click Generate test cases to create executable tests from the requirements document
                                </p>
                            )}
                        </div>
                    )}

                    {/* No Results */}
                    {!result && execTests.length === 0 && (
                        <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 p-12 text-center">
                            <Sparkles className="w-12 h-12 text-violet-300 dark:text-violet-600 mx-auto mb-3" />
                            <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Paste requirements or development documents and start checking</p>
                            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">AI checks document quality and testability before generating test cases</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default RequirementPage;
