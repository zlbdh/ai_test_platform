import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Compass, Loader2, Shield, Sword, Swords, Wrench } from '../components/icons';
import LegionControlCenter from '../components/legion/LegionControlCenter';
import LegionExplorationCenter from '../components/legion/LegionExplorationCenter';
import CommanderPage from './CommanderPage';
import WarRoomPage from './WarRoomPage';
import SkillsPanel from './SkillsPanel';
import {
    clearControlAuthSession,
    fetchControlAuthProfile,
    getStoredControlAuthToken,
    loginControl,
    logoutControl,
    type ControlAuthProfile,
} from '../services/controlAuthService';
import { useLegionControlStore } from '../stores';

const TABS = [
    { id: 'command', label: '指挥台', icon: <Sword className="h-4 w-4" /> },
    { id: 'control', label: '控制中心', icon: <Shield className="h-4 w-4" /> },
    { id: 'exploration', label: '探索发现', icon: <Compass className="h-4 w-4" /> },
    { id: 'warroom', label: '作战室', icon: <Swords className="h-4 w-4" /> },
    { id: 'skills', label: '技能库', icon: <Wrench className="h-4 w-4" /> },
] as const;

type TabId = typeof TABS[number]['id'];

function isTabId(value: string | null): value is TabId {
    return TABS.some((item) => item.id === value);
}

const LegionPage: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const {
        setActiveTab,
        setSelectedAssessmentId,
        setSelectedFindingId,
        setSelectedRunId,
        setSelectedSessionId,
    } = useLegionControlStore();
    const [profile, setProfile] = useState<ControlAuthProfile | null>(null);
    const [authLoading, setAuthLoading] = useState(true);
    const [authError, setAuthError] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [loggingIn, setLoggingIn] = useState(false);

    const tabParam = searchParams.get('tab');
    const activeTab: TabId = isTabId(tabParam) ? tabParam : 'command';
    const selectedRunId = searchParams.get('run');
    const selectedSessionId = searchParams.get('session');
    const selectedAssessmentId = searchParams.get('assessment');
    const selectedFindingId = searchParams.get('finding');

    const updateParams = useCallback((patch: Partial<Record<'tab' | 'run' | 'session' | 'assessment' | 'finding', string | null>>) => {
        setSearchParams((current) => {
            const next = new URLSearchParams(current);
            Object.entries(patch).forEach(([key, value]) => {
                if (!value) {
                    next.delete(key);
                } else {
                    next.set(key, value);
                }
            });
            if (!next.get('tab')) {
                next.set('tab', activeTab);
            }
            return next;
        }, { replace: true });
    }, [activeTab, setSearchParams]);

    useEffect(() => {
        setActiveTab(activeTab);
        setSelectedRunId(selectedRunId);
        setSelectedSessionId(selectedSessionId);
        setSelectedAssessmentId(selectedAssessmentId);
        setSelectedFindingId(selectedFindingId);
    }, [
        activeTab,
        selectedAssessmentId,
        selectedFindingId,
        selectedRunId,
        selectedSessionId,
        setActiveTab,
        setSelectedAssessmentId,
        setSelectedFindingId,
        setSelectedRunId,
        setSelectedSessionId,
    ]);

    useEffect(() => {
        let cancelled = false;

        const restoreProfile = async () => {
            const storedToken = getStoredControlAuthToken();
            try {
                let nextProfile = await fetchControlAuthProfile(storedToken);
                if (!nextProfile && storedToken) {
                    clearControlAuthSession();
                    nextProfile = await fetchControlAuthProfile('');
                }
                if (cancelled) return;
                setProfile(nextProfile);
                setAuthError(nextProfile || !storedToken ? '' : '登录态已失效，请重新登录 Legion 控制中台。');
            } catch {
                if (cancelled) return;
                if (storedToken) {
                    clearControlAuthSession();
                }
                setProfile(null);
                setAuthError('认证状态校验失败，请稍后重试。');
            } finally {
                if (!cancelled) {
                    setAuthLoading(false);
                }
            }
        };

        void restoreProfile();
        return () => {
            cancelled = true;
        };
    }, []);

    const permissionsSummary = useMemo(
        () => profile?.permissions.join(' / ') || '未登录',
        [profile],
    );
    const hasPersistentSession = Boolean(profile?.token);
    const isDevBypassSession = Boolean(profile && !profile.token);

    const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setLoggingIn(true);
        setAuthError('');
        try {
            const nextProfile = await loginControl(username.trim(), password);
            setProfile(nextProfile);
            if (!searchParams.get('tab')) {
                updateParams({ tab: 'command' });
            }
        } catch (error) {
            setAuthError(error instanceof Error ? error.message : '登录失败');
        } finally {
            setLoggingIn(false);
        }
    };

    const handleLogout = async () => {
        await logoutControl();
        setProfile(null);
        setPassword('');
    };

    if (authLoading) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="inline-flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在恢复 Legion 控制中台登录态...
                </div>
            </div>
        );
    }

    if (!profile) {
        return (
            <div className="mx-auto flex h-full w-full max-w-xl items-center justify-center">
                <div className="w-full rounded-3xl border border-slate-200 bg-white p-8 shadow-xl dark:border-slate-800 dark:bg-slate-900">
                    <div className="text-2xl font-semibold text-slate-900 dark:text-white">Legion 控制中台</div>
                    <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">继续复用现有平台认证体系，登录后即可查看命令运行、探索发现和发布风险。</div>
                    {authError && (
                        <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-200">
                            {authError}
                        </div>
                    )}
                    <form onSubmit={handleLogin} className="mt-6 space-y-4">
                        <label className="block text-sm text-slate-600 dark:text-slate-300">
                            用户名
                            <input
                                value={username}
                                onChange={(event) => setUsername(event.target.value)}
                                className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-950"
                            />
                        </label>
                        <label className="block text-sm text-slate-600 dark:text-slate-300">
                            密码
                            <input
                                type="password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-950"
                            />
                        </label>
                        <button
                            type="submit"
                            disabled={loggingIn}
                            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                        >
                            {loggingIn ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
                            登录控制中台
                        </button>
                    </form>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-full flex-col gap-5">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <div className="text-sm uppercase tracking-[0.24em] text-slate-400">Legion</div>
                        <div className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">AI 指挥中台</div>
                        <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">Web 先成为统一事实来源，通知平台下一阶段直接复用同一套 command run / exploration / release risk 数据。</div>
                        {isDevBypassSession ? (
                            <div className="mt-3 inline-flex items-center rounded-full bg-cyan-100 px-3 py-1 text-xs font-medium text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300">
                                开发模式免登录
                            </div>
                        ) : null}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-300">
                        <div>当前用户：<span className="font-medium text-slate-900 dark:text-white">{profile.username}</span></div>
                        <div>角色：{profile.role}</div>
                        <div>访问方式：{isDevBypassSession ? '开发免登录' : '登录态认证'}</div>
                        <div>项目范围：{profile.project_ids.length ? profile.project_ids.join(', ') : '全部项目'}</div>
                        <div className="mt-1 text-xs text-slate-400">权限：{permissionsSummary}</div>
                    </div>
                </div>
                <div className="mt-5 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-950/60">
                    {TABS.map((tab) => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                type="button"
                                onClick={() => updateParams({ tab: tab.id })}
                                className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition ${isActive
                                    ? 'bg-slate-900 text-white shadow-sm dark:bg-white dark:text-slate-900'
                                    : 'text-slate-500 hover:bg-white hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'
                                }`}
                            >
                                {tab.icon}
                                {tab.label}
                            </button>
                        );
                    })}
                    {hasPersistentSession ? (
                        <div className="ml-auto">
                            <button
                                type="button"
                                onClick={() => void handleLogout()}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-white dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                                退出登录
                            </button>
                        </div>
                    ) : null}
                </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
                {activeTab === 'command' && <CommanderPage />}
                {activeTab === 'control' && (
                    <LegionControlCenter
                        profile={profile}
                        selectedRunId={selectedRunId}
                        selectedSessionId={selectedSessionId}
                        selectedAssessmentId={selectedAssessmentId}
                        selectedFindingId={selectedFindingId}
                        onSelectRun={(runId) => updateParams({ run: runId })}
                        onSelectSession={(sessionId) => updateParams({ session: sessionId })}
                        onSelectAssessment={(assessmentId) => updateParams({ assessment: assessmentId })}
                        onUpdateSelection={({ tab, runId, sessionId, assessmentId, findingId }) => updateParams({
                            ...(tab !== undefined ? { tab } : {}),
                            ...(runId !== undefined ? { run: runId } : {}),
                            ...(sessionId !== undefined ? { session: sessionId } : {}),
                            ...(assessmentId !== undefined ? { assessment: assessmentId } : {}),
                            ...(findingId !== undefined ? { finding: findingId } : {}),
                        })}
                    />
                )}
                {activeTab === 'exploration' && (
                    <LegionExplorationCenter
                        profile={profile}
                        selectedSessionId={selectedSessionId}
                        selectedFindingId={selectedFindingId}
                        onSelectSession={(sessionId) => updateParams({ session: sessionId })}
                        onSelectFinding={(findingId) => updateParams({ finding: findingId })}
                        onSelectRun={(runId) => updateParams({ run: runId })}
                        onSelectRunAndSession={({ runId, sessionId, findingId }) => updateParams({
                            run: runId,
                            session: sessionId,
                            ...(findingId !== undefined ? { finding: findingId } : {}),
                        })}
                        onUpdateSelection={({ tab, runId, sessionId, assessmentId, findingId }) => updateParams({
                            ...(tab !== undefined ? { tab } : {}),
                            ...(runId !== undefined ? { run: runId } : {}),
                            ...(sessionId !== undefined ? { session: sessionId } : {}),
                            ...(assessmentId !== undefined ? { assessment: assessmentId } : {}),
                            ...(findingId !== undefined ? { finding: findingId } : {}),
                        })}
                    />
                )}
                {activeTab === 'warroom' && <WarRoomPage />}
                {activeTab === 'skills' && <SkillsPanel />}
            </div>
        </div>
    );
};

export default LegionPage;
