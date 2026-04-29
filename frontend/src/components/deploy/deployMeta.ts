import { createElement, type ReactNode } from 'react';
import { Download, Package, Play } from '../icons';
import Badge from '../ui/Badge';

export const statusBadge = (status: string): ReactNode => {
    const meta: Record<string, { variant: 'success' | 'error' | 'warning' | 'info' | 'neutral'; label: string }> = {
        running: { variant: 'success', label: '运行中' },
        cloned: { variant: 'info', label: '已克隆' },
        not_deployed: { variant: 'neutral', label: '未部署' },
        success: { variant: 'success', label: '成功' },
        failed: { variant: 'error', label: '失败' },
        pending: { variant: 'warning', label: '等待中' },
        approved: { variant: 'success', label: '已批准' },
        rejected: { variant: 'error', label: '已驳回' },
        cancel_requested: { variant: 'warning', label: '取消中' },
        cancelled: { variant: 'neutral', label: '已取消' },
        orphaned: { variant: 'warning', label: '孤儿任务' },
    };
    const item = meta[status] || { variant: 'neutral' as const, label: status };
    return createElement(Badge, { variant: item.variant, dot: true, size: 'sm', children: item.label });
};

export const actionLabel = (action: string): string => {
    const meta: Record<string, string> = {
        clone: '克隆',
        install: '安装',
        start: '启动',
        stop: '停止',
        full_deploy: '直接部署',
        full_deploy_all: '全部直接部署',
    };
    return meta[action] || action;
};

export const STEP_META: Record<string, { label: string; icon: ReactNode }> = {
    clone: { label: '📥 克隆', icon: createElement(Download, { className: 'w-4 h-4' }) },
    install: { label: '📦 安装', icon: createElement(Package, { className: 'w-4 h-4' }) },
    start: { label: '🚀 启动', icon: createElement(Play, { className: 'w-4 h-4' }) },
};
