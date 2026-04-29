import React, { useState, useCallback } from 'react';
import {
    Smartphone, Play, RefreshCw, Monitor, Tablet,
    CheckCircle2, AlertTriangle, RotateCcw, Plus, X
} from '../components/icons';
import Badge from '../components/ui/Badge';
import PageHeader from '../components/ui/PageHeader';
import { API_BASE_URL } from '../config';

// ── Types ──
interface DevicePreset {
    name: string;
    width: number;
    height: number;
    deviceScaleFactor: number;
    userAgent: string;
    icon: React.ReactNode;
}

interface MobileIssue {
    ruleId: string;
    description: string;
    severity: string;
    device: string;
    suggestion: string;
}

interface RawMobileIssue {
    ruleId?: string;
    rule_id?: string;
    description?: string;
    severity?: string;
    device?: string;
    suggestion?: string;
}

interface MobileViewport {
    width: number;
    height: number;
}

interface RawMobileTestResult {
    device: string;
    viewport?: string | MobileViewport;
    issues?: Array<string | RawMobileIssue>;
    screenshot_url?: string;
    score?: number;
}

interface MobileTestResult {
    device: string;
    viewport: MobileViewport;
    viewportText: string;
    issues: MobileIssue[];
    screenshot_url?: string;
    score: number;
}

interface MobileTestResponse {
    results?: RawMobileTestResult[];
}

const ISSUE_SEVERITY_STYLES: Record<string, string> = {
    critical: 'bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300',
    major: 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
    minor: 'bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
    info: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300',
    unknown: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300',
};

const ISSUE_SEVERITY_LABELS: Record<string, string> = {
    critical: '严重',
    major: '主要',
    minor: '次要',
    info: '提示',
    unknown: '未知',
};

const toSafeText = (value: unknown, fallback = ''): string => {
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    return fallback;
};

export const normalizeMobileIssue = (issue: string | RawMobileIssue | undefined, fallbackDevice: string): MobileIssue => {
    if (typeof issue === 'string') {
        return {
            ruleId: '',
            description: issue,
            severity: 'unknown',
            device: fallbackDevice,
            suggestion: '',
        };
    }

    const raw = issue && typeof issue === 'object' ? issue : {};
    return {
        ruleId: toSafeText((raw as Record<string, unknown>).ruleId ?? (raw as Record<string, unknown>).rule_id, ''),
        description: toSafeText(raw.description, '存在移动端问题'),
        severity: toSafeText(raw.severity, 'unknown').toLowerCase() || 'unknown',
        device: toSafeText(raw.device, fallbackDevice) || fallbackDevice,
        suggestion: toSafeText(raw.suggestion, ''),
    };
};

const parseViewport = (viewport: string | MobileViewport | undefined): MobileViewport => {
    if (viewport && typeof viewport === 'object') {
        return {
            width: Number(viewport.width || 0),
            height: Number(viewport.height || 0),
        };
    }

    if (typeof viewport === 'string') {
        const match = viewport.match(/(\d+)\s*[xX×]\s*(\d+)/);
        if (match) {
            return {
                width: Number(match[1]),
                height: Number(match[2]),
            };
        }
    }

    return { width: 0, height: 0 };
};

const calculateDeviceScore = (issues: MobileIssue[]): number => {
    const deduction = issues.reduce((total, issue) => {
        if (issue.severity === 'critical') return total + 20;
        if (issue.severity === 'major') return total + 10;
        if (issue.severity === 'minor') return total + 3;
        return total + 1;
    }, 0);
    return Math.max(0, Math.min(100, 100 - deduction));
};

export const normalizeMobileTestResult = (raw: RawMobileTestResult): MobileTestResult => {
    const device = toSafeText(raw.device, '未知设备');
    const viewport = parseViewport(raw.viewport);
    const issues = (raw.issues || []).map(issue => normalizeMobileIssue(issue, device));
    return {
        device,
        viewport,
        viewportText: viewport.width > 0 && viewport.height > 0 ? `${viewport.width}×${viewport.height}` : '未知视口',
        issues,
        screenshot_url: raw.screenshot_url,
        score: typeof raw.score === 'number' ? raw.score : calculateDeviceScore(issues),
    };
};

const DEVICE_PRESETS: DevicePreset[] = [
    { name: 'iPhone 14 Pro', width: 393, height: 852, deviceScaleFactor: 3, userAgent: 'iPhone', icon: <Smartphone className="w-4 h-4" /> },
    { name: 'iPhone SE', width: 375, height: 667, deviceScaleFactor: 2, userAgent: 'iPhone', icon: <Smartphone className="w-4 h-4" /> },
    { name: 'Pixel 7', width: 412, height: 915, deviceScaleFactor: 2.625, userAgent: 'Android', icon: <Smartphone className="w-4 h-4" /> },
    { name: 'iPad Air', width: 820, height: 1180, deviceScaleFactor: 2, userAgent: 'iPad', icon: <Tablet className="w-4 h-4" /> },
    { name: 'Galaxy Tab S8', width: 800, height: 1280, deviceScaleFactor: 2, userAgent: 'Android', icon: <Tablet className="w-4 h-4" /> },
    { name: 'Desktop 1920', width: 1920, height: 1080, deviceScaleFactor: 1, userAgent: 'Desktop', icon: <Monitor className="w-4 h-4" /> },
];

// ── API ──
const runMobileTest = async (url: string, devices: string[]): Promise<MobileTestResponse> => {
    const res = await fetch(`${API_BASE_URL}/api/mobile/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, devices }),
    });
    return res.json();
};

// ============================================================================
const MobilePage: React.FC = () => {
    const [url, setUrl] = useState('');
    const [selectedDevices, setSelectedDevices] = useState<string[]>(['iPhone 14 Pro', 'Pixel 7', 'iPad Air']);
    const [results, setResults] = useState<MobileTestResult[]>([]);
    const [testing, setTesting] = useState(false);
    const [isLandscape, setIsLandscape] = useState(false);
    const [customWidth, setCustomWidth] = useState('390');
    const [customHeight, setCustomHeight] = useState('844');
    const [customScale, setCustomScale] = useState('2');
    const [customDevices, setCustomDevices] = useState<DevicePreset[]>([]);

    const addCustomDevice = () => {
        const w = parseInt(customWidth) || 390;
        const h = parseInt(customHeight) || 844;
        const s = parseFloat(customScale) || 2;
        const name = `Custom ${w}×${h}`;
        if (customDevices.some(d => d.name === name)) return;
        setCustomDevices(prev => [...prev, { name, width: w, height: h, deviceScaleFactor: s, userAgent: 'Custom', icon: <Monitor className="w-4 h-4" /> }]);
        setSelectedDevices(prev => [...prev, name]);
    };

    const removeCustomDevice = (name: string) => {
        setCustomDevices(prev => prev.filter(d => d.name !== name));
        setSelectedDevices(prev => prev.filter(d => d !== name));
    };

    const allDevices = [...DEVICE_PRESETS, ...customDevices].map(d => isLandscape
        ? { ...d, width: d.height, height: d.width }
        : d
    );

    const toggleDevice = (name: string) => {
        setSelectedDevices(prev =>
            prev.includes(name) ? prev.filter(d => d !== name) : [...prev, name]
        );
    };

    const handleTest = useCallback(async () => {
        if (!url || selectedDevices.length === 0) return;
        setTesting(true);
        try {
            const r = await runMobileTest(url, selectedDevices);
            setResults((r.results || []).map(normalizeMobileTestResult));
        } catch { /* */ }
        setTesting(false);
    }, [url, selectedDevices]);

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            <PageHeader
                icon={<Smartphone className="w-5 h-5" />}
                title="移动端模拟测试"
                description="选择设备、输入 URL，检测响应式布局和移动端兼容性"
                accent="pink"
            />

            {/* Config */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-4">
                <div className="grid md:grid-cols-3 gap-3 items-end">
                    <div className="md:col-span-2 space-y-1">
                        <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">目标 URL</label>
                        <input type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://example.com" className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-pink-500/30" />
                    </div>
                    <button onClick={handleTest} disabled={testing || !url || selectedDevices.length === 0} className="flex items-center justify-center gap-2 rounded-lg bg-pink-500 hover:bg-pink-600 text-white text-sm font-medium py-2 transition-colors disabled:opacity-50">
                        {testing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                        {testing ? '测试中...' : `测试 (${selectedDevices.length} 设备)`}
                    </button>
                </div>

                {/* Device Selection */}
                <div>
                    <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-2 flex items-center justify-between">
                        <span>选择设备</span>
                        <button onClick={() => setIsLandscape(!isLandscape)}
                            className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium transition-all border ${isLandscape
                                ? 'bg-pink-50 dark:bg-pink-900/20 border-pink-300 dark:border-pink-500/30 text-pink-600'
                                : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-pink-300'}`}>
                            <RotateCcw className="w-3 h-3" />
                            {isLandscape ? '横屏' : '竖屏'}
                        </button>
                    </label>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
                        {allDevices.map(device => (
                            <button
                                key={device.name}
                                onClick={() => toggleDevice(device.name)}
                                className={`relative flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-all ${selectedDevices.includes(device.name)
                                    ? 'border-pink-500 bg-pink-50 dark:bg-pink-900/20 text-pink-600 dark:text-pink-400'
                                    : 'border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300'
                                    }`}
                            >
                                {device.icon}
                                <div className="text-left">
                                    <div className="font-medium">{device.name}</div>
                                    <div className="text-[10px] opacity-60">{device.width}×{device.height}</div>
                                </div>
                                {customDevices.some(cd => cd.name === device.name) && (
                                    <button onClick={e => { e.stopPropagation(); removeCustomDevice(device.name); }}
                                        className="absolute -top-1 -right-1 p-0.5 bg-red-500 rounded-full text-white opacity-0 group-hover:opacity-100 hover:bg-red-600 transition">
                                        <X className="w-2.5 h-2.5" />
                                    </button>
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Custom Resolution */}
                    <div className="mt-3 flex items-end gap-2">
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">宽</label>
                            <input type="number" value={customWidth} onChange={e => setCustomWidth(e.target.value)}
                                className="w-20 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 outline-none focus:ring-2 focus:ring-pink-500/30" />
                        </div>
                        <span className="text-slate-400 text-xs pb-1.5">×</span>
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">高</label>
                            <input type="number" value={customHeight} onChange={e => setCustomHeight(e.target.value)}
                                className="w-20 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 outline-none focus:ring-2 focus:ring-pink-500/30" />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] text-slate-400">缩放</label>
                            <input type="number" step="0.5" value={customScale} onChange={e => setCustomScale(e.target.value)}
                                className="w-16 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 outline-none focus:ring-2 focus:ring-pink-500/30" />
                        </div>
                        <button onClick={addCustomDevice}
                            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-pink-600 bg-pink-50 dark:bg-pink-900/20 border border-pink-200 dark:border-pink-800 rounded-lg hover:bg-pink-100 transition">
                            <Plus className="w-3 h-3" /> 添加
                        </button>
                    </div>
                </div>
            </div>

            {/* Results */}
            {results.length > 0 ? (
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {results.map((result, i) => (
                        <div key={i} className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
                            {/* Device Header */}
                            <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Smartphone className="w-4 h-4 text-pink-500" />
                                    <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{result.device}</span>
                                </div>
                                <Badge variant={result.score >= 80 ? 'success' : result.score >= 50 ? 'warning' : 'error'} size="sm">
                                    {result.score}/100
                                </Badge>
                            </div>
                            {/* Viewport Info */}
                            <div className="px-4 py-2 bg-slate-50 dark:bg-slate-800/50 text-[10px] text-slate-400 flex items-center gap-3">
                                <span>{result.viewportText}</span>
                            </div>
                            {/* Issues */}
                            <div className="px-4 py-3 space-y-1.5">
                                {result.issues.length === 0 ? (
                                    <div className="flex items-center gap-2 text-emerald-500 text-xs">
                                        <CheckCircle2 className="w-3.5 h-3.5" /> 无问题
                                    </div>
                                ) : (
                                    result.issues.map((issue, j) => (
                                        <div key={j} className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-300">
                                            <AlertTriangle className="w-3 h-3 mt-0.5 text-amber-500 shrink-0" />
                                            <div className="min-w-0 space-y-1">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span>{issue.description}</span>
                                                    <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${ISSUE_SEVERITY_STYLES[issue.severity] || ISSUE_SEVERITY_STYLES.unknown}`}>
                                                        {ISSUE_SEVERITY_LABELS[issue.severity] || issue.severity || '未知'}
                                                    </span>
                                                </div>
                                                {issue.ruleId && (
                                                    <div className="text-[10px] text-slate-400">
                                                        规则：{issue.ruleId}
                                                    </div>
                                                )}
                                                {issue.suggestion && (
                                                    <div className="text-[10px] text-slate-500 dark:text-slate-400">
                                                        建议：{issue.suggestion}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 p-12 text-center">
                    <Smartphone className="w-12 h-12 text-pink-300 dark:text-pink-700 mx-auto mb-3" />
                    <p className="text-sm font-medium text-slate-500 dark:text-slate-400">选择设备并输入 URL 开始移动端测试</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">检测响应式布局、触摸适配、视口兼容性</p>
                </div>
            )}
        </div>
    );
};

export default MobilePage;
