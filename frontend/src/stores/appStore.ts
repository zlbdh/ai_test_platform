import { create } from 'zustand';
import type { Locale } from '../i18n';

// ============================================================================
// App Store — 全局控制参数 + 主题管理
// ============================================================================

const DARK_MODE_KEY = 'ai-test-dark-mode';
const SIDEBAR_KEY = 'ai-test-sidebar-collapsed';
const LOCALE_KEY = 'ai-test-locale';

interface AppStoreState {
    // 执行控制
    enableVision: boolean;
    setEnableVision: (v: boolean) => void;
    useMultiAgent: boolean;
    setUseMultiAgent: (v: boolean) => void;

    // 全局设置弹窗
    showSettings: boolean;
    setShowSettings: (v: boolean) => void;

    // 主题
    darkMode: boolean;
    setDarkMode: (v: boolean) => void;
    toggleDarkMode: () => void;

    // 侧边栏
    sidebarCollapsed: boolean;
    setSidebarCollapsed: (v: boolean) => void;
    toggleSidebar: () => void;

    // 国际化 (P2-1)
    locale: Locale;
    setLocale: (v: Locale) => void;
}

export const useAppStore = create<AppStoreState>((set) => ({
    // 执行控制
    enableVision: true,
    setEnableVision: (v) => set({ enableVision: v }),
    useMultiAgent: true,
    setUseMultiAgent: (v) => set({ useMultiAgent: v }),

    // 全局设置弹窗
    showSettings: false,
    setShowSettings: (v) => set({ showSettings: v }),

    // 主题 (从 localStorage 初始化)
    darkMode: (() => {
        const saved = localStorage.getItem(DARK_MODE_KEY);
        return saved !== null ? saved === 'true' : true;
    })(),
    setDarkMode: (v) => {
        document.documentElement.classList.toggle('dark', v);
        localStorage.setItem(DARK_MODE_KEY, String(v));
        set({ darkMode: v });
    },
    toggleDarkMode: () => set((state) => {
        const next = !state.darkMode;
        document.documentElement.classList.toggle('dark', next);
        localStorage.setItem(DARK_MODE_KEY, String(next));
        return { darkMode: next };
    }),

    // 侧边栏
    sidebarCollapsed: localStorage.getItem(SIDEBAR_KEY) === 'true',
    setSidebarCollapsed: (v) => {
        localStorage.setItem(SIDEBAR_KEY, String(v));
        set({ sidebarCollapsed: v });
    },
    toggleSidebar: () => set((state) => {
        const next = !state.sidebarCollapsed;
        localStorage.setItem(SIDEBAR_KEY, String(next));
        return { sidebarCollapsed: next };
    }),

    // 国际化 (P2-1)
    locale: (localStorage.getItem(LOCALE_KEY) as Locale) || 'zh-CN',
    setLocale: (v) => {
        localStorage.setItem(LOCALE_KEY, v);
        document.documentElement.lang = v;
        set({ locale: v });
    },
}));
