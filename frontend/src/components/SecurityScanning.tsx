import React, { useState, useEffect } from 'react';
import { Shield, Play, Square, AlertTriangle, AlertCircle, Info, CheckCircle, FileText, Trash2, ShieldCheck, Bug } from './icons';
import { API_ENDPOINTS, DEFAULT_CONFIG } from '../config';
import ExecutionBatchBanner from './ExecutionBatchBanner';
import { ensureExecutionContextPayload } from '../utils/executionContext';

interface SecurityAlert {
    name: string;
    risk: string;
    confidence: string;
    url: string;
    description: string;
    solution: string;
}

interface ScanResult {
    scan_id: string;
    status: string;
    stats: {
        total_alerts: number;
        high: number;
        medium: number;
        low: number;
        info?: number;
    };
    alerts_count: number;
}

interface ScanHistory {
    scan_id: string;
    status: string;
    stats: {
        high: number;
        medium: number;
        low: number;
    };
    finished_at: string;
    duration: number;
    alerts: SecurityAlert[];
}

const SecurityScanning: React.FC = () => {
    const [targetUrl, setTargetUrl] = useState<string>(DEFAULT_CONFIG.securityScanUrl);
    const [scanType, setScanType] = useState('standard');
    const [vulnTypes, setVulnTypes] = useState<string[]>(['xss', 'sqli', 'csrf', 'headers']);
    const [isScanning, setIsScanning] = useState(false);
    const [result, setResult] = useState<ScanResult | null>(null);
    const [history, setHistory] = useState<ScanHistory[]>([]);
    const [selectedScan, setSelectedScan] = useState<ScanHistory | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchHistory();
    }, []);

    const fetchHistory = async () => {
        try {
            const res = await fetch(API_ENDPOINTS.security.history);
            const data = await res.json();
            setHistory(data.history || []);
        } catch (e) {
            console.error('Failed to fetch history:', e);
        }
    };

    const runScan = async () => {
        setIsScanning(true);
        setError(null);
        setResult(null);

        try {
            const res = await fetch(API_ENDPOINTS.security.scan, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_url: targetUrl,
                    scan_type: scanType,
                    vuln_types: vulnTypes.length > 0 ? vulnTypes : undefined,
                    ...ensureExecutionContextPayload("Security test suite", { targetUrl }),
                })
            });

            const data = await res.json();
            if (data.status === 'success') {
                setResult(data);
                fetchHistory();
            } else {
                setError(data.detail || 'Scan failed');
            }
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Connection error');
        } finally {
            setIsScanning(false);
        }
    };

    const stopScan = async () => {
        try {
            await fetch(API_ENDPOINTS.security.stop, { method: 'POST' });
            setIsScanning(false);
        } catch (e) {
            console.error('Failed to stop scan:', e);
        }
    };

    const deleteHistory = async (scanId: string) => {
        if (!confirm("Delete this record?")) return;
        try {
            await fetch(API_ENDPOINTS.security.delete(scanId), { method: 'DELETE' });
            fetchHistory();
        } catch (e) {
            console.error('Failed to delete:', e);
        }
    };

    const clearHistory = async () => {
        if (!confirm("Clear all scan history? This cannot be undone.")) return;
        try {
            await fetch(API_ENDPOINTS.security.clear, { method: 'DELETE' });
            setHistory([]);
        } catch (e) {
            console.error('Failed to clear:', e);
        }
    };



    const getRiskIcon = (risk: string) => {
        switch (risk.toLowerCase()) {
            case 'high': return <AlertCircle className="w-4 h-4" />;
            case 'medium': return <AlertTriangle className="w-4 h-4" />;
            case 'low': return <Info className="w-4 h-4" />;
            default: return <Info className="w-4 h-4" />;
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <ExecutionBatchBanner standaloneHint={"Security scan results are saved in the execution center. The first run creates a specialized test batch if none is active."} />

            {/* Configuration panel*/}
            <div className="relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6 transition-all hover:border-slate-300 dark:hover:border-slate-700">
                <h2 className="text-xl font-bold text-slate-900 dark:text-red-400 mb-6 flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-red-500/10">
                        <Shield className="w-5 h-5 text-red-500" />
                    </div>
                    Security scan configuration
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Target URL</label>
                        <input
                            type="text"
                            value={targetUrl}
                            onChange={(e) => setTargetUrl(e.target.value)}
                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2.5 text-slate-900 dark:text-white focus:ring-2 focus:ring-red-500/20 focus:border-red-500 transition-all outline-none"
                            disabled={isScanning}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Scan type</label>
                        <select
                            value={scanType}
                            onChange={(e) => setScanType(e.target.value)}
                            className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2.5 text-slate-900 dark:text-white focus:ring-2 focus:ring-red-500/20 focus:border-red-500 transition-all outline-none"
                            disabled={isScanning}
                        >
                            <option value="quick">Quick scan</option>
                            <option value="standard">Standard scan</option>
                            <option value="full">Full scan</option>
                        </select>
                    </div>
                </div>

                {/* Vulnerability Type Selection */}
                <div className="mt-4">
                    <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 flex items-center gap-1.5">
                        <Bug className="w-3.5 h-3.5" /> Vulnerability types
                    </label>
                    <div className="flex flex-wrap gap-2">
                        {[
                            { key: 'xss', label: "Cross-site scripting (XSS)", color: 'red' },
                            { key: 'sqli', label: "SQL injection", color: 'orange' },
                            { key: 'csrf', label: 'CSRF', color: 'amber' },
                            { key: 'traversal', label: "Directory traversal", color: 'yellow' },
                            { key: 'info_leak', label: "Information disclosure", color: 'blue' },
                            { key: 'headers', label: "Missing security headers", color: 'purple' },
                            { key: 'ssl', label: 'SSL/TLS', color: 'teal' },
                            { key: 'sensitive', label: "Sensitive files", color: 'pink' },
                        ].map(vt => {
                            const active = vulnTypes.includes(vt.key);
                            return (
                                <button key={vt.key} disabled={isScanning}
                                    onClick={() => setVulnTypes(prev => active ? prev.filter(k => k !== vt.key) : [...prev, vt.key])}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all disabled:opacity-50 ${active
                                        ? `bg-${vt.color}-500/10 text-${vt.color}-600 dark:text-${vt.color}-400 border-${vt.color}-500/30 shadow-sm`
                                        : 'bg-slate-50 dark:bg-slate-800 text-slate-400 border-slate-200 dark:border-slate-700 hover:border-slate-300'
                                        }`}
                                >
                                    {active ? '✔ ' : ''}{vt.label}
                                </button>
                            );
                        })}
                    </div>
                    <div className="mt-2 flex gap-2">
                        <button onClick={() => setVulnTypes(['xss', 'sqli', 'csrf', 'traversal', 'info_leak', 'headers', 'ssl', 'sensitive'])} disabled={isScanning}
                            className="text-[11px] text-slate-400 hover:text-slate-600 transition-colors disabled:opacity-50">Select all</button>
                        <button onClick={() => setVulnTypes([])} disabled={isScanning}
                            className="text-[11px] text-slate-400 hover:text-slate-600 transition-colors disabled:opacity-50">Deselect all</button>
                    </div>
                </div>

                <div className="flex gap-4 mt-8">
                    {!isScanning ? (
                        <button
                            onClick={runScan}
                            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 text-white rounded-lg font-medium shadow-lg shadow-red-500/20 hover:shadow-red-500/40 active:scale-95 transition-all duration-200"
                        >
                            <Play className="w-4 h-4 fill-current" />
                            Start scan
                        </button>
                    ) : (
                        <button
                            onClick={stopScan}
                            className="flex items-center gap-2 px-6 py-2.5 bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-lg font-medium active:scale-95 transition-all duration-200"
                        >
                            <Square className="w-4 h-4 fill-current" />
                            Stop scan
                        </button>
                    )}
                </div>

                {error && (
                    <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/50 rounded-lg text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                        {error}
                    </div>
                )}
            </div>

            {/* Results panel*/}
            {result && result.stats && (
                <div className="relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6">
                    <div className="absolute top-0 right-0 p-6 pointer-events-none">
                        <div className="w-32 h-32 bg-red-500/5 rounded-full blur-3xl" />
                    </div>

                    <h2 className="text-xl font-bold text-slate-900 dark:text-green-400 mb-6 flex items-center gap-2">
                        <div className="p-2 rounded-lg bg-green-500/10">
                            <CheckCircle className="w-5 h-5 text-green-500" />
                        </div>
                        Scan results
                    </h2>

                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-5 border border-slate-100 dark:border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 left-0 w-1 h-full bg-red-500 group-hover:w-1.5 transition-all" />
                            <div className="text-sm text-slate-500 dark:text-slate-400 mb-1 pl-2">High risk</div>
                            <div className="text-3xl font-bold text-red-500 pl-2">{result.stats.high}</div>
                        </div>
                        <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-5 border border-slate-100 dark:border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 left-0 w-1 h-full bg-orange-500 group-hover:w-1.5 transition-all" />
                            <div className="text-sm text-slate-500 dark:text-slate-400 mb-1 pl-2">Medium risk</div>
                            <div className="text-3xl font-bold text-orange-500 pl-2">{result.stats.medium}</div>
                        </div>
                        <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-5 border border-slate-100 dark:border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 left-0 w-1 h-full bg-blue-500 group-hover:w-1.5 transition-all" />
                            <div className="text-sm text-slate-500 dark:text-slate-400 mb-1 pl-2">Low risk</div>
                            <div className="text-3xl font-bold text-blue-500 pl-2">{result.stats.low}</div>
                        </div>
                        <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-5 border border-slate-100 dark:border-slate-800 relative overflow-hidden group">
                            <div className="absolute top-0 left-0 w-1 h-full bg-slate-400 group-hover:w-1.5 transition-all" />
                            <div className="text-sm text-slate-500 dark:text-slate-400 mb-1 pl-2">Informational</div>
                            <div className="text-3xl font-bold text-slate-500 pl-2">{result.stats.info || 0}</div>
                        </div>
                        {/* Security Score */}
                        <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-5 border border-slate-100 dark:border-slate-800 relative overflow-hidden group">
                            <div className={`absolute top-0 left-0 w-1 h-full group-hover:w-1.5 transition-all ${result.stats.high === 0 && result.stats.medium === 0 ? 'bg-emerald-500' : result.stats.high === 0 ? 'bg-amber-500' : 'bg-red-500'
                                }`} />
                            <div className="text-sm text-slate-500 dark:text-slate-400 mb-1 pl-2 flex items-center gap-1">
                                <ShieldCheck className="w-3.5 h-3.5" /> Security score
                            </div>
                            <div className={`text-3xl font-bold pl-2 ${result.stats.high === 0 && result.stats.medium === 0 ? 'text-emerald-500' : result.stats.high === 0 ? 'text-amber-500' : 'text-red-500'
                                }`}>
                                {Math.max(0, 100 - result.stats.high * 25 - result.stats.medium * 10 - result.stats.low * 2)}
                            </div>
                        </div>
                    </div>

                    {/* Severity Distribution Bar */}
                    {result.stats.total_alerts > 0 && (
                        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
                            <div className="text-xs font-medium text-slate-500 mb-2">Risk distribution</div>
                            <div className="flex h-3 rounded-full overflow-hidden bg-slate-100 dark:bg-slate-800">
                                {result.stats.high > 0 && (
                                    <div className="bg-red-500 transition-all" style={{ width: `${(result.stats.high / result.stats.total_alerts) * 100}%` }} />
                                )}
                                {result.stats.medium > 0 && (
                                    <div className="bg-orange-500 transition-all" style={{ width: `${(result.stats.medium / result.stats.total_alerts) * 100}%` }} />
                                )}
                                {result.stats.low > 0 && (
                                    <div className="bg-blue-500 transition-all" style={{ width: `${(result.stats.low / result.stats.total_alerts) * 100}%` }} />
                                )}
                                {(result.stats.info || 0) > 0 && (
                                    <div className="bg-slate-400 transition-all" style={{ width: `${((result.stats.info || 0) / result.stats.total_alerts) * 100}%` }} />
                                )}
                            </div>
                            <div className="flex gap-4 mt-2">
                                <span className="flex items-center gap-1 text-[11px] text-slate-400"><span className="w-2 h-2 rounded-full bg-red-500" />High</span>
                                <span className="flex items-center gap-1 text-[11px] text-slate-400"><span className="w-2 h-2 rounded-full bg-orange-500" />Medium</span>
                                <span className="flex items-center gap-1 text-[11px] text-slate-400"><span className="w-2 h-2 rounded-full bg-blue-500" />Low</span>
                                <span className="flex items-center gap-1 text-[11px] text-slate-400"><span className="w-2 h-2 rounded-full bg-slate-400" />Informational</span>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* History*/}
            {history.length > 0 && (
                <div className="relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-200 flex items-center gap-2">
                            <div className="p-2 rounded-lg bg-slate-500/10">
                                <FileText className="w-5 h-5 text-slate-500" />
                            </div>
                            Scan history
                        </h2>
                        <button
                            onClick={clearHistory}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-colors"
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                            Clear all
                        </button>
                    </div>

                    <div className="space-y-3">
                        {history.slice(0, 5).map((h) => (
                            <div
                                key={h.scan_id}
                                className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition border border-transparent hover:border-slate-200 dark:hover:border-slate-700"
                                onClick={() => setSelectedScan(selectedScan?.scan_id === h.scan_id ? null : h)}
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <span className="font-mono text-cyan-600 dark:text-cyan-400 bg-cyan-500/10 px-2 py-1 rounded text-xs">#{h.scan_id}</span>
                                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${h.status === 'completed'
                                            ? 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20'
                                            : 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20'
                                            }`}>
                                            <span className={`w-1.5 h-1.5 rounded-full ${h.status === 'completed' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                            {h.status}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-4 text-sm font-medium">
                                        {(h.stats?.high || 0) > 0 && <span className="text-red-500 flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {h.stats.high}</span>}
                                        {(h.stats?.medium || 0) > 0 && <span className="text-orange-500 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> {h.stats.medium}</span>}
                                        {(h.stats?.low || 0) > 0 && <span className="text-blue-500 flex items-center gap-1"><Info className="w-3 h-3" /> {h.stats.low}</span>}
                                        <span className="text-slate-400 text-xs font-normal ml-2">{new Date(h.finished_at || Date.now()).toLocaleTimeString()}</span>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); deleteHistory(h.scan_id); }}
                                            className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-500/10 rounded-md transition-colors ml-1"
                                            title={"Delete"}
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </div>

                                {/* Expanded alert details*/}
                                {selectedScan?.scan_id === h.scan_id && h.alerts && h.alerts.length > 0 && (
                                    <div className="mt-4 space-y-2 border-t border-slate-200 dark:border-slate-700 pt-4 animate-in slide-in-from-top-2 duration-200">
                                        {h.alerts.map((alert, i) => (
                                            <div key={i} className={`p-4 rounded-lg border ${alert.risk === 'High' ? 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30' :
                                                alert.risk === 'Medium' ? 'bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/30' :
                                                    'bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/30'
                                                }`}>
                                                <div className="flex items-start gap-3">
                                                    <div className={`mt-0.5 ${alert.risk === 'High' ? 'text-red-500' :
                                                        alert.risk === 'Medium' ? 'text-orange-500' :
                                                            'text-blue-500'
                                                        }`}>
                                                        {getRiskIcon(alert.risk)}
                                                    </div>
                                                    <div>
                                                        <div className={`font-semibold text-sm ${alert.risk === 'High' ? 'text-red-700 dark:text-red-400' :
                                                            alert.risk === 'Medium' ? 'text-orange-700 dark:text-orange-400' :
                                                                'text-blue-700 dark:text-blue-400'
                                                            }`}>
                                                            {alert.name}
                                                        </div>
                                                        <div className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
                                                            {alert.description}
                                                        </div>
                                                        {alert.solution && (
                                                            <div className="mt-2 text-xs bg-white/50 dark:bg-black/20 p-2 rounded border border-slate-200 dark:border-slate-700/50">
                                                                <span className="font-semibold text-slate-700 dark:text-slate-300">Suggested fix:</span>
                                                                <span className="text-slate-600 dark:text-slate-400">{alert.solution}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default SecurityScanning;
