import { useState, useEffect, useCallback } from 'react';
import { Activity, BarChart3, Target, Zap, Brain, RefreshCw, Shield } from '../components/icons';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8020';

interface MetricDef { name: string; description: string }
interface Scenario { id: string; name: string; category: string; difficulty: string; goal: string; expected_steps: number }
interface EvalResult { run_id: string; scenario_id: string; model: string; success: number; overall_score: number; duration_ms: number; total_tokens: number; timestamp: number }

const scoreColor = (s: number) => s >= 0.8 ? 'text-emerald-600 dark:text-emerald-400' : s >= 0.6 ? 'text-amber-600 dark:text-amber-400' : 'text-rose-600 dark:text-rose-400';
const difficultyBadge: Record<string, string> = {
    easy: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
    medium: 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
    hard: 'bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-400',
};

export default function EvaluationDashboard() {
    const [metrics, setMetrics] = useState<MetricDef[]>([]);
    const [scenarios, setScenarios] = useState<Scenario[]>([]);
    const [results, setResults] = useState<EvalResult[]>([]);
    const [comparison, setComparison] = useState<any>(null);
    const [tab, setTab] = useState<'overview' | 'scenarios' | 'history' | 'compare'>('overview');
    const [loading, setLoading] = useState(false);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        try {
            const [mRes, sRes, rRes, cRes] = await Promise.all([
                fetch(`${API_BASE}/api/evaluation/metrics`).then(r => r.json()),
                fetch(`${API_BASE}/api/evaluation/scenarios`).then(r => r.json()),
                fetch(`${API_BASE}/api/evaluation/results?limit=30`).then(r => r.json()),
                fetch(`${API_BASE}/api/evaluation/compare`).then(r => r.json()),
            ]);
            setMetrics(mRes.metrics || []);
            setScenarios(sRes.scenarios || []);
            setResults(rRes.results || []);
            setComparison(cRes.comparison || null);
        } catch (e) { console.error('Fetch error', e); }
        setLoading(false);
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void fetchAll();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [fetchAll]);

    const avgScore = results.length > 0 ? results.reduce((s, r) => s + r.overall_score, 0) / results.length : 0;
    const successRate = results.length > 0 ? results.filter(r => r.success).length / results.length : 0;

    return (
        <div className="space-y-6 pb-8">
            {/* Title*/}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 text-white">
                        <Brain className="w-5 h-5" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Agent evaluation center</h2>
                        <p className="text-sm text-slate-500 dark:text-slate-400">Measure each agent's decision quality and reliability</p>
                    </div>
                </div>
                <button onClick={fetchAll} disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-500 to-violet-600 hover:from-violet-600 hover:to-violet-700 rounded-lg text-sm text-white transition-all disabled:opacity-50 shadow-sm">
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </button>
            </div>

            {/* Overview cards*/}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                {[
                    { label: "Overall score", value: (avgScore * 100).toFixed(1) + '%', icon: Target, iconBg: 'bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-400', valueColor: scoreColor(avgScore) },
                    { label: "Success rate", value: (successRate * 100).toFixed(0) + '%', icon: Shield, iconBg: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400', valueColor: scoreColor(successRate) },
                    { label: "Evaluations", value: results.length.toString(), icon: Activity, iconBg: 'bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400', valueColor: 'text-blue-600 dark:text-blue-400' },
                    { label: "Benchmark scenarios", value: scenarios.length.toString(), icon: BarChart3, iconBg: 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400', valueColor: 'text-amber-600 dark:text-amber-400' },
                ].map(c => (
                    <div key={c.label} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-slate-300 dark:border-slate-700/80 dark:bg-slate-800/60 dark:hover:border-slate-600">
                        <div className={`rounded-xl p-2.5 w-fit ${c.iconBg}`}><c.icon className="w-5 h-5" /></div>
                        <div className="mt-4">
                            <p className={`text-3xl font-extrabold tracking-tight ${c.valueColor}`}>{c.value}</p>
                            <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">{c.label}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* Tabs*/}
            <div className="flex gap-1 p-1 bg-slate-100 rounded-lg w-fit dark:bg-slate-800/60">
                {(['overview', 'scenarios', 'history', 'compare'] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${tab === t
                            ? 'bg-white text-indigo-600 shadow-sm dark:bg-slate-700 dark:text-indigo-400'
                            : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
                            }`}>
                        {{ overview: "Metrics overview", scenarios: "Benchmark scenarios", history: "Evaluation history", compare: "Model comparison" }[t]}
                    </button>
                ))}
            </div>

            {/* Content area*/}
            {tab === 'overview' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {metrics.map(m => (
                        <div key={m.name} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all dark:border-slate-700/80 dark:bg-slate-800/60 dark:hover:border-indigo-500/30">
                            <div className="flex items-center gap-2 mb-2">
                                <Zap className="w-4 h-4 text-violet-500 dark:text-violet-400" />
                                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">{m.name}</span>
                            </div>
                            <p className="text-xs text-slate-500 dark:text-slate-400">{m.description}</p>
                        </div>
                    ))}
                </div>
            )}

            {tab === 'scenarios' && (
                <div className="space-y-3">
                    {scenarios.map(s => (
                        <div key={s.id} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all dark:border-slate-700/80 dark:bg-slate-800/60 dark:hover:border-indigo-500/30">
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-3">
                                    <span className="font-semibold text-slate-800 dark:text-slate-200">{s.name}</span>
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${difficultyBadge[s.difficulty] || difficultyBadge.medium}`}>{s.difficulty}</span>
                                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300">{s.category}</span>
                                </div>
                                <span className="text-xs text-slate-500 dark:text-slate-400">{s.expected_steps} steps</span>
                            </div>
                            <p className="text-sm text-slate-500 dark:text-slate-400">{s.goal}</p>
                        </div>
                    ))}
                </div>
            )}

            {tab === 'history' && (
                <div className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm overflow-hidden dark:border-slate-700/60 dark:bg-slate-800/60">
                    <table className="w-full text-sm">
                        <thead><tr className="border-b border-slate-200 dark:border-slate-700">
                            {["Time", "Scenario", "Model", "Score", "Status", "Duration", 'Tokens'].map(h => (
                                <th key={h} className="text-left text-slate-500 dark:text-slate-400 font-medium p-3 first:pl-5">{h}</th>
                            ))}
                        </tr></thead>
                        <tbody>
                            {results.map(r => (
                                <tr key={r.run_id} className="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-700/50 dark:hover:bg-slate-700/30">
                                    <td className="p-3 pl-5 text-slate-500 dark:text-slate-400">{new Date(r.timestamp * 1000).toLocaleString('en-US')}</td>
                                    <td className="p-3 text-slate-800 dark:text-slate-200 font-medium">{r.scenario_id || '-'}</td>
                                    <td className="p-3 text-slate-600 dark:text-slate-300">{r.model || '-'}</td>
                                    <td className={`p-3 font-mono font-bold ${scoreColor(r.overall_score)}`}>{(r.overall_score * 100).toFixed(1)}%</td>
                                    <td className="p-3">{r.success ? <span className="text-emerald-500">✓</span> : <span className="text-rose-500">✗</span>}</td>
                                    <td className="p-3 text-slate-500 dark:text-slate-400">{(r.duration_ms / 1000).toFixed(1)}s</td>
                                    <td className="p-3 text-slate-500 dark:text-slate-400">{r.total_tokens?.toLocaleString() || '-'}</td>
                                </tr>
                            ))}
                            {results.length === 0 && <tr><td colSpan={7} className="p-8 text-center text-slate-400 dark:text-slate-500">No evaluation data yet</td></tr>}
                        </tbody>
                    </table>
                </div>
            )}

            {tab === 'compare' && comparison && (
                <div className="space-y-4">
                    {Object.entries(comparison.models || {}).map(([model, stats]: [string, any]) => (
                        <div key={model} className="card-hover-lift rounded-2xl border border-slate-200/60 bg-white/80 backdrop-blur-sm p-5 dark:border-slate-700/60 dark:bg-slate-800/60">
                            <div className="flex items-center justify-between mb-4">
                                <span className="font-semibold text-slate-800 dark:text-slate-200">{model}</span>
                                <span className="text-xs text-slate-500 dark:text-slate-400">{stats.runs} runs</span>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                                {[
                                    { label: "Success rate", value: (stats.success_rate * 100).toFixed(0) + '%', color: scoreColor(stats.success_rate) },
                                    { label: "Average score", value: (stats.avg_score * 100).toFixed(1) + '%', color: scoreColor(stats.avg_score) },
                                    { label: "Average tokens", value: stats.avg_tokens?.toLocaleString(), color: 'text-blue-600 dark:text-blue-400' },
                                    { label: "Average duration", value: (stats.avg_duration_ms / 1000).toFixed(1) + 's', color: 'text-amber-600 dark:text-amber-400' },
                                ].map(s => (
                                    <div key={s.label} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                                        <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
                                        <div className="text-xs text-slate-500 dark:text-slate-400">{s.label}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                    {!comparison.models || Object.keys(comparison.models).length === 0 &&
                        <div className="text-center text-slate-400 dark:text-slate-500 py-8">No model comparison data yet</div>}
                </div>
            )}
        </div>
    );
}
