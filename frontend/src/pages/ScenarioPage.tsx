import { useState, useEffect, useCallback } from 'react';
import {
    GitBranch, Plus, Play, Trash2, Edit3, Save, X,
    ArrowDown, Workflow,
    CheckCircle2, XCircle, AlertTriangle, Clock, RefreshCw, BookOpen,
} from '../components/icons';
import { API_BASE_URL } from '../config';

interface Step {
    id?: string;
    name: string;
    url: string;
    instruction: string;
    mode: string;
    timeout: number;
    on_failure: string;
}

interface Scenario {
    id: string;
    name: string;
    description: string;
    stepCount: number;
    status: string;
    tags: string[];
    updated_at: string;
}

interface ScenarioExecutionRow {
    status: string;
    step: string;
    duration_ms?: number;
}

interface ScenarioExecutionResult {
    status: string;
    total_steps: number;
    executed: number;
    passed: number;
    failed: number;
    results: ScenarioExecutionRow[];
}

interface ImportedScenarioSummary {
    id: string;
    name: string;
    stepCount: number;
    tags: string[];
}

interface ImportedScenarioResult {
    playbook_id: string;
    playbook_name?: string;
    playbook_title?: string;
    project_name?: string;
    imported_count: number;
    scenarios: ImportedScenarioSummary[];
}

const STATUS_MAP: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
    draft: { icon: <Edit3 className="w-3.5 h-3.5" />, label: "Draft", color: 'text-slate-500 bg-slate-100 dark:bg-slate-700' },
    completed: { icon: <CheckCircle2 className="w-3.5 h-3.5" />, label: "Passed", color: 'text-emerald-600 bg-emerald-100 dark:bg-emerald-500/20' },
    failed: { icon: <XCircle className="w-3.5 h-3.5" />, label: "Failed", color: 'text-red-600 bg-red-100 dark:bg-red-500/20' },
    running: { icon: <Clock className="w-3.5 h-3.5 animate-spin" />, label: "Running", color: 'text-blue-600 bg-blue-100 dark:bg-blue-500/20' },
};

const EMPTY_STEP: Step = { name: '', url: '', instruction: '', mode: 'smart', timeout: 60, on_failure: 'stop' };

const playbookSummaryText = (result: ImportedScenarioResult) => {
    if (result.playbook_id === 'sample-platform-prototype') {
        return `Imported ${result.imported_count} prototype scenarios covering login, 15 business modules, and cross-module workflows. Add the real environment details before running them.`;
    }
    return `Imported ${result.imported_count} scenarios covering Wave 0 through Wave 4. Run them individually or edit them first.`;
};

const ScenarioPage: React.FC = () => {
    const [scenarios, setScenarios] = useState<Scenario[]>([]);
    const [editing, setEditing] = useState<{ id?: string; name: string; description: string; steps: Step[]; tags: string } | null>(null);
    const [executing, setExecuting] = useState<string | null>(null);
    const [execResult, setExecResult] = useState<ScenarioExecutionResult | null>(null);
    const [importingPlaybook, setImportingPlaybook] = useState(false);
    const [importResult, setImportResult] = useState<ImportedScenarioResult | null>(null);

    const loadScenarios = useCallback(async () => {
        try {
            const resp = await fetch(`${API_BASE_URL}/api/scenarios`);
            const data = await resp.json();
            setScenarios(data.scenarios || []);
        } catch { /* ignore */ }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void loadScenarios();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [loadScenarios]);

    const startCreate = () => {
        setEditing({
            name: '', description: '', tags: '',
            steps: [{ ...EMPTY_STEP, name: "Step 1" }],
        });
        setExecResult(null);
    };

    const saveScenario = async () => {
        if (!editing || !editing.name.trim()) return;
        const body = {
            name: editing.name,
            description: editing.description,
            steps: editing.steps,
            tags: editing.tags.split(',').map(t => t.trim()).filter(Boolean),
        };
        const method = editing.id ? 'PUT' : 'POST';
        const url = editing.id ? `${API_BASE_URL}/api/scenarios/${editing.id}` : `${API_BASE_URL}/api/scenarios`;
        await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        setEditing(null);
        loadScenarios();
    };

    const deleteScenario = async (id: string) => {
        await fetch(`${API_BASE_URL}/api/scenarios/${id}`, { method: 'DELETE' });
        loadScenarios();
    };

    const executeScenario = async (id: string) => {
        setExecuting(id);
        setExecResult(null);
        try {
            const resp = await fetch(`${API_BASE_URL}/api/scenarios/${id}/execute`, { method: 'POST' });
            const data = await resp.json();
            setExecResult(data as ScenarioExecutionResult);
        } catch { /* ignore */ }
        setExecuting(null);
        loadScenarios();
    };

    const editScenario = async (id: string) => {
        const resp = await fetch(`${API_BASE_URL}/api/scenarios/${id}`);
        const data = await resp.json();
        setEditing({
            id: data.id,
            name: data.name,
            description: data.description,
            steps: data.steps || [],
            tags: (data.tags || []).join(', '),
        });
    };

    const addStep = () => {
        if (!editing) return;
        setEditing({
            ...editing,
            steps: [...editing.steps, { ...EMPTY_STEP, name: `Step ${editing.steps.length + 1}` }],
        });
    };

    const removeStep = (i: number) => {
        if (!editing) return;
        setEditing({ ...editing, steps: editing.steps.filter((_, idx) => idx !== i) });
    };

    const updateStep = <K extends keyof Step>(i: number, field: K, value: Step[K]) => {
        if (!editing) return;
        const updated = [...editing.steps];
        updated[i] = { ...updated[i], [field]: value };
        setEditing({ ...editing, steps: updated });
    };

    const importPlaybook = async (playbookId: string) => {
        setImportingPlaybook(true);
        try {
            const resp = await fetch(`${API_BASE_URL}/api/scenarios/import-playbook/${playbookId}`, {
                method: 'POST',
            });
            const data = await resp.json();
            setImportResult({
                playbook_id: data.playbook_id,
                playbook_name: data.playbook_name,
                playbook_title: data.playbook_title,
                project_name: data.project_name,
                imported_count: data.imported_count || 0,
                scenarios: data.scenarios || [],
            });
            setExecResult(null);
            await loadScenarios();
        } catch {
            setImportResult(null);
        }
        setImportingPlaybook(false);
    };

    return (
        <div className="space-y-6">
            {/* Title*/}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 text-white">
                            <Workflow className="w-5 h-5" />
                        </div>
                        E2E scenario chains
                    </h2>
                    <p className="text-slate-500 mt-2 text-sm">Connect multiple test steps to build end-to-end scenarios</p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => void importPlaybook('sample-first-regression')}
                        disabled={importingPlaybook}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl border border-violet-200 bg-violet-50 text-violet-700 text-sm font-medium transition-all hover:bg-violet-100 disabled:opacity-50 dark:border-violet-800/50 dark:bg-violet-900/20 dark:text-violet-200 dark:hover:bg-violet-900/30"
                    >
                        {importingPlaybook ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
                        {importingPlaybook ? "Importing..." : "Import sample project scenarios"}
                    </button>
                    <button
                        onClick={() => void importPlaybook('sample-platform-prototype')}
                        disabled={importingPlaybook}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl border border-blue-200 bg-blue-50 text-blue-700 text-sm font-medium transition-all hover:bg-blue-100 disabled:opacity-50 dark:border-blue-800/50 dark:bg-blue-900/20 dark:text-blue-200 dark:hover:bg-blue-900/30"
                    >
                        {importingPlaybook ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BookOpen className="w-4 h-4" />}
                        {importingPlaybook ? "Importing..." : "Import platform prototype scenarios"}
                    </button>
                    <button onClick={startCreate} className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white rounded-xl text-sm font-medium shadow-md hover:shadow-lg active:scale-[0.98] transition-all">
                        <Plus className="w-4 h-4" /> New scenario
                    </button>
                </div>
            </div>

            {importResult && importResult.scenarios.length > 0 && (
                <div className="rounded-2xl border border-violet-200 bg-violet-50/70 p-5 dark:border-violet-800/50 dark:bg-violet-900/10">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-xs uppercase tracking-wide text-violet-500">Project scenario package</p>
                            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
                                {importResult.playbook_title || importResult.playbook_name || importResult.project_name || "Project scenario package"}
                            </h3>
                            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                {playbookSummaryText(importResult)}
                            </p>
                        </div>
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-violet-700 shadow-sm dark:bg-slate-800 dark:text-violet-200">
                            Naming convention: [role]-[module]-[scenario]-[environment]
                        </span>
                    </div>
                    <div className="mt-4 grid gap-2 md:grid-cols-2">
                        {importResult.scenarios.map(item => (
                            <div key={item.id} className="rounded-xl border border-violet-100 bg-white/80 p-3 dark:border-violet-900/40 dark:bg-slate-800/60">
                                <div className="flex items-center justify-between gap-3">
                                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{item.name}</p>
                                    <span className="text-xs text-slate-400">{item.stepCount} steps</span>
                                </div>
                                <div className="mt-2 flex gap-1.5 flex-wrap">
                                    {item.tags.map(tag => (
                                        <span key={`${item.id}-${tag}`} className="px-2 py-0.5 rounded-full bg-violet-100 text-[11px] text-violet-700 dark:bg-violet-900/30 dark:text-violet-200">
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Editor*/}
            {editing && (
                <div className="rounded-2xl border-2 border-violet-300 dark:border-violet-500/40 bg-white dark:bg-slate-800 p-6 space-y-4 shadow-lg">
                    <div className="flex items-center justify-between">
                        <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
                            {editing.id ? "Edit scenario" : "New scenario"}
                        </h3>
                        <div className="flex gap-2">
                            <button onClick={() => setEditing(null)} className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400">
                                <X className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={saveScenario} className="px-4 py-1.5 text-xs bg-violet-500 text-white rounded-lg hover:bg-violet-600 flex items-center gap-1">
                                <Save className="w-3.5 h-3.5" /> Save
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs text-slate-500 mb-1 block">Scenario name *</label>
                            <input value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })}
                                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200"
                                placeholder={"Example: Complete login and checkout workflow"} />
                        </div>
                        <div>
                            <label className="text-xs text-slate-500 mb-1 block">Tags (comma-separated)</label>
                            <input value={editing.tags} onChange={e => setEditing({ ...editing, tags: e.target.value })}
                                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200"
                                placeholder={"regression, smoke, P0"} />
                        </div>
                    </div>
                    <div>
                        <label className="text-xs text-slate-500 mb-1 block">Description</label>
                        <input value={editing.description} onChange={e => setEditing({ ...editing, description: e.target.value })}
                            className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200"
                            placeholder={"Scenario description..."} />
                    </div>

                    {/* Step list*/}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase">Test steps ( {editing.steps.length})</span>
                            <button onClick={addStep} className="text-xs text-violet-500 hover:text-violet-600 flex items-center gap-1">
                                <Plus className="w-3 h-3" /> Add step
                            </button>
                        </div>

                        {editing.steps.map((step, i) => (
                            <div key={i} className="relative border border-slate-200 dark:border-slate-600 rounded-xl p-4 bg-slate-50/50 dark:bg-slate-700/30">
                                {i > 0 && (
                                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                                        <ArrowDown className="w-4 h-4 text-violet-400" />
                                    </div>
                                )}
                                <div className="flex items-center gap-2 mb-3">
                                    <span className="w-6 h-6 rounded-full bg-violet-100 dark:bg-violet-500/20 text-violet-600 dark:text-violet-400 text-xs font-bold flex items-center justify-center">{i + 1}</span>
                                    <input value={step.name} onChange={e => updateStep(i, 'name', e.target.value)}
                                        className="flex-1 px-2 py-1 text-sm rounded border border-transparent focus:border-violet-300 bg-transparent text-slate-800 dark:text-slate-200 font-medium"
                                        placeholder={"Step name"} />
                                    <select value={step.on_failure} onChange={e => updateStep(i, 'on_failure', e.target.value)}
                                        className="px-2 py-1 text-[11px] rounded border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-400">
                                        <option value="stop">Stop on failure</option>
                                        <option value="skip">Skip remaining steps</option>
                                        <option value="continue">Continue</option>
                                    </select>
                                    {editing.steps.length > 1 && (
                                        <button onClick={() => removeStep(i)} className="text-red-400 hover:text-red-500">
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    )}
                                </div>
                                <div className="grid grid-cols-3 gap-3">
                                    <input value={step.url} onChange={e => updateStep(i, 'url', e.target.value)}
                                        className="px-2 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-300"
                                        placeholder={"Target URL"} />
                                    <input value={step.instruction} onChange={e => updateStep(i, 'instruction', e.target.value)}
                                        className="col-span-2 px-2 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-300"
                                        placeholder={"Test instruction, such as 'Search for AI and verify the results'"} />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/*Scenario list*/}
            {scenarios.length === 0 && !editing ? (
                <div className="text-center py-16 text-slate-400">
                    <GitBranch className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="text-sm">No scenarios yet. Click "New scenario" to get started.</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {scenarios.map(sc => {
                        const st = STATUS_MAP[sc.status] || STATUS_MAP.draft;
                        return (
                            <div key={sc.id} className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm p-4 dark:border-slate-700/60 dark:bg-slate-800/60 hover:shadow-md transition-shadow">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <span className={`flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full font-medium ${st.color}`}>
                                            {st.icon} {st.label}
                                        </span>
                                        <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{sc.name}</h4>
                                        <span className="text-xs text-slate-400">{sc.stepCount} steps</span>
                                        {sc.tags.map(t => (
                                            <span key={t} className="px-1.5 py-0.5 text-[10px] rounded bg-slate-100 dark:bg-slate-700 text-slate-500">{t}</span>
                                        ))}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-[11px] text-slate-400">{sc.updated_at?.slice(0, 16)}</span>
                                        <button onClick={() => editScenario(sc.id)} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600">
                                            <Edit3 className="w-3.5 h-3.5" />
                                        </button>
                                        <button
                                            onClick={() => executeScenario(sc.id)}
                                            disabled={executing === sc.id}
                                            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-violet-500 text-white rounded-lg hover:bg-violet-600 disabled:opacity-50 transition-all"
                                        >
                                            <Play className="w-3 h-3" /> {executing === sc.id ? "Running..." : "Run"}
                                        </button>
                                        <button onClick={() => deleteScenario(sc.id)} className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 text-slate-400 hover:text-red-500">
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </div>
                                {sc.description && (
                                    <p className="mt-2 text-xs text-slate-500 pl-[4.5rem]">{sc.description}</p>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/*Execution results*/}
            {execResult && (
                <div className={`rounded-2xl border p-5 ${execResult.status === 'completed' ? 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-500/30 dark:bg-emerald-500/5' : 'border-red-200 bg-red-50/50 dark:border-red-500/30 dark:bg-red-500/5'}`}>
                    <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                        {execResult.status === 'completed'
                            ? <><CheckCircle2 className="w-4 h-4 text-emerald-500" /> Scenario passed</>
                            : <><XCircle className="w-4 h-4 text-red-500" /> Scenario failed</>
                        }
                    </h4>
                    <div className="grid grid-cols-4 gap-3 mb-3">
                        {[
                            { label: "Total steps", value: execResult.total_steps },
                            { label: "Executed", value: execResult.executed },
                            { label: "Passed", value: execResult.passed },
                            { label: "Failed", value: execResult.failed },
                        ].map(m => (
                            <div key={m.label} className="text-center p-2 bg-white dark:bg-slate-800 rounded-lg">
                                <div className="text-lg font-bold text-slate-800 dark:text-slate-200">{String(m.value)}</div>
                                <div className="text-[11px] text-slate-500">{m.label}</div>
                            </div>
                        ))}
                    </div>
                    <div className="space-y-1.5">
                        {execResult.results.map((r, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs">
                                <span className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-[10px] font-bold text-slate-500">{i + 1}</span>
                                {r.status === 'passed' ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : r.status === 'skipped' ? <AlertTriangle className="w-3.5 h-3.5 text-amber-500" /> : <XCircle className="w-3.5 h-3.5 text-red-500" />}
                                <span className="text-slate-700 dark:text-slate-300 font-medium">{r.step}</span>
                                {r.duration_ms && <span className="text-slate-400 ml-auto">{String(r.duration_ms)}ms</span>}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ScenarioPage;
