/** ReportDropdown: report actions embedded in the ExecutionHistory toolbar.
 * Generate a report, show toast feedback, refresh history automatically, and open reports.
 */
import React, { useState, useEffect, useRef } from 'react';
import {
    FileText, Loader2, ExternalLink, CheckCircle2, XCircle, Clock,
    ChevronDown, Trash2, AlertCircle, Download
} from './icons';
import { API_ENDPOINTS } from '../config';

interface ReportItem {
    id?: string;
    timestamp: string;
    title?: string;
    report_scope?: 'record' | 'summary' | 'batch';
    task_id?: string;
    record_count?: number;
    case_count?: number;
    platform_issue_count?: number;
    execution_issue_count?: number;
    total_steps?: number;
    passed?: number;
    failed?: number;
    duration_ms?: number;
    report_url?: string;
    allure_url?: string;
    [key: string]: unknown;
}

function getScopeLabel(scope?: ReportItem['report_scope']) {
    if (scope === 'record') return "Dedicated report";
    if (scope === 'batch') return "Batch report";
    return "Summary report";
}

/* Simple toast message*/
const Toast: React.FC<{ message: string; type: 'success' | 'error'; onClose: () => void }> = ({ message, type, onClose }) => {
    useEffect(() => {
        const timer = setTimeout(onClose, 4000);
        return () => clearTimeout(timer);
    }, [onClose]);

    return (
        <div className={`fixed top-20 right-6 z-[9999] flex items-center gap-2 px-4 py-3 rounded-xl shadow-2xl text-sm font-medium animate-in slide-in-from-top-3 duration-300 ${type === 'success'
            ? 'bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30'
            : 'bg-red-50 dark:bg-red-500/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-500/30'
            }`}>
            {type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            {message}
        </div>
    );
};

const ReportDropdown: React.FC = () => {
    const [reports, setReports] = useState<ReportItem[]>([]);
    const [generating, setGenerating] = useState(false);
    const [isOpen, setIsOpen] = useState(false);
    const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);

    const loadReports = async () => {
        try {
            const res = await fetch(`${API_ENDPOINTS.report.history}?limit=10`);
            const data = await res.json();
            setReports(data.history || []);
        } catch { /* ignore */ }
    };

    useEffect(() => {
        loadReports();
    }, []);

    // Close on outside click
    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        };
        if (isOpen) document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [isOpen]);

    const handleGenerate = async () => {
        setGenerating(true);
        try {
            const res = await fetch(API_ENDPOINTS.report.generate, { method: 'POST' });
            const data = await res.json();

            if (!res.ok || data.status === 'error') {
                setToast({ message: data.message || "Report generation failed", type: 'error' });
                return;
            }

            // Refresh history.
            await loadReports();

            const recordCount = data.record_count || 0;
            const caseCount = data.case_count || data.total_steps || 0;
            const platformIssueCount = data.platform_issue_count || 0;
            const passed = data.passed || 0;
            const failed = data.failed || 0;
            const scopeLabel = getScopeLabel(data.report_scope);

            if (recordCount === 0 && caseCount === 0) {
                setToast({ message: `${scopeLabel}Generated (no test data yet)`, type: 'success' });
            } else {
                setToast({
                    message: `${scopeLabel}Generated: ${recordCount} records, ${caseCount} test cases, ${platformIssueCount} platform issues${failed > 0 ? `，${failed} failed test cases` : ''}${passed > 0 ? `，${passed} passed test cases` : ''}`,
                    type: 'success'
                });
            }

            // Open report history automatically.
            setIsOpen(true);
        } catch (err) {
            setToast({ message: `Report generation failed: ${err instanceof Error ? err.message : "Network error"}`, type: 'error' });
        } finally {
            setGenerating(false);
        }
    };

    const handleClear = async () => {
        if (!confirm("Clear all test reports?")) return;
        try {
            await fetch(API_ENDPOINTS.report.clear, { method: 'POST' });
            setReports([]);
            setToast({ message: "All reports cleared", type: 'success' });
        } catch {
            setToast({ message: "Failed to clear", type: 'error' });
        }
    };

    const handleDelete = async (e: React.MouseEvent, id?: string) => {
        e.stopPropagation();
        if (!id) return;
        if (!confirm("Delete this report?")) return;
        try {
            const res = await fetch(API_ENDPOINTS.report.delete(id), { method: 'DELETE' });
            if (res.ok) {
                setReports(prev => prev.filter(r => r.id !== id));
                setToast({ message: "Report deleted", type: 'success' });
            } else {
                setToast({ message: "Failed to delete", type: 'error' });
            }
        } catch {
            setToast({ message: "Network error: deletion failed", type: 'error' });
        }
    };

    const handleDownloadReport = async (e: React.MouseEvent, r: ReportItem) => {
        e.stopPropagation();
        try {
            const url = r.allure_url || r.report_url;
            if (!url) return;
            const fullUrl = url.startsWith('http') ? url : `${API_ENDPOINTS.report.history.split('/api/')[0]}${url}`;
            const res = await fetch(fullUrl);
            if (!res.ok) throw new Error('Download failed');
            const html = await res.text();
            const blob = new Blob([html], { type: 'text/html' });
            const objUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = objUrl;
            a.download = `AI_Test_Report_${r.id || new Date().getTime()}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(objUrl);
            setToast({ message: "Starting report download...", type: 'success' });
        } catch {
            setToast({ message: "Download failed", type: 'error' });
        }
    };

    const formatDuration = (ms?: number) => {
        if (!ms) return '—';
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
        return `${(ms / 60_000).toFixed(1)}m`;
    };

    return (
        <>
            {/* Toast */}
            {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

            <div className="relative flex items-center gap-2 z-[50]" ref={dropdownRef}>
                {/* Generate Button */}
                <button
                    onClick={handleGenerate}
                    disabled={generating}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 text-white rounded-lg text-xs font-medium transition-all shadow-md shadow-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />}
                    {generating ? "Generating..." : "Generate summary report"}
                </button>

                {/* Dropdown Toggle */}
                <button
                    onClick={() => { setIsOpen(!isOpen); if (!isOpen) loadReports(); }}
                    className={`flex items-center gap-1 px-2 py-1.5 text-xs font-medium rounded-lg border transition-all ${isOpen
                        ? 'bg-indigo-50 dark:bg-indigo-500/10 border-indigo-300 dark:border-indigo-500/30 text-indigo-600 dark:text-indigo-400'
                        : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                        }`}
                >
                    Test reports
                    {reports.length > 0 && <span className="px-1.5 py-0.5 text-[10px] bg-slate-100 dark:bg-slate-700 rounded-full">{reports.length}</span>}
                    <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Dropdown Panel */}
                {isOpen && (
                    <div className="absolute right-0 top-full mt-2 w-96 max-h-80 overflow-y-auto bg-white/95 dark:bg-slate-800/95 backdrop-blur-xl rounded-xl border border-slate-200/80 dark:border-slate-700/80 shadow-2xl shadow-black/20 dark:shadow-black/50 z-[9999] animate-in fade-in slide-in-from-top-2 duration-200">
                        {reports.length === 0 ? (
                            <div className="py-8 text-center text-xs text-slate-400">
                                <FileText className="w-8 h-8 mx-auto mb-2 opacity-20" />
                                No test reports yet. Click Generate summary report to begin.
                            </div>
                        ) : (
                            <>
                                <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                                    {reports.map((r, i) => {
                                        const total = r.case_count || r.total_steps || 0;
                                        const passed = r.passed || 0;
                                        const failed = r.failed || 0;
                                        const recordCount = r.record_count || 0;
                                        const platformIssueCount = r.platform_issue_count || 0;
                                        const rate = total > 0 ? Math.round((passed / total) * 100) : 0;

                                        return (
                                            <div key={r.id || i} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                                                <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${failed > 0
                                                    ? 'bg-red-50 dark:bg-red-500/10 text-red-500'
                                                    : total > 0
                                                        ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-500'
                                                        : 'bg-slate-100 dark:bg-slate-700 text-slate-400'
                                                    }`}>
                                                    {failed > 0 ? <XCircle className="w-4 h-4" />
                                                        : total > 0 ? <CheckCircle2 className="w-4 h-4" />
                                                            : <FileText className="w-4 h-4" />}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">
                                                        {r.title || `Report #${reports.length - i}`}
                                                    </p>
                                                    <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400">
                                                        <span className="flex items-center gap-0.5"><Clock className="w-2.5 h-2.5" />{new Date(r.timestamp).toLocaleString('en-US')}</span>
                                                        <span>{formatDuration(r.duration_ms)}</span>
                                                        <span>{getScopeLabel(r.report_scope)}</span>
                                                        {recordCount > 0 && <span>{recordCount} records</span>}
                                                        {platformIssueCount > 0 && <span>{platformIssueCount} issues</span>}
                                                    </div>
                                                </div>
                                                {total > 0 && (
                                                    <div className="flex items-center gap-1.5 text-[10px] shrink-0">
                                                        <span className="font-bold text-slate-600 dark:text-slate-300">{rate}%</span>
                                                        <span className="px-1.5 py-0.5 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded">✓{passed}</span>
                                                        {failed > 0 && <span className="px-1.5 py-0.5 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 rounded">✗{failed}</span>}
                                                    </div>
                                                )}
                                                {total === 0 && (
                                                    <span className="text-[10px] text-slate-400 shrink-0">Empty</span>
                                                )}
                                                {(r.report_url || r.allure_url) && (
                                                    <a href={r.allure_url || r.report_url} target="_blank" rel="noreferrer"
                                                        className="p-1.5 rounded-lg text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors shrink-0"
                                                        onClick={(e) => e.stopPropagation()} title={"Open in new tab"}>
                                                        <ExternalLink className="w-3.5 h-3.5" />
                                                    </a>
                                                )}
                                                <button onClick={(e) => handleDownloadReport(e, r)} title={"Download offline report"}
                                                    className="p-1.5 rounded-lg text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors shrink-0">
                                                    <Download className="w-3.5 h-3.5" />
                                                </button>
                                                <button onClick={(e) => handleDelete(e, r.id)} title={"Delete"}
                                                    className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors shrink-0">
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                                <div className="px-4 py-2 border-t border-slate-100 dark:border-slate-700/50">
                                    <button onClick={handleClear}
                                        className="flex items-center gap-1 text-[10px] text-red-500 hover:text-red-600 transition-colors">
                                        <Trash2 className="w-3 h-3" /> Clear all reports
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                )}
            </div>
        </>
    );
};

export default ReportDropdown;
