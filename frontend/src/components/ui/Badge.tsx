import React, { type ReactNode } from 'react';

type BadgeVariant = 'success' | 'error' | 'warning' | 'info' | 'neutral' | 'healing';
type BadgeSize = 'sm' | 'md';

interface BadgeProps {
    variant?: BadgeVariant;
    size?: BadgeSize;
    dot?: boolean;
    icon?: ReactNode;
    children: ReactNode;
    className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
    success: 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20',
    error: 'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20',
    warning: 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20',
    info: 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20',
    neutral: 'bg-slate-100 dark:bg-slate-700/50 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-600',
    healing: 'bg-teal-50 dark:bg-teal-500/10 text-teal-700 dark:text-teal-400 border-teal-200 dark:border-teal-500/20',
};

const dotColors: Record<BadgeVariant, string> = {
    success: 'bg-emerald-500',
    error: 'bg-red-500',
    warning: 'bg-amber-500',
    info: 'bg-blue-500',
    neutral: 'bg-slate-400',
    healing: 'bg-teal-500',
};

const sizeClasses: Record<BadgeSize, string> = {
    sm: 'text-[10px] px-1.5 py-0.5',
    md: 'text-xs px-2 py-0.5',
};

const Badge: React.FC<BadgeProps> = ({
    variant = 'neutral', size = 'md', dot, icon, children, className = '',
}) => (
    <span className={`inline-flex items-center gap-1 rounded-full border font-medium whitespace-nowrap shadow-sm ${variantStyles[variant]} ${sizeClasses[size]} ${className}`}>
        {dot && <span className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]} ${variant === 'healing' ? 'animate-pulse shadow-sm shadow-teal-500/50' : ''}`} />}
        {icon && <span className="shrink-0">{icon}</span>}
        {children}
    </span>
);

export default Badge;
