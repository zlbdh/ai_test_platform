import React, { type ReactNode } from 'react';
import { Inbox } from '../icons';

interface EmptyStateProps {
    icon?: ReactNode;
    title: string;
    description?: string;
    action?: ReactNode;
    className?: string;
}

const EmptyState: React.FC<EmptyStateProps> = ({
    icon, title, description, action, className = '',
}) => (
    <div className={`flex flex-col items-center justify-center py-12 text-center ${className}`}>
        <div className="rounded-2xl bg-gradient-to-br from-slate-100 to-indigo-50 dark:from-slate-800/50 dark:to-indigo-500/5 p-4 mb-4 float-subtle">
            {icon || <Inbox className="w-8 h-8 text-slate-300 dark:text-slate-600" />}
        </div>
        <h3 className="text-base font-semibold text-slate-700 dark:text-slate-300 mb-1">
            {title}
        </h3>
        {description && (
            <p className="text-sm text-slate-400 dark:text-slate-500 max-w-xs mb-4 leading-relaxed">
                {description}
            </p>
        )}
        {action && <div>{action}</div>}
    </div>
);

export default EmptyState;
