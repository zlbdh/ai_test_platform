import React from 'react';
import { NavLink } from 'react-router-dom';
import { useT } from '../../hooks/useT';

// ============================================================================
// NavItem types exported for Layout.tsx.
// ============================================================================
export interface NavItemConfig {
    path: string;
    label: string;        // English fallback label
    labelKey?: string;     // i18n translation key, for example 'nav.dashboard'
    icon: React.ReactNode;
    group: string;
}

// ============================================================================
// NavItem: reusable sidebar navigation button with i18n support.
// ============================================================================
interface NavItemProps {
    item: NavItemConfig;
    collapsed: boolean;
}

const NavItem: React.FC<NavItemProps> = ({ item, collapsed }) => {
    const tt = useT();
    const displayLabel = item.labelKey ? tt(item.labelKey) : item.label;
    // Fall back to label when tt returns the original key for a missing translation.
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
