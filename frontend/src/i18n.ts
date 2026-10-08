/** English interface messages and legacy navigation group aliases. */

export type Locale = 'en-US';

export interface I18nMessages {
    [key: string]: string | I18nMessages;
}

const enUS: I18nMessages = {
    common: {
        search: 'Search...',
        settings: 'Settings',
        save: 'Save',
        cancel: 'Cancel',
        confirm: 'Confirm',
        close: 'Close',
        delete: 'Delete',
        loading: 'Loading...',
        noData: 'No data',
        success: 'Success',
        error: 'Error',
        warning: 'Warning',
    },
    nav: {
        frontdoor: 'Unified Testing',
        dashboard: 'Control Center',
        legion: 'Legion Center',
        orchestrator: 'Orchestrator',
        prototypeAgents: 'Prototype Testing',
        history: 'Execution Center',
        batch: 'Batch Testing',
        performance: 'Performance',
        security: 'Security Scan',
        api: 'API Workbench',
        database: 'Database',
        quality: 'Quality Audit',
        resilience: 'Resilience',
        knowledge: 'Knowledge Base',
        cicd: 'CI/CD',
        requirement: 'Requirements',
        exploratory: 'Exploratory',
        contract: 'Contract Testing',
        i18nA11y: 'i18n & A11y',
        mobile: 'Mobile Testing',
        evaluation: 'Evaluation',
        qualityGate: 'Quality Gate',
        scenario: 'Scenario Chain',
        visual: 'Visual Regression',
        testdata: 'Test Data',
        deploy: 'Deployment',
        notifications: 'Notifications',
        scheduler: 'Scheduler',
        settings: 'More Tools',
    },
    layout: {
        brandName: 'AI Test Platform',
        collapse: 'Collapse',
        expand: 'Expand sidebar',
        darkMode: 'Switch to dark mode',
        lightMode: 'Switch to light mode',
        notifications: 'Notifications',
        searchPages: 'Search pages and actions',
        language: 'Language',
    },
    dashboard: {
        title: 'Control Center',
        subtitle: 'Agent overview & system monitoring',
        todayExec: 'Today Executions',
        passRate: 'Pass Rate',
        avgDuration: 'Avg Duration',
        defects: 'Defects Found',
        trend7Days: 'Last 7 Days Trend',
        agentStatus: 'Agent Status',
        noExecData: 'No execution data',
    },
    orchestrator: {
        title: 'Test Orchestrator',
        generatePlan: 'Generate Plan',
        execute: 'Execute',
        stop: 'Stop',
        requirement: 'Enter test requirement...',
        targetUrl: 'Target URL',
        planGenerated: 'Plan generated successfully',
        planFailed: 'Plan generation failed',
        taskStarted: 'Test task started',
        taskCompleted: 'Test task completed',
    },
    reasoning: {
        title: 'AI Reasoning Trace',
        noData: 'No AI reasoning data',
        noDataHint: 'Run a test to see AI reasoning process here',
        thinking: 'Thinking',
        decided: 'Decided',
        executing: 'Executing',
        healed: 'Self-healed',
    },
    commandPalette: {
        searchPlaceholder: 'Search pages, actions...',
        noResults: 'No matching results',
        navGroup: 'Navigation',
        actionGroup: 'Actions',
        settingsGroup: 'Settings',
        openSettings: 'Open Settings',
        toggleTheme: 'Toggle Theme',
        shortcuts: 'Keyboard Shortcuts',
    },
    notifications: {
        title: 'Notifications',
        markAllRead: 'Mark all as read',
        clearAll: 'Clear all',
        noNotifications: 'No notifications',
        justNow: 'Just now',
        minutesAgo: 'min ago',
        hoursAgo: 'hr ago',
        daysAgo: 'days ago',
    },
};

const MESSAGES: Record<Locale, I18nMessages> = { 'en-US': enUS };

/** Resolve a dotted message key, falling back to English for legacy locale values. */
export function t(locale: Locale, key: string): string {
    const parts = key.split('.');
    let result: I18nMessages | string = MESSAGES[locale] || MESSAGES['en-US'];
    for (const part of parts) {
        if (typeof result === 'string') return key;
        result = result[part];
        if (result === undefined) return key;
    }
    return typeof result === 'string' ? result : key;
}

export const SUPPORTED_LOCALES: { code: Locale; label: string; flag: string }[] = [
    { code: 'en-US', label: 'English (US)', flag: '🇺🇸' },
];

/** Preserve legacy group identifiers while displaying English labels. */
const GROUP_NAMES: Record<string, Record<Locale, string>> = {
    "主入口": { 'en-US': "Main Entry" },
    "专家入口": { 'en-US': "Expert Entry" },
    "专家入口（深挖）": { 'en-US': "Expert Entry (Deep Dive)" },
    "治理入口": { 'en-US': "Governance Entry" },
    "治理入口（后座）": { 'en-US': "Governance Entry (Back Office)" },
    "核心": { 'en-US': "Core" },
    "测试工具": { 'en-US': "Tools" },
    "质量保障": { 'en-US': "Quality" },
    "知识管理": { 'en-US': "Knowledge" },
    "运维管理": { 'en-US': "Operations" },
    "设置": { 'en-US': "Settings" },
};

export function translateGroupName(groupName: string, locale: Locale): string {
    return GROUP_NAMES[groupName]?.[locale] || GROUP_NAMES[groupName]?.['en-US'] || groupName;
}

export default MESSAGES;
