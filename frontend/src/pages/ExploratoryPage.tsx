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

    // 从全局 store 读取执行状态 — 跨页面持久化
    const {
        running, taskId, logs, status, stats,
        start, appendLog, finish, updateStats,
    } = useExploratoryStore();

    const handleStart = useCallback(async () => {
        if (!targetUrl.trim()) return;
        const task = `探索性测试: 自动探索 ${targetUrl}，策略=${strategy}，最大步骤${maxSteps}，点击深度${clickDepth}，超时${timeout}秒${excludePaths ? `，排除路径: ${excludePaths}` : ''}${screenshotOnAnomaly ? '，异常时截图' : ''}`;
        try {
            const result = await startExecution(task, useMultiAgent, enableVision, targetUrl);
            start(result.task_id);
        } catch (err: any) {
            const msg = err?.message || String(err);
            if (msg.includes('409')) {
                // 后端有活跃任务 — 先停止再重试
                appendLog('[提示] 检测到后端有运行中的任务，正在停止...');
                try {
                    const { stopExecution } = await import('../services/backendService');
                    await stopExecution();
                    appendLog('[提示] 旧任务已停止，正在重新启动...');
                    // 等待后端清理
                    await new Promise(r => setTimeout(r, 1500));
                    const result = await startExecution(task, useMultiAgent, enableVision, targetUrl);
                    start(result.task_id);
                    return;
                } catch (retryErr) {
                    appendLog(`[错误] 重试失败: ${retryErr}`);
                }
            } else {
                appendLog(`[错误] 启动失败: ${msg}`);
            }
            finish('error');
        }
    }, [targetUrl, maxSteps, useMultiAgent, enableVision, clickDepth, excludePaths, screenshotOnAnomaly, strategy, timeout, start, appendLog, finish]);

    // Poll execution status via /api/status (运行中的任务不在 history 里)
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
                    // 任务已结束 — 尝试从 history 获取最终统计
                    stopped = true;
                    clearInterval(timer);
                    const finalStatus = data.status === 'STOPPED' ? 'stopped' : 'completed';
                    finish(finalStatus);
                    appendLog(`[${finalStatus === 'completed' ? '完成' : '结束'}] 探索结束`);

                    try {
                        const detail = await getExecutionDetail(taskId);
                        updateStats({
                            pages: Math.max(stats.pages, Math.floor((detail.log_count || 0) / 3)),
                            actions: detail.log_count || 0,
                            anomalies: detail.error_count || 0,
                        });
                    } catch {
                        // 统计获取失败，忽略
                    }
                }
            } catch {
                // 网络错误，忽略
            }
        }, 3000);
        return () => { stopped = true; clearInterval(timer); };
    }, [taskId, running, appendLog, finish, stats.pages, updateStats]);

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            {/* Header */}
            <PageHeader
                icon={<Compass className="w-5 h-5" />}
                title="探索性测试"
                description="输入目标 URL，AI 自主探索页面发现异常行为和潜在缺陷"
                accent="teal"
            />

            {/* Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard icon={<Map className="w-5 h-5" />} label="已探索页面" value={stats.pages} gradient="bg-gradient-to-br from-teal-500 to-teal-700" />
                <StatCard icon={<Activity className="w-5 h-5" />} label="执行操作" value={stats.actions} gradient="bg-gradient-to-br from-blue-500 to-blue-700" />
                <StatCard icon={<AlertTriangle className="w-5 h-5" />} label="发现异常" value={stats.anomalies} gradient="bg-gradient-to-br from-red-500 to-red-700" />
                <StatCard
                    icon={status === 'running' ? <RefreshCw className="w-5 h-5 animate-spin" /> : status === 'completed' ? <CheckCircle2 className="w-5 h-5" /> : <Clock className="w-5 h-5" />}
                    label="状态"
                    value={status === 'running' ? '探索中' : status === 'completed' ? '完成' : status === 'error' ? '错误' : '就绪'}
                    gradient={status === 'running' ? 'bg-gradient-to-br from-amber-500 to-amber-700' : status === 'completed' ? 'bg-gradient-to-br from-emerald-500 to-emerald-700' : 'bg-gradient-to-br from-slate-500 to-slate-700'}
                />
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                {/* ── Config Panel ── */}
                <div className="lg:col-span-1 space-y-4">
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                            <Globe className="w-4 h-4 text-teal-500" />
                            目标配置
                        </h3>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">目标 URL</label>
                            <input
                                type="url"
                                value={targetUrl}
                                onChange={e => setTargetUrl(e.target.value)}
                                placeholder="https://example.com"
                                className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-teal-500/30"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">最大探索步骤</label>
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
                                视觉模式{enableVision ? '开' : '关'}
                            </button>
                            <button onClick={() => setUseMultiAgent(!useMultiAgent)} disabled={running}
                                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${useMultiAgent
                                    ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/15 dark:text-blue-400 dark:border-blue-500/30'
                                    : 'bg-slate-100 text-slate-500 border-slate-200 dark:bg-slate-700 dark:text-slate-400 dark:border-slate-600'
                                    }`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${useMultiAgent ? 'bg-blue-500 animate-pulse' : 'bg-slate-400'}`} />
                                多Agent{useMultiAgent ? '开' : '关'}
                            </button>
                        </div>

                        {/* Advanced Config Toggle */}
                        <button onClick={() => setShowAdvanced(!showAdvanced)}
                            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-teal-500 font-medium transition-colors w-full">
                            <Settings className={`w-3 h-3 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
                            高级配置
                            <ChevronDown className={`w-3 h-3 ml-auto transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
                        </button>

                        {showAdvanced && (
                            <div className="space-y-3 animate-in slide-in-from-top-2 duration-200 py-2 border-t border-b border-slate-200 dark:border-slate-700">
                                {/* Strategy */}
                                <div className="space-y-1">
                                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">探索策略</label>
                                    <div className="flex gap-1">
                                        {([['breadth', '广度优先'], ['depth', '深度优先'], ['smart', 'AI 智能']] as const).map(([key, label]) => (
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
                                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">点击深度 (层级)</label>
                                    <input type="range" value={clickDepth} onChange={e => setClickDepth(Number(e.target.value))} min={1} max={10} disabled={running}
                                        className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-teal-500" />
                                    <div className="text-right text-[10px] text-slate-400 font-mono">{clickDepth} 层</div>
                                </div>

                                {/* Timeout */}
                                <div className="space-y-1">
                                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">单步超时 (秒)</label>
                                    <input type="number" value={timeout} onChange={e => setTimeout_(Number(e.target.value))} min={10} max={300} disabled={running}
                                        className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-1.5 outline-none focus:ring-2 focus:ring-teal-500/30" />
                                </div>

                                {/* Exclude Paths */}
                                <div className="space-y-1">
                                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">排除路径 (逗号分隔)</label>
                                    <input type="text" value={excludePaths} onChange={e => setExcludePaths(e.target.value)} disabled={running}
                                        placeholder="/logout, /admin, /api/*"
                                        className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-1.5 outline-none focus:ring-2 focus:ring-teal-500/30 placeholder-slate-400" />
                                </div>

                                {/* Screenshot Toggle */}
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" checked={screenshotOnAnomaly} onChange={e => setScreenshotOnAnomaly(e.target.checked)} disabled={running}
                                        className="w-3.5 h-3.5 text-teal-500 rounded border-slate-300 focus:ring-teal-500/30" />
                                    <span className="text-[11px] text-slate-500 dark:text-slate-400">异常时自动截图</span>
                                </label>
                            </div>
                        )}

                        <button
                            onClick={handleStart}
                            disabled={running || !targetUrl.trim()}
                            className="w-full flex items-center justify-center gap-2 rounded-lg bg-teal-500 hover:bg-teal-600 text-white text-sm font-medium py-2.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                            {running ? '探索中...' : '开始探索'}
                        </button>
                    </div>

                    {/* Info Card */}
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 p-4 space-y-2">
                        <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400">探索能力</h4>
                        <ul className="text-[11px] text-slate-500 dark:text-slate-400 space-y-1.5">
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> 自动发现页面链接和表单</li>
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> 检测 JS 控制台错误</li>
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> 识别死链接和 404 页面</li>
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> 视觉异常检测（需开启视觉模式）</li>
                            <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-teal-500" /> 自动构建状态转换图</li>
                        </ul>
                    </div>
                </div>

                {/* ── Activity Log ── */}
                <div className="lg:col-span-2">
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
                        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                                <Activity className="w-4 h-4 text-teal-500" />
                                探索日志
                            </h3>
                            {running && <Badge variant="warning" dot size="sm">探索中</Badge>}
                        </div>
                        <div className="h-[420px] overflow-y-auto p-4 font-mono text-xs leading-relaxed bg-slate-950 text-slate-300 space-y-0.5">
                            {logs.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-full text-slate-600">
                                    <Compass className="w-10 h-10 mb-3 opacity-30" />
                                    <p>输入目标 URL 并点击"开始探索"</p>
                                </div>
                            ) : (
                                logs.map((log, i) => {
                                    const isError = log.includes('[错误]') || log.includes('[异常]');
                                    const isSuccess = log.includes('[完成]') || log.includes('[发现]');
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
