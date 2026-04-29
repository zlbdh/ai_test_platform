import {
    LayoutDashboard, FlaskConical, History, Gauge, ShieldCheck,
    Globe, Database, Table2, Eye, BookOpen, Swords, Settings,
    Brain, Sparkles, ShieldAlert, Bell, Calendar, Compass, Rocket
} from './icons';
import { type NavItemConfig } from './ui/NavItem';

// ============================================================================
// Navigation Config — 导出供 Layout + Breadcrumb 使用
// labelKey 用于 i18n 翻译；label 为中文默认值（当翻译缺失时回退）
// ============================================================================
export const NAV_ITEMS: NavItemConfig[] = [
    // 主入口
    { path: '/', label: '统一测试', labelKey: 'nav.frontdoor', icon: <Sparkles className="w-4 h-4" />, group: '主入口' },
    { path: '/history', label: '执行中心', labelKey: 'nav.history', icon: <History className="w-4 h-4" />, group: '主入口' },
    { path: '/quality-gate', label: '质量门禁', labelKey: 'nav.qualityGate', icon: <ShieldAlert className="w-4 h-4" />, group: '主入口' },
    // 专家入口（深挖）
    { path: '/orchestrator', label: '测试编排', labelKey: 'nav.orchestrator', icon: <FlaskConical className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/prototype-agents', label: '原型测试', labelKey: 'nav.prototypeAgents', icon: <Sparkles className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/exploratory', label: '探索性测试', labelKey: 'nav.exploratory', icon: <Compass className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/scenario', label: '场景链', labelKey: 'nav.scenario', icon: <Sparkles className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/visual', label: '视觉回归', labelKey: 'nav.visual', icon: <Eye className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/api-workbench', label: 'API 工作台', labelKey: 'nav.api', icon: <Globe className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/database', label: '数据库测试', labelKey: 'nav.database', icon: <Database className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/testdata', label: '测试数据', labelKey: 'nav.testdata', icon: <Table2 className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/performance', label: '性能测试', labelKey: 'nav.performance', icon: <Gauge className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/security', label: '安全扫描', labelKey: 'nav.security', icon: <ShieldCheck className="w-4 h-4" />, group: '专家入口（深挖）' },
    { path: '/evaluation', label: '评估中心', labelKey: 'nav.evaluation', icon: <Brain className="w-4 h-4" />, group: '专家入口（深挖）' },
    // 治理入口（后座）
    { path: '/legion', label: '军团中心', labelKey: 'nav.legion', icon: <Swords className="w-4 h-4" />, group: '治理入口（后座）' },
    { path: '/knowledge', label: '知识库', labelKey: 'nav.knowledge', icon: <BookOpen className="w-4 h-4" />, group: '治理入口（后座）' },
    { path: '/deploy', label: '项目部署', labelKey: 'nav.deploy', icon: <Rocket className="w-4 h-4" />, group: '治理入口（后座）' },
    { path: '/notifications', label: '通知配置', labelKey: 'nav.notifications', icon: <Bell className="w-4 h-4" />, group: '治理入口（后座）' },
    { path: '/scheduler', label: '定时任务', labelKey: 'nav.scheduler', icon: <Calendar className="w-4 h-4" />, group: '治理入口（后座）' },
    { path: '/dashboard', label: '平台概览', labelKey: 'nav.dashboard', icon: <LayoutDashboard className="w-4 h-4" />, group: '治理入口（后座）' },
    { path: '/settings', label: '更多工具', labelKey: 'nav.settings', icon: <Settings className="w-4 h-4" />, group: '治理入口（后座）' },
];
