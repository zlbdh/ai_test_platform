import React, { useState, useCallback } from 'react';
import {
    Languages, Accessibility, RefreshCw,
    AlertTriangle, Globe,
} from '../components/icons';
import Badge from '../components/ui/Badge';
import PageHeader from '../components/ui/PageHeader';
import Tabs from '../components/ui/Tabs';
import { API_BASE_URL } from '../config';
import ExecutionBatchBanner from '../components/ExecutionBatchBanner';
import { ensureExecutionContextPayload } from '../utils/executionContext';
import type { ExecutionContextPayload } from '../utils/executionContext';

// ── Types ──
interface I18nIssue {
    type: string;
    element: string;
    locale: string;
    message: string;
    severity: string;
}

interface A11yViolation {
    id: string;
    impact: string;
    description: string;
    help: string;
    nodes: number;
}

// ── API ──
const runI18nTest = async (url: string, locales: string[], payload: ExecutionContextPayload): Promise<{ issues: I18nIssue[]; score: number }> => {
    const res = await fetch(`${API_BASE_URL}/api/i18n/quick-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            url,
            locale: locales[0] || 'en-US',
            ...payload,
        }),
    });
    return res.json();
};

const runA11yAudit = async (url: string, payload: ExecutionContextPayload): Promise<{ violations: A11yViolation[]; score: number; passes: number }> => {
    const res = await fetch(`${API_BASE_URL}/api/accessibility/quick-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            url,
            ...payload,
        }),
    });
    return res.json();
};

const impactBadge = (impact: string) => {
    const map: Record<string, 'error' | 'warning' | 'info' | 'neutral'> = { critical: 'error', serious: 'error', moderate: 'warning', minor: 'info' };
    return <Badge variant={map[impact] || 'neutral'} size="sm">{impact}</Badge>;
};

// ============================================================================
const I18nA11yPage: React.FC = () => {
    const [url, setUrl] = useState('');
    const [locales, setLocales] = useState('en-US');
    const [activeTab, setActiveTab] = useState('i18n');
    const [i18nResult, setI18nResult] = useState<{ issues: I18nIssue[]; score: number } | null>(null);
    const [a11yResult, setA11yResult] = useState<{ violations: A11yViolation[]; score: number; passes: number } | null>(null);
    const [loadingI18n, setLoadingI18n] = useState(false);
    const [loadingA11y, setLoadingA11y] = useState(false);

    const handleI18n = useCallback(async () => {
        if (!url) return;
        setLoadingI18n(true);
        try {
            const r = await runI18nTest(
                url,
                locales.split(',').map(l => l.trim()),
                ensureExecutionContextPayload("Internationalization test suite", { targetUrl: url })
            );
            setI18nResult(r);
        } catch { /* */ }
        setLoadingI18n(false);
    }, [url, locales]);

    const handleA11y = useCallback(async () => {
        if (!url) return;
        setLoadingA11y(true);
        try {
            const r = await runA11yAudit(
                url,
                ensureExecutionContextPayload("Accessibility test suite", { targetUrl: url })
            );
            setA11yResult(r);
        } catch { /* */ }
        setLoadingA11y(false);
    }, [url]);

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            <ExecutionBatchBanner standaloneHint={"Internationalization and accessibility checks also appear in the execution center. The first run creates a specialized test batch if none is active."} />

            <PageHeader
                icon={<Languages className="w-5 h-5" />}
                title={"Internationalization and accessibility testing"}
                description={"Multilingual content checks (i18n) and WCAG accessibility audits"}
                accent="sky"
            />

            {/* Input */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
                <div className="grid md:grid-cols-4 gap-3 items-end">
                    <div className="md:col-span-2 space-y-1">
                        <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Target URL</label>
                        <input type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://example.com" className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-sky-500/30" />
                    </div>
                    <div className="space-y-1">
                        <label className="block text-[10px] font-medium uppercase tracking-wider text-slate-400">Languages</label>
                        <input type="text" value={locales} onChange={e => setLocales(e.target.value)} placeholder="en-US, es-US, fr-CA" className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-sky-500/30" />
                    </div>
                    <div className="flex gap-2">
                        <button onClick={handleI18n} disabled={loadingI18n || !url} className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-xs font-medium py-2 transition-colors disabled:opacity-50">
                            {loadingI18n ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Languages className="w-3 h-3" />}
                            i18n
                        </button>
                        <button onClick={handleA11y} disabled={loadingA11y || !url} className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-violet-500 hover:bg-violet-600 text-white text-xs font-medium py-2 transition-colors disabled:opacity-50">
                            {loadingA11y ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Accessibility className="w-3 h-3" />}
                            WCAG
                        </button>
                    </div>
                </div>
            </div>

            {/* Tabs + Results */}
            <Tabs
                activeKey={activeTab}
                onChange={setActiveTab}
                items={[
                    { key: 'i18n', label: `Internationalization ${i18nResult ? `(${i18nResult.issues.length})` : ''}`, content: <></> },
                    { key: 'a11y', label: `Accessibility ${a11yResult ? `(${a11yResult.violations.length})` : ''}`, content: <></> },
                ]}
                variant="underline"
            />

            {activeTab === 'i18n' && (
                <div className="space-y-3">
                    {i18nResult && (
                        <div className="flex items-center gap-3 mb-4">
                            <Badge variant={i18nResult.score >= 80 ? 'success' : i18nResult.score >= 50 ? 'warning' : 'error'} size="sm">
                                i18n score: {i18nResult.score}/100
                            </Badge>
                            <Badge variant="neutral" size="sm">{i18nResult.issues.length} issues</Badge>
                        </div>
                    )}
                    {i18nResult?.issues.map((issue, i) => (
                        <div key={i} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3 flex items-start gap-3">
                            <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${issue.severity === 'error' ? 'text-red-500' : 'text-amber-500'}`} />
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                    <Badge variant="neutral" size="sm">{issue.type}</Badge>
                                    <Badge variant="info" size="sm">{issue.locale}</Badge>
                                </div>
                                <p className="text-xs text-slate-700 dark:text-slate-300">{issue.message}</p>
                                <code className="text-[10px] text-slate-400 mt-0.5 block">{issue.element}</code>
                            </div>
                        </div>
                    ))}
                    {!i18nResult && (
                        <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 p-12 text-center">
                            <Globe className="w-10 h-10 text-sky-300 dark:text-sky-700 mx-auto mb-3" />
                            <p className="text-sm text-slate-500">Enter a URL and click i18n to start multilingual checks</p>
                        </div>
                    )}
                </div>
            )}

            {activeTab === 'a11y' && (
                <div className="space-y-3">
                    {a11yResult && (
                        <div className="flex items-center gap-3 mb-4">
                            <Badge variant={a11yResult.score >= 80 ? 'success' : a11yResult.score >= 50 ? 'warning' : 'error'} size="sm">
                                WCAG score: {a11yResult.score}/100
                            </Badge>
                            <Badge variant="success" size="sm">{a11yResult.passes} Passed</Badge>
                            <Badge variant="error" size="sm">{a11yResult.violations.length} violations</Badge>
                        </div>
                    )}
                    {a11yResult?.violations.map((v, i) => (
                        <div key={i} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">
                            <div className="flex items-center gap-2 mb-1.5">
                                <code className="text-[10px] text-slate-400 font-mono">{v.id}</code>
                                {impactBadge(v.impact)}
                                <Badge variant="neutral" size="sm">{v.nodes} nodes</Badge>
                            </div>
                            <p className="text-xs font-medium text-slate-700 dark:text-slate-200">{v.description}</p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{v.help}</p>
                        </div>
                    ))}
                    {!a11yResult && (
                        <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 p-12 text-center">
                            <Accessibility className="w-10 h-10 text-violet-300 dark:text-violet-700 mx-auto mb-3" />
                            <p className="text-sm text-slate-500">Enter a URL and click WCAG to start an accessibility audit</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default I18nA11yPage;
