import React, { useEffect, useRef } from 'react';
import {
    CheckCircle2, XCircle, Clock, X, Loader2,
} from '../icons';
import { STEP_META } from './deployMeta';

export interface ProgressState {
    open: boolean;
    repoLabel: string;
    steps: { name: string; label: string; status: string; message: string; duration_ms: number }[];
    logs: string[];
    finalStatus: string;  // '' | 'success' | 'failed'
    finalMessage: string;
}

const DeployProgressPanel: React.FC<{ state: ProgressState; onClose: () => void }> = ({ state, onClose }) => {
    const logEndRef = useRef<HTMLDivElement>(null);
    useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [state.logs]);

    if (!state.open) return null;

    const isDone = !!state.finalStatus;
    const isSuccess = state.finalStatus === 'success';
    const isCancelled = state.finalStatus === 'cancelled';
    const headerClass = isSuccess
        ? 'bg-gradient-to-r from-emerald-500 to-teal-500'
        : isCancelled
            ? 'bg-gradient-to-r from-amber-500 to-orange-500'
            : state.finalStatus
                ? 'bg-gradient-to-r from-red-500 to-rose-500'
                : 'bg-gradient-to-r from-cyan-500 to-blue-500';
    const footerClass = isSuccess
        ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600'
        : isCancelled
            ? 'bg-amber-50 dark:bg-amber-900/20 text-amber-600'
            : 'bg-red-50 dark:bg-red-900/20 text-red-600';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-300" onClick={isDone ? onClose : undefined}>
            <div className="w-full max-w-xl rounded-2xl bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl shadow-2xl border border-slate-200/80 dark:border-slate-700/80 overflow-hidden flex flex-col animate-in zoom-in-95 duration-300"
                style={{ maxHeight: 'calc(100vh - 4rem)' }} onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className={`px-6 py-4 flex items-center justify-between ${headerClass}`}>
                    <h3 className="text-white text-sm font-bold flex items-center gap-2">
                        {!isDone ? <Loader2 className="w-4 h-4 animate-spin" /> : isSuccess ? <CheckCircle2 className="w-4 h-4" /> : isCancelled ? <Clock className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                        Direct deployment · {state.repoLabel}
                    </h3>
                    {isDone && <button onClick={onClose} className="text-white/70 hover:text-white transition"><X className="w-4 h-4" /></button>}
                </div>

                {/* Step Timeline */}
                <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
                    <div className="flex items-center gap-0">
                        {state.steps.map((step, i) => {
                            const meta = STEP_META[step.name] || { label: step.name, icon: null };
                            const isActive = step.status === 'running';
                            const isSuccess = step.status === 'success';
                            const isFailed = step.status === 'failed';
                            const isSkipped = step.status === 'skipped';
                            return (
                                <React.Fragment key={step.name}>
                                    <div className={`flex flex-col items-center gap-1.5 flex-1 ${isSkipped ? 'opacity-40' : ''
                                        }`}>
                                        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white transition-all duration-500 ${isActive ? 'bg-cyan-500 ring-4 ring-cyan-200 dark:ring-cyan-800 animate-pulse' :
                                            isSuccess ? 'bg-emerald-500' :
                                                isFailed ? 'bg-red-500' :
                                                    'bg-slate-200 dark:bg-slate-700 text-slate-400'
                                            }`}>
                                            {isActive ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                                isSuccess ? <CheckCircle2 className="w-4 h-4" /> :
                                                    isFailed ? <XCircle className="w-4 h-4" /> :
                                                        meta.icon || <Clock className="w-4 h-4" />}
                                        </div>
                                        <span className={`text-[11px] font-semibold ${isActive ? 'text-cyan-600 dark:text-cyan-400' :
                                            isSuccess ? 'text-emerald-600 dark:text-emerald-400' :
                                                isFailed ? 'text-red-600 dark:text-red-400' :
                                                    'text-slate-400'
                                            }`}>{meta.label}</span>
                                        {step.duration_ms > 0 && (
                                            <span className="text-[9px] text-slate-400">{(step.duration_ms / 1000).toFixed(1)}s</span>
                                        )}
                                        {step.message && (
                                            <span className={`text-[9px] max-w-[140px] truncate ${isFailed ? 'text-red-500' : 'text-slate-400'
                                                }`} title={step.message}>{step.message}</span>
                                        )}
                                    </div>
                                    {i < state.steps.length - 1 && (
                                        <div className={`h-0.5 w-8 mt-[-30px] transition-colors duration-500 ${isSuccess ? 'bg-emerald-400' : 'bg-slate-200 dark:bg-slate-700'
                                            }`} />
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </div>
                </div>

                {/* Live Logs */}
                <div className="flex-1 max-h-64 overflow-auto bg-slate-950 p-4 font-mono text-[11px] text-green-400 leading-relaxed">
                    {state.logs.length === 0 ? <span className="text-slate-500">Waiting for direct deployment to start...</span> : state.logs.map((l, i) => (
                        <div key={i} className={`whitespace-pre-wrap break-all ${(l.includes('🔧 自愈') || l.includes("🔧 Self-healing")) ? 'text-amber-400' :
                            l.includes('❌') || l.includes('ERROR') ? 'text-red-400' :
                                l.includes('✅') ? 'text-emerald-400' : ''
                            }`}>
                            <span className="text-slate-600 mr-2 select-none">{String(i + 1).padStart(3, ' ')}</span>{l}
                        </div>
                    ))}
                    <div ref={logEndRef} />
                </div>

                {/* Footer */}
                {isDone && (
                    <div className={`px-6 py-3 text-center text-xs font-medium ${footerClass}`}>
                        {state.finalMessage}
                    </div>
                )}
            </div>
        </div>
    );
};

export default DeployProgressPanel;
