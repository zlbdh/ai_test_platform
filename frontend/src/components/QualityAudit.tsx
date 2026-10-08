import React, { useState } from 'react';
import {
    Eye, Globe, ShieldCheck, Play, RefreshCw,
    CheckCircle, XCircle, AlertTriangle, Info, ChevronDown
} from './icons';
import { API_ENDPOINTS } from '../config';
import ExecutionBatchBanner from './ExecutionBatchBanner';
import { ensureExecutionContextPayload } from '../utils/executionContext';

// ============================================================
// Types
// ============================================================
type AuditType = 'accessibility' | 'i18n' | 'compliance';

interface AuditIssue {
    rule_id: string;
    description: string;
    severity: string;
    wcag_level?: string;
    standard?: string;
    locale?: string;
    element?: string;
    selector?: string;
    suggestion?: string;
    details?: string;
}

interface AuditReport {
    url?: string;
    total_issues: number;
    critical?: number;
    major?: number;
    minor?: number;
    score: number;
    issues: AuditIssue[];
    summary: string;
    passed_rules?: number;
    failed_rules?: number;
    passed_checks?: number;
    failed_checks?: number;
    standards_checked?: string[];
    locales_tested?: string[];
}

const SEVERITY_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
    critical: { icon: <XCircle className="w-4 h-4" />, color: 'text-red-500 bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-800', label: "Critical" },
    major: { icon: <AlertTriangle className="w-4 h-4" />, color: 'text-orange-500 bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-800', label: "Major" },
    minor: { icon: <Info className="w-4 h-4" />, color: 'text-blue-500 bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-800', label: "Minor" },
    info: { icon: <Info className="w-4 h-4" />, color: 'text-slate-500 bg-slate-50 dark:bg-slate-500/10 border-slate-200 dark:border-slate-800', label: "Informational" },
};

const AUDIT_TABS: Record<AuditType, { label: string; icon: React.ReactNode; color: string; desc: string }> = {
    accessibility: { label: "Accessibility", icon: <Eye className="w-4 h-4" />, color: 'text-teal-500 bg-teal-500/10 border-teal-500/30', desc: "Automated WCAG 2.1 AA audit" },
    i18n: { label: "Internationalization", icon: <Globe className="w-4 h-4" />, color: 'text-sky-500 bg-sky-500/10 border-sky-500/30', desc: "Multilingual support and localization checks" },
    compliance: { label: "Compliance", icon: <ShieldCheck className="w-4 h-4" />, color: 'text-amber-500 bg-amber-500/10 border-amber-500/30', desc: "GDPR, SOC 2, and PCI DSS compliance checks" },
};

// ============================================================
// Score Gauge Component
// ============================================================
const ScoreGauge: React.FC<{ score: number }> = ({ score }) => {
    const radius = 60;
    const stroke = 8;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (Math.max(0, score) / 100) * circumference;
    const color = score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';

    return (
        <div className="relative inline-flex items-center justify-center">
            <svg width="140" height="140" className="-rotate-90">
                <circle cx="70" cy="70" r={radius} fill="none" stroke="currentColor" strokeWidth={stroke} className="text-slate-200 dark:text-slate-700" />
                <circle cx="70" cy="70" r={radius} fill="none" stroke={color} strokeWidth={stroke}
                    strokeDasharray={circumference} strokeDashoffset={offset}
                    strokeLinecap="round" className="transition-all duration-1000" />
            </svg>
            <div className="absolute flex flex-col items-center">
                <span className="text-3xl font-bold" style={{ color }}>{score < 0 ? '--' : score}</span>
                <span className="text-xs text-slate-400">/ 100</span>
            </div>
        </div>
    );
};

// ============================================================
// Issue List Component
// ============================================================
const IssueList: React.FC<{ issues: AuditIssue[] }> = ({ issues }) => {
    const [expanded, setExpanded] = useState<Set<number>>(new Set());

    const toggle = (i: number) => {
        const n = new Set(expanded);
        n.has(i) ? n.delete(i) : n.add(i);
        setExpanded(n);
    };

    if (issues.length === 0) {
        return (
            <div className="p-8 text-center text-slate-400">
                <CheckCircle className="w-10 h-10 mx-auto mb-3 text-green-400 opacity-50" />
                <p className="text-sm">No issues found</p>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {issues.map((issue, i) => {
                const sev = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.info;
                return (
                    <div key={i} className={`rounded-lg border p-3 cursor-pointer transition-all ${sev.color}`}
                        onClick={() => toggle(i)}>
                        <div className="flex items-start gap-2">
                            {sev.icon}
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium">{issue.description}</span>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/50 dark:bg-black/20 font-mono">{issue.rule_id}</span>
                                    {issue.wcag_level && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/50 dark:bg-black/20">WCAG {issue.wcag_level}</span>}
                                    {issue.standard && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/50 dark:bg-black/20">{issue.standard}</span>}
                                    {issue.locale && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/50 dark:bg-black/20">{issue.locale}</span>}
                                </div>
                                {expanded.has(i) && (
                                    <div className="mt-2 space-y-1 text-xs opacity-80">
                                        {issue.element && <p><span className="font-medium">Element: </span><code className="bg-white/30 dark:bg-black/20 px-1 rounded">{issue.element}</code></p>}
                                        {issue.selector && <p><span className="font-medium">Selector: </span><code className="bg-white/30 dark:bg-black/20 px-1 rounded">{issue.selector}</code></p>}
                                        {issue.suggestion && <p className="text-emerald-700 dark:text-emerald-300"><span className="font-medium">Suggestion: </span>{issue.suggestion}</p>}
                                    </div>
                                )}
                            </div>
                            <ChevronDown className={`w-4 h-4 flex-shrink-0 transition-transform ${expanded.has(i) ? 'rotate-180' : ''}`} />
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

// ============================================================
// Main Component
// ============================================================
const QualityAudit: React.FC = () => {
    const [activeType, setActiveType] = useState<AuditType>('accessibility');
    const [url, setUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [report, setReport] = useState<AuditReport | null>(null);

    // i18n specific
    const [locales, setLocales] = useState('en-US');
    // compliance specific
    const [standards, setStandards] = useState<string[]>(['GDPR', 'SOC2', 'PCI-DSS']);
    // a11y specific
    const [wcagLevel, setWcagLevel] = useState('AA');

    const runAudit = async () => {
        if (!url) return;
        setLoading(true);
        setReport(null);
        try {
            let endpoint = '';
            let body: Record<string, unknown> = {};
            const executionPayload = ensureExecutionContextPayload(`Quality test suite · ${activeType}`, { targetUrl: url });

            switch (activeType) {
                case 'accessibility':
                    endpoint = API_ENDPOINTS.accessibility.audit;
                    body = { url, level: wcagLevel, ...executionPayload };
                    break;
                case 'i18n':
                    endpoint = API_ENDPOINTS.i18n.test;
                    body = {
                        url,
                        locales: locales.split(',').map(l => l.trim()).filter(Boolean),
                        ...executionPayload,
                    };
                    break;
                case 'compliance':
                    endpoint = API_ENDPOINTS.compliance.audit;
                    body = { url, standards, ...executionPayload };
                    break;
            }

            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            setReport(data);
        } catch (e: unknown) {
            setReport({ total_issues: 0, score: -1, issues: [], summary: `Request failed: ${(e as Error).message}` });
        } finally {
            setLoading(false);
        }
    };

    const quickCheck = async () => {
        if (!url) return;
        setLoading(true);
        setReport(null);
        try {
            let endpoint = '';
            const executionPayload = ensureExecutionContextPayload(`Quality test suite · ${activeType}`, { targetUrl: url });
            let body: Record<string, unknown> = { url, ...executionPayload };
            if (activeType === 'accessibility') endpoint = API_ENDPOINTS.accessibility.quickCheck;
            else if (activeType === 'i18n') {
                endpoint = API_ENDPOINTS.i18n.quickCheck;
                body = {
                    url,
                    locale: locales.split(',').map(l => l.trim()).find(Boolean) || 'en-US',
                    ...executionPayload,
                };
            }
            else { await runAudit(); return; }

            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            setReport({
                total_issues: data.total || 0,
                score: data.total === 0 ? 100 : Math.max(0, 100 - data.total * 15),
                issues: data.issues || [],
                summary: `Quick check completed: ${data.total || 0} issues (${data.mode || 'quick'} mode)`
            });
        } catch (e: unknown) {
            setReport({ total_issues: 0, score: -1, issues: [], summary: `Request failed: ${(e as Error).message}` });
        } finally {
            setLoading(false);
        }
    };

    const tabConfig = AUDIT_TABS[activeType];

    return (
        <div className="flex flex-col h-full gap-4 animate-in fade-in duration-500">
            <ExecutionBatchBanner standaloneHint={"Quality audit results also appear in the execution center. The first run creates a specialized test batch if none is active."} />

            {/* Type Tabs */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/50 w-fit">
                {(Object.entries(AUDIT_TABS) as [AuditType, typeof AUDIT_TABS[AuditType]][]).map(([key, config]) => (
                    <button key={key} onClick={() => { setActiveType(key); setReport(null); }}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${activeType === key
                            ? `${config.color} border shadow-sm`
                            : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 border border-transparent'
                            }`}>
                        {config.icon}
                        {config.label}
                    </button>
                ))}
            </div>

            {/* URL & Options Bar */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-4">
                <div className="flex items-center gap-3">
                    <div className={`px-3 py-2 text-sm font-bold rounded-lg ${tabConfig.color}`}>
                        {tabConfig.label}
                    </div>
                    <input type="text" value={url} onChange={(e) => setUrl(e.target.value)}
                        placeholder={"Enter a URL to audit (for example, https://example.com)"}
                        className="flex-1 px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500/20" />
                    <button onClick={quickCheck} disabled={loading}
                        className="px-3 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition border border-slate-200 dark:border-slate-700">
                        Quick check
                    </button>
                    <button onClick={runAudit} disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-lg font-medium shadow-lg shadow-indigo-500/20 active:scale-95 transition-all disabled:opacity-50">
                        {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                        Full audit
                    </button>
                </div>

                {/* Options row */}
                <div className="flex items-center gap-4 mt-3 text-sm">
                    {activeType === 'accessibility' && (
                        <div className="flex items-center gap-2">
                            <span className="text-slate-500">WCAG level:</span>
                            {['A', 'AA', 'AAA'].map(l => (
                                <button key={l} onClick={() => setWcagLevel(l)}
                                    className={`px-2 py-1 rounded text-xs font-medium ${wcagLevel === l ? 'bg-teal-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
                                    {l}
                                </button>
                            ))}
                        </div>
                    )}
                    {activeType === 'i18n' && (
                        <div className="flex items-center gap-2 flex-1">
                            <span className="text-slate-500">Languages:</span>
                            <input type="text" value={locales} onChange={(e) => setLocales(e.target.value)}
                                placeholder="en-US, es-US, fr-CA"
                                className="flex-1 max-w-md px-3 py-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none font-mono" />
                        </div>
                    )}
                    {activeType === 'compliance' && (
                        <div className="flex items-center gap-2">
                            <span className="text-slate-500">Standards:</span>
                            {['GDPR', 'SOC2', 'PCI-DSS'].map(s => (
                                <button key={s} onClick={() => setStandards(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s])}
                                    className={`px-2 py-1 rounded text-xs font-medium ${standards.includes(s) ? 'bg-amber-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
                                    {s}
                                </button>
                            ))}
                        </div>
                    )}
                    <span className="text-xs text-slate-400 ml-auto">{tabConfig.desc}</span>
                </div>
            </div>

            {/* Results */}
            <div className="flex-1 flex gap-4 min-h-0">
                {report ? (
                    <>
                        {/* Score Card */}
                        <div className="w-64 flex-shrink-0 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md p-6 flex flex-col items-center gap-4">
                            <ScoreGauge score={report.score} />
                            <p className="text-sm text-center text-slate-600 dark:text-slate-400 leading-relaxed">
                                {report.summary}
                            </p>
                            <div className="w-full space-y-2 mt-2">
                                {report.critical !== undefined && report.critical > 0 && (
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="flex items-center gap-1.5 text-red-500"><XCircle className="w-3.5 h-3.5" />Critical</span>
                                        <span className="font-bold text-red-500">{report.critical}</span>
                                    </div>
                                )}
                                {report.major !== undefined && report.major > 0 && (
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="flex items-center gap-1.5 text-orange-500"><AlertTriangle className="w-3.5 h-3.5" />Major</span>
                                        <span className="font-bold text-orange-500">{report.major}</span>
                                    </div>
                                )}
                                {report.minor !== undefined && report.minor > 0 && (
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="flex items-center gap-1.5 text-blue-500"><Info className="w-3.5 h-3.5" />Minor</span>
                                        <span className="font-bold text-blue-500">{report.minor}</span>
                                    </div>
                                )}
                                {report.passed_rules !== undefined && (
                                    <div className="flex items-center justify-between text-sm pt-2 border-t border-slate-200 dark:border-slate-700">
                                        <span className="text-green-500">Rules passed</span>
                                        <span className="font-bold text-green-500">{report.passed_rules}</span>
                                    </div>
                                )}
                                {report.passed_checks !== undefined && (
                                    <div className="flex items-center justify-between text-sm pt-2 border-t border-slate-200 dark:border-slate-700">
                                        <span className="text-green-500">Checks passed</span>
                                        <span className="font-bold text-green-500">{report.passed_checks}</span>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Issues List */}
                        <div className="flex-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col min-h-0">
                            <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                                <span className="text-sm font-bold text-slate-700 dark:text-white">
                                    Issues ( {report.total_issues})
                                </span>
                            </div>
                            <div className="flex-1 overflow-y-auto p-3">
                                <IssueList issues={report.issues} />
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md">
                        <div className="text-center text-slate-400">
                            {loading ? (
                                <>
                                    <RefreshCw className="w-12 h-12 mx-auto mb-4 animate-spin opacity-30" />
                                    <p className="text-lg font-medium">Audit in progress...</p>
                                    <p className="text-sm mt-1">This may take a few seconds</p>
                                </>
                            ) : (
                                <>
                                    {activeType === 'accessibility' && <Eye className="w-12 h-12 mx-auto mb-4 opacity-30" />}
                                    {activeType === 'i18n' && <Globe className="w-12 h-12 mx-auto mb-4 opacity-30" />}
                                    {activeType === 'compliance' && <ShieldCheck className="w-12 h-12 mx-auto mb-4 opacity-30" />}
                                    <p className="text-lg font-medium">Enter a URL to begin {tabConfig.label} Audit</p>
                                    <p className="text-sm mt-1">{tabConfig.desc}</p>
                                </>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default QualityAudit;
