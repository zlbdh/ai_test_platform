/**
 * i18n — 轻量级国际化基础设施 (P2-1)
 * 
 * 支持中英文切换，无第三方依赖
 * 使用 Zustand store 管理语言状态
 */

export type Locale = 'zh-CN' | 'en-US';

export interface I18nMessages {
    [key: string]: string | I18nMessages;
}

// ── 中文翻译 ──
const zhCN: I18nMessages = {
    common: {
        search: '搜索...',
        settings: '设置',
        save: '保存',
        cancel: '取消',
        confirm: '确认',
        close: '关闭',
        delete: '删除',
        loading: '加载中...',
        noData: '暂无数据',
        success: '成功',
        error: '错误',
        warning: '警告',
    },
    nav: {
        frontdoor: '统一测试',
        dashboard: '控制中心',
        legion: '军团中心',
        orchestrator: '测试编排',
        prototypeAgents: '原型测试',
        history: '执行中心',
        batch: '批量测试',
        performance: '性能测试',
        security: '安全扫描',
        api: 'API 工作台',
        database: '数据库测试',
        quality: '质量审计',
        resilience: '韧性测试',
        knowledge: '知识库',
        cicd: 'CI/CD',
        requirement: '需求管理',
        exploratory: '探索性测试',
        contract: '契约测试',
        i18nA11y: 'i18n & A11y',
        mobile: '移动测试',
        evaluation: '评估中心',
        qualityGate: '质量门禁',
        scenario: '场景链',
        visual: '视觉回归',
        testdata: '测试数据',
        deploy: '项目部署',
        notifications: '通知配置',
        scheduler: '定时任务',
        settings: '更多工具',
    },
    layout: {
        brandName: 'AI Test Platform',
        collapse: '收起',
        expand: '展开侧边栏',
        darkMode: '切换暗色模式',
        lightMode: '切换亮色模式',
        notifications: '通知中心',
        searchPages: '搜索页面和操作',
        language: '语言',
    },
    dashboard: {
        title: '控制中心',
        subtitle: '智能体状态总览与系统监控',
        todayExec: '今日执行',
        passRate: '通过率',
        avgDuration: '平均耗时',
        defects: '发现缺陷',
        trend7Days: '最近 7 天趋势',
        agentStatus: '智能体状态',
        noExecData: '暂无执行数据',
    },
    orchestrator: {
        title: '测试编排',
        generatePlan: '生成计划',
        execute: '执行',
        stop: '停止',
        requirement: '输入测试需求...',
        targetUrl: '目标URL',
        planGenerated: '计划生成成功',
        planFailed: '计划生成失败',
        taskStarted: '测试任务已启动',
        taskCompleted: '测试任务已完成',
    },
    reasoning: {
        title: 'AI 决策追溯',
        noData: '尚无 AI 决策记录',
        noDataHint: '执行测试后，AI 的推理过程将在此展示',
        thinking: '思考中',
        decided: '已决策',
        executing: '执行中',
        healed: '自愈',
    },
    commandPalette: {
        searchPlaceholder: '搜索页面、操作...',
        noResults: '没有匹配的结果',
        navGroup: '页面导航',
        actionGroup: '操作',
        settingsGroup: '设置',
        openSettings: '打开设置',
        toggleTheme: '切换主题',
        shortcuts: '快捷键一览',
    },
    notifications: {
        title: '通知',
        markAllRead: '全部标为已读',
        clearAll: '清空所有',
        noNotifications: '暂无通知',
        justNow: '刚刚',
        minutesAgo: '分钟前',
        hoursAgo: '小时前',
        daysAgo: '天前',
    },
};

// ── 英文翻译 ──
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

const MESSAGES: Record<Locale, I18nMessages> = {
    'zh-CN': zhCN,
    'en-US': enUS,
};

/**
 * 获取翻译文本
 * @param locale 当前语言
 * @param key 翻译键（支持点号路径，如 'nav.dashboard'）
 * @returns 翻译文本
 */
export function t(locale: Locale, key: string): string {
    const parts = key.split('.');
    let result: I18nMessages | string = MESSAGES[locale] || MESSAGES['zh-CN'];

    for (const part of parts) {
        if (typeof result === 'string') return key; // 路径错误
        result = result[part];
        if (result === undefined) return key; // 未找到翻译
    }

    return typeof result === 'string' ? result : key;
}

/** 获取所有支持的语言列表 */
export const SUPPORTED_LOCALES: { code: Locale; label: string; flag: string }[] = [
    { code: 'zh-CN', label: '中文', flag: '🇨🇳' },
    { code: 'en-US', label: 'English', flag: '🇺🇸' },
];


/** 导航分组名翻译 */
const GROUP_NAMES: Record<string, Record<Locale, string>> = {
    '主入口': { 'zh-CN': '主入口', 'en-US': 'Main Entry' },
    '专家入口': { 'zh-CN': '专家入口', 'en-US': 'Expert Entry' },
    '专家入口（深挖）': { 'zh-CN': '专家入口（深挖）', 'en-US': 'Expert Entry (Deep Dive)' },
    '治理入口': { 'zh-CN': '治理入口', 'en-US': 'Governance Entry' },
    '治理入口（后座）': { 'zh-CN': '治理入口（后座）', 'en-US': 'Governance Entry (Back Office)' },
    '核心': { 'zh-CN': '核心', 'en-US': 'Core' },
    '测试工具': { 'zh-CN': '测试工具', 'en-US': 'Tools' },
    '质量保障': { 'zh-CN': '质量保障', 'en-US': 'Quality' },
    '知识管理': { 'zh-CN': '知识管理', 'en-US': 'Knowledge' },
    '运维管理': { 'zh-CN': '运维管理', 'en-US': 'Operations' },
    '设置': { 'zh-CN': '设置', 'en-US': 'Settings' },
};

export function translateGroupName(group: string, locale: Locale): string {
    return GROUP_NAMES[group]?.[locale] ?? group;
}

export default MESSAGES;
