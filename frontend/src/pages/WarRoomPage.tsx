import React, { useState, useEffect, useCallback } from 'react';
import {
    Swords, RefreshCcw, Zap, Shield, Database, Eye, Gauge,
    CheckCircle2, XCircle, Clock, Brain, Sparkles,
    ChevronRight,
} from '../components/icons';
import {
    commanderHealth, commanderProfiles, commanderMissions,
    type AgentHealth, type AgentProfile, type MissionResult,
} from '../services/commanderService';
import { API_BASE_URL } from '../config';

// Types

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

// Constants

const TYPE_ICON: Record<string, React.ReactNode> = {
    ui_e2e: <Eye className="w-3.5 h-3.5" />,
    security: <Shield className="w-3.5 h-3.5" />,
    performance: <Gauge className="w-3.5 h-3.5" />,
    database: <Database className="w-3.5 h-3.5" />,
    api_rest: <Zap className="w-3.5 h-3.5" />,
};

// Main page

const WarRoomPage: React.FC = () => {
    const [agents, setAgents] = useState<AgentHealth[]>([]);
    const [profiles, setProfiles] = useState<AgentProfile[]>([]);
    const [skills, setSkills] = useState<SkillSummary[]>([]);
    const [missions, setMissions] = useState<MissionResult[]>([]);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        setLoading(true);
        try {
            const [h, p, m, s] = await Promise.all([
                commanderHealth(),
                commanderProfiles(),
                commanderMissions(5),
                fetch(`${API_BASE_URL}/api/commander/skills`).then(r => r.json()),
            ]);
            setAgents(h.agents);
            setProfiles(p.profiles);
            setMissions(m);
            setSkills(s.skills || []);
        } catch { /* ignore */ }
        setLoading(false);
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void refresh();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [refresh]);

    const onlineCount = agents.filter(a => a.healthy).length;
    const squadProfiles = profiles.filter(p => p.role === 'squad');
    const commanderProfile = profiles.find(p => p.role === 'commander');

    return (
        <div className="flex flex-col gap-6 h-full">
            {/* Hero Header */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-indigo-950 to-purple-950 p-6 text-white">
                <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImciIHdpZHRoPSIyMCIgaGVpZ2h0PSIyMCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjAuNSIgZmlsbD0icmdiYSgyNTUsMjU1LDI1NSwwLjA1KSIvPjwvcGF0dGVybj48L2RlZnM+PHJlY3QgZmlsbD0idXJsKCNnKSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIvPjwvc3ZnPg==')] opacity-50" />
                <div className="relative flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                            <Swords className="w-6 h-6" />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold">Agent war room</h1>
                            <p className="text-sm text-indigo-200">Live monitoring · Global overview · Intelligent scheduling</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-6 text-sm">
                            <div className="text-center">
                                <div className="text-2xl font-bold text-emerald-400">{onlineCount}</div>
                                <div className="text-xs text-slate-400">Online</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold text-indigo-400">{agents.length}</div>
                                <div className="text-xs text-slate-400">Total agents</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold text-purple-400">{skills.length}</div>
                                <div className="text-xs text-slate-400">Skill packages</div>
                            </div>
                        </div>
                        <button
                            onClick={refresh}
                            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
                        >
                            <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Commander + Squads Topology */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Commander Card */}
                {commanderProfile && (
                    <div className="bg-white dark:bg-slate-800 rounded-xl border border-amber-200 dark:border-amber-500/30 p-5 col-span-1">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center text-white shadow-lg shadow-amber-500/25">
                                <Swords className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-800 dark:text-slate-100">{commanderProfile.name}</h3>
                                <p className="text-xs text-slate-500">Commander · Global coordination</p>
                            </div>
                            <div className="ml-auto w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400 space-y-1">
                            <p>• Oversees {squadProfiles.length} testing squads</p>
                            <p>• Manages {agents.length} agents</p>
                            <p>• Equipped with {skills.length} skill packages</p>
                        </div>
                    </div>
                )}

                {/* Squad Grid */}
                <div className="col-span-1 lg:col-span-2 grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {squadProfiles.map(squad => {
                        const squadAgent = agents.find(a => a.name === squad.agent_id);
                        const squadSkills = skills.filter(s => s.target_squad === squad.agent_id);
                        return (
                            <div
                                key={squad.agent_id}
                                className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4 hover:border-indigo-300 dark:hover:border-indigo-500/50 transition-all hover:shadow-md"
                            >
                                <div className="flex items-center gap-2 mb-3">
                                    <div className={`w-2.5 h-2.5 rounded-full ${squadAgent?.healthy ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
                                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-200 truncate">
                                        {squad.name}
                                    </span>
                                </div>

                                {/* Supported types */}
                                <div className="flex flex-wrap gap-1 mb-2">
                                    {squad.supported_types.map(t => (
                                        <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-full">
                                            {TYPE_ICON[t] || <Zap className="w-3 h-3" />}
                                            {t.replace('_', ' ')}
                                        </span>
                                    ))}
                                </div>

                                {/* Members */}
                                {squad.members.length > 0 && (
                                    <div className="text-[10px] text-slate-400 dark:text-slate-500">
                                        👥 {squad.members.length} members
                                    </div>
                                )}

                                {/* Skills */}
                                {squadSkills.length > 0 && (
                                    <div className="text-[10px] text-purple-500 dark:text-purple-400 mt-1">
                                        🧰 {squadSkills.length} skill packages
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Skills Arsenal + Recent Missions */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Skills */}
                <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-purple-500" />
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Skill library</h3>
                        <span className="ml-auto px-2 py-0.5 text-xs bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400 rounded-full">{skills.length}</span>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                        {skills.map(skill => (
                            <div key={skill.skill_id} className="px-5 py-3 flex items-center gap-3 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500/10 to-pink-500/10 flex items-center justify-center">
                                    {TYPE_ICON[skill.test_type] || <Brain className="w-4 h-4 text-purple-500" />}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{skill.name}</p>
                                    <p className="text-[11px] text-slate-400 truncate">{skill.description}</p>
                                </div>
                                <div className="flex items-center gap-1.5 shrink-0">
                                    {skill.has_strategy && (
                                        <span className="px-1.5 py-0.5 text-[10px] bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded">Strategy ✓</span>
                                    )}
                                    <span className="px-1.5 py-0.5 text-[10px] bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded">
                                        {skill.test_type.replace('_', ' ')}
                                    </span>
                                </div>
                            </div>
                        ))}
                        {skills.length === 0 && (
                            <div className="px-5 py-8 text-center text-sm text-slate-400">No skill packages</div>
                        )}
                    </div>
                </div>

                {/* Recent Missions */}
                <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center gap-2">
                        <Clock className="w-4 h-4 text-slate-400" />
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Recent reports</h3>
                        <span className="ml-auto px-2 py-0.5 text-xs bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 rounded-full">{missions.length}</span>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                        {missions.map(m => {
                            const isOk = m.status === 'completed';
                            const isFailed = m.status === 'failed';
                            return (
                                <div key={m.mission_id} className="px-5 py-3 flex items-center gap-3">
                                    <div className={`shrink-0 ${isOk ? 'text-emerald-500' : isFailed ? 'text-red-500' : 'text-slate-400'}`}>
                                        {isOk ? <CheckCircle2 className="w-4 h-4" /> : isFailed ? <XCircle className="w-4 h-4" /> : <Clock className="w-4 h-4" />}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm text-slate-700 dark:text-slate-200 truncate">{m.user_input}</p>
                                        <p className="text-[11px] text-slate-400">
                                            #{m.mission_id} · {new Date(m.created_at).toLocaleString('en-US')}
                                            {m.test_results_count > 0 && ` · ${m.test_results_count} test tracks`}
                                        </p>
                                    </div>
                                    <ChevronRight className="w-4 h-4 text-slate-300" />
                                </div>
                            );
                        })}
                        {missions.length === 0 && (
                            <div className="px-5 py-8 text-center text-sm text-slate-400">No reports yet</div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default WarRoomPage;
