import { useState, useEffect, useCallback } from 'react';
import {
    Eye, Upload, Trash2, Check, ImageIcon,
    ZoomIn, RefreshCw, Layers,
    CheckCircle2, XCircle,
} from '../components/icons';
import { API_BASE_URL } from '../config';
import { fetchRequirementPlaybook, type RequirementPlaybook } from '../services/requirementService';

interface Baseline {
    name: string;
    width: number;
    height: number;
    timestamp: string;
    size_bytes?: number;
}

interface CompareResult {
    result: string;
    diff_percentage: number;
    threshold: number;
    diff_image?: string;
    baseline_image?: string;
}

const VisualPage: React.FC = () => {
    const [baselines, setBaselines] = useState<Baseline[]>([]);
    const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
    const [comparing, setComparing] = useState(false);
    const [selectedName, setSelectedName] = useState('');
    const [threshold, setThreshold] = useState(0.01);
    const [uploadName, setUploadName] = useState('');
    const [viewMode, setViewMode] = useState<'side' | 'overlay' | 'diff'>('side');
    const [prototypeGuide, setPrototypeGuide] = useState<RequirementPlaybook | null>(null);
    const [loadingGuide, setLoadingGuide] = useState(false);

    const loadBaselines = useCallback(async () => {
        try {
            const resp = await fetch(`${API_BASE_URL}/api/visual/baselines`);
            const data = await resp.json();
            setBaselines(data.baselines || []);
        } catch { /* ignore */ }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void loadBaselines();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [loadBaselines]);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, mode: 'baseline' | 'compare') => {
        const file = e.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async () => {
            const base64 = (reader.result as string).split(',')[1];
            const name = uploadName || file.name.replace(/\.[^.]+$/, '');

            if (mode === 'baseline') {
                await fetch(`${API_BASE_URL}/api/visual/baselines`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, image_base64: base64 }),
                });
                loadBaselines();
                setUploadName('');
            } else {
                setComparing(true);
                try {
                    const resp = await fetch(`${API_BASE_URL}/api/visual/compare`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: selectedName, image_base64: base64, threshold }),
                    });
                    const data = await resp.json();
                    setCompareResult(data);
                } catch { /* ignore */ }
                setComparing(false);
            }
        };
        reader.readAsDataURL(file);
        e.target.value = '';
    };

    const deleteBaseline = async (name: string) => {
        await fetch(`${API_BASE_URL}/api/visual/baselines/${name}`, { method: 'DELETE' });
        loadBaselines();
    };

    const approveBaseline = async (name: string) => {
        await fetch(`${API_BASE_URL}/api/visual/baselines/${name}/approve`, { method: 'PUT' });
        loadBaselines();
        setCompareResult(null);
    };

    const loadPrototypeGuide = async () => {
        setLoadingGuide(true);
        try {
            const payload = await fetchRequirementPlaybook('sample-platform-prototype');
            setPrototypeGuide(payload);
        } catch { /* ignore */ }
        setLoadingGuide(false);
    };

    return (
        <div className="space-y-6">
            {/* Title*/}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-gradient-to-br from-pink-500 to-rose-600 text-white">
                            <Eye className="w-5 h-5" />
                        </div>
                        Visual regression testing
                    </h2>
                    <p className="text-slate-500 mt-2 text-sm">
                        Manage screenshot baselines, detect pixel differences, and approve or reject changes
                    </p>
                </div>
                <button
                    onClick={loadPrototypeGuide}
                    disabled={loadingGuide}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl border border-pink-200 bg-pink-50 text-pink-700 text-sm font-medium transition-all hover:bg-pink-100 disabled:opacity-50 dark:border-pink-800/50 dark:bg-pink-900/20 dark:text-pink-200 dark:hover:bg-pink-900/30"
                >
                    {loadingGuide ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
                    {loadingGuide ? "Loading..." : "Load platform baseline recommendations"}
                </button>
            </div>

            {prototypeGuide?.mapping_summary && (
                <div className="rounded-2xl border border-pink-200 bg-pink-50/70 p-5 dark:border-pink-800/50 dark:bg-pink-900/10">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <p className="text-xs uppercase tracking-wide text-pink-500">Prototype baseline recommendations</p>
                            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">{prototypeGuide.title}</h3>
                            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                Create visual baselines for list, detail, form, dashboard, and login pages first.
                            </p>
                        </div>
                        <div className="flex gap-2 flex-wrap justify-end">
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-pink-700 shadow-sm dark:bg-slate-800 dark:text-pink-200">
                                Candidates {prototypeGuide.mapping_summary.baseline_candidates}
                            </span>
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-pink-700 shadow-sm dark:bg-slate-800 dark:text-pink-200">
                                Mapped {prototypeGuide.mapping_summary.mapped_pages}/{prototypeGuide.mapping_summary.total_pages}
                            </span>
                        </div>
                    </div>
                    <div className="mt-4 grid gap-2 md:grid-cols-2">
                        {(prototypeGuide.page_mappings || [])
                            .filter(mapping => mapping.baseline_candidate)
                            .slice(0, 6)
                            .map(mapping => (
                                <div key={mapping.mapping_id} className="rounded-xl border border-pink-100 bg-white/80 p-3 dark:border-pink-900/40 dark:bg-slate-800/60">
                                    <div className="flex items-center justify-between gap-3">
                                        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                                            {mapping.module_name} / {mapping.page_name}
                                        </p>
                                        <span className={`text-[11px] ${mapping.prototype_source.exists ? 'text-emerald-500' : 'text-amber-500'}`}>
                                            {mapping.prototype_source.exists ? "Ready for a baseline" : "Awaiting prototype sync"}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                        {mapping.route || "No route"} · {mapping.page_type}
                                    </p>
                                </div>
                            ))}
                    </div>
                </div>
            )}

            {/* Upload and comparison areas*/}
            <div className="grid grid-cols-2 gap-4">
                {/* Upload a new baseline*/}
                <div className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm dark:border-slate-700/60 dark:bg-slate-800/60 p-5">
                    <h3 className="text-sm font-semibold mb-3 text-slate-700 dark:text-slate-300 flex items-center gap-2">
                        <Upload className="w-4 h-4 text-pink-500" /> Upload baseline
                    </h3>
                    <input value={uploadName} onChange={e => setUploadName(e.target.value)}
                        className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200 mb-3"
                        placeholder={"Baseline name (for example, homepage or login-form)"} />
                    <label className="flex items-center justify-center py-6 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl cursor-pointer hover:border-pink-400 hover:bg-pink-50/30 dark:hover:bg-pink-500/5 transition-colors">
                        <input type="file" accept="image/*" className="hidden" onChange={e => handleFileUpload(e, 'baseline')} />
                        <div className="text-center">
                            <ImageIcon className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                            <p className="text-xs text-slate-400">Drop a screenshot here or click to upload</p>
                        </div>
                    </label>
                </div>

                {/* Compare screenshots*/}
                <div className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm dark:border-slate-700/60 dark:bg-slate-800/60 p-5">
                    <h3 className="text-sm font-semibold mb-3 text-slate-700 dark:text-slate-300 flex items-center gap-2">
                        <Layers className="w-4 h-4 text-violet-500" /> Compare screenshots
                    </h3>
                    <div className="flex gap-3 mb-3">
                        <select value={selectedName} onChange={e => setSelectedName(e.target.value)}
                            className="flex-1 px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200">
                            <option value="">Select a baseline...</option>
                            {baselines.map(b => <option key={b.name} value={b.name}>{b.name} ({b.width}×{b.height})</option>)}
                        </select>
                        <div className="flex items-center gap-1">
                            <span className="text-[11px] text-slate-400">Threshold</span>
                            <input type="number" value={threshold} onChange={e => setThreshold(Number(e.target.value))}
                                step={0.01} min={0} max={1}
                                className="w-16 px-2 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200" />
                        </div>
                    </div>
                    <label className={`flex items-center justify-center py-6 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${selectedName ? 'border-violet-300 hover:border-violet-400 hover:bg-violet-50/30' : 'border-slate-200 opacity-50 cursor-not-allowed'}`}>
                        <input type="file" accept="image/*" className="hidden" disabled={!selectedName}
                            onChange={e => handleFileUpload(e, 'compare')} />
                        <div className="text-center">
                            {comparing ? (
                                <RefreshCw className="w-8 h-8 mx-auto text-violet-400 mb-2 animate-spin" />
                            ) : (
                                <ZoomIn className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                            )}
                            <p className="text-xs text-slate-400">{comparing ? "Comparing..." : "Upload a screenshot to compare"}</p>
                        </div>
                    </label>
                </div>
            </div>

            {/* Comparison results*/}
            {compareResult && (
                <div className={`rounded-2xl border p-5 ${compareResult.result === 'match' ? 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-500/30 dark:bg-emerald-500/5' : 'border-red-200 bg-red-50/50 dark:border-red-500/30 dark:bg-red-500/5'}`}>
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-semibold flex items-center gap-2">
                            {compareResult.result === 'match'
                                ? <><CheckCircle2 className="w-4 h-4 text-emerald-500" /> Visual match ✅</>
                                : <><XCircle className="w-4 h-4 text-red-500" /> Differences detected ( {(compareResult.diff_percentage * 100).toFixed(2)}%)</>
                            }
                        </h3>
                        <div className="flex items-center gap-3">
                            {/* View mode*/}
                            <div className="flex gap-1 bg-slate-100 dark:bg-slate-700 rounded-lg p-0.5">
                                {['side', 'diff'].map(m => (
                                    <button key={m} onClick={() => setViewMode(m as typeof viewMode)}
                                        className={`px-2 py-1 text-[11px] rounded ${viewMode === m ? 'bg-white dark:bg-slate-600 shadow text-slate-800 dark:text-white' : 'text-slate-500'}`}>
                                        {m === 'side' ? "Side-by-side comparison" : "Difference image"}
                                    </button>
                                ))}
                            </div>
                            {compareResult.result !== 'match' && (
                                <button onClick={() => approveBaseline(selectedName)}
                                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-emerald-500 text-white rounded-lg hover:bg-emerald-600">
                                    <Check className="w-3.5 h-3.5" /> Approve as new baseline
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Image comparison*/}
                    <div className="grid grid-cols-2 gap-4">
                        {viewMode === 'side' && (
                            <>
                                <div>
                                    <span className="text-[11px] text-slate-500 mb-1 block">📸 Baseline</span>
                                    {compareResult.baseline_image && (
                                        <img src={`data:image/png;base64,${compareResult.baseline_image}`}
                                            className="w-full rounded-lg border border-slate-200 dark:border-slate-600" alt="baseline" />
                                    )}
                                </div>
                                <div>
                                    <span className="text-[11px] text-slate-500 mb-1 block">🔄 Current</span>
                                    {compareResult.diff_image && (
                                        <img src={`data:image/png;base64,${compareResult.diff_image}`}
                                            className="w-full rounded-lg border border-red-200 dark:border-red-500/30" alt="diff" />
                                    )}
                                </div>
                            </>
                        )}
                        {viewMode === 'diff' && compareResult.diff_image && (
                            <div className="col-span-2">
                                <span className="text-[11px] text-slate-500 mb-1 block">🔴 Highlighted differences</span>
                                <img src={`data:image/png;base64,${compareResult.diff_image}`}
                                    className="w-full rounded-lg border border-red-200 dark:border-red-500/30" alt="diff overlay" />
                            </div>
                        )}
                    </div>

                    <div className="flex gap-4 mt-3 text-xs text-slate-500">
                        <span>Difference rate: <strong>{(compareResult.diff_percentage * 100).toFixed(2)}%</strong></span>
                        <span>Threshold: {(compareResult.threshold * 100).toFixed(1)}%</span>
                        <span>Result: {compareResult.result}</span>
                    </div>
                </div>
            )}

            {/* Baseline list*/}
            <div className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm dark:border-slate-700/60 dark:bg-slate-800/60">
                <div className="px-5 py-3 border-b border-slate-200 dark:border-slate-700">
                    <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                        Baseline library ( {baselines.length})
                    </h3>
                </div>
                {baselines.length === 0 ? (
                    <div className="text-center py-12 text-slate-400">
                        <Eye className="w-10 h-10 mx-auto mb-2 opacity-30" />
                        <p className="text-sm">No baselines yet. Upload a screenshot to create the first one.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 p-5">
                        {baselines.map(b => (
                            <div key={b.name} className="rounded-xl border border-slate-200 dark:border-slate-600 p-3 hover:shadow-md transition-shadow group">
                                <div className="aspect-video bg-slate-100 dark:bg-slate-700 rounded-lg flex items-center justify-center mb-2 overflow-hidden">
                                    <ImageIcon className="w-8 h-8 text-slate-300" />
                                </div>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 truncate">{b.name}</div>
                                        <div className="text-[10px] text-slate-400">{b.width}×{b.height} · {b.timestamp?.slice(0, 10)}</div>
                                    </div>
                                    <button onClick={() => deleteBaseline(b.name)} className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 dark:hover:bg-red-500/10 text-red-400 transition-all">
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default VisualPage;
