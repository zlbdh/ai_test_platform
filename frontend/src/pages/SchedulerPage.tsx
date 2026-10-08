import { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../config';
import {
    Clock, Plus, Trash2, Play, Pause, Loader2, X, RefreshCw, Calendar,
} from '../components/icons';

interface Task {
    id: string;
    name: string;
    cron: string;
    task_type: string;
    enabled: boolean;
    last_run: string | null;
    next_run: string;
    status: string;
}

const CRON_PRESETS = [
    { label: "Daily at 8:00 AM", cron: '0 8 * * *' },
    { label: "Daily at 8:00 PM", cron: '0 20 * * *' },
    { label: "Hourly", cron: '0 * * * *' },
    { label: "Every Monday at 9:00 AM", cron: '0 9 * * 1' },
];

export default function SchedulerPage() {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [showAdd, setShowAdd] = useState(false);
    const [name, setName] = useState('');
    const [cron, setCron] = useState('0 8 * * *');
    const [taskType, setTaskType] = useState('exploratory');
    const [triggering, setTriggering] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/scheduler/tasks`);
            const data = await res.json();
            setTasks(data.tasks || []);
        } catch { /* ignore */ }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void load();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    const handleAdd = async () => {
        if (!name.trim()) return;
        await fetch(`${API_BASE_URL}/api/scheduler/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, cron, task_type: taskType }),
        });
        setShowAdd(false);
        setName('');
        load();
    };

    const handleDelete = async (id: string) => {
        await fetch(`${API_BASE_URL}/api/scheduler/tasks/${id}`, { method: 'DELETE' });
        load();
    };

    const handleToggle = async (id: string) => {
        await fetch(`${API_BASE_URL}/api/scheduler/tasks/${id}/toggle`, { method: 'POST' });
        load();
    };

    const handleRunNow = async (id: string) => {
        setTriggering(id);
        await fetch(`${API_BASE_URL}/api/scheduler/tasks/${id}/run-now`, { method: 'POST' });
        await load();
        setTriggering(null);
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-gradient-to-br from-teal-500 to-cyan-500 text-white">
                            <Calendar className="w-5 h-5" />
                        </div>
                        Scheduled tasks
                    </h2>
                    <p className="text-slate-500 mt-2 text-sm">Configure test plans to run on a cron schedule</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={load} className="p-2.5 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-indigo-500 transition-colors">
                        <RefreshCw className="w-4 h-4" />
                    </button>
                    <button onClick={() => setShowAdd(true)}
                        className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl text-sm font-medium shadow-lg shadow-teal-500/25 transition-all hover:shadow-xl">
                        <Plus className="w-4 h-4" /> New task
                    </button>
                </div>
            </div>

            {/* Task List */}
            <div className="bg-white/80 dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/60 backdrop-blur-sm overflow-hidden card-hover-lift">
                {tasks.length === 0 ? (
                    <div className="py-20 text-center">
                        <Clock className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                        <p className="text-slate-400 text-sm">No scheduled tasks</p>
                        <p className="text-slate-400 text-xs mt-1">Tasks run automatically according to their cron expressions</p>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                        {tasks.map(t => (
                            <div key={t.id} className={`flex items-center gap-4 px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors ${!t.enabled ? 'opacity-50' : ''}`}>
                                <div className="w-10 h-10 rounded-xl bg-teal-50 dark:bg-teal-500/10 text-teal-500 flex items-center justify-center shrink-0">
                                    <Clock className="w-5 h-5" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{t.name}</p>
                                    <div className="flex gap-3 mt-0.5 text-xs text-slate-400">
                                        <span className="font-mono bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded">{t.cron}</span>
                                        <span>Type: {t.task_type}</span>
                                        {t.next_run && <span>Next: {new Date(t.next_run).toLocaleString('en-US')}</span>}
                                    </div>
                                </div>
                                <div className="flex gap-1 shrink-0">
                                    <button onClick={() => handleToggle(t.id)}
                                        className={`p-2 rounded-lg transition-colors ${t.enabled ? 'text-emerald-500 hover:bg-emerald-50' : 'text-slate-400 hover:bg-slate-100'}`}
                                        title={t.enabled ? "Disable" : "Enable"}>
                                        {t.enabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                                    </button>
                                    <button onClick={() => handleRunNow(t.id)} disabled={triggering === t.id}
                                        className="p-2 rounded-lg text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors" title={"Run now"}>
                                        {triggering === t.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                                    </button>
                                    <button onClick={() => handleDelete(t.id)}
                                        className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors" title={"Delete"}>
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Add Modal */}
            {showAdd && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-300">
                    <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/50 border border-slate-200/80 dark:border-slate-700/80 w-full max-w-md p-6 relative animate-in zoom-in-95 duration-300">
                        <button onClick={() => setShowAdd(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-600">
                            <X className="w-5 h-5" />
                        </button>
                        <h3 className="text-lg font-bold text-slate-800 dark:text-white mb-4 flex items-center gap-2">
                            <Calendar className="w-5 h-5 text-teal-500" /> New scheduled task
                        </h3>
                        <div className="space-y-3">
                            <div>
                                <label className="text-xs font-medium text-slate-500">Task name</label>
                                <input type="text" value={name} onChange={e => setName(e.target.value)}
                                    placeholder={"Example: Daily regression tests"} className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm outline-none" />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-500">Task type</label>
                                <select value={taskType} onChange={e => setTaskType(e.target.value)}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm outline-none">
                                    <option value="exploratory">Exploratory testing</option>
                                    <option value="commander">Commander task</option>
                                    <option value="api">API testing</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-500">Cron expression</label>
                                <input type="text" value={cron} onChange={e => setCron(e.target.value)}
                                    className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 text-sm font-mono outline-none" />
                                <div className="flex gap-2 mt-2 flex-wrap">
                                    {CRON_PRESETS.map(p => (
                                        <button key={p.cron} onClick={() => setCron(p.cron)}
                                            className={`px-2 py-1 text-xs rounded-lg border transition-colors ${cron === p.cron ? 'bg-teal-50 border-teal-300 text-teal-600' : 'border-slate-200 text-slate-500 hover:border-teal-300'}`}>
                                            {p.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <button onClick={handleAdd} disabled={!name.trim()}
                                className="w-full mt-2 px-4 py-2.5 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl text-sm font-medium disabled:opacity-50 transition-all">
                                Create task
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
