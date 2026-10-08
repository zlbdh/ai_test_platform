import {
    LayoutDashboard, FlaskConical, History, Gauge, ShieldCheck,
    Globe, Database, Table2, Eye, BookOpen, Swords, Settings,
    Brain, Sparkles, ShieldAlert, Bell, Calendar, Compass, Rocket
} from './icons';
import { type NavItemConfig } from './ui/NavItem';

// ============================================================================
// Navigation configuration exported for Layout and Breadcrumb.
// labelKey selects an i18n translation; label is the English fallback.
// ============================================================================
export const NAV_ITEMS: NavItemConfig[] = [
    // Main entry
    { path: '/', label: "Unified testing", labelKey: 'nav.frontdoor', icon: <Sparkles className="w-4 h-4" />, group: "Main entry" },
    { path: '/history', label: "Execution center", labelKey: 'nav.history', icon: <History className="w-4 h-4" />, group: "Main entry" },
    { path: '/quality-gate', label: "Quality gate", labelKey: 'nav.qualityGate', icon: <ShieldAlert className="w-4 h-4" />, group: "Main entry" },
    // Expert tools
    { path: '/orchestrator', label: "Test orchestration", labelKey: 'nav.orchestrator', icon: <FlaskConical className="w-4 h-4" />, group: "Expert tools" },
    { path: '/prototype-agents', label: "Prototype testing", labelKey: 'nav.prototypeAgents', icon: <Sparkles className="w-4 h-4" />, group: "Expert tools" },
    { path: '/exploratory', label: "Exploratory testing", labelKey: 'nav.exploratory', icon: <Compass className="w-4 h-4" />, group: "Expert tools" },
    { path: '/scenario', label: "Scenario chains", labelKey: 'nav.scenario', icon: <Sparkles className="w-4 h-4" />, group: "Expert tools" },
    { path: '/visual', label: "Visual regression", labelKey: 'nav.visual', icon: <Eye className="w-4 h-4" />, group: "Expert tools" },
    { path: '/api-workbench', label: "API workbench", labelKey: 'nav.api', icon: <Globe className="w-4 h-4" />, group: "Expert tools" },
    { path: '/database', label: "Database testing", labelKey: 'nav.database', icon: <Database className="w-4 h-4" />, group: "Expert tools" },
    { path: '/testdata', label: "Test data", labelKey: 'nav.testdata', icon: <Table2 className="w-4 h-4" />, group: "Expert tools" },
    { path: '/performance', label: "Performance testing", labelKey: 'nav.performance', icon: <Gauge className="w-4 h-4" />, group: "Expert tools" },
    { path: '/security', label: "Security scanning", labelKey: 'nav.security', icon: <ShieldCheck className="w-4 h-4" />, group: "Expert tools" },
    { path: '/evaluation', label: "Evaluation center", labelKey: 'nav.evaluation', icon: <Brain className="w-4 h-4" />, group: "Expert tools" },
    // Governance tools
    { path: '/legion', label: "Agent hub", labelKey: 'nav.legion', icon: <Swords className="w-4 h-4" />, group: "Governance tools" },
    { path: '/knowledge', label: "Knowledge base", labelKey: 'nav.knowledge', icon: <BookOpen className="w-4 h-4" />, group: "Governance tools" },
    { path: '/deploy', label: "Project deployment", labelKey: 'nav.deploy', icon: <Rocket className="w-4 h-4" />, group: "Governance tools" },
    { path: '/notifications', label: "Notification settings", labelKey: 'nav.notifications', icon: <Bell className="w-4 h-4" />, group: "Governance tools" },
    { path: '/scheduler', label: "Scheduled tasks", labelKey: 'nav.scheduler', icon: <Calendar className="w-4 h-4" />, group: "Governance tools" },
    { path: '/dashboard', label: "Platform overview", labelKey: 'nav.dashboard', icon: <LayoutDashboard className="w-4 h-4" />, group: "Governance tools" },
    { path: '/settings', label: "More tools", labelKey: 'nav.settings', icon: <Settings className="w-4 h-4" />, group: "Governance tools" },
];
