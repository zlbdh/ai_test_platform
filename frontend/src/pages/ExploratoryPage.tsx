import React, { useState, useCallback, useEffect } from 'react';
import {
    Compass, Play, RefreshCw, Globe, AlertTriangle,
    CheckCircle2, Clock, Activity, Map, Settings, ChevronDown,
} from '../components/icons';
import Badge from '../components/ui/Badge';
import PageHeader from '../components/ui/PageHeader';
import { startExecution, getExecutionDetail } from '../services/backendService';
import { API_BASE_URL } from '../config';
import { useAppStore, useExploratoryStore } from '../stores';
import StatCard from '../components/ui/StatCard';


// ============================================================================
const ExploratoryPage: React.FC = () => {
    const [targetUrl, setTargetUrl] = useState('');
    const [maxSteps, setMaxSteps] = useState(20);
    const { useMultiAgent, enableVision, setEnableVision, setUseMultiAgent } = useAppStore();
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [strategy, setStrategy] = useState<'breadth' | 'depth' | 'smart'>('smart');
    const [screenshotOnAnomaly, setScreenshotOnAnomaly] = useState(true);
    const [timeout, setTimeout_] = useState(60);
    const [excludePaths, setExcludePaths] = useState('');
    const [clickDepth, setClickDepth] = useState(3);

    // Read execution state from the global store to persist across pages.
    const {
        running, taskId, logs, status, stats,
        start, appendLog, finish, updateStats,
    } = useExploratoryStore();

    const handleStart = useCallback(async () => {
        if (!targetUrl.trim()) return;
        const task = `Exploratory testing: automatically explore ${targetUrl}, strategy=${strategy}, maximum steps ${maxSteps}, click depth ${clickDepth}, timeout ${timeout} seconds${excludePaths ? `, excluding paths: ${excludePaths}` : ''}${screenshotOnAnomaly ? ", capture screenshots on errors" : ''}`;
        try {
            const result = await startExecution(task, useMultiAgent, enableVision, targetUrl);
            start(result.task_id);
        } catch (err: any) {
            const msg = err?.message || String(err);
            if (msg.includes('409')) {
                // The backend has an active task; stop it before retrying.
                appendLog("[Notice] An active backend task was detected. Stopping it...");
                try {
                    const { stopExecution } = await import('../services/backendService');
                    await stopExecution();
                    appendLog("[Notice] Previous task stopped. Restarting...");
                    // Wait for backend cleanup.
                    await new Promise(r => setTimeout(r, 1500));
                    const result = await startExecution(task, useMultiAgent, enableVision, targetUrl);
                    start(result.task_id);
                    return;
                } catch (retryErr) {
                    appendLog(`[Error] Retry failed: ${retryErr}`);
                }
            } else {
                appendLog(`[Error] Failed to start: ${msg}`);
            }
            finish('error');
        }
    }, [targetUrl, maxSteps, useMultiAgent, enableVision, clickDepth, excludePaths, screenshotOnAnomaly, strategy, timeout, start, appendLog, finish]);

    // Poll execution status through /api/status; running tasks are not in history.
    useEffect(() => {
        if (!taskId || !running) return;
        let stopped = false;
        const timer = setInterval(async () => {
            if (stopped) return;
            try {
                const res = await fetch(`${API_BASE_URL}/api/status?session_id=default_session`);
                if (!res.ok) return;
                const data = await res.json();

                if (!data.is_running) {
                    // The task ended; try to retrieve final statistics from history.
                    stopped = true;
                    clearInterval(timer);
                    const finalStatus = data.status === 'STOPPED' ? 'stopped' : 'completed';
                    finish(finalStatus);
                    appendLog(`[${finalStatus === 'completed' ? "Complete" : "Finished"}] Exploration finished`);

                    try {
                        const detail = await getExecutionDetail(taskId);
                        updateStats({
                            pages: Math.max(stats.pages, Math.floor((detail.log_count || 0) / 3)),
                            actions: detail.log_count || 0,
                            anomalies: detail.error_count || 0,
                        });
                    } catch {
                        // Ignore failed statistics retrieval.
                    }
                }
            } catch {
                // Ignore network errors.
            }
        }, 3000);
        return () => { stopped = true; clearInterval(timer); };
    }, [taskId, running, appendLog, finish, stats.pages, updateStats]);

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            {/* Header */}
            <PageHeader
                icon={<Compass className="w-5 h-5" />}
                title={"Exploratory testing"}
                description={"Enter a target URL. AI explores the pages to find unexpected behavior and potential defects."}
                accent="teal"
            />

            {/* Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard icon={<Map className="w-5 h-5" />} label={"Pages explored"} value={stats.pages} gradient="bg-gradient-to-br from-teal-500 to-teal-700" />
                <StatCard icon={<Activity className="w-5 h-5" />} label={"Actions performed"} value={stats.actions} gradient="bg-gradient-to-br from-blue-500 to-blue-700" />
                <StatCard icon={<AlertTriangle className="w-5 h-5" />} label={"Anomalies found"} value={stats.anomalies} gradient="bg-gradient-to-br from-red-500 to-red-700" />
                <StatCard
                    icon={status === 'running' ? <RefreshCw className="w-5 h-5 animate-spin" /> : status === 'completed' ? <CheckCircle2 className="w-5 h-5" /> : <Clock className="w-5 h-5" />}
                    label={"Status"}
                    value={status === 'running' ? "Exploring" : status === 'completed' ? "Complete" : status === 'error' ? "Error" : "Ready"}
                    gradient={status === 'running' ? 'bg-gradient-to-br from-amber-500 to-amber-700' : status === 'completed' ? 'bg-gradient-to-br from-emerald-500 to-emerald-700' : 'bg-gradient-to-br from-slate-500 to-slate-700'}
                />
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                {/* ── Config Panel ── */}
                <div className="lg:col-span-1 space-y-4">
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <Globe className="w-4 h-4 text-teal-500" />
                            Target configuration
                        </h3>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Target URL</label>
                            <input
                                type="url"
                                value={targetUrl}
                                onChange={e => setTargetUrl(e.target.value)}
                                placeholder="https://example.com"
                                className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-teal-500/30"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Maximum exploration steps</label>
                            <input
                                type="number"
                                value={maxSteps}
                                onChange={e => setMaxSteps(Number(e.target.value))}
                                min={5}
                                max={100}
                                className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-teal-500/30"
                            />
                        </div>
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                            <button onClick={() => setEnableVision(!enableVision)} disabled={running}
                                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${enableVision
                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-400 dark:border-emerald-500/30'
                                    : 'bg-slate-100 text-slate-500 border-slate-200 dark:bg-slate-700 dark:text-slate-400 dark:border-slate-600'
                                    }`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${enableVision ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
                                Vision mode {enableVision ? "On" : "Off"}
                            </button>
                            <button onClick={() => setUseMultiAgent(!useMultiAgent)} disabled={running}
                                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${useMultiAgent
                                    ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/15 dark:text-blue-400 dark:border-blue-500/30'
                                    : 'bg-slate-100 text-slate-500 border-slate-200 dark:bg-slate-700 dark:text-slate-400 dark:border-slate-600'
                                    }`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${useMultiAgent ? 'bg-blue-500 animate-pulse' : 'bg-slate-400'}`} />
                                Multi-agent {useMultiAgent ? "On" : "Off"}
                            </button>
                        </div>

                        {/* Advanced Config Toggle */}
                        <button onClick={() => setShowAdvanced(!showAdvanced)}
                            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-teal-500 font-medium transition-colors w-full">
                            <Settings className={`w-3 h-3 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
                            Advanced settings
                            <ChevronDown className={`w-3 h-3 ml-auto transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
                        </button>

                        {showAdvanced && (
                            <div className="space-y-3 animate-in slide-in-from-top-2 duration-200 py-2 border-t border-b border-slate-200 dark:border-slate-700">
                                {/* Strategy */}
                                <div className="space-y-1">
                                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Exploration strategy</label>
                                    <div className="flex gap-1">
                                        {([['breadth', "Breadth-first"], ['depth', "Depth-first"], ['smart', "AI-guided"]] as const).map(([key, label]) => (
                                            <button key={key} onClick={() => setStrategy(key)} disabled={running}
                                                className={`flex-1 px-2 py-1.5 rounded-lg text-[11px] font-medium border transition-all disabled:opacity-50 ${strategy === key
                                                    ? 'bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/30 shadow-sm'
                                                    : 'bg-slate-50 dark:bg-slate-800 text-slate-400 border-slate-200 dark:border-slate-700'
                                                    }`}>{label}</button>
                                        ))}
                                    </div>
                                </div>

                                {/* Click Depth */}
                                <div className="space-y-1">
                                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Click depth (levels)</label>
                                    <input type="range" value={clickDepth} onChange={e => setClickDepth(Number(e.target.value))} min={1} max={10} disabled={running}
                                        className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-teal-500" />
                                    <div className="text-right text-[10px] text-slate-400 font-mono">{clickDepth} levels</div>
                                </div>

                                {/* Timeout */}
                                <div className="space-y-1">
                                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Step timeout (seconds)</label>
                                    <input type="number" value={timeout} onChange={e => setTimeout_(Number(e.target.value))} min={10} max={300} disabled={running}
                                        className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-1.5 outline-none focus:ring-2 focus:ring-teal-500/30" />
                                </div>

                                {/* Exclude Paths */}
                                <div className="space-y-1">
                                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Excluded paths (comma-separated)</label>
                                    <input type="text" value={excludePaths} onChange={e => setExcludePaths(e.target.value)} disabled={running}
                                        placeholder="/logout, /admin, /api/*"
                                        className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-1.5 outline-none focus:ring-2 focus:ring-teal-500/30 placeholder-slate-400" />
                                </div>

                                {/* Screenshot Toggle */}
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" checked={screenshotOnAnomaly} onChange={e => setScreenshotOnAnomaly(e.target.checked)} disabled={running}
                                        className="w-3.5 h-3.5 text-teal-500 rounded border-slate-300 focus:ring-teal-500/30" />
                                    <span className="text-[11px] text-slate-500 dark:text-slate-400">Capture screenshots automatically on errors</span>
                                </label>
                            </div>
                        )}

                        <button
                            onClick={handleStart}
                            disabled={running || !targetUrl.trim()}
                            className="w-full flex items-center justify-center gap-2 rounded-lg bg-teal-500 hover:bg-teal-600 text-white text-sm font-medium py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                            {running ? "Exploring..." : "Start exploration"}
                        </button>
                    </div>

                    {/* Info Card */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 p-4 space-y-2">
                        <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400">Exploration capabilities</h4>
                        <ul className="text-[11px] text-slate-500 dark:text-slate-400 space-y-1.5">
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> Automatically discover page links and forms</li>
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> Detect JavaScript console errors</li>
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> Identify broken links and 404 pages</li>
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> Detect visual anomalies (requires vision mode)</li>
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> Automatically build a state transition graph</li>
                        </ul>
                    </div>
                </div>

                {/* ── Activity Log ── */}
                <div className="lg:col-span-2">
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
                        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                                <Activity className="w-4 h-4 text-teal-500" />
                                Exploration logs
                            </h3>
                            {running && <Badge variant="warning" dot size="sm">Exploring</Badge>}
                        </div>
                        <div className="h-[420px] overflow-y-auto p-4 font-mono text-xs leading-relaxed bg-slate-950 text-slate-300 space-y-0.5">
                            {logs.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-full text-slate-600">
                                    <Compass className="w-10 h-10 mb-3 opacity-30" />
                                    <p>Enter a target URL and click Start exploration</p>
                                </div>
                            ) : (
                                logs.map((log, i) => {
                                    const isError = (log.includes('[错误]') || log.includes("[Error]")) || (log.includes('[异常]') || log.includes("[Exception]"));
                                    const isSuccess = (log.includes('[完成]') || log.includes("[Completed]")) || (log.includes('[发现]') || log.includes("[Found]"));
                                    return (
                                        <div key={i} className={`flex items-start gap-2 ${isError ? 'text-red-400' : isSuccess ? 'text-emerald-400' : ''}`}>
                                            <span className="text-slate-600 shrink-0 select-none">{String(i + 1).padStart(3, '0')}</span>
                                            <span>{log}</span>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ExploratoryPage;
