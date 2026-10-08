import { create } from 'zustand';
import type { Locale } from '../i18n';

// ============================================================================
// App store: global controls and theme management
// ============================================================================

const DARK_MODE_KEY = 'ai-test-dark-mode';
const SIDEBAR_KEY = 'ai-test-sidebar-collapsed';
const LOCALE_KEY = 'ai-test-locale';

interface AppStoreState {
    // Execution controls
    enableVision: boolean;
    setEnableVision: (v: boolean) => void;
    useMultiAgent: boolean;
    setUseMultiAgent: (v: boolean) => void;

    // Global settings dialog
    showSettings: boolean;
    setShowSettings: (v: boolean) => void;

    // Theme
    darkMode: boolean;
    setDarkMode: (v: boolean) => void;
    toggleDarkMode: () => void;

    // Sidebar
    sidebarCollapsed: boolean;
    setSidebarCollapsed: (v: boolean) => void;
    toggleSidebar: () => void;

    // Interface locale (P2-1)
    locale: Locale;
    setLocale: (v: Locale) => void;
}

export const useAppStore = create<AppStoreState>((set) => ({
    // Execution controls
    enableVision: true,
    setEnableVision: (v) => set({ enableVision: v }),
    useMultiAgent: true,
    setUseMultiAgent: (v) => set({ useMultiAgent: v }),

    // Global settings dialog
    showSettings: false,
    setShowSettings: (v) => set({ showSettings: v }),

    // Theme initialized from localStorage
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

    // Sidebar
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

    // Interface locale (P2-1)
    locale: 'en-US',
    setLocale: (v) => {
        localStorage.setItem(LOCALE_KEY, v);
        document.documentElement.lang = v;
        set({ locale: v });
    },
}));
