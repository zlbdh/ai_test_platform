import React from 'react';
import { NavLink } from 'react-router-dom';
import { useT } from '../../hooks/useT';

// ============================================================================
// NavItem Types — 导出供 Layout.tsx 使用
// ============================================================================
export interface NavItemConfig {
    path: string;
    label: string;        // 中文默认值（回退）
    labelKey?: string;     // i18n 翻译键，如 'nav.dashboard'
    icon: React.ReactNode;
    group: string;
}

// ============================================================================
// NavItem Component — 可复用的侧边栏导航按钮（集成 i18n）
// ============================================================================
interface NavItemProps {
    item: NavItemConfig;
    collapsed: boolean;
}

const NavItem: React.FC<NavItemProps> = ({ item, collapsed }) => {
    const tt = useT();
    const displayLabel = item.labelKey ? tt(item.labelKey) : item.label;
    // 如果 tt 返回原 key（翻译缺失），回退到 label
    const finalLabel = displayLabel === item.labelKey ? item.label : displayLabel;

    return (
        <NavLink
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
                `nav-active-bar flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium transition-all duration-200 group
            ${isActive
                    ? 'active bg-gradient-to-r from-indigo-50 to-indigo-50/50 dark:from-indigo-500/10 dark:to-indigo-500/5 text-indigo-600 dark:text-indigo-400'
                    : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/60 hover:text-slate-800 dark:hover:text-slate-200 hover:translate-x-0.5'
                }
            ${collapsed ? 'justify-center' : ''}`
            }
            title={collapsed ? finalLabel : undefined}
        >
            <span className="shrink-0 transition-transform duration-200 group-[.active]:scale-110">{item.icon}</span>
            {!collapsed && <span className="truncate">{finalLabel}</span>}
        </NavLink>
    );
};

export default NavItem;
