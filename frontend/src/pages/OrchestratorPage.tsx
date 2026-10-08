import React from 'react';
import TestOrchestrator from '../components/TestOrchestrator';
import { useAgentStore, useAppStore, useAISettingsStore, useExecutionStore } from '../stores';
import { useNavigate } from 'react-router-dom';
import { Plus, X, Monitor, MonitorSmartphone } from '../components/icons';

const OrchestratorPage: React.FC = () => {
    const { updateAgentStatus, incrementAgentTasks } = useAgentStore();
    const { enableVision, setEnableVision, useMultiAgent, setUseMultiAgent, setShowSettings } = useAppStore();
    const { aiSettings } = useAISettingsStore();
    const navigate = useNavigate();

    // Read the session list from the global store to persist across pages.
    const { sessions, activeSessionId, addSession, removeSession, setActiveSession } = useExecutionStore();

    // Initialize activeSessionId on the first render.
    React.useEffect(() => {
        if (!activeSessionId && sessions.length > 0) {
            setActiveSession(sessions[0].id);
        }
    }, [activeSessionId, sessions, setActiveSession]);

    const handleAddSession = (mode: 'chromium' | 'real') => {
        addSession(mode);
    };

    const handleRemoveSession = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        removeSession(id);
    };

    return (
        <div className="flex flex-col h-full">
            {/* Session Tabs */}
            <div className="flex items-center gap-2 mb-4 bg-white dark:bg-slate-800 p-2 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-x-auto">
                {sessions.map(s => (
                    <div
                        key={s.id}
                        onClick={() => setActiveSession(s.id)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg cursor-pointer transition-colors whitespace-nowrap min-w-[120px] ${activeSessionId === s.id
                            ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-medium'
                            : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 text-slate-600 dark:text-slate-400'
                            }`}
                    >
                        {s.mode === 'real' ? <MonitorSmartphone size={16} /> : <Monitor size={16} />}
                        <span>{s.name}</span>
                        {sessions.length > 1 && (
                            <button
                                onClick={(e) => handleRemoveSession(s.id, e)}
                                className="ml-auto text-slate-400 hover:text-red-500 p-1 rounded-md hover:bg-slate-200 dark:hover:bg-slate-700"
                            >
                                <X size={14} />
                            </button>
                        )}
                    </div>
                ))}

                <div className="flex items-center gap-2 ml-2 pl-2 border-l border-slate-200 dark:border-slate-700">
                    <button
                        onClick={() => handleAddSession('chromium')}
                        className="flex items-center gap-1 px-3 py-2 text-sm text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 dark:text-slate-400 dark:hover:bg-slate-700/50 rounded-lg transition-colors whitespace-nowrap"
                        title={"New sandbox test"}
                    >
                        <Plus size={16} /> Sandbox instance
                    </button>
                    <button
                        onClick={() => handleAddSession('real')}
                        className="flex items-center gap-1 px-3 py-2 text-sm text-amber-600 hover:bg-amber-50 dark:text-amber-500 dark:hover:bg-amber-500/10 rounded-lg transition-colors whitespace-nowrap"
                        title={"Connect to Chrome running on this computer for testing (port 9222)"}
                    >
                        <MonitorSmartphone size={16} /> Local instance
                    </button>
                </div>
            </div>

            {/* Test Orchestrators (Hidden if not active to preserve state) */}
            <div className="flex-1 relative min-h-0">
                {sessions.map(session => (
                    <div
                        key={session.id}
                        style={{ display: session.id === activeSessionId ? 'block' : 'none', height: '100%' }}
                    >
                        <TestOrchestrator
                            sessionId={session.id}
                            browserMode={session.mode}
                            updateAgentStatus={updateAgentStatus}
                            incrementAgentTasks={incrementAgentTasks}
                            enableVision={enableVision}
                            setEnableVision={setEnableVision}
                            useMultiAgent={useMultiAgent}
                            setUseMultiAgent={setUseMultiAgent}
                            onShowHistory={() => navigate('/history')}
                            aiSettings={aiSettings}
                            onOpenSettings={() => setShowSettings(true)}
                        />
                    </div>
                ))}
            </div>
        </div>
    );
};

export default OrchestratorPage;
