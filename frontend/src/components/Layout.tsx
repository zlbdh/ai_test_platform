import React, { useState, useEffect } from 'react';
import AnimatedOutlet from './AnimatedOutlet';
import {
    Settings, Moon, Sun, PanelLeftClose, PanelLeftOpen,
    Zap, Menu, X, Search, Globe, ChevronDown, ChevronRight
} from './icons';
import { useAISettingsStore, useAppStore } from '../stores';
import SettingsModal from './SettingsModal';
import CommandPalette from './CommandPalette';
import NotificationCenter from './NotificationCenter';
import { useHotkeys } from '../hooks/useHotkeys';
import { useNotifications } from '../hooks/useNotifications';
import NavItem, { type NavItemConfig } from './ui/NavItem';
import Breadcrumb from './Breadcrumb';
import { NAV_ITEMS } from './navConfig';
import { SUPPORTED_LOCALES, translateGroupName, type Locale } from '../i18n';
import { useT } from '../hooks/useT';
import { API_ENDPOINTS } from '../config';
import { normalizeAISettings, normalizeBackendConfig } from '../config/aiModelConfig';
import { AIProvider } from '../types';

// ============================================================================
// Layout Component — 使用 Zustand store（无 Context）
// ============================================================================
const Layout: React.FC = () => {
    // Zustand stores
    const { aiSettings, setAiSettings } = useAISettingsStore();
    const { darkMode, toggleDarkMode, sidebarCollapsed, toggleSidebar, locale, setLocale, showSettings, setShowSettings } = useAppStore();
    const tt = useT();

    // Local UI state
    const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
    const [showCommandPalette, setShowCommandPalette] = useState(false);
    const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({
        '主入口': false,
        '专家入口（深挖）': true,
        '治理入口（后座）': true,
    });

    // P2-1: Notifications
    const { notifications, markRead, markAllRead, clearAll, removeOne } = useNotifications();

    // P2-1: 全局快捷键
    useHotkeys([
        {
            key: 'ctrl+k',
            description: '打开命令面板',
            handler: () => setShowCommandPalette(true),
            enableInInput: true,
        },
        {
            key: 'ctrl+.',
            description: '打开设置',
            handler: () => setShowSettings(true),
        },
        {
            key: 'escape',
            description: '关闭弹窗',
            handler: () => {
                if (showCommandPalette) setShowCommandPalette(false);
                else if (showSettings) setShowSettings(false);
            },
        },
    ]);

    // Dark mode sync on mount
    useEffect(() => {
        document.documentElement.classList.toggle('dark', darkMode);
    }, [darkMode]);

    useEffect(() => {
        let cancelled = false;

        (async () => {
            try {
                const res = await fetch(API_ENDPOINTS.config.ai);
                const data = await res.json();
                if (!cancelled && data?.config) {
                    const runtimeConfig = normalizeBackendConfig(data.config);
                    setAiSettings(normalizeAISettings({
                        provider: AIProvider.OPENAI,
                        modelName: runtimeConfig.model,
                        baseUrl: runtimeConfig.base_url,
                    }));
                }
            } catch {
                // ignore and fallback to local defaults
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [setAiSettings]);

    // Group nav items
    const groups = NAV_ITEMS.reduce<Record<string, NavItemConfig[]>>((acc, item) => {
        (acc[item.group] = acc[item.group] || []).push(item);
        return acc;
    }, {});

    // ── Sidebar content (shared between desktop and mobile) ──
    const sidebarContent = (collapsed: boolean, onNavClick?: () => void) => (
        <>
            {/* Nav Groups */}
            <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-5">
                {Object.entries(groups).map(([groupName, items]) => (
                    <div key={groupName}>
                        {!collapsed && (
                            <button
                                type="button"
                                onClick={() => setCollapsedGroups((prev) => ({ ...prev, [groupName]: !prev[groupName] }))}
                                className="mb-2 flex w-full items-center justify-between px-2 text-[10px] font-bold uppercase tracking-widest text-slate-400/70 transition-colors hover:text-slate-500 dark:text-slate-500/70 dark:hover:text-slate-300"
                            >
                                <span>{translateGroupName(groupName, locale as Locale)}</span>
                                {collapsedGroups[groupName] ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            </button>
                        )}
                        {collapsed && <div className="h-px bg-gradient-to-r from-transparent via-slate-200 dark:via-slate-700 to-transparent mx-2 my-1" />}
                        {(collapsed || !collapsedGroups[groupName]) && (
                            <div className="space-y-0.5" onClick={onNavClick}>
                                {items.map(item => (
                                    <NavItem key={item.path} item={item} collapsed={collapsed} />
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </nav>
        </>
    );

    return (
        <>
            <div className={`dashboard-grid bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-200 transition-colors duration-300 ${sidebarCollapsed ? 'collapsed' : ''}`}>

                {/* ─── Desktop Sidebar (grid-area: sidebar) ─── */}
                <aside
                    data-area="sidebar"
                    className="hidden md:flex flex-col border-r border-slate-200/80 dark:border-slate-800/80 bg-gradient-to-b from-white via-white to-slate-50/80 dark:from-slate-950 dark:via-slate-950 dark:to-slate-900/80 transition-[width] duration-300"
                >
                    {/* Logo / Brand */}
                    <div className="flex items-center gap-2.5 px-4 border-b border-slate-200/80 dark:border-slate-800/80 shrink-0" style={{ height: 'var(--header-height)' }}>
                        <div className="relative">
                            <div className="absolute inset-0 bg-indigo-500/20 rounded-lg blur-md animate-pulse" />
                            <div className="relative p-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
                                <Zap className="w-4 h-4 text-white" />
                            </div>
                        </div>
                        {!sidebarCollapsed && (
                            <span className="font-bold text-sm gradient-text truncate tracking-wide">
                                AI Test Platform
                            </span>
                        )}
                    </div>

                    {sidebarContent(sidebarCollapsed)}

                    {/* Sidebar Footer */}
                    <div className="border-t border-slate-200/80 dark:border-slate-800/80 p-2 shrink-0">
                        <button
                            onClick={toggleSidebar}
                            className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-slate-400 hover:text-indigo-500 dark:hover:text-indigo-400 hover:bg-indigo-50/50 dark:hover:bg-indigo-500/10 transition-all duration-200 group/collapse"
                            title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
                        >
                            {sidebarCollapsed
                                ? <PanelLeftOpen className="w-4 h-4 mx-auto group-hover/collapse:scale-110 transition-transform" />
                                : <><PanelLeftClose className="w-4 h-4 group-hover/collapse:scale-110 transition-transform" /><span>收起</span></>
                            }
                        </button>
                    </div>
                </aside>

                {/* ─── Top Bar (grid-area: header) ─── */}
                <header
                    data-area="header"
                    className="relative z-[100] flex items-center justify-between px-4 md:px-6 border-b border-slate-200/80 dark:border-slate-800/80 glass-panel"
                >
                    <div className="flex items-center gap-3">
                        {/* Mobile hamburger */}
                        <button
                            onClick={() => setMobileDrawerOpen(true)}
                            className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors md:hidden"
                        >
                            <Menu className="w-5 h-5" />
                        </button>
                        {/* Breadcrumb */}
                        <Breadcrumb navItems={NAV_ITEMS} />
                    </div>
                    <div className="flex items-center gap-1.5">
                        {/* Command Palette trigger */}
                        <button
                            onClick={() => setShowCommandPalette(true)}
                            className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs text-slate-400 hover:text-indigo-500 dark:hover:text-indigo-400 hover:border-indigo-300 dark:hover:border-indigo-500/40 hover:bg-indigo-50/50 dark:hover:bg-indigo-500/10 bg-slate-50/50 dark:bg-slate-800/50 transition-all duration-200 hover:shadow-sm"
                            style={{ borderColor: 'var(--color-border)' }}
                            title="搜索页面和操作 (Ctrl+K)"
                        >
                            <Search className="w-3.5 h-3.5" />
                            <span>{tt('common.search')}</span>
                            <kbd className="text-[10px] px-1.5 py-0.5 rounded border font-mono ml-2 bg-white dark:bg-slate-800 text-slate-400" style={{ borderColor: 'var(--color-border)' }}>Ctrl K</kbd>
                        </button>
                        <NotificationCenter
                            notifications={notifications}
                            onMarkRead={markRead}
                            onMarkAllRead={markAllRead}
                            onClear={clearAll}
                            onRemove={removeOne}
                        />
                        {/* Language switcher */}
                        <button
                            onClick={() => {
                                const currentIdx = SUPPORTED_LOCALES.findIndex(l => l.code === locale);
                                const nextIdx = (currentIdx + 1) % SUPPORTED_LOCALES.length;
                                setLocale(SUPPORTED_LOCALES[nextIdx].code);
                            }}
                            className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all duration-200 flex items-center gap-1"
                            title={`${SUPPORTED_LOCALES.find(l => l.code === locale)?.flag} ${SUPPORTED_LOCALES.find(l => l.code === locale)?.label}`}
                        >
                            <Globe className="w-4 h-4" />
                            <span className="text-[10px] font-medium hidden sm:inline">{SUPPORTED_LOCALES.find(l => l.code === locale)?.flag}</span>
                        </button>
                        <button
                            onClick={toggleDarkMode}
                            className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all duration-200"
                            title={darkMode ? '切换亮色模式' : '切换暗色模式'}
                        >
                            {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                        </button>
                        <button
                            onClick={() => setShowSettings(true)}
                            className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all duration-200"
                            title={tt('common.settings')}
                        >
                            <Settings className="w-4 h-4" />
                        </button>
                    </div>
                </header>

                {/* ─── Page Content (grid-area: main) ─── */}
                <main data-area="main" style={{ padding: 'var(--page-padding)' }}>
                    <div className="content-area">
                        <AnimatedOutlet context={{ onOpenSettings: () => setShowSettings(true) }} />
                    </div>
                </main>
            </div>

            {/* ─── Mobile Drawer Overlay ─── */}
            {mobileDrawerOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
                    onClick={() => setMobileDrawerOpen(false)}
                />
            )}

            {/* ─── Mobile Drawer ─── */}
            <aside className={`fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 flex flex-col transform transition-transform duration-300 md:hidden ${mobileDrawerOpen ? 'translate-x-0' : '-translate-x-full'}`}>
                {/* Mobile Drawer Header */}
                <div className="flex items-center justify-between px-4 border-b border-slate-200 dark:border-slate-800 shrink-0" style={{ height: 'var(--header-height)' }}>
                    <div className="flex items-center gap-2.5">
                        <div className="relative">
                            <div className="absolute inset-0 bg-indigo-500/20 rounded-lg blur-md animate-pulse" />
                            <div className="relative p-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
                                <Zap className="w-4 h-4 text-white" />
                            </div>
                        </div>
                        <span className="font-bold text-sm gradient-text tracking-wide">
                            AI Test Platform
                        </span>
                    </div>
                    <button
                        onClick={() => setMobileDrawerOpen(false)}
                        className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {sidebarContent(false, () => setMobileDrawerOpen(false))}
            </aside>

            {/* Settings Modal */}
            <SettingsModal
                isOpen={showSettings}
                initialSettings={aiSettings}
                onSave={(settings) => {
                    setAiSettings(settings);
                    setShowSettings(false);
                }}
                onClose={() => setShowSettings(false)}
            />

            {/* Command Palette */}
            <CommandPalette
                isOpen={showCommandPalette}
                onClose={() => setShowCommandPalette(false)}
                onOpenSettings={() => setShowSettings(true)}
                onToggleTheme={toggleDarkMode}
                isDark={darkMode}
            />
        </>
    );
};

export default Layout;
