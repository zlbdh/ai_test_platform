import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Layers, Webhook, FileSearch, FileCode2, Smartphone,
    ShieldAlert, ClipboardCheck, ChevronRight, Sparkles, Settings,
} from '../components/icons';
import PageHeader from '../components/ui/PageHeader';

// More tools

const TOOLS = [
    { path: '/batch', label: "Batch testing", desc: "Run multiple sets of test cases in batches", icon: <Layers className="w-5 h-5" /> },
    { path: '/semantic', label: "Semantic testing", desc: "Control the browser step by step using natural language", icon: <Sparkles className="w-5 h-5" /> },
    { path: '/cicd', label: "CI/CD integration", desc: "Connect Jenkins or GitHub Actions", icon: <Webhook className="w-5 h-5" /> },
    { path: '/requirement', label: "Requirements analysis", desc: "Generate test requirements from documents", icon: <FileSearch className="w-5 h-5" /> },
    { path: '/contract', label: "Contract testing", desc: "Verify API contract consistency", icon: <FileCode2 className="w-5 h-5" /> },
    { path: '/mobile', label: "Mobile testing", desc: "iOS / Android automation", icon: <Smartphone className="w-5 h-5" /> },
    { path: '/quality', label: "Quality audit", desc: "Analyze code quality and coverage", icon: <ClipboardCheck className="w-5 h-5" /> },
    { path: '/resilience', label: "Resilience testing", desc: "Chaos engineering and fault injection", icon: <ShieldAlert className="w-5 h-5" /> },
];

const SettingsPage: React.FC = () => {
    const navigate = useNavigate();

    return (
        <div className="flex flex-col gap-6">
            <PageHeader
                icon={<Settings className="w-5 h-5" />}
                title={"More tools"}
                description={"Use these specialized testing tools when needed"}
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
