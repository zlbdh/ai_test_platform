import React from 'react';
import { Play, Square, ClipboardList } from './icons';
import type { TestStep } from '../types';
import type { CoverageSummary } from '../services/backendService';
import PlanStepItem from './PlanStepItem';
import StepTimeline from './StepTimeline';

interface PlanPreviewProps {
    testPlan: TestStep[];
    coverageSummary: CoverageSummary | null;
    stepStatuses: Map<number, 'running' | 'success' | 'error' | 'skipped'>;
    isExecuting: boolean;
    onExecute: () => void;
    onStop: () => void;
}

const PlanPreview: React.FC<PlanPreviewProps> = ({
    testPlan, coverageSummary, stepStatuses,
    isExecuting, onExecute, onStop,
}) => {
    return (
        <div className="flex-1 min-h-0 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 p-6 backdrop-blur-md overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white">Execution plan</h2>
                    {testPlan.length > 0 && (
                        <span className="text-xs bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 px-2 py-0.5 rounded-full font-medium">
                            {testPlan.length} steps
                        </span>
                    )}
                </div>
                {/* Control Buttons */}
                <div className="flex gap-2">
                    {!isExecuting && (
                        <button
                            onClick={onExecute}
                            className="flex items-center gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-full transition-colors font-medium">
                            <Play className="w-3 h-3" /> Run
                        </button>
                    )}
                    {isExecuting && (
                        <button onClick={onStop} className="flex items-center gap-1.5 text-xs bg-red-600 px-3 py-1.5 rounded-full text-white animate-pulse">
                            <Square className="w-3 h-3" /> Stop
                        </button>
                    )}
                </div>
            </div>

            {/* Coverage Summary Panel */}
            {coverageSummary && testPlan.length > 0 && (
                <div className="mb-3 p-3 rounded-lg bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20">
                    <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-1.5">
                            <span className="text-slate-500">Scenario</span>
                            <span className="font-bold text-indigo-400">{coverageSummary.total_scenarios}</span>
                        </div>
                        <div className="flex items-center gap-1">
                            {coverageSummary.by_priority.P0 > 0 && (
                                <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-bold">P0:{coverageSummary.by_priority.P0}</span>
                            )}
                            {coverageSummary.by_priority.P1 > 0 && (
                                <span className="px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 font-bold">P1:{coverageSummary.by_priority.P1}</span>
                            )}
                            {coverageSummary.by_priority.P2 > 0 && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-500/20 text-slate-400 font-bold">P2:{coverageSummary.by_priority.P2}</span>
                            )}
                        </div>
                        {coverageSummary.dimensions_covered.length > 0 && (
                            <div className="flex items-center gap-1 flex-wrap">
                                <span className="text-slate-500">Coverage:</span>
                                {coverageSummary.dimensions_covered.slice(0, 4).map((dim, i) => (
                                    <span key={i} className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px]">{dim}</span>
                                ))}
                                {coverageSummary.dimensions_covered.length > 4 && (
                                    <span className="text-slate-500">+{coverageSummary.dimensions_covered.length - 4}</span>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Step Timeline */}
            {testPlan.length > 0 && (
                <div className="mb-3">
                    <StepTimeline steps={testPlan} statuses={stepStatuses} />
                </div>
            )}

            <div className="flex-1 overflow-y-auto pr-1 space-y-2 min-h-0 max-h-[420px]">
                {testPlan.map((step, idx) => (
                    <PlanStepItem
                        key={idx}
                        step={step}
                        idx={idx}
                        status={stepStatuses.get(idx)}
                    />
                ))}
                {testPlan.length === 0 && (
                    <div className="text-slate-500 text-center text-sm mt-8 flex flex-col items-center gap-2">
                        <ClipboardList className="w-8 h-8 text-slate-300" />
                        <span>No execution plan yet</span>
                        <span className="text-xs text-slate-600">Enter test requirements, then click Generate test plan</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PlanPreview;
