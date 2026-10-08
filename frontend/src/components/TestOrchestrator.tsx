
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AgentType, TestStep, LogEntry, ExecutionState, AISettings } from '../types';
import { API_ENDPOINTS } from '../config';
import {
    generateTestPlanWithCoverage,
    startExecution,
    stopExecution,
    checkBackendHealth
} from '../services/backendService';
import type { CoverageSummary } from '../services/backendService';
import { beginExecutionCampaign, clearExecutionCampaign, summarizeExecutionTitle } from '../utils/executionContext';

import LogTerminal from './LogTerminal';
import RemoteBrowserView from './RemoteBrowserView';
import TestConfigPanel from './TestConfigPanel';
import PlanPreview from './PlanPreview';
import AIReasoningPanel from './AIReasoningPanel';
import { useToast } from './ui/Toast';

type StepExecutionStatus = 'running' | 'success' | 'error' | 'skipped';

interface StreamLogPayload {
    type?: string;
    event?: string;
    content?: string;
    step?: string;
    status?: string;
    step_index?: number;
    task_id?: string;
    action?: string;
    target?: string;
    value?: string;
    ui_track?: boolean;
    duration?: number;
}

interface TestOrchestratorProps {
    updateAgentStatus: (agent: AgentType, status: 'IDLE' | 'BUSY' | 'ERROR' | 'HEALING') => void;
    incrementAgentTasks: (agent: AgentType, success: boolean) => void;
    enableVision: boolean;
    setEnableVision: (val: boolean) => void;
    useMultiAgent: boolean;
    setUseMultiAgent: (val: boolean) => void;
    onShowHistory: () => void;
    aiSettings: AISettings;
    onOpenSettings?: () => void;
    sessionId: string;
    browserMode: 'chromium' | 'real';
}

export function resolveTaskDisplayText(task?: string, taskDisplay?: string): string {
    const preferredDisplay = (taskDisplay || '').trim();
    if (preferredDisplay) {
        return preferredDisplay;
    }
    return (task || '').trim();
}

const TestOrchestrator: React.FC<TestOrchestratorProps> = ({
    enableVision,
    useMultiAgent,
    setUseMultiAgent,
    aiSettings,
    onOpenSettings,
    sessionId,
    browserMode
}) => {
    const [isExecuting, setIsExecuting] = useState(false);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [currentAction, setCurrentAction] = useState("Waiting for a task...");
    const [executionState, setExecutionState] = useState<ExecutionState>(ExecutionState.IDLE);
    const { showToast } = useToast();

    // Planning State
    const [requirement, setRequirement] = useState('');
    const [targetUrl, setTargetUrl] = useState('');
    const [probeMode, setProbeMode] = useState(false);
    const [isPlanning, setIsPlanning] = useState(false);
    const [testPlan, setTestPlan] = useState<TestStep[]>([]);
    const [coverageSummary, setCoverageSummary] = useState<CoverageSummary | null>(null);
    const [runtimeExecutionMode, setRuntimeExecutionMode] = useState<'default' | 'probe'>('default');
    const [runtimeInteractionPolicy, setRuntimeInteractionPolicy] = useState<'default' | 'read_only'>('default');
    const [runtimeStepBudget, setRuntimeStepBudget] = useState<number | null>(null);
    const [stepStatuses, setStepStatuses] = useState<Map<number, StepExecutionStatus>>(new Map());
    const activeStepRef = useRef<number>(-1);
    const stepStatusesRef = useRef<Map<number, StepExecutionStatus>>(new Map());
    const taskStepIndexRef = useRef<Map<string, number>>(new Map());

    // Refs to avoid exhaustive-deps issues in polling/SSE effects
    const sessionIdRef = useRef(sessionId);
    const currentActionRef = useRef(currentAction);
    const testPlanRef = useRef(testPlan);
    useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
    useEffect(() => { currentActionRef.current = currentAction; }, [currentAction]);
    useEffect(() => { testPlanRef.current = testPlan; }, [testPlan]);

    const addLog = (agent: AgentType, level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS' | 'HEAL', message: string) => {
        setLogs(prev => [...prev, { timestamp: new Date().toLocaleTimeString(), agent, level, message }]);
    };

    const scrollToStep = (stepIndex: number) => {
        window.setTimeout(() => {
            const el = document.getElementById(`plan-step-${stepIndex}`);
            el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
    };

    const setTrackedStepStatus = useCallback((stepIndex: number, status: StepExecutionStatus) => {
        if (stepIndex < 0) return;
        const next = new Map(stepStatusesRef.current);
        next.set(stepIndex, status);
        stepStatusesRef.current = next;
        setStepStatuses(next);
        if (status === 'running') {
            activeStepRef.current = stepIndex;
            scrollToStep(stepIndex);
        }
    }, []);

    const markRemainingStepsSkipped = useCallback(() => {
        const next = new Map(stepStatusesRef.current);
        for (let i = 0; i < testPlanRef.current.length; i++) {
            if (!next.has(i)) {
                next.set(i, 'skipped');
            }
        }
        const activeStep = activeStepRef.current;
        if (activeStep >= 0 && next.get(activeStep) === 'running') {
            next.set(activeStep, 'success');
        }
        stepStatusesRef.current = next;
        setStepStatuses(next);
    }, []);

    const normalizeStructuredText = (value?: string) => (value || '').trim().toLowerCase();

    const resolveStructuredStepIndex = useCallback((logEntry: StreamLogPayload): number => {
        if (typeof logEntry.step_index === 'number') {
            return logEntry.step_index;
        }

        if (logEntry.task_id) {
            const mappedIndex = taskStepIndexRef.current.get(logEntry.task_id);
            if (typeof mappedIndex === 'number') {
                return mappedIndex;
            }
        }

        const action = normalizeStructuredText(logEntry.action);
        const target = normalizeStructuredText(logEntry.target);
        const value = normalizeStructuredText(logEntry.value);
        const event = logEntry.event || '';

        if (action || target || value) {
            const exactMatch = testPlanRef.current.findIndex((step, index) => {
                const stepAction = normalizeStructuredText(step.action);
                const stepTarget = normalizeStructuredText(step.target);
                const stepValue = normalizeStructuredText(step.value);
                const isFinal = stepStatusesRef.current.get(index) === 'success'
                    || stepStatusesRef.current.get(index) === 'error'
                    || stepStatusesRef.current.get(index) === 'skipped';

                if (event === 'step_start' && isFinal) {
                    return false;
                }

                return stepAction === action && stepTarget === target && stepValue === value;
            });

            if (exactMatch >= 0) {
                return exactMatch;
            }

            const partialMatch = testPlanRef.current.findIndex((step, index) => {
                const stepAction = normalizeStructuredText(step.action);
                const stepTarget = normalizeStructuredText(step.target);
                const isFinal = stepStatusesRef.current.get(index) === 'success'
                    || stepStatusesRef.current.get(index) === 'error'
                    || stepStatusesRef.current.get(index) === 'skipped';

                if (event === 'step_start' && isFinal) {
                    return false;
                }

                return stepAction === action && stepTarget === target;
            });

            if (partialMatch >= 0) {
                return partialMatch;
            }
        }

        if (event === 'step_start') {
            const nextIndex = activeStepRef.current + 1;
            if (nextIndex >= 0 && nextIndex < testPlanRef.current.length) {
                return nextIndex;
            }
        }

        return activeStepRef.current;
    }, []);

    const trackStructuredStep = useCallback((logEntry: StreamLogPayload) => {
        if (!logEntry.event || logEntry.ui_track === false) {
            return false;
        }

        const stepIndex = resolveStructuredStepIndex(logEntry);
        if (stepIndex < 0) {
            return false;
        }

        if (logEntry.task_id) {
            taskStepIndexRef.current.set(logEntry.task_id, stepIndex);
        }

        if (logEntry.event === 'step_start') {
            setTrackedStepStatus(stepIndex, 'running');
            return true;
        }

        if (logEntry.event === 'step_result') {
            setTrackedStepStatus(stepIndex, logEntry.status === 'success' ? 'success' : 'error');
            if (logEntry.task_id) {
                taskStepIndexRef.current.delete(logEntry.task_id);
            }
            return true;
        }

        return false;
    }, [resolveStructuredStepIndex, setTrackedStepStatus]);

    // ── State Polling ──
    useEffect(() => {
        if (!isExecuting && executionState !== ExecutionState.RUNNING) return;

        const interval = setInterval(async () => {
            try {
                const res = await fetch(API_ENDPOINTS.status(sessionIdRef.current));
                const data = await res.json();

                if (data.is_running === false && isExecuting) {
                    setExecutionState(ExecutionState.IDLE);
                    setIsExecuting(false);
                    setCurrentAction("Task completed");
                } else if (data.signal === 'PAUSED') {
                    if (executionState !== ExecutionState.PAUSED) setExecutionState(ExecutionState.PAUSED);
                } else if (data.signal === 'RUNNING') {
                    if (executionState !== ExecutionState.RUNNING) setExecutionState(ExecutionState.RUNNING);
                } else if (data.signal === 'STOPPED') {
                    if (executionState !== ExecutionState.STOPPED) {
                        setExecutionState(ExecutionState.STOPPED);
                        setIsExecuting(false);
                    }
                }

                const nextTask = resolveTaskDisplayText(data.task, data.task_display);
                if (nextTask && nextTask !== currentActionRef.current) {
                    setCurrentAction(nextTask);
                }
                setRuntimeExecutionMode((data.execution_mode || 'default') as 'default' | 'probe');
                setRuntimeInteractionPolicy((data.interaction_policy || 'default') as 'default' | 'read_only');
                setRuntimeStepBudget(typeof data.step_budget === 'number' ? data.step_budget : null);
            } catch (e) {
                console.error("Status Poll Error", e);
            }
        }, 1000);

        return () => clearInterval(interval);
    }, [isExecuting, executionState]);

    // ── SSE Log Streaming ──
    useEffect(() => {
        let eventSource: EventSource | null = null;

        if (isExecuting || executionState === ExecutionState.RUNNING || executionState === ExecutionState.PAUSED) {
            eventSource = new EventSource(API_ENDPOINTS.stream(sessionIdRef.current));

            eventSource.onmessage = (event) => {
                try {
                    const logData = JSON.parse(event.data);
                    const logEntry: StreamLogPayload = typeof logData === 'string' ? { content: logData } : logData;

                    if (logEntry.type === 'done') {
                        addLog(AgentType.PLANNER, 'SUCCESS', "✅[Completed] Test task completed");
                        setExecutionState(ExecutionState.IDLE);
                        setIsExecuting(false);
                        setCurrentAction("Task completed");
                        eventSource?.close();
                        return;
                    }

                    const level = logEntry.type === 'heal'
                        ? 'HEAL'
                        : logEntry.type === 'error' || logEntry.status === 'error'
                            ? 'ERROR'
                            : (logEntry.type === 'result' && logEntry.status === 'success') || (logEntry.type === 'assertion' && logEntry.status === 'pass')
                                ? 'SUCCESS'
                                : 'INFO';
                    const content = logEntry.content || logEntry.step || JSON.stringify(logEntry);
                    addLog(AgentType.PLANNER, level, content);

                    const trackedByStructuredEvent = trackStructuredStep(logEntry);

                    // Legacy step status tracking fallback
                    if (!trackedByStructuredEvent && !logEntry.event && content.includes('▶')) {
                        const nextIdx = activeStepRef.current + 1;
                        setTrackedStepStatus(nextIdx, 'running');
                    } else if (!logEntry.event && (content.includes('✅ success') || content.includes('Assert Passed'))) {
                        const idx = activeStepRef.current;
                        if (idx >= 0) {
                            setTrackedStepStatus(idx, 'success');
                        }
                    } else if (!logEntry.event && (content.includes('❌') || content.includes('Assert Failed'))) {
                        const idx = activeStepRef.current;
                        if (idx >= 0) {
                            setTrackedStepStatus(idx, 'error');
                        }
                    }

                    if (content.includes('Mission Accomplished') || (content.includes('任务已完成') || content.includes("Task completed"))) {
                        markRemainingStepsSkipped();
                    }

                    if (logEntry.content) {
                        setCurrentAction(logEntry.content.slice(0, 50));
                    } else if (logEntry.step) {
                        setCurrentAction(logEntry.step.slice(0, 50));
                    }
                } catch {
                    // SSE Parse Error — silent
                }
            };

            eventSource.onerror = () => {
                if (!isExecuting) {
                    eventSource?.close();
                }
            };
        }

        return () => { eventSource?.close(); };
    }, [isExecuting, executionState, markRemainingStepsSkipped, setTrackedStepStatus, trackStructuredStep]);

    const handleGeneratePlan = async () => {
        if (!requirement.trim()) return;
        setIsPlanning(true);
        setTestPlan([]);
        setCoverageSummary(null);
        setLogs([]);
        const resetStatuses = new Map<number, StepExecutionStatus>();
        setStepStatuses(resetStatuses);
        stepStatusesRef.current = resetStatuses;
        taskStepIndexRef.current = new Map();
        activeStepRef.current = -1;

        const backendAvailable = await checkBackendHealth();
        if (!backendAvailable) {
            addLog(AgentType.PLANNER, 'WARN', 'Backend service (Port 8010) is offline.');
        }

        try {
            const executionMode = probeMode ? 'probe' : 'default';
            const interactionPolicy = probeMode ? 'read_only' : 'default';
            const result = await generateTestPlanWithCoverage(requirement, targetUrl, executionMode, interactionPolicy);
            setTestPlan(result.steps);
            setCoverageSummary(result.coverage_summary);
            if (result.steps.length === 0) {
                addLog(AgentType.PLANNER, 'ERROR', "Plan generation failed: the LLM returned an empty plan. Check the API configuration.");
                showToast('error', "Plan generation failed: the LLM returned no valid steps. Check the API key or network connection.");
            } else {
                const cs = result.coverage_summary;
                const coverageInfo = cs ? ` | P0:${cs.by_priority.P0} P1:${cs.by_priority.P1} P2:${cs.by_priority.P2} | ${cs.dimensions_covered.length} dimensional coverage` : '';
                addLog(AgentType.PLANNER, 'SUCCESS', `Plan Generated: ${result.steps.length} steps.${coverageInfo}`);
                showToast('success', `Plan generated: ${result.steps.length} steps`);
            }
        } catch (e: unknown) {
            const errMsg = e instanceof Error ? e.message : "Unknown error";
            addLog(AgentType.PLANNER, 'ERROR', `Plan Generation Failed: ${errMsg}`);
            showToast('error', `Plan generation failed: ${errMsg}`);
        } finally {
            setIsPlanning(false);
        }
    };

    const executePlan = async () => {
        setIsExecuting(true);
        setExecutionState(ExecutionState.RUNNING);
        const resetStatuses = new Map<number, StepExecutionStatus>();
        setStepStatuses(resetStatuses);
        stepStatusesRef.current = resetStatuses;
        taskStepIndexRef.current = new Map();
        activeStepRef.current = -1;

        const modeLabel = useMultiAgent ? "Multi-Agent System (v1.3.0)" : "Legacy ReAct Engine";
        addLog(AgentType.PLANNER, 'INFO', `[Starting] Dispatching task to ${modeLabel}... (Vision: ${enableVision ? 'ON' : 'OFF'})`);

        let taskToExecute = requirement || "Unnamed test task";
        if (testPlan.length > 0) {
            const planText = testPlan.map((step, i) =>
                `Step ${i + 1}: ${step.action}(${step.target}${step.value ? ', ' + step.value : ''})`
            ).join('\n');
            taskToExecute += `\n\n[Guiding Plan]:\n${planText}`;
            addLog(AgentType.PLANNER, 'INFO', `[Plan] Attached a ${testPlan.length}-step execution plan to the task context.`);
        }

        const campaignTitle = summarizeExecutionTitle(requirement || taskToExecute);
        const executionCampaign = beginExecutionCampaign(campaignTitle, {
            sessionId,
            targetUrl,
            source: 'orchestrator',
        });
        addLog(AgentType.PLANNER, 'INFO', `[Batch] Current test batch: ${executionCampaign.title} (${executionCampaign.id})`);

        try {
            const executionMode = probeMode ? 'probe' : 'default';
            const interactionPolicy = probeMode ? 'read_only' : 'default';
            await startExecution(
                taskToExecute,
                useMultiAgent,
                enableVision,
                targetUrl,
                sessionId,
                browserMode,
                executionCampaign.id,
                executionMode,
                interactionPolicy
            );
            setRuntimeExecutionMode(executionMode);
            setRuntimeInteractionPolicy(interactionPolicy);
            setRuntimeStepBudget(executionMode === 'probe' ? 8 : null);
            showToast('info', "Test task started");
        } catch (e: unknown) {
            const errMsg = e instanceof Error ? e.message : "Unknown error";
            clearExecutionCampaign(sessionId);
            addLog(AgentType.PLANNER, 'ERROR', `Execution Start Failed: ${errMsg}`);
            showToast('error', `Failed to start: ${errMsg}`);
            setIsExecuting(false);
            setExecutionState(ExecutionState.IDLE);
        }
    };

    const handleStop = async () => {
        try {
            await stopExecution(sessionId);
            setExecutionState(ExecutionState.STOPPED);
            setIsExecuting(false);
            addLog(AgentType.PLANNER, 'WARN', "[Stop] Stop requested");
            showToast('warning', "Task stopped");
        } catch (e: unknown) {
            showToast('error', `Failed to stop: ${e instanceof Error ? e.message : "Network error"}`);
        }
    };

    const handleQuickDiagnose = () => {
        if (!targetUrl) return;
        const diagRequirement = `Visual diagnostics: open ${targetUrl}, check the layout, element visibility, text readability, and responsive design, then take screenshots and report any issues`;
        setRequirement(diagRequirement);
        showToast('info', "Quick diagnostics filled in. Click Generate test plan.");
    };

    // ── Render ──
    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-140px)] min-h-0">

            {/* Left Col: Input & Plan */}
            <div className="lg:col-span-1 flex flex-col gap-6 min-h-0 overflow-y-auto">
                <TestConfigPanel
                    requirement={requirement}
                    setRequirement={setRequirement}
                    targetUrl={targetUrl}
                    setTargetUrl={setTargetUrl}
                    probeMode={probeMode}
                    setProbeMode={setProbeMode}
                    useMultiAgent={useMultiAgent}
                    setUseMultiAgent={setUseMultiAgent}
                    aiSettings={aiSettings}
                    isPlanning={isPlanning}
                    isExecuting={isExecuting}
                    onGeneratePlan={handleGeneratePlan}
                    onQuickDiagnose={handleQuickDiagnose}
                    onOpenSettings={onOpenSettings}
                />
                <PlanPreview
                    testPlan={testPlan}
                    coverageSummary={coverageSummary}
                    stepStatuses={stepStatuses}
                    isExecuting={isExecuting}
                    onExecute={executePlan}
                    onStop={handleStop}
                />
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                    Current execution mode:
                    <span className="ml-1 font-semibold text-slate-900 dark:text-white">
                        {runtimeExecutionMode === 'probe' ? "Read-only probe" : "Default execution"}
                    </span>
                    {runtimeInteractionPolicy === 'read_only' && (
                        <span className="ml-2 text-emerald-600 dark:text-emerald-400">Read-only policy is active</span>
                    )}
                    {runtimeStepBudget !== null && <span className="ml-2">Step budget: {runtimeStepBudget}</span>}
                </div>
            </div>

            {/* Middle Col: Remote Browser */}
            <div className="lg:col-span-1 flex flex-col min-h-0 overflow-hidden">
                <RemoteBrowserView url={targetUrl} isActive={isExecuting} currentAction={currentAction} sessionId={sessionId} />
            </div>

            {/* Right Col: AI Reasoning + Logs */}
            <div className="lg:col-span-1 flex flex-col gap-3 min-h-0 overflow-hidden">
                <div className="h-[40%] min-h-0 overflow-hidden">
                    <AIReasoningPanel logs={logs} steps={testPlan} isExecuting={isExecuting} />
                </div>
                <div className="flex-1 min-h-0 overflow-hidden">
                    <LogTerminal logs={logs} onClear={() => setLogs([])} />
                </div>
            </div>
        </div>
    );
};

export default TestOrchestrator;
