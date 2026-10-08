import React from 'react';
import type { TestStep } from '../types';

// ── Style constants ──
const ACTION_STYLES: Record<string, string> = {
    goto: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    fill: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    click: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    assert: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    wait: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    key: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    select: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    hover: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
    scroll: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    screenshot: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    extract: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
    set_var: 'bg-fuchsia-500/20 text-fuchsia-400 border-fuchsia-500/30',
    visual_check: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
    mock: 'bg-lime-500/20 text-lime-400 border-lime-500/30',
    api_call: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
    db_query: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    assert_db: 'bg-amber-600/20 text-amber-300 border-amber-600/30',
    snapshot_db: 'bg-stone-500/20 text-stone-400 border-stone-500/30',
};

const ACTION_ICONS: Record<string, string> = {
    goto: '▶', fill: '✎', click: '○',
    assert: '✓', wait: '⏳', key: '⌨',
    select: '≡', hover: '→', scroll: '↕',
    screenshot: '▣', extract: '↑', set_var: '$',
    visual_check: '◎', mock: '∼', api_call: '⇄',
    db_query: '⊞', assert_db: '✔', snapshot_db: '⬇',
};

const STATUS_STYLES: Record<string, string> = {
    running: 'border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-950/30',
    success: 'border-green-400 dark:border-green-500 bg-green-50 dark:bg-green-950/30',
    error: 'border-red-400 dark:border-red-500 bg-red-50 dark:bg-red-950/30',
    skipped: 'border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800/50 opacity-50',
};

const STATUS_ICONS: Record<string, string> = {
    running: '●',
    success: '✓',
    error: '✗',
    skipped: '→',
};

interface PlanStepItemProps {
    step: TestStep;
    idx: number;
    status?: 'running' | 'success' | 'error' | 'skipped';
}

const PlanStepItem: React.FC<PlanStepItemProps> = ({ step, idx, status }) => {
    const baseStyle = status
        ? STATUS_STYLES[status]
        : 'border-slate-200 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-800/80';
    const style = ACTION_STYLES[step.action] || 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    const icon = ACTION_ICONS[step.action] || '▶';
    const scenarioName = step.description?.split(':')[0] || '';

    return (
        <div
            id={`plan-step-${idx}`}
            className={`p-2.5 rounded-lg border ${baseStyle} hover:bg-slate-100 dark:hover:bg-slate-800 transition-all group ${status === 'skipped' ? 'line-through' : ''}`}
        >
            <div className="flex items-center gap-2 mb-1">
                {status ? (
                    <span className={`text-sm ${status === 'running' ? 'animate-pulse' : ''}`}>
                        {STATUS_ICONS[status]}
                    </span>
                ) : (
                    <span className="text-[10px] font-mono text-slate-500 bg-slate-200 dark:bg-slate-700/50 px-1.5 py-0.5 rounded">
                        {idx + 1}
                    </span>
                )}
                <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${style}`}>
                    {icon} {step.action}
                </span>
                {step.priority && (
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${step.priority === 'P0' ? 'bg-red-500/20 text-red-400' :
                        step.priority === 'P1' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-slate-500/20 text-slate-400'
                        }`}>
                        {step.priority}
                    </span>
                )}
                {scenarioName && (
                    <span className="text-[10px] text-slate-500 truncate" title={scenarioName}>
                        {scenarioName}
                    </span>
                )}
            </div>
            <div className="flex items-center gap-2 pl-6 text-xs">
                {step.target && (
                    <span className="text-slate-700 dark:text-slate-300">
                        <span className="text-slate-500">Target:</span> {String(step.target)}
                    </span>
                )}
                {step.value && (
                    <span className="text-indigo-400">
                        <span className="text-slate-500">Value:</span> {step.value}
                    </span>
                )}
            </div>
        </div>
    );
};

export default PlanStepItem;
