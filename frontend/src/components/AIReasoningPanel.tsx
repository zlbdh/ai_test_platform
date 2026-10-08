/** AIReasoningPanel: AI decision history (P2-1).
 * Extract reasoning, decisions, and strategies from SSE logs; show step-by-step decisions and status, with expandable details.
 */
import React, { useState, useMemo } from 'react';
import { Brain, ChevronDown, ChevronRight, Sparkles, Target, Lightbulb, Cpu, Zap } from './icons';
import type { LogEntry, TestStep } from '../types';

interface ReasoningEntry {
    id: string;
    stepIndex: number;
    phase: 'thinking' | 'decided' | 'executing' | 'healed';
    title: string;
    reasoning: string;
    timestamp: string;
    confidence?: number;
    strategy?: string;
    alternatives?: string[];
}

interface AIReasoningPanelProps {
    logs: LogEntry[];
    steps: TestStep[];
    isExecuting: boolean;
}

const PHASE_CONFIG = {
    thinking: { icon: <Brain size={14} className="text-purple-400 animate-pulse" />, label: "Thinking", color: 'purple' },
    decided: { icon: <Target size={14} className="text-blue-400" />, label: "Decided", color: 'blue' },
    executing: { icon: <Zap size={14} className="text-amber-400" />, label: "Running", color: 'amber' },
    healed: { icon: <Sparkles size={14} className="text-emerald-400" />, label: "Self-healing", color: 'emerald' },
};

/* Extract AI reasoning from the log stream.*/
function extractReasoning(logs: LogEntry[], steps: TestStep[]): ReasoningEntry[] {
    const entries: ReasoningEntry[] = [];
    let currentStepIdx = -1;
    let entryId = 0;

    for (const log of logs) {
        const msg = log.message;

        // Detect step advancement.
        if (msg.includes('▶')) {
            currentStepIdx++;
            const step = steps[currentStepIdx];
            entries.push({
                id: `r-${entryId++}`,
                stepIndex: currentStepIdx,
                phase: 'executing',
                title: step ? `Step ${currentStepIdx + 1}: ${step.action}(${step.target})` : `Step ${currentStepIdx + 1}`,
                reasoning: `Starting action: ${msg.replace(/▶\s*/, '')}`,
                timestamp: log.timestamp,
            });
        }

        // Detect AI strategy selection.
        if (msg.includes('Strategy') || (msg.includes('策略') || msg.includes("Strategy")) || msg.includes('strategy')) {
            entries.push({
                id: `r-${entryId++}`,
                stepIndex: currentStepIdx,
                phase: 'decided',
                title: "AI strategy selection",
                reasoning: msg,
                timestamp: log.timestamp,
                strategy: msg,
            });
        }

        // Detect LLM reasoning and analysis.
        if (msg.includes('Plan') || (msg.includes('计划') || msg.includes("Plan")) || (msg.includes('分析') || msg.includes("Analysis"))
            || msg.includes('Thinking') || (msg.includes('推理') || msg.includes("Reasoning")) || msg.includes('LLM')
            || msg.includes('Generated') || (msg.includes('生成') || msg.includes("Generate"))) {
            entries.push({
                id: `r-${entryId++}`,
                stepIndex: currentStepIdx,
                phase: 'thinking',
                title: "AI reasoning analysis",
                reasoning: msg,
                timestamp: log.timestamp,
            });
        }

        // Detect self-healing.
        if (msg.includes('Heal') || (msg.includes('自愈') || msg.includes("Self-healing")) || (msg.includes('重试') || msg.includes("Retry")) || msg.includes('retry')) {
            entries.push({
                id: `r-${entryId++}`,
                stepIndex: currentStepIdx,
                phase: 'healed',
                title: "AI self-healing decision",
                reasoning: msg,
                timestamp: log.timestamp,
            });
        }

        // Detect coverage and dimensions.
        if (msg.includes('P0:') || (msg.includes('维覆盖') || msg.includes("dimensional coverage")) || msg.includes('coverage')) {
            entries.push({
                id: `r-${entryId++}`,
                stepIndex: currentStepIdx,
                phase: 'decided',
                title: "Test coverage decision",
                reasoning: msg,
                timestamp: log.timestamp,
            });
        }
    }

    return entries;
}

const AIReasoningPanel: React.FC<AIReasoningPanelProps> = ({ logs, steps, isExecuting }) => {
    const [expanded, setExpanded] = useState<Set<string>>(new Set());
    const [showAll, setShowAll] = useState(false);

    const reasoningEntries = useMemo(() => extractReasoning(logs, steps), [logs, steps]);

    const displayed = showAll ? reasoningEntries : reasoningEntries.slice(-10);

    const toggleExpand = (id: string) => {
        setExpanded(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    };

    // Statistics
    const thinkingCount = reasoningEntries.filter(e => e.phase === 'thinking').length;
    const decidedCount = reasoningEntries.filter(e => e.phase === 'decided').length;
    const healedCount = reasoningEntries.filter(e => e.phase === 'healed').length;

    return (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md overflow-hidden flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800 shrink-0">
                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                    <Brain size={16} className="text-purple-500" />
                    AI decision history
                    {isExecuting && (
                        <span className="flex items-center gap-1 text-[10px] font-normal text-purple-400 animate-pulse">
                            <Cpu size={10} /> Reasoning...
                        </span>
                    )}
                </h3>
                <div className="flex items-center gap-3 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                    <span className="flex items-center gap-1"><Lightbulb size={10} /> {thinkingCount}</span>
                    <span className="flex items-center gap-1"><Target size={10} /> {decidedCount}</span>
                    {healedCount > 0 && <span className="flex items-center gap-1"><Sparkles size={10} /> {healedCount}</span>}
                </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
                {reasoningEntries.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center" style={{ color: 'var(--color-text-muted)' }}>
                        <Brain size={32} className="mb-3 opacity-30" />
                        <p className="text-sm">No AI decisions yet</p>
                        <p className="text-[11px] mt-1 opacity-60">AI reasoning will appear here after a test runs</p>
                    </div>
                ) : (
                    <>
                        {!showAll && reasoningEntries.length > 10 && (
                            <button
                                onClick={() => setShowAll(true)}
                                className="w-full text-center text-[11px] py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                                style={{ color: 'var(--color-text-muted)' }}
                            >
                                Show all {reasoningEntries.length} reasoning records ↑
                            </button>
                        )}
                        {displayed.map((entry) => {
                            const cfg = PHASE_CONFIG[entry.phase];
                            const isExpanded = expanded.has(entry.id);

                            return (
                                <button
                                    key={entry.id}
                                    className={`w-full text-left rounded-lg px-3 py-2 transition-all border ${isExpanded
                                        ? 'border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-900/10'
                                        : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/50'
                                        }`}
                                    onClick={() => toggleExpand(entry.id)}
                                >
                                    <div className="flex items-center gap-2">
                                        {cfg.icon}
                                        <span className="text-[11px] font-medium truncate flex-1" style={{ color: 'var(--color-text)' }}>
                                            {entry.title}
                                        </span>
                                        <span className="text-[9px] font-mono shrink-0" style={{ color: 'var(--color-text-muted)' }}>
                                            {entry.timestamp}
                                        </span>
                                        {isExpanded ? <ChevronDown size={12} className="shrink-0 opacity-40" /> : <ChevronRight size={12} className="shrink-0 opacity-40" />}
                                    </div>

                                    {isExpanded && (
                                        <div className="mt-2 pl-5">
                                            <div
                                                className="text-[11px] leading-relaxed p-2 rounded-md bg-slate-100 dark:bg-slate-800 font-mono whitespace-pre-wrap break-all"
                                                style={{ color: 'var(--color-text-secondary)' }}
                                            >
                                                {entry.reasoning}
                                            </div>
                                            {entry.strategy && (
                                                <div className="mt-1.5 text-[10px] flex items-center gap-1" style={{ color: 'var(--color-text-muted)' }}>
                                                    <Target size={10} /> Strategy: {entry.strategy.slice(0, 60)}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </button>
                            );
                        })}
                    </>
                )}
            </div>
        </div>
    );
};

export default AIReasoningPanel;
