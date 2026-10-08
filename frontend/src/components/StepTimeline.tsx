import React, { useState } from 'react';
import { Timer } from './icons';
import type { TestStep } from '../types';

type StepStatus = 'running' | 'success' | 'error' | 'skipped';

interface StepTimelineProps {
    steps: TestStep[];
    statuses: Map<number, StepStatus>;
}

const STATUS_CONFIG: Record<StepStatus | 'pending', { color: string; bg: string; icon: string; label: string }> = {
    pending: { color: 'text-slate-400', bg: 'bg-slate-300 dark:bg-slate-600', icon: '○', label: "Pending" },
    running: { color: 'text-blue-500', bg: 'bg-blue-500', icon: '●', label: "Running" },
    success: { color: 'text-emerald-500', bg: 'bg-emerald-500', icon: '✓', label: "Passed" },
    error: { color: 'text-red-500', bg: 'bg-red-500', icon: '✗', label: "Failed" },
    skipped: { color: 'text-slate-400', bg: 'bg-slate-400', icon: '→', label: "Skipped" },
};

const StepTimeline: React.FC<StepTimelineProps> = ({ steps, statuses }) => {
    const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

    if (steps.length === 0) return null;

    // Statistics
    const total = steps.length;
    const completed = Array.from(statuses.values()).filter(s => s === 'success').length;
    const failed = Array.from(statuses.values()).filter(s => s === 'error').length;
    const running = Array.from(statuses.values()).filter(s => s === 'running').length;
    const progress = total > 0 ? Math.round(((completed + failed) / total) * 100) : 0;

    return (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 p-4 backdrop-blur-md">
            {/* Title and progress bar*/}
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                    <Timer className="w-3.5 h-3.5 text-indigo-400" /> Step timeline
                    <span className="text-[10px] font-normal text-slate-500">
                        {completed}/{total} completed
                        {failed > 0 && <span className="text-red-400 ml-1">({failed} failed)</span>}
                        {running > 0 && <span className="text-blue-400 ml-1 animate-pulse">({running} running)</span>}
                    </span>
                </h3>
                <span className="text-[10px] font-mono text-slate-500">{progress}%</span>
            </div>

            {/* Progress bar*/}
            <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full mb-3 overflow-hidden">
                <div
                    className="h-full rounded-full transition-all duration-500 ease-out"
                    style={{
                        width: `${progress}%`,
                        background: failed > 0
                            ? 'linear-gradient(90deg, #22c55e, #ef4444)'
                            : 'linear-gradient(90deg, #6366f1, #22c55e)',
                    }}
                />
            </div>

            {/* Horizontal timeline with compact nodes*/}
            <div className="flex items-center gap-0.5 overflow-x-auto pb-2 custom-scrollbar">
                {steps.map((step, idx) => {
                    const status = statuses.get(idx) || 'pending';
                    const cfg = STATUS_CONFIG[status];
                    const isExpanded = expandedIdx === idx;

                    return (
                        <React.Fragment key={idx}>
                            {/* Connector*/}
                            {idx > 0 && (
                                <div className={`h-0.5 w-3 flex-shrink-0 transition-colors duration-300 ${status !== 'pending' ? cfg.bg : 'bg-slate-300 dark:bg-slate-600'
                                    }`} />
                            )}
                            {/* Node*/}
                            <button
                                onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                                className={`flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-bold border-2 transition-all duration-300 hover:scale-110 ${status === 'running' ? 'animate-pulse' : ''
                                    } ${status === 'pending'
                                        ? 'border-slate-300 dark:border-slate-600 text-slate-400 bg-white dark:bg-slate-800'
                                        : `border-current ${cfg.color} bg-white dark:bg-slate-800`
                                    }`}
                                title={`Step ${idx + 1}: ${step.action} — ${cfg.label}`}
                            >
                                {status === 'pending' ? idx + 1 : cfg.icon}
                            </button>
                        </React.Fragment>
                    );
                })}
            </div>

            {/* Expanded details*/}
            {expandedIdx !== null && steps[expandedIdx] && (
                <div className="mt-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 animate-in slide-in-from-top-1 duration-200">
                    <div className="flex items-center gap-2 mb-2">
                        <span className={`text-sm font-bold ${STATUS_CONFIG[statuses.get(expandedIdx) || 'pending'].color}`}>
                            {STATUS_CONFIG[statuses.get(expandedIdx) || 'pending'].icon}
                        </span>
                        <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                            Step {expandedIdx + 1}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 font-bold uppercase">
                            {steps[expandedIdx].action}
                        </span>
                        <span className="text-[10px] text-slate-500">
                            {STATUS_CONFIG[statuses.get(expandedIdx) || 'pending'].label}
                        </span>
                    </div>
                    {steps[expandedIdx].target && (
                        <div className="text-[11px] text-slate-600 dark:text-slate-400 mb-1">
                            <span className="text-slate-500">Target:</span> {String(steps[expandedIdx].target)}
                        </div>
                    )}
                    {steps[expandedIdx].value && (
                        <div className="text-[11px] text-indigo-400">
                            <span className="text-slate-500">Value:</span> {steps[expandedIdx].value}
                        </div>
                    )}
                    {steps[expandedIdx].description && (
                        <div className="text-[11px] text-slate-500 mt-1 italic">
                            {steps[expandedIdx].description}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default StepTimeline;
