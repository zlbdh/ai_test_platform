import { createElement, type ReactNode } from 'react';
import { Download, Package, Play } from '../icons';
import Badge from '../ui/Badge';

export const statusBadge = (status: string): ReactNode => {
    const meta: Record<string, { variant: 'success' | 'error' | 'warning' | 'info' | 'neutral'; label: string }> = {
        running: { variant: 'success', label: "Running" },
        cloned: { variant: 'info', label: "Cloned" },
        not_deployed: { variant: 'neutral', label: "Not deployed" },
        success: { variant: 'success', label: "Success" },
        failed: { variant: 'error', label: "Failed" },
        pending: { variant: 'warning', label: "Waiting" },
        approved: { variant: 'success', label: "Approved" },
        rejected: { variant: 'error', label: "Rejected" },
        cancel_requested: { variant: 'warning', label: "Canceling" },
        cancelled: { variant: 'neutral', label: "Canceled" },
        orphaned: { variant: 'warning', label: "Orphaned task" },
    };
    const item = meta[status] || { variant: 'neutral' as const, label: status };
    return createElement(Badge, { variant: item.variant, dot: true, size: 'sm', children: item.label });
};

export const actionLabel = (action: string): string => {
    const meta: Record<string, string> = {
        clone: "Clone",
        install: "Install",
        start: "Start",
        stop: "Stop",
        full_deploy: "Direct deployment",
        full_deploy_all: "Deploy all directly",
    };
    return meta[action] || action;
};

export const STEP_META: Record<string, { label: string; icon: ReactNode }> = {
    clone: { label: "📥 Clone", icon: createElement(Download, { className: 'w-4 h-4' }) },
    install: { label: "📦 Install", icon: createElement(Package, { className: 'w-4 h-4' }) },
    start: { label: "🚀 Start", icon: createElement(Play, { className: 'w-4 h-4' }) },
};
