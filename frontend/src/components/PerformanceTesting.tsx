import React, { useState, useEffect } from 'react';
import {
    Play, Square, Zap, CheckCircle, BarChart3, Trash2,
    Settings, Plus, X, Timer, TrendingUp, AlertTriangle,
    ArrowDown, ArrowUp, Activity, Globe
} from './icons';
import { API_ENDPOINTS, DEFAULT_CONFIG } from '../config';
import StatCard from './ui/StatCard';
import ExecutionBatchBanner from './ExecutionBatchBanner';
import { ensureExecutionContextPayload } from '../utils/executionContext';

// ── Types ──
interface PerformanceStats {
    total_requests: number;
    success: number;
    failures: number;
    success_rate: number;
    avg_response_time: number;
    min_response_time: number;
    max_response_time: number;
    requests_per_second: number;
    p95_response_time?: number;
    p99_response_time?: number;
}

interface TestResult {
    test_id: string;
    status: string;
    duration: number;
    stats: PerformanceStats;
    started_at: string;
    finished_at: string;
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

interface HeaderEntry { key: string; value: string; }



// ── Metric Bar ──
const MetricBar: React.FC<{ label: string; value: number; max: number; color: string; suffix?: string }> = ({ label, value, max, color, suffix = 'ms' }) => (
    <div className="space-y-1">
        <div className="flex justify-between text-xs">
            <span className="text-slate-500 dark:text-slate-400">{label}</span>
            <span className="font-mono font-medium text-slate-700 dark:text-slate-200">{value.toFixed(0)}{suffix}</span>
        </div>
        <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-700 ${color}`}
                style={{ width: `${Math.min(100, (value / Math.max(max, 1)) * 100)}%` }} />
        </div>
    </div>
);

// ============================================================================
// Main Component
// ============================================================================
const PerformanceTesting: React.FC = () => {
    const [targetUrl, setTargetUrl] = useState<string>(DEFAULT_CONFIG.performanceTestUrl);
    const [method, setMethod] = useState<HttpMethod>('GET');
    const [users, setUsers] = useState(10);
    const [duration, setDuration] = useState(30);
    const [headers, setHeaders] = useState<HeaderEntry[]>([]);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [result, setResult] = useState<TestResult | null>(null);
    const [history, setHistory] = useState<TestResult[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => { fetchHistory(); }, []);

    const fetchHistory = async () => {
        try {
            const res = await fetch(API_ENDPOINTS.performance.history);
            const data = await res.json();
            setHistory(data.history || []);
        } catch (e) { console.error('Failed to fetch history:', e); }
    };

    const runTest = async () => {
        setIsRunning(true);
        setError(null);
        setResult(null);
        try {
            const headersObj: Record<string, string> = {};
            headers.forEach(h => { if (h.key.trim()) headersObj[h.key.trim()] = h.value; });

            const res = await fetch(API_ENDPOINTS.performance.run, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_url: targetUrl,
                    method: method,
                    users,
                    spawn_rate: Math.max(1, Math.ceil(users / 5)),
                    duration,
                    custom_headers: Object.keys(headersObj).length > 0 ? headersObj : undefined,
                    ...ensureExecutionContextPayload("Performance test suite", { targetUrl }),
                })
            });
            const data = await res.json();
            if (data.status === 'success') {
                setResult(data);
                fetchHistory();
            } else {
                setError(data.detail || 'Test failed');
            }
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Connection error');
        } finally {
            setIsRunning(false);
        }
    };

    const stopTest = async () => {
        try { await fetch(API_ENDPOINTS.performance.stop, { method: 'POST' }); setIsRunning(false); }
        catch (e) { console.error('Failed to stop test:', e); }
    };

    const deleteHistory = async (testId: string) => {
        if (!confirm("Delete this record?")) return;
        try { await fetch(API_ENDPOINTS.performance.delete(testId), { method: 'DELETE' }); fetchHistory(); }
        catch (e) { console.error('Failed to delete:', e); }
    };

    const clearHistory = async () => {
        if (!confirm("Clear all history?")) return;
        try { await fetch(API_ENDPOINTS.performance.clear, { method: 'DELETE' }); setHistory([]); }
        catch (e) { console.error('Failed to clear:', e); }
    };

    const addHeader = () => setHeaders(prev => [...prev, { key: '', value: '' }]);
    const removeHeader = (i: number) => setHeaders(prev => prev.filter((_, idx) => idx !== i));
    const updateHeader = (i: number, field: 'key' | 'value', val: string) =>
        setHeaders(prev => prev.map((h, idx) => idx === i ? { ...h, [field]: val } : h));

    const methodColors: Record<HttpMethod, string> = {
        GET: 'bg-emerald-500', POST: 'bg-blue-500', PUT: 'bg-amber-500',
        DELETE: 'bg-red-500', PATCH: 'bg-purple-500',
    };

    const stats = result?.stats;

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <ExecutionBatchBanner standaloneHint={"The first run on this page creates a specialized test batch. If you start an overall task from orchestration first, these results are added to that task."} />

            {/* Config Panel */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6">
                <h2 className="text-xl font-bold text-slate-900 dark:text-cyan-400 mb-6 flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-cyan-500/10">
                        <Zap className="w-5 h-5 text-cyan-500" />
                    </div>
                    Performance test configuration
                </h2>

                {/* URL + Method Row */}
                <div className="flex gap-3 mb-4">
                    <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
                        {(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'] as HttpMethod[]).map(m => (
                            <button key={m} onClick={() => setMethod(m)} disabled={isRunning}
                                className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${method === m
                                    ? `${methodColors[m]} text-white shadow-sm` : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                                    }`}>{m}</button>
                        ))}
                    </div>
                    <div className="flex-1 relative">
                        <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input type="text" value={targetUrl} onChange={e => setTargetUrl(e.target.value)} disabled={isRunning}
                            placeholder="https://example.com/api"
                            className="w-full pl-10 pr-3 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none transition-all" />
                    </div>
                </div>

                {/* Load Config Row */}
                <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">Concurrent users</label>
                        <input type="number" value={users} onChange={e => setUsers(parseInt(e.target.value) || 10)}
                            disabled={isRunning} min={1} max={500}
                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-cyan-500/20 outline-none" />
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">Duration (seconds)</label>
                        <input type="number" value={duration} onChange={e => setDuration(parseInt(e.target.value) || 30)}
                            disabled={isRunning} min={5} max={600}
                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-cyan-500/20 outline-none" />
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">Spawn rate (users/second)</label>
                        <div className="w-full bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-500 dark:text-slate-400">
                            {Math.max(1, Math.ceil(users / 5))} /s (automatic)
                        </div>
                    </div>
                </div>

                {/* Advanced: Custom Headers */}
                <div className="mb-4">
                    <button onClick={() => setShowAdvanced(!showAdvanced)}
                        className="flex items-center gap-2 text-xs font-medium text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors">
                        <Settings className={`w-3.5 h-3.5 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
                        Advanced configuration (headers)
                    </button>
                    {showAdvanced && (
                        <div className="mt-3 space-y-2 animate-in slide-in-from-top-2 duration-200">
                            {headers.map((h, i) => (
                                <div key={i} className="flex gap-2 items-center">
                                    <input type="text" value={h.key} onChange={e => updateHeader(i, 'key', e.target.value)}
                                        placeholder="Header Name" disabled={isRunning}
                                        className="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-cyan-500/20" />
                                    <input type="text" value={h.value} onChange={e => updateHeader(i, 'value', e.target.value)}
                                        placeholder="Value" disabled={isRunning}
                                        className="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-cyan-500/20" />
                                    <button onClick={() => removeHeader(i)} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
                                        <X className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            ))}
                            <button onClick={addHeader} disabled={isRunning}
                                className="flex items-center gap-1.5 text-xs text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 transition-colors disabled:opacity-50">
                                <Plus className="w-3 h-3" /> Add header
                            </button>
                        </div>
                    )}
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3">
                    {!isRunning ? (
                        <button onClick={runTest}
                            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-lg font-medium shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 active:scale-95 transition-all">
                            <Play className="w-4 h-4 fill-current" /> Start performance test
                        </button>
                    ) : (
                        <button onClick={stopTest}
                            className="flex items-center gap-2 px-6 py-2.5 bg-red-500/10 text-red-500 border border-red-500/50 hover:bg-red-500/20 rounded-lg font-medium active:scale-95 transition-all">
                            <Square className="w-4 h-4 fill-current" /> Stop test
                        </button>
                    )}
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                        <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-cyan-500 animate-pulse' : 'bg-slate-300 dark:bg-slate-600'}`} />
                        {isRunning ? "Test in progress..." : "Ready"}
                    </div>
                </div>

                {error && (
                    <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/50 rounded-lg text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
                    </div>
                )}
            </div>

            {/* Results Dashboard */}
            {stats && stats.total_requests != null && (
                <div className="space-y-4">
                    {/* Top Stats Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <StatCard label={"Total requests"} value={(stats.total_requests || 0).toLocaleString()}
                            icon={<Activity className="w-5 h-5 text-white/80" />}
                            gradient="bg-gradient-to-br from-indigo-500 to-indigo-700"
                            subValue={`Passed ${stats.success || 0} / Failed ${stats.failures || 0}`} />
                        <StatCard label={"Throughput (RPS)"} value={stats.requests_per_second?.toFixed(1) || '0'} unit="req/s"
                            icon={<TrendingUp className="w-5 h-5 text-white/80" />}
                            gradient="bg-gradient-to-br from-purple-500 to-purple-700" />
                        <StatCard label={"Success rate"} value={`${stats.success_rate ?? 0}`} unit="%"
                            icon={<CheckCircle className="w-5 h-5 text-white/80" />}
                            gradient={`bg-gradient-to-br ${(stats.success_rate ?? 0) >= 99 ? 'from-emerald-500 to-emerald-700' : (stats.success_rate ?? 0) >= 90 ? 'from-amber-500 to-amber-700' : 'from-red-500 to-red-700'}`} />
                        <StatCard label={"Average latency"} value={stats.avg_response_time?.toFixed(0) || '0'} unit="ms"
                            icon={<Timer className="w-5 h-5 text-white/80" />}
                            gradient="bg-gradient-to-br from-cyan-500 to-cyan-700"
                            subValue={`Range ${stats.min_response_time?.toFixed(0) || 0} - ${stats.max_response_time?.toFixed(0) || 0} ms`} />
                    </div>

                    {/* Response Time Distribution */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6">
                        <h3 className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-4 flex items-center gap-2">
                            <BarChart3 className="w-4 h-4 text-cyan-500" /> Response time distribution
                        </h3>
                        <div className="space-y-3">
                            <MetricBar label={"Minimum response time"} value={stats.min_response_time || 0} max={stats.max_response_time || 100} color="bg-emerald-500" />
                            <MetricBar label={"Average response time"} value={stats.avg_response_time || 0} max={stats.max_response_time || 100} color="bg-cyan-500" />
                            <MetricBar label={"P95 response time"} value={stats.p95_response_time || stats.avg_response_time * 1.5 || 0} max={stats.max_response_time || 100} color="bg-amber-500" />
                            <MetricBar label={"P99 response time"} value={stats.p99_response_time || stats.max_response_time * 0.9 || 0} max={stats.max_response_time || 100} color="bg-red-500" />
                            <MetricBar label={"Maximum response time"} value={stats.max_response_time || 0} max={stats.max_response_time || 100} color="bg-red-600" />
                        </div>

                        {/* Summary Row */}
                        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700 grid grid-cols-3 gap-4">
                            <div className="flex items-center gap-2 text-xs">
                                <ArrowDown className="w-3.5 h-3.5 text-emerald-500" />
                                <span className="text-slate-500">Minimum</span>
                                <span className="font-mono font-bold text-slate-900 dark:text-white">{stats.min_response_time?.toFixed(0)}ms</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                                <Activity className="w-3.5 h-3.5 text-cyan-500" />
                                <span className="text-slate-500">Average</span>
                                <span className="font-mono font-bold text-slate-900 dark:text-white">{stats.avg_response_time?.toFixed(0)}ms</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                                <ArrowUp className="w-3.5 h-3.5 text-red-500" />
                                <span className="text-slate-500">Maximum</span>
                                <span className="font-mono font-bold text-slate-900 dark:text-white">{stats.max_response_time?.toFixed(0)}ms</span>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* History Table */}
            {history.length > 0 && (
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <BarChart3 className="w-4 h-4 text-slate-500" /> Test history ( {history.length})
                        </h3>
                        <button onClick={clearHistory}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-600 dark:text-red-400 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-colors">
                            <Trash2 className="w-3 h-3" /> Clear
                        </button>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-slate-400 border-b border-slate-200 dark:border-slate-800">
                                    <th className="py-2 px-3 text-left text-xs font-medium">ID</th>
                                    <th className="py-2 px-3 text-left text-xs font-medium">Status</th>
                                    <th className="py-2 px-3 text-right text-xs font-medium">Requests</th>
                                    <th className="py-2 px-3 text-right text-xs font-medium">Success rate</th>
                                    <th className="py-2 px-3 text-right text-xs font-medium">RPS</th>
                                    <th className="py-2 px-3 text-right text-xs font-medium">Average latency</th>
                                    <th className="py-2 px-3 text-right text-xs font-medium">Duration</th>
                                    <th className="py-2 px-3 text-right text-xs font-medium"></th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                {history.slice(0, 10).map(h => (
                                    <tr key={h.test_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                        <td className="py-2.5 px-3 font-mono text-xs text-cyan-600 dark:text-cyan-400">#{h.test_id}</td>
                                        <td className="py-2.5 px-3">
                                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${h.status === 'completed'
                                                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-red-500/10 text-red-600 dark:text-red-400'}`}>
                                                <span className={`w-1.5 h-1.5 rounded-full ${h.status === 'completed' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                                                {h.status}
                                            </span>
                                        </td>
                                        <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-300">{h.stats?.total_requests || 0}</td>
                                        <td className="py-2.5 px-3 text-right font-medium text-slate-900 dark:text-white">{h.stats?.success_rate || 0}%</td>
                                        <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-300">{h.stats?.requests_per_second?.toFixed(1) || 0}</td>
                                        <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-300">{h.stats?.avg_response_time?.toFixed(0) || 0}ms</td>
                                        <td className="py-2.5 px-3 text-right text-slate-400">{h.duration?.toFixed(1)}s</td>
                                        <td className="py-2.5 px-3 text-right">
                                            <button onClick={() => deleteHistory(h.test_id)}
                                                className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-500/10 rounded transition-colors" title={"Delete"}>
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};

export default PerformanceTesting;
