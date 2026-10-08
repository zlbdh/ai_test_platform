import React, { useEffect, useRef, useState, useMemo } from 'react';
import { LogEntry, AgentType } from '../types';
import { Terminal, Trash2, ChevronDown, ChevronUp } from './icons';

interface LogTerminalProps {
    logs: LogEntry[];
    onClear?: () => void;
}

type LogFilter = 'ALL' | 'ERROR' | 'WARN' | 'SUCCESS' | 'HEAL';

const FILTER_STYLES: Record<LogFilter, { active: string; label: string }> = {
    ALL: { active: 'bg-slate-600 text-white', label: "All" },
    ERROR: { active: 'bg-red-500/30 text-red-400', label: "Error" },
    WARN: { active: 'bg-amber-500/30 text-amber-400', label: "Warning" },
    SUCCESS: { active: 'bg-emerald-500/30 text-emerald-400', label: "Success" },
    HEAL: { active: 'bg-purple-500/30 text-purple-400', label: "Self-healing" },
};

const LogTerminal: React.FC<LogTerminalProps> = ({ logs, onClear }) => {
    const endRef = useRef<HTMLDivElement>(null);
    const [collapsed, setCollapsed] = useState(false);
    const [filter, setFilter] = useState<LogFilter>('ALL');

    const MAX_VISIBLE_LOGS = 500;

    const filteredLogs = useMemo(() => {
        if (filter === 'ALL') return logs;
        return logs.filter(log => log.level === filter);
    }, [logs, filter]);

    // Trim logs to the latest MAX_VISIBLE_LOGS entries.
    const truncatedCount = Math.max(0, filteredLogs.length - MAX_VISIBLE_LOGS);
    const visibleLogs = useMemo(() => {
        if (filteredLogs.length <= MAX_VISIBLE_LOGS) return filteredLogs;
        return filteredLogs.slice(-MAX_VISIBLE_LOGS);
    }, [filteredLogs]);

    useEffect(() => {
        if (!collapsed) {
            endRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [visibleLogs, collapsed]);

    const getLogColor = (level: string) => {
        switch (level) {
            case 'ERROR': return 'text-red-400';
            case 'WARN': return 'text-amber-400';
            case 'SUCCESS': return 'text-emerald-400';
            case 'HEAL': return 'text-purple-600 dark:text-purple-400 font-bold';
            default: return 'text-slate-600 dark:text-slate-300';
        }
    };

    const getAgentLabel = (agent: AgentType) => {
        switch (agent) {
            case AgentType.UI: return 'UI-BOT';
            case AgentType.API: return 'API-BOT';
            case AgentType.DATA: return 'DB-BOT';
            case AgentType.RCA: return 'RCA-CORE';
            case AgentType.PLANNER: return 'ORCHESTRATOR';
            default: return 'SYS';
        }
    };

    // Count entries by level.
    const errorCount = logs.filter(l => l.level === 'ERROR').length;

    return (
        <div className="flex flex-col h-full min-h-0 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 overflow-hidden shadow-2xl">
            <div className="shrink-0 flex items-center justify-between border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 px-4 py-2">
                <div className="flex items-center gap-2 text-slate-400">
                    <Terminal className="w-4 h-4" />
                    <span className="text-xs font-mono font-bold uppercase tracking-wider">Live system logs</span>
                    {logs.length > 0 && (
                        <span className="text-[10px] bg-slate-200 dark:bg-slate-800 text-slate-500 px-1.5 py-0.5 rounded-full">
                            {filter === 'ALL' ? logs.length : `${filteredLogs.length}/${logs.length}`}
                        </span>
                    )}
                    {errorCount > 0 && filter === 'ALL' && (
                        <span className="text-[10px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full font-bold animate-pulse">
                            {errorCount} Errors
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1.5">
                    {/* Log level filter buttons*/}
                    <div className="flex items-center gap-0.5 mr-2">
                        {(Object.keys(FILTER_STYLES) as LogFilter[]).map((f) => (
                            <button
                                key={f}
                                onClick={() => setFilter(f)}
                                className={`px-1.5 py-0.5 text-[10px] rounded transition-all ${filter === f
                                    ? FILTER_STYLES[f].active + ' font-bold'
                                    : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
                                    }`}
                            >
                                {FILTER_STYLES[f].label}
                            </button>
                        ))}
                    </div>
                    {onClear && (
                        <button
                            onClick={onClear}
                            title={"Clear logs"}
                            className="p-1 text-slate-400 hover:text-red-400 transition-colors rounded"
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                        </button>
                    )}
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        title={collapsed ? "Expand logs" : "Collapse logs"}
                        className="p-1 text-slate-400 hover:text-slate-200 transition-colors rounded"
                    >
                        {collapsed ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                </div>
            </div>
            {!collapsed && (
                <div className="flex-1 min-h-0 overflow-y-auto p-4 font-mono text-sm space-y-2">
                    {truncatedCount > 0 && (
                        <div className="text-center text-[10px] text-slate-500 bg-slate-100 dark:bg-slate-800/50 rounded py-1 mb-2">
                            ↑ Omitted {truncatedCount} older log entries
                        </div>
                    )}
                    {visibleLogs.length === 0 && (
                        <div className="text-slate-400 dark:text-slate-600 italic">
                            {filter === 'ALL' ? "No activity yet..." : `No ${FILTER_STYLES[filter].label} logs`}
                        </div>
                    )}
                    {visibleLogs.map((log, idx) => (
                        <div key={idx} className="flex gap-3 hover:bg-slate-100 dark:hover:bg-slate-900/50 p-1 rounded transition-colors">
                            <span className="text-slate-400 dark:text-slate-500 whitespace-nowrap text-xs pt-0.5">{log.timestamp}</span>
                            <div className="flex-1 break-words">
                                <span className={`font-bold mr-3 text-xs px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 ${getLogColor(log.level)}`}>
                                    {getAgentLabel(log.agent)}
                                </span>
                                <span className={getLogColor(log.level)}>{log.message}</span>
                            </div>
                        </div>
                    ))}
                    <div ref={endRef} />
                </div>
            )}
        </div>
    );
};

export default LogTerminal;
