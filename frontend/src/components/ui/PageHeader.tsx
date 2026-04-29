import React from 'react';

interface PageHeaderProps {
    icon: React.ReactNode;
    title: string;
    description?: string;
    /** Accent color for the icon background. Must be a Tailwind bg color class fragment like 'indigo' */
    accent?: string;
    actions?: React.ReactNode;
}

/**
 * 统一的页面标题组件 — 确保所有页面外观一致。
 *
 * 用法:
 * ```tsx
 * <PageHeader
 *   icon={<Webhook className="w-5 h-5" />}
 *   title="CI/CD 集成"
 *   description="配置 Webhook、查看触发历史"
 *   accent="indigo"
 *   actions={<button>刷新</button>}
 * />
 * ```
 */
const PageHeader: React.FC<PageHeaderProps> = ({ icon, title, description, accent = 'indigo', actions }) => {
    const accentBg: Record<string, string> = {
        indigo: 'bg-gradient-to-br from-indigo-500/15 to-violet-500/10 text-indigo-500 dark:from-indigo-500/20 dark:to-violet-500/15',
        violet: 'bg-gradient-to-br from-violet-500/15 to-purple-500/10 text-violet-500 dark:from-violet-500/20 dark:to-purple-500/15',
        emerald: 'bg-gradient-to-br from-emerald-500/15 to-teal-500/10 text-emerald-500 dark:from-emerald-500/20 dark:to-teal-500/15',
        pink: 'bg-gradient-to-br from-pink-500/15 to-rose-500/10 text-pink-500 dark:from-pink-500/20 dark:to-rose-500/15',
        orange: 'bg-gradient-to-br from-orange-500/15 to-amber-500/10 text-orange-500 dark:from-orange-500/20 dark:to-amber-500/15',
        teal: 'bg-gradient-to-br from-teal-500/15 to-cyan-500/10 text-teal-500 dark:from-teal-500/20 dark:to-cyan-500/15',
        sky: 'bg-gradient-to-br from-sky-500/15 to-blue-500/10 text-sky-500 dark:from-sky-500/20 dark:to-blue-500/15',
        amber: 'bg-gradient-to-br from-amber-500/15 to-yellow-500/10 text-amber-500 dark:from-amber-500/20 dark:to-yellow-500/15',
        red: 'bg-gradient-to-br from-red-500/15 to-pink-500/10 text-red-500 dark:from-red-500/20 dark:to-pink-500/15',
        cyan: 'bg-gradient-to-br from-cyan-500/15 to-sky-500/10 text-cyan-500 dark:from-cyan-500/20 dark:to-sky-500/15',
        blue: 'bg-gradient-to-br from-blue-500/15 to-indigo-500/10 text-blue-500 dark:from-blue-500/20 dark:to-indigo-500/15',
        slate: 'bg-gradient-to-br from-slate-500/15 to-gray-500/10 text-slate-500 dark:from-slate-500/20 dark:to-gray-500/15',
    };

    return (
        <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-xl ${accentBg[accent] || accentBg.indigo} shadow-sm ring-1 ring-inset ring-white/10`}>
                    {icon}
                </div>
                <div>
                    <h1 className="text-xl font-bold text-slate-800 dark:text-white tracking-tight">{title}</h1>
                    {description && (
                        <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5 max-w-lg">{description}</p>
                    )}
                </div>
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
    );
};

export default PageHeader;
