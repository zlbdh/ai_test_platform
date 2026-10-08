import React from 'react';
import { Layers, Link2, Radio } from './icons';
import { useActiveExecutionContext } from '../utils/executionContext';

interface ExecutionBatchBannerProps {
    standaloneHint: string;
}

const ExecutionBatchBanner: React.FC<ExecutionBatchBannerProps> = ({ standaloneHint }) => {
    const { sessionId, batch } = useActiveExecutionContext();

    return (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 backdrop-blur-md px-4 py-3">
            {batch ? (
                <div className="flex flex-wrap items-center gap-3 text-sm">
                    <div className="inline-flex items-center gap-2 rounded-full bg-indigo-500/10 px-3 py-1 text-indigo-600 dark:text-indigo-300">
                        <Layers className="h-4 w-4" />
                        Current test batch
                    </div>
                    <span className="font-medium text-slate-800 dark:text-slate-100">{batch.title}</span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-300">
                        <Link2 className="h-3.5 w-3.5" />
                        {batch.id}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-600 dark:text-emerald-300">
                        <Radio className="h-3.5 w-3.5" />
                        Session {sessionId}
                    </span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                        Results from this page are automatically added to this test run.
                    </span>
                </div>
            ) : (
                <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
                    <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        <Layers className="h-4 w-4" />
                        No test batch linked
                    </div>
                    <span>{standaloneHint}</span>
                </div>
            )}
        </div>
    );
};

export default ExecutionBatchBanner;
