import React, { useState, useEffect } from 'react';
import {
    Flame, Smartphone, RefreshCw, CheckCircle, XCircle,
    AlertTriangle, Wifi, WifiOff, Timer, Cpu, HardDrive,
    MonitorSmartphone, ChevronDown, Plus, Settings
} from './icons';
import { API_ENDPOINTS } from '../config';
import ExecutionBatchBanner from './ExecutionBatchBanner';
import { ensureExecutionContextPayload } from '../utils/executionContext';

type TestMode = 'chaos' | 'mobile';

// ============================================================
// Chaos Engineering Panel
// ============================================================
interface ChaosScenario {
    id: string;
    name: string;
    description: string;
}

interface ChaosResult {
    scenario: string;
    status: string;
    duration_ms: number;
    details: string;
    metrics: Record<string, unknown>;
}

const SCENARIO_ICONS: Record<string, React.ReactNode> = {
    'slow_network': <Wifi className="w-4 h-4" />,
    'offline_recovery': <WifiOff className="w-4 h-4" />,
    'api_timeout': <Timer className="w-4 h-4" />,
    'api_500': <XCircle className="w-4 h-4" />,
    'cpu_throttle': <Cpu className="w-4 h-4" />,
    'large_payload': <HardDrive className="w-4 h-4" />,
    'memory_pressure': <HardDrive className="w-4 h-4" />,
};

const ChaosPanel: React.FC<{ url: string }> = ({ url }) => {
    const [scenarios, setScenarios] = useState<ChaosScenario[]>([]);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [results, setResults] = useState<ChaosResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [showCustom, setShowCustom] = useState(false);
    const [customName, setCustomName] = useState('');
    const [customLatency, setCustomLatency] = useState(3000);
    const [customErrorRate, setCustomErrorRate] = useState(50);
    const [customTimeout, setCustomTimeout] = useState(10);

    useEffect(() => {
        fetch(API_ENDPOINTS.chaos.scenarios)
            .then(r => r.json())
            .then(d => {
                const s = d.scenarios || [];
                setScenarios(s);
                setSelected(new Set(s.map((x: ChaosScenario) => x.id)));
            })
            .catch(() => { });
    }, []);

    const toggleScenario = (id: string) => {
        const n = new Set(selected);
        if (n.has(id)) {
            n.delete(id);
        } else {
            n.add(id);
        }
        setSelected(n);
    };

    const runChaos = async () => {
        if (!url || selected.size === 0) return;
        setLoading(true);
        setResults([]);
        try {
            const res = await fetch(API_ENDPOINTS.chaos.run, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, scenarios: Array.from(selected), ...ensureExecutionContextPayload('混沌专项测试', { targetUrl: url }) })
            });
            const data = await res.json();
            setResults(data.results || []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 flex-1 min-h-0">
            {/* Scenario Selection */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-4">
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-slate-700 dark:text-white flex items-center gap-2">
                        <Flame className="w-4 h-4 text-orange-500" /> 混沌场景 ({selected.size}/{scenarios.length})
                    </h3>
                    <button onClick={runChaos} disabled={loading || !url || selected.size === 0}
                        className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-orange-500/20 active:scale-95 transition-all disabled:opacity-50">
                        {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Flame className="w-4 h-4" />}
                        启动混沌测试
                    </button>
                </div>

                {/* Select All / Deselect All */}
                <div className="flex gap-2 mb-2">
                    <button onClick={() => setSelected(new Set(scenarios.map(s => s.id)))} className="text-[11px] text-slate-400 hover:text-orange-500 transition-colors">全选</button>
                    <button onClick={() => setSelected(new Set())} className="text-[11px] text-slate-400 hover:text-orange-500 transition-colors">全不选</button>
                </div>
                <div className="grid grid-cols-2 xl:grid-cols-4 gap-2">
                    {scenarios.map(s => (
                        <button key={s.id} onClick={() => toggleScenario(s.id)}
                            className={`p-3 rounded-lg border text-left text-xs transition-all ${selected.has(s.id)
                                ? 'bg-orange-50 dark:bg-orange-500/10 border-orange-300 dark:border-orange-500/30 text-orange-700 dark:text-orange-300'
                                : 'bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500'
                                }`}>
                            <div className="flex items-center gap-1.5 mb-1">
                                {SCENARIO_ICONS[s.id] || <Flame className="w-3.5 h-3.5" />}
                                <span className="font-medium">{s.name}</span>
                            </div>
                            <p className="opacity-70 text-[11px]">{s.description}</p>
                        </button>
                    ))}
                </div>

                {/* Custom Scenario Creator */}
                <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
                    <button onClick={() => setShowCustom(!showCustom)}
                        className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-orange-500 font-medium transition-colors w-full">
                        <Plus className={`w-3 h-3 ${showCustom ? 'rotate-45' : ''} transition-transform`} />
                        自定义混沌场景
                        <Settings className={`w-3 h-3 ml-auto ${showCustom ? 'rotate-90' : ''} transition-transform`} />
                    </button>
                    {showCustom && (
                        <div className="mt-2 space-y-2 animate-in slide-in-from-top-2 duration-200">
                            <input type="text" value={customName} onChange={e => setCustomName(e.target.value)}
                                placeholder="场景名称，例如: 随机延迟峰值"
                                className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-1.5 outline-none focus:ring-2 focus:ring-orange-500/30 placeholder-slate-400" />
                            <div className="grid grid-cols-3 gap-2">
                                <div>
                                    <label className="block text-[10px] text-slate-400 mb-0.5">延迟 (ms)</label>
                                    <input type="number" value={customLatency} onChange={e => setCustomLatency(Number(e.target.value))} min={0} max={30000}
                                        className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 outline-none focus:ring-2 focus:ring-orange-500/30" />
                                </div>
                                <div>
                                    <label className="block text-[10px] text-slate-400 mb-0.5">错误率 (%)</label>
                                    <input type="number" value={customErrorRate} onChange={e => setCustomErrorRate(Number(e.target.value))} min={0} max={100}
                                        className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 outline-none focus:ring-2 focus:ring-orange-500/30" />
                                </div>
                                <div>
                                    <label className="block text-[10px] text-slate-400 mb-0.5">超时 (s)</label>
                                    <input type="number" value={customTimeout} onChange={e => setCustomTimeout(Number(e.target.value))} min={1} max={120}
                                        className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 outline-none focus:ring-2 focus:ring-orange-500/30" />
                                </div>
                            </div>
                            <button onClick={() => {
                                if (!customName.trim()) return;
                                const newId = `custom_${Date.now()}`;
                                setScenarios(prev => [...prev, { id: newId, name: customName, description: `延迟 ${customLatency}ms, 错误率 ${customErrorRate}%, 超时 ${customTimeout}s` }]);
                                setSelected(prev => new Set([...prev, newId]));
                                setCustomName('');
                                setShowCustom(false);
                            }}
                                disabled={!customName.trim()}
                                className="w-full px-3 py-1.5 text-xs font-medium bg-orange-500/10 text-orange-600 dark:text-orange-400 border border-orange-500/30 rounded-lg hover:bg-orange-500/20 transition-colors disabled:opacity-50">
                                + 添加场景
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Results */}
            <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col min-h-0">
                <div className="p-3 border-b border-slate-200 dark:border-slate-800">
                    <span className="text-sm font-bold text-slate-700 dark:text-white">
                        测试结果 ({results.length})
                    </span>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                    {results.length === 0 ? (
                        <div className="p-8 text-center text-slate-400">
                            <Flame className="w-10 h-10 mx-auto mb-3 opacity-20" />
                            <p className="text-sm">选择场景并点击启动</p>
                        </div>
                    ) : results.map((r, i) => (
                        <div key={i} className={`p-4 rounded-lg border ${r.status === 'passed' ? 'bg-green-50 dark:bg-green-500/5 border-green-200 dark:border-green-800'
                            : r.status === 'failed' ? 'bg-red-50 dark:bg-red-500/5 border-red-200 dark:border-red-800'
                                : 'bg-yellow-50 dark:bg-yellow-500/5 border-yellow-200 dark:border-yellow-800'
                            }`}>
                            <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                    {r.status === 'passed' ? <CheckCircle className="w-4 h-4 text-green-500" />
                                        : r.status === 'failed' ? <XCircle className="w-4 h-4 text-red-500" />
                                            : <AlertTriangle className="w-4 h-4 text-yellow-500" />}
                                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{r.scenario}</span>
                                </div>
                                <span className="text-xs font-mono text-slate-400">{Math.round(r.duration_ms)}ms</span>
                            </div>
                            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">{r.details}</p>
                            {r.metrics && Object.keys(r.metrics).length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                    {Object.entries(r.metrics).map(([k, v]) => (
                                        <span key={k} className="text-[10px] px-2 py-0.5 rounded-full bg-white/50 dark:bg-black/20 text-slate-500 font-mono">
                                            {k}: {typeof v === 'number' ? v.toLocaleString() : String(v)}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// ============================================================
// Mobile Emulation Panel
// ============================================================
interface DeviceInfo {
    id: string;
    name: string;
    viewport: string;
    type: string;
}

interface DeviceResult {
    device: string;
    viewport: string;
    issues: { rule_id: string; description: string; severity: string; device: string; suggestion?: string }[];
    metrics: Record<string, unknown>;
}

const MobilePanel: React.FC<{ url: string }> = ({ url }) => {
    const [devices, setDevices] = useState<DeviceInfo[]>([]);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [results, setResults] = useState<DeviceResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [expanded, setExpanded] = useState<Set<number>>(new Set());

    useEffect(() => {
        fetch(API_ENDPOINTS.mobile.devices)
            .then(r => r.json())
            .then(d => {
                const devs = d.devices || [];
                setDevices(devs);
                setSelected(new Set(devs.filter((x: DeviceInfo) => ['iphone_14', 'pixel_7', 'ipad_pro'].includes(x.id)).map((x: DeviceInfo) => x.id)));
            })
            .catch(() => { });
    }, []);

    const toggleDevice = (id: string) => {
        const n = new Set(selected);
        if (n.has(id)) {
            n.delete(id);
        } else {
            n.add(id);
        }
        setSelected(n);
    };

    const runMobile = async () => {
        if (!url || selected.size === 0) return;
        setLoading(true);
        setResults([]);
        try {
            const res = await fetch(API_ENDPOINTS.mobile.test, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, devices: Array.from(selected), ...ensureExecutionContextPayload('移动专项测试', { targetUrl: url }) })
            });
            const data = await res.json();
            setResults(data.results || []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const toggleExpand = (i: number) => {
        const n = new Set(expanded);
        if (n.has(i)) {
            n.delete(i);
        } else {
            n.add(i);
        }
        setExpanded(n);
    };

    return (
        <div className="flex flex-col gap-4 flex-1 min-h-0">
            {/* Device Selection */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-4">
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-slate-700 dark:text-white flex items-center gap-2">
                        <Smartphone className="w-4 h-4 text-sky-500" /> 设备选择 ({selected.size}/{devices.length})
                    </h3>
                    <button onClick={runMobile} disabled={loading || !url || selected.size === 0}
                        className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-sky-500/20 active:scale-95 transition-all disabled:opacity-50">
                        {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <MonitorSmartphone className="w-4 h-4" />}
                        启动设备测试
                    </button>
                </div>
                <div className="flex flex-wrap gap-2">
                    {devices.map(d => (
                        <button key={d.id} onClick={() => toggleDevice(d.id)}
                            className={`px-3 py-2 rounded-lg border text-xs font-medium transition-all ${selected.has(d.id)
                                ? 'bg-sky-50 dark:bg-sky-500/10 border-sky-300 dark:border-sky-500/30 text-sky-700 dark:text-sky-300'
                                : 'bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500'
                                }`}>
                            {d.type === 'tablet' ? '□' : '■'} {d.name}
                            <span className="text-[10px] opacity-60 ml-1">{d.viewport}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Results */}
            <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col min-h-0">
                <div className="p-3 border-b border-slate-200 dark:border-slate-800">
                    <span className="text-sm font-bold text-slate-700 dark:text-white">
                        设备测试结果 ({results.length})
                    </span>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                    {results.length === 0 ? (
                        <div className="p-8 text-center text-slate-400">
                            <Smartphone className="w-10 h-10 mx-auto mb-3 opacity-20" />
                            <p className="text-sm">选择设备并点击启动</p>
                        </div>
                    ) : results.map((r, i) => (
                        <div key={i} className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                            <div className="p-3 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between cursor-pointer"
                                onClick={() => toggleExpand(i)}>
                                <div className="flex items-center gap-2">
                                    <Smartphone className="w-4 h-4 text-sky-500" />
                                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{r.device}</span>
                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-500 font-mono">{r.viewport}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    {r.issues.length === 0 ? (
                                        <span className="text-xs text-green-500 flex items-center gap-1"><CheckCircle className="w-3.5 h-3.5" /> 无问题</span>
                                    ) : (
                                        <span className="text-xs text-orange-500">{r.issues.length} 个问题</span>
                                    )}
                                    <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${expanded.has(i) ? 'rotate-180' : ''}`} />
                                </div>
                            </div>
                            {expanded.has(i) && (
                                <div className="p-3 space-y-2">
                                    {r.issues.length === 0 ? (
                                        <p className="text-xs text-green-500 text-center">✓ 该设备测试通过</p>
                                    ) : r.issues.map((issue, j) => (
                                        <div key={j} className={`p-2 rounded text-xs ${issue.severity === 'critical' ? 'bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400'
                                            : issue.severity === 'major' ? 'bg-orange-50 dark:bg-orange-500/10 text-orange-600 dark:text-orange-400'
                                                : 'bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400'
                                            }`}>
                                            <p className="font-medium">{issue.description}</p>
                                            {issue.suggestion && <p className="mt-1 opacity-70">→ {issue.suggestion}</p>}
                                        </div>
                                    ))}
                                    {r.metrics && Object.keys(r.metrics).length > 0 && (
                                        <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                                            <p className="text-[10px] font-medium text-slate-400 mb-1">指标</p>
                                            <div className="flex flex-wrap gap-2">
                                                {Object.entries(r.metrics).filter(([k]) => typeof r.metrics[k] !== 'object').map(([k, v]) => (
                                                    <span key={k} className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 font-mono">
                                                        {k}: {String(v)}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// ============================================================
// Main Component
// ============================================================
const ResilienceTesting: React.FC = () => {
    const [mode, setMode] = useState<TestMode>('chaos');
    const [url, setUrl] = useState('');

    return (
        <div className="flex flex-col h-full gap-4 animate-in fade-in duration-500">
            <ExecutionBatchBanner standaloneHint="这里的混沌测试和移动端测试会作为独立子记录写入执行中心。" />

            {/* Mode Tabs + URL Bar */}
            <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/50">
                    <button onClick={() => setMode('chaos')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${mode === 'chaos'
                            ? 'text-orange-500 bg-orange-500/10 border border-orange-500/30 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 border border-transparent'
                            }`}>
                        <Flame className="w-4 h-4" /> 混沌工程
                    </button>
                    <button onClick={() => setMode('mobile')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${mode === 'mobile'
                            ? 'text-sky-500 bg-sky-500/10 border border-sky-500/30 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 border border-transparent'
                            }`}>
                        <Smartphone className="w-4 h-4" /> 移动端模拟
                    </button>
                </div>
                <input type="text" value={url} onChange={(e) => setUrl(e.target.value)}
                    placeholder="输入要测试的 URL"
                    className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
            </div>

            {/* Panels */}
            {mode === 'chaos' && <ChaosPanel url={url} />}
            {mode === 'mobile' && <MobilePanel url={url} />}
        </div>
    );
};

export default ResilienceTesting;
