import React, { useState, useEffect, useCallback } from 'react';
import {
    Wrench, Shield, Eye, Gauge, Database, Zap, Brain,
    ChevronDown, ChevronUp, CheckCircle2, BookOpen,
    Target,
} from '../components/icons';
import { API_BASE_URL } from '../config';

// ── 类型 ────────────────────────────────────────────────────

interface SkillSummary {
    skill_id: string;
    name: string;
    description: string;
    test_type: string;
    target_squad: string;
    tags: string[];
    has_strategy: boolean;
    examples_count: number;
}

interface SkillDetail extends SkillSummary {
    preconditions: string[];
    strategy_text: string;
    prompt_preview: string;
}

const TYPE_ICON: Record<string, React.ReactNode> = {
    ui_e2e: <Eye className="w-4 h-4" />,
    security: <Shield className="w-4 h-4" />,
    performance: <Gauge className="w-4 h-4" />,
    database: <Database className="w-4 h-4" />,
    api_rest: <Zap className="w-4 h-4" />,
};

const TYPE_COLOR: Record<string, string> = {
    ui_e2e: 'from-blue-500/10 to-cyan-500/10 text-blue-600 dark:text-blue-400',
    security: 'from-red-500/10 to-orange-500/10 text-red-600 dark:text-red-400',
    performance: 'from-green-500/10 to-emerald-500/10 text-green-600 dark:text-green-400',
    database: 'from-purple-500/10 to-indigo-500/10 text-purple-600 dark:text-purple-400',
    api_rest: 'from-amber-500/10 to-yellow-500/10 text-amber-600 dark:text-amber-400',
};

// ── 主组件 ──────────────────────────────────────────────────

const SkillsPanel: React.FC = () => {
    const [skills, setSkills] = useState<SkillSummary[]>([]);
    const [expanded, setExpanded] = useState<string | null>(null);
    const [detail, setDetail] = useState<SkillDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const fetchSkills = useCallback(() => {
        setLoading(true);
        setError('');
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        fetch(`${API_BASE_URL}/api/commander/skills`, { signal: controller.signal })
            .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
            .then(d => setSkills(d.skills || []))
            .catch((e) => {
                if (e.name === 'AbortError') {
                    setError('后端服务连接超时，请确认服务已启动');
                } else {
                    setError(`获取技能列表失败: ${e.message}`);
                }
            })
            .finally(() => { clearTimeout(timer); setLoading(false); });
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(fetchSkills, 0);
        return () => window.clearTimeout(timer);
    }, [fetchSkills]);

    const toggleExpand = async (skillId: string) => {
        if (expanded === skillId) {
            setExpanded(null);
            setDetail(null);
            return;
        }
        setExpanded(skillId);
        try {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 8000);
            const resp = await fetch(`${API_BASE_URL}/api/commander/skills/${skillId}`, { signal: controller.signal });
            clearTimeout(timer);
            const data = await resp.json();
            setDetail(data);
        } catch {
            setDetail(null);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-64 gap-3">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
                <p className="text-sm text-slate-400">加载技能列表...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
                <div className="w-12 h-12 rounded-full bg-red-50 dark:bg-red-500/10 flex items-center justify-center">
                    <Wrench className="w-6 h-6 text-red-400" />
                </div>
                <p className="text-sm text-slate-500 dark:text-slate-400">{error}</p>
                <button onClick={fetchSkills}
                    className="px-4 py-2 rounded-lg bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium transition-colors">
                    重试
                </button>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white shadow-lg shadow-purple-500/25">
                        <Wrench className="w-5 h-5" />
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">技能武器库</h2>
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                            {skills.length} 个技能包已装备 · 点击展开查看测试策略
                        </p>
                    </div>
                </div>
            </div>

            {/* Skill Cards */}
            <div className="grid grid-cols-1 gap-3">
                {skills.map(skill => {
                    const isExpanded = expanded === skill.skill_id;
                    const colorClass = TYPE_COLOR[skill.test_type] || TYPE_COLOR.ui_e2e;

                    return (
                        <div
                            key={skill.skill_id}
                            className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden transition-all hover:shadow-md"
                        >
                            {/* Card Header */}
                            <div
                                onClick={() => toggleExpand(skill.skill_id)}
                                className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors"
                            >
                                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colorClass} flex items-center justify-center shrink-0`}>
                                    {TYPE_ICON[skill.test_type] || <Brain className="w-5 h-5" />}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{skill.name}</h3>
                                        {skill.has_strategy && (
                                            <span className="flex items-center gap-1 px-2 py-0.5 text-[10px] bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-full font-medium">
                                                <CheckCircle2 className="w-3 h-3" /> 策略就绪
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">{skill.description}</p>
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                    <span className="px-2.5 py-1 text-xs bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg">
                                        {skill.test_type.replace('_', ' ')}
                                    </span>
                                    <span className="px-2.5 py-1 text-xs bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-lg">
                                        → {skill.target_squad || '通用'}
                                    </span>
                                    <div className="text-slate-400">
                                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                    </div>
                                </div>
                            </div>

                            {/* Expanded Detail */}
                            {isExpanded && detail && detail.skill_id === skill.skill_id && (
                                <div className="px-5 py-4 border-t border-slate-100 dark:border-slate-700/50 bg-slate-50/50 dark:bg-slate-800/50">
                                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                                        {/* Tags + Preconditions */}
                                        <div className="space-y-3">
                                            {detail.tags && detail.tags.length > 0 && (
                                                <div>
                                                    <div className="text-xs font-medium text-slate-500 mb-1.5 flex items-center gap-1">
                                                        <Target className="w-3 h-3" /> 标签
                                                    </div>
                                                    <div className="flex flex-wrap gap-1">
                                                        {detail.tags.map(tag => (
                                                            <span key={tag} className="px-2 py-0.5 text-[10px] bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-full">
                                                                {tag}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                            {detail.preconditions && detail.preconditions.length > 0 && (
                                                <div>
                                                    <div className="text-xs font-medium text-slate-500 mb-1.5">📋 前置条件</div>
                                                    <ul className="space-y-1">
                                                        {detail.preconditions.map((p, i) => (
                                                            <li key={i} className="text-xs text-slate-600 dark:text-slate-400 flex items-start gap-1.5">
                                                                <span className="text-emerald-500 mt-0.5">•</span> {p}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </div>

                                        {/* Strategy Preview */}
                                        <div className="lg:col-span-2">
                                            <div className="text-xs font-medium text-slate-500 mb-1.5 flex items-center gap-1">
                                                <BookOpen className="w-3 h-3" /> 测试策略
                                            </div>
                                            <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-3 max-h-64 overflow-y-auto">
                                                <pre className="text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
                                                    {detail.strategy_text || '暂无策略文档'}
                                                </pre>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default SkillsPanel;
