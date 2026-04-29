import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { ChevronRight, Home } from './icons';
import type { NavItemConfig } from './ui/NavItem';

// ============================================================================
// Breadcrumb — 面包屑导航，根据当前路由自动显示层级
// ============================================================================
interface BreadcrumbProps {
    navItems: NavItemConfig[];
}

const Breadcrumb: React.FC<BreadcrumbProps> = ({ navItems }) => {
    const location = useLocation();
    const currentPath = location.pathname;

    if (currentPath.startsWith('/tasks/')) {
        return (
            <nav className="flex items-center gap-1.5 text-sm animate-in fade-in duration-300" aria-label="面包屑导航">
                <Link
                    to="/"
                    className="text-slate-400 dark:text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400 transition-colors"
                >
                    <Home className="w-3.5 h-3.5" />
                </Link>
                <ChevronRight className="w-3 h-3 text-slate-300 dark:text-slate-600" />
                <span className="text-slate-400 dark:text-slate-500">主入口</span>
                <ChevronRight className="w-3 h-3 text-slate-300 dark:text-slate-600" />
                <Link to="/" className="text-slate-400 dark:text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400 transition-colors">
                    统一测试
                </Link>
                <ChevronRight className="w-3 h-3 text-slate-300 dark:text-slate-600" />
                <span className="font-medium text-slate-700 dark:text-slate-300 gradient-text">任务结果</span>
            </nav>
        );
    }

    // Find current nav item
    const currentItem = navItems.find(item =>
        item.path === '/' ? currentPath === '/' : currentPath.startsWith(item.path)
    );

    // Home is the root
    if (!currentItem || currentPath === '/') {
        return (
            <div className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
                <Home className="w-3.5 h-3.5" />
                <span className="font-medium text-slate-700 dark:text-slate-300">控制中心</span>
            </div>
        );
    }

    return (
        <nav className="flex items-center gap-1.5 text-sm animate-in fade-in duration-300" aria-label="面包屑导航">
            <Link
                to="/"
                className="text-slate-400 dark:text-slate-500 hover:text-indigo-500 dark:hover:text-indigo-400 transition-colors"
            >
                <Home className="w-3.5 h-3.5" />
            </Link>
            <ChevronRight className="w-3 h-3 text-slate-300 dark:text-slate-600" />
            {currentItem.group && (
                <>
                    <span className="text-slate-400 dark:text-slate-500">{currentItem.group}</span>
                    <ChevronRight className="w-3 h-3 text-slate-300 dark:text-slate-600" />
                </>
            )}
            <span className="font-medium text-slate-700 dark:text-slate-300 gradient-text">{currentItem.label}</span>
        </nav>
    );
};

export default Breadcrumb;
