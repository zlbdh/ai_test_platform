/** GalleryPanel: task screenshot panel extracted from VisualGallery.
 * Embedded in ExecutionHistory to show step screenshots, with list/grid views, a full-screen lightbox, and screenshot diffs.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
    CheckCircle2, XCircle, Clock, Camera, Maximize2,
    Timer, BarChart3, GitCompareArrows, Grid3X3, LayoutGrid,
    ChevronLeft, ChevronRight, X
} from './icons';
import { API_ENDPOINTS } from '../config';
import ScreenshotDiff from './ScreenshotDiff';

// ============================================================================
// Types
// ============================================================================
interface GalleryStep {
    index: number;
    step: string;
    content: string;
    type: string;
    status: 'pass' | 'fail';
    duration: number;
    screenshot: string | null;
    snapshots: Record<string, string> | null;
}

// ============================================================================
// Helpers
// ============================================================================
function formatDuration(s: number): string {
    if (!s || s <= 0) return '-';
    if (s < 1) return `${Math.round(s * 1000)}ms`;
    return `${s.toFixed(1)}s`;
}

// ============================================================================
// Lightbox: full-screen image preview
// ============================================================================
const Lightbox: React.FC<{
    steps: GalleryStep[];
    currentIndex: number;
    onClose: () => void;
    onNav: (idx: number) => void;
}> = ({ steps, currentIndex, onClose, onNav }) => {
    const current = steps[currentIndex];

    const handleKeyDown = useCallback((e: KeyboardEvent) => {
        if (e.key === 'Escape') onClose();
        if (e.key === 'ArrowLeft' && currentIndex > 0) onNav(currentIndex - 1);
        if (e.key === 'ArrowRight' && currentIndex < steps.length - 1) onNav(currentIndex + 1);
    }, [currentIndex, steps.length, onClose, onNav]);

    useEffect(() => {
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [handleKeyDown]);

    if (!current) return null;
    const imgSrc = current.screenshot || (current.snapshots?.actual) || null;

    return (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xl flex flex-col animate-in fade-in duration-300" onClick={onClose}>
            <div className="flex items-center justify-between px-6 py-4 text-white border-b border-white/10 bg-gradient-to-r from-white/5 to-transparent" onClick={e => e.stopPropagation()}>
                <div className="flex items-center gap-3">
                    <span className="text-xs font-mono bg-white/10 px-2 py-1 rounded">
                        {currentIndex + 1} / {steps.length}
                    </span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${current.status === 'pass' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                        {current.status === 'pass' ? '✅PASS' : '❌FAIL'}
                    </span>
                    <span className="text-sm truncate max-w-md">{current.step}</span>
                </div>
                <button onClick={onClose} className="p-2 rounded-full hover:bg-white/10 transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500/40">
                    <X className="w-5 h-5" />
                </button>
            </div>
            <div className="flex-1 flex items-center justify-center p-4 relative" onClick={e => e.stopPropagation()}>
                {currentIndex > 0 && (
                    <button onClick={() => onNav(currentIndex - 1)}
                        className="absolute left-4 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white transition-all z-10 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 backdrop-blur-sm">
                        <ChevronLeft className="w-6 h-6" />
                    </button>
                )}
                {currentIndex < steps.length - 1 && (
                    <button onClick={() => onNav(currentIndex + 1)}
                        className="absolute right-4 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white transition-all z-10 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 backdrop-blur-sm">
                        <ChevronRight className="w-6 h-6" />
                    </button>
                )}
                {imgSrc ? (
                    <img src={imgSrc} className="max-w-full max-h-full object-contain rounded-lg shadow-2xl shadow-black/50" alt={current.step} />
                ) : (
                    <div className="text-white/40 text-center">
                        <Camera className="w-16 h-16 mx-auto mb-4 opacity-30" />
                        <p>No screenshot for this step</p>
                    </div>
                )}
            </div>
            <div className="px-6 py-3 text-center text-xs text-white/50 border-t border-white/10 bg-gradient-to-r from-transparent via-white/5 to-transparent" onClick={e => e.stopPropagation()}>
                {current.content}
                {current.duration > 0 && <span className="ml-3">⏱ {formatDuration(current.duration)}</span>}
            </div>
        </div>
    );
};

// ============================================================================
// Main Component
// ============================================================================
interface GalleryPanelProps {
    taskId: string;
    isOpen: boolean;
}

const GalleryPanel: React.FC<GalleryPanelProps> = ({ taskId, isOpen }) => {
    const [steps, setSteps] = useState<GalleryStep[]>([]);
    const [loading, setLoading] = useState(false);
    const [fetchedFor, setFetchedFor] = useState<string | null>(null);
    const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
    const [diffIndex, setDiffIndex] = useState<number | null>(null);
    const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');

    // Trigger loading before effect runs
    if (isOpen && fetchedFor !== taskId) {
        setLoading(true);
        setFetchedFor(taskId);
    }

    useEffect(() => {
        if (!isOpen || !loading) return;
        fetch(API_ENDPOINTS.gallery(taskId))
            .then(r => r.ok ? r.json() : [])
            .then(data => setSteps(Array.isArray(data) ? data : []))
            .catch(() => setSteps([]))
            .finally(() => setLoading(false));
    }, [isOpen, taskId, loading]);

    if (!isOpen) return null;

    const passCount = steps.filter(s => s.status === 'pass').length;
    const failCount = steps.filter(s => s.status === 'fail').length;
    const totalDuration = steps.reduce((sum, s) => sum + (s.duration || 0), 0);

    if (loading) {
        return <div className="text-xs text-slate-400 p-3 flex items-center gap-2"><Camera className="w-4 h-4 animate-pulse" /> Loading screenshots...</div>;
    }

    if (steps.length === 0) {
        return (
            <div className="text-xs text-slate-500 p-3 bg-slate-100 dark:bg-slate-800/50 rounded-lg flex items-center gap-2">
                <Camera className="w-4 h-4 opacity-40" /> No screenshots for this task
            </div>
        );
    }

    return (
        <div className="animate-in slide-in-from-top-2 duration-200">
            {/* Lightbox */}
            {lightboxIndex !== null && (
                <Lightbox steps={steps} currentIndex={lightboxIndex} onClose={() => setLightboxIndex(null)} onNav={setLightboxIndex} />
            )}

            {/* Screenshot Diff */}
            {diffIndex !== null && diffIndex > 0 && (() => {
                const prevStep = steps[diffIndex - 1];
                const currStep = steps[diffIndex];
                const prevSrc = prevStep?.screenshot || prevStep?.snapshots?.actual;
                const currSrc = currStep?.screenshot || currStep?.snapshots?.actual;
                if (!prevSrc || !currSrc) return null;
                return (
                    <ScreenshotDiff
                        beforeSrc={prevSrc} afterSrc={currSrc}
                        beforeLabel={`Step ${diffIndex}: ${prevStep.step}`}
                        afterLabel={`Step ${diffIndex + 1}: ${currStep.step}`}
                        onClose={() => setDiffIndex(null)}
                    />
                );
            })()}

            {/* Stats */}
            <div className="flex items-center gap-4 mb-3 text-xs text-slate-500">
                <span className="flex items-center gap-1"><BarChart3 className="w-3 h-3" /> {steps.length} Step</span>
                <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400"><CheckCircle2 className="w-3 h-3" /> {passCount} Passed</span>
                {failCount > 0 && <span className="flex items-center gap-1 text-red-600 dark:text-red-400"><XCircle className="w-3 h-3" /> {failCount} Failed</span>}
                <span className="flex items-center gap-1"><Timer className="w-3 h-3" /> {formatDuration(totalDuration)}</span>
                <div className="ml-auto flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5">
                    <button onClick={() => setViewMode('list')}
                        className={`p-1 rounded-md transition-all ${viewMode === 'list' ? 'bg-white dark:bg-slate-700 shadow-sm text-indigo-500' : 'text-slate-400'}`}>
                        <LayoutGrid className="w-3 h-3" />
                    </button>
                    <button onClick={() => setViewMode('grid')}
                        className={`p-1 rounded-md transition-all ${viewMode === 'grid' ? 'bg-white dark:bg-slate-700 shadow-sm text-indigo-500' : 'text-slate-400'}`}>
                        <Grid3X3 className="w-3 h-3" />
                    </button>
                </div>
            </div>

            {/* Steps */}
            <div className={viewMode === 'grid' ? 'grid grid-cols-2 lg:grid-cols-3 gap-3' : 'space-y-3'}>
                {steps.map((step, idx) => {
                    const imgSrc = step.screenshot || step.snapshots?.actual || null;
                    return (
                        <div key={`step-${idx}`}
                            className={`rounded-lg border overflow-hidden transition-all ${step.status === 'pass'
                                ? 'border-slate-200 dark:border-slate-700/50 hover:border-emerald-300 dark:hover:border-emerald-500/30'
                                : 'border-red-200/50 dark:border-red-500/20 hover:border-red-300'
                                } bg-white dark:bg-slate-800/50`}>
                            {/* Step Header */}
                            <div className="flex items-center gap-2 px-3 py-2 bg-slate-50/50 dark:bg-slate-800/80">
                                <span className="text-[10px] font-mono font-bold text-slate-400 w-5 text-center shrink-0">{idx + 1}</span>
                                {step.status === 'pass'
                                    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                                    : <XCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                                }
                                <span className="text-xs font-medium text-slate-900 dark:text-white truncate flex-1" title={step.step}>{step.step}</span>
                                {step.duration > 0 && (
                                    <span className="text-[10px] font-mono text-slate-400 flex items-center gap-0.5 shrink-0">
                                        <Clock className="w-2.5 h-2.5" />{formatDuration(step.duration)}
                                    </span>
                                )}
                                <span className="text-[9px] font-mono uppercase tracking-wider text-slate-400 bg-slate-100 dark:bg-slate-700/50 px-1 py-0.5 rounded shrink-0">{step.type}</span>
                            </div>
                            {/* Screenshot */}
                            {imgSrc && (
                                <div className="relative cursor-pointer group" onClick={() => setLightboxIndex(idx)}>
                                    <img src={imgSrc}
                                        className={viewMode === 'grid' ? 'w-full h-36 object-cover bg-slate-950' : 'w-full h-auto max-h-64 object-contain bg-slate-950'}
                                        loading="lazy" alt={step.step} />
                                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                        <Maximize2 className="w-6 h-6 text-white/0 group-hover:text-white/80 transition-all" />
                                    </div>
                                    {idx > 0 && (steps[idx - 1]?.screenshot || steps[idx - 1]?.snapshots?.actual) && (
                                        <button onClick={(e) => { e.stopPropagation(); setDiffIndex(idx); }}
                                            className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded-lg bg-black/60 hover:bg-indigo-600 text-white/70 hover:text-white text-[10px] font-bold opacity-0 group-hover:opacity-100 transition-all z-10"
                                            title={"Compare with previous step"}>
                                            <GitCompareArrows className="w-3 h-3" /> Compare
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default GalleryPanel;
