import { useState, useEffect } from 'react';
import {
    Database, PlayCircle, Download, Copy, Check, Sparkles,
    Settings2,
} from '../components/icons';
import { API_BASE_URL } from '../config';

interface Template {
    id: string;
    label: string;
    description: string;
    fields: string[];
}

const TEMPLATE_ICONS: Record<string, string> = {
    user: '👤',
    address: '📍',
    payment: '💳',
    search: '🔍',
    boundary: '⚡',
    sample_platform_work_order: '🧾',
    sample_platform_property_parking: '🅿️',
    sample_platform_elder_profile: '🩺',
    sample_platform_announcement: '📣',
};

const TestDataPage: React.FC = () => {
    const [templates, setTemplates] = useState<Template[]>([]);
    const [selected, setSelected] = useState('user');
    const [count, setCount] = useState(5);
    const [includeEdge, setIncludeEdge] = useState(true);
    const [resultState, setResultState] = useState<{ templateId: string; rows: Record<string, unknown>[] } | null>(null);
    const [loading, setLoading] = useState(false);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        fetch(`${API_BASE_URL}/api/testdata/templates`)
            .then(r => r.json())
            .then(d => setTemplates(d.templates || []))
            .catch(() => { });
    }, []);

    const generate = async () => {
        setLoading(true);
        setResultState(null);
        try {
            const resp = await fetch(`${API_BASE_URL}/api/testdata/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ template: selected, count, include_edge: includeEdge }),
            });
            const data = await resp.json();
            setResultState({ templateId: selected, rows: data.data || [] });
        } catch {
            setResultState({ templateId: selected, rows: [] });
        }
        setLoading(false);
    };

    const result = resultState?.templateId === selected ? resultState.rows : null;

    const copyJSON = () => {
        if (!result) return;
        navigator.clipboard.writeText(JSON.stringify(result, null, 2));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const downloadCSV = () => {
        if (!result || result.length === 0) return;
        const keys = Object.keys(result[0]).filter(k => k !== '_edge');
        const csv = [keys.join(','), ...result.map(r =>
            keys.map(k => {
                const v = String((r as Record<string, unknown>)[k] ?? '');
                return v.includes(',') || v.includes('"') ? `"${v.replace(/"/g, '""')}"` : v;
            }).join(',')
        )].join('\n');
        const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `testdata_${selected}_${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

const selTpl = templates.find(t => t.id === selected);
    const isSampleTemplate = selected.startsWith('sample_platform_');

    return (
        <div className="space-y-6">
            {/* Title*/}
            <div className="mb-2">
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-white">
                        <Database className="w-5 h-5" />
                    </div>
                    Test data management
                </h2>
                <p className="text-slate-500 mt-2 text-sm">
                    AI-powered test data generation: boundary values, security attack data, and formatted data
                </p>
            </div>

            {/* Template selection cards*/}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {templates.map(t => (
                    <button
                        key={t.id}
                        onClick={() => setSelected(t.id)}
                        className={`relative p-4 rounded-2xl border text-left transition-all
                            ${selected === t.id
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10 shadow-md shadow-blue-500/10'
                                : 'border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 hover:border-blue-300'
                            }`}
                    >
                        <div className="text-2xl mb-2">{TEMPLATE_ICONS[t.id] || '📊'}</div>
                        <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">{t.label}</div>
                        <div className="text-xs text-slate-500 mt-1 leading-relaxed">{t.description}</div>
                        {selected === t.id && (
                            <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-blue-500" />
                        )}
                    </button>
                ))}
            </div>

            {/* Configuration row*/}
            <div className="flex flex-wrap items-center gap-4 bg-white/80 dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/60 backdrop-blur-sm p-4">
                <div className="flex items-center gap-2">
                    <Settings2 className="w-4 h-4 text-slate-400" />
                    <span className="text-sm text-slate-600 dark:text-slate-400">Number to generate</span>
                    <select
                        value={count}
                        onChange={e => setCount(Number(e.target.value))}
                        className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200"
                    >
                        {[3, 5, 10, 20, 50].map(n => <option key={n} value={n}>{n} entries</option>)}
                    </select>
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={includeEdge}
                        onChange={e => setIncludeEdge(e.target.checked)}
                        className="w-4 h-4 rounded border-slate-300 text-blue-500 focus:ring-blue-500"
                    />
                    <span className="text-sm text-slate-600 dark:text-slate-400">Include boundary values and attack data</span>
                </label>

                {selTpl && (
                    <div className="flex items-center gap-1.5 text-xs text-slate-400 ml-auto">
                        Fields:
                        {selTpl.fields.map(f => (
                            <span key={f} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400">
                                {f}
                            </span>
                        ))}
                    </div>
                )}

                <button
                    onClick={generate}
                    disabled={loading}
                    className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-xl
                        font-medium text-sm shadow-md shadow-blue-500/20 hover:shadow-lg hover:shadow-blue-500/30
                        active:scale-[0.98] transition-all disabled:opacity-50"
                >
                    {loading ? (
                        <><Sparkles className="w-4 h-4 animate-spin" /> Generating...</>
                    ) : (
                        <><PlayCircle className="w-4 h-4" /> Generate data</>
                    )}
                </button>
            </div>

            {isSampleTemplate && (
                <div className="rounded-2xl border border-cyan-200 bg-cyan-50/70 p-4 dark:border-cyan-800/50 dark:bg-cyan-900/10">
                    <p className="text-xs uppercase tracking-wide text-cyan-500">Sample project test data conventions</p>
                    <h3 className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-200">Use the `TEST_SAMPLE` prefix consistently for real regression tests</h3>
                    <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                        These templates generate filterable, removable data identifiers for create, edit, and status transition tests of work orders, announcements, parking contracts, and senior profiles.
                    </p>
                </div>
            )}

            {/* Results*/}
            {result && (
                <div className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm dark:border-slate-700/60 dark:bg-slate-800/60 overflow-hidden">
                    <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 dark:border-slate-700">
                        <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                            Generated results ( {result.length} records)
                        </span>
                        <div className="flex gap-2">
                            <button onClick={copyJSON} className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400 transition-colors">
                                {copied ? <><Check className="w-3.5 h-3.5 text-green-500" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy JSON</>}
                            </button>
                            <button onClick={downloadCSV} className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400 transition-colors">
                                <Download className="w-3.5 h-3.5" /> Export CSV
                            </button>
                        </div>
                    </div>

                    {result.length > 0 ? (
                        <div className="overflow-x-auto">
                            <table className="min-w-full">
                                <thead>
                                    <tr className="bg-slate-50 dark:bg-slate-700/50">
                                        <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase">#</th>
                                        {Object.keys(result[0]).filter(k => k !== '_edge').map(k => (
                                            <th key={k} className="px-4 py-2 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase">{k}</th>
                                        ))}
                                        {result.some(r => (r as Record<string, unknown>)._edge) && (
                                            <th className="px-4 py-2 text-left text-xs font-medium text-amber-500 uppercase">Marker</th>
                                        )}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
                                    {result.map((row, i) => {
                                        const edgeValue = (row as Record<string, unknown>)._edge;
                                        const edgeLabel = typeof edgeValue === 'string' ? edgeValue : '';
                                        return (
                                            <tr key={i} className={`${edgeLabel ? 'bg-amber-50/50 dark:bg-amber-500/5' : ''} hover:bg-slate-50 dark:hover:bg-slate-700/30`}>
                                                <td className="px-4 py-2 text-xs text-slate-400 font-mono">{i + 1}</td>
                                                {Object.entries(row).filter(([k]) => k !== '_edge').map(([k, v]) => (
                                                    <td key={k} className="px-4 py-2 text-xs text-slate-700 dark:text-slate-300 max-w-[200px] truncate" title={String(v)}>
                                                        {String(v).length > 40 ? String(v).slice(0, 40) + '…' : String(v)}
                                                    </td>
                                                ))}
                                                {result.some(r => (r as Record<string, unknown>)._edge) && (
                                                    <td className="px-4 py-2">
                                                        {edgeLabel && (
                                                            <span className="px-2 py-0.5 text-[10px] rounded bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400 font-medium">
                                                                {edgeLabel}
                                                            </span>
                                                        )}
                                                    </td>
                                                )}
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="text-center py-12 text-slate-400">No data yet</div>
                    )}
                </div>
            )}
        </div>
    );
};

export default TestDataPage;
