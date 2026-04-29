import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Layers, Webhook, FileSearch, FileCode2, Smartphone,
    ShieldAlert, ClipboardCheck, ChevronRight, Sparkles, Settings,
} from '../components/icons';
import PageHeader from '../components/ui/PageHeader';

// ── 更多工具入口 ─────────────────────────────────────────────

const TOOLS = [
    { path: '/batch', label: '批量测试', desc: '批量执行多组测试用例', icon: <Layers className="w-5 h-5" /> },
    { path: '/semantic', label: '语义测试', desc: '自然语言逐步操控浏览器', icon: <Sparkles className="w-5 h-5" /> },
    { path: '/cicd', label: 'CI/CD 集成', desc: 'Jenkins / GitHub Actions 接入', icon: <Webhook className="w-5 h-5" /> },
    { path: '/requirement', label: '需求解析', desc: '从文档自动生成测试需求', icon: <FileSearch className="w-5 h-5" /> },
    { path: '/contract', label: '契约测试', desc: 'API 契约一致性验证', icon: <FileCode2 className="w-5 h-5" /> },
    { path: '/mobile', label: '移动端测试', desc: 'iOS / Android 自动化', icon: <Smartphone className="w-5 h-5" /> },
    { path: '/quality', label: '质量审计', desc: '代码质量与覆盖率分析', icon: <ClipboardCheck className="w-5 h-5" /> },
    { path: '/resilience', label: '韧性测试', desc: '混沌工程与故障注入', icon: <ShieldAlert className="w-5 h-5" /> },
];

const SettingsPage: React.FC = () => {
    const navigate = useNavigate();

    return (
        <div className="flex flex-col gap-6">
            <PageHeader
                icon={<Settings className="w-5 h-5" />}
                title="更多工具"
                description="这些是低频但有用的测试工具，按需使用"
                accent="slate"
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {TOOLS.map(tool => (
                    <button
                        key={tool.path}
                        onClick={() => navigate(tool.path)}
                        className="card-hover-lift flex items-center gap-4 p-4 bg-white/80 dark:bg-slate-800/60 backdrop-blur-sm rounded-xl border border-slate-200/60 dark:border-slate-700/60 hover:border-indigo-300 dark:hover:border-indigo-500/50 transition-all text-left group"
                    >
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-100 to-slate-50 dark:from-slate-700 dark:to-slate-800 flex items-center justify-center text-slate-500 dark:text-slate-400 group-hover:text-indigo-500 group-hover:bg-gradient-to-br group-hover:from-indigo-50 group-hover:to-indigo-100 dark:group-hover:from-indigo-500/10 dark:group-hover:to-indigo-500/5 transition-all duration-200 group-hover:scale-110 shrink-0">
                            {tool.icon}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{tool.label}</p>
                            <p className="text-xs text-slate-400 dark:text-slate-500 truncate">{tool.desc}</p>
                        </div>
                        <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-indigo-400 group-hover:translate-x-0.5 transition-all duration-200 shrink-0" />
                    </button>
                ))}
            </div>
        </div>
    );
};

export default SettingsPage;
