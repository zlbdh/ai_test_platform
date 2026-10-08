import React, { useState } from 'react';
import {
    Plus, Trash2, Pencil, X, ChevronDown, Layers, Key,
} from '../icons';
import { type AddProjectPayload } from '../../services/deployService';

export interface RepoFormItem {
    label: string; repo_url: string; branch: string;
    install_cmd: string; start_cmd: string; port: number; tech_stack: string;
}
const emptyRepo = (): RepoFormItem => ({
    label: '', repo_url: '', branch: 'master',
    install_cmd: '', start_cmd: '', port: 0, tech_stack: '',
});

interface DialogProps {
    open: boolean;
    onClose: () => void;
    onSubmit: (data: AddProjectPayload) => void;
    initialName?: string;
    initialRepos?: RepoFormItem[];
    initialToken?: string;
    mode: 'add' | 'edit';
}

const buildInitialRepos = (initialRepos?: RepoFormItem[]) => (
    initialRepos && initialRepos.length > 0
        ? initialRepos.map(repo => ({ ...repo }))
        : [
            { ...emptyRepo(), label: "Frontend" },
            { ...emptyRepo(), label: "Backend" },
        ]
);

type ProjectDialogFormProps = Omit<DialogProps, 'open'>;

const ProjectDialogForm: React.FC<ProjectDialogFormProps> = ({ onClose, onSubmit, initialName, initialRepos, initialToken, mode }) => {
    const [name, setName] = useState(() => initialName || '');
    const [repos, setRepos] = useState<RepoFormItem[]>(() => buildInitialRepos(initialRepos));
    const [token, setToken] = useState(() => initialToken || '');

    const updateRepo = (idx: number, field: string, val: string | number) => {
        setRepos(prev => prev.map((r, i) => i === idx ? { ...r, [field]: val } : r));
    };
    const addRepoRow = () => setRepos(prev => [...prev, emptyRepo()]);
    const removeRepoRow = (idx: number) => setRepos(prev => prev.filter((_, i) => i !== idx));

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const validRepos = repos.filter(r => r.repo_url.trim());
        if (!name || validRepos.length === 0) return;
        onSubmit({ name, repos: validRepos, git_token: token || undefined });
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-300" onClick={onClose}>
            <div className="w-full max-w-2xl max-h-[85vh] rounded-2xl bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl shadow-2xl shadow-black/20 dark:shadow-black/50 border border-slate-200/80 dark:border-slate-700/80 overflow-hidden flex flex-col animate-in zoom-in-95 duration-300" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-gradient-to-r from-cyan-500/10 to-transparent shrink-0">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                        {mode === 'add' ? <Plus className="w-4 h-4 text-cyan-500" /> : <Pencil className="w-4 h-4 text-amber-500" />}
                        {mode === 'add' ? "Add project to test" : "Edit project"}
                    </h3>
                    <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"><X className="w-4 h-4" /></button>
                </div>

                <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
                    <div className="p-6 overflow-y-auto flex-1 space-y-5">
                        {/* Project Name */}
                        <div>
                            <label className="block text-[11px] font-semibold text-slate-500 mb-1.5">Project name *</label>
                            <input required value={name} onChange={e => setName(e.target.value)}
                                placeholder={"Example: Sample project management system"}
                                className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2.5 outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-400 transition-all" />
                        </div>

                        {/* Git Token */}
                        <div>
                            <label className="block text-[11px] font-semibold text-slate-500 mb-1.5 flex items-center gap-1">
                                <Key className="w-3 h-3" /> Git token {token ? <span className="text-emerald-500">(Configured)</span> : <span className="text-slate-400">(Optional)</span>}
                            </label>
                            <input type="password" value={token} onChange={e => setToken(e.target.value)}
                                placeholder={"Enter an access token for private repositories (Git, GitHub, or GitLab)"}
                                className="w-full text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2.5 outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-400 font-mono transition-all" />
                        </div>

                        {/* Repos */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className="text-[11px] font-semibold text-slate-500 flex items-center gap-1">
                                    <Layers className="w-3 h-3" /> Repositories (frontend, backend, or other)
                                </label>
                                <button type="button" onClick={addRepoRow}
                                    className="flex items-center gap-1 text-[10px] text-cyan-500 hover:text-cyan-600 font-medium">
                                    <Plus className="w-3 h-3" /> Add repository
                                </button>
                            </div>

                            <div className="space-y-3">
                                {repos.map((repo, idx) => (
                                    <div key={idx} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 p-4 space-y-3 relative group">
                                        {repos.length > 1 && (
                                            <button type="button" onClick={() => removeRepoRow(idx)}
                                                className="absolute top-2 right-2 p-1 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-50 dark:hover:bg-red-900/20 text-slate-400 hover:text-red-500 transition-all" title={"Remove"}>
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        )}
                                        <div className="grid grid-cols-[100px_1fr] gap-3">
                                            <div>
                                                <label className="block text-[10px] text-slate-400 mb-1">Label</label>
                                                <input value={repo.label} onChange={e => updateRepo(idx, 'label', e.target.value)}
                                                    placeholder={"Frontend"}
                                                    className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2.5 py-2 outline-none focus:ring-2 focus:ring-cyan-500/30 transition-all" />
                                            </div>
                                            <div>
                                                <label className="block text-[10px] text-slate-400 mb-1">Git repository URL *</label>
                                                <input value={repo.repo_url} onChange={e => updateRepo(idx, 'repo_url', e.target.value)}
                                                    placeholder="https://github.com/user/repo.git"
                                                    className="w-full text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2.5 py-2 outline-none focus:ring-2 focus:ring-cyan-500/30 font-mono transition-all" />
                                            </div>
                                        </div>

                                        <details className="group/adv">
                                            <summary className="flex items-center gap-1 text-[10px] text-slate-400 cursor-pointer hover:text-cyan-500">
                                                <ChevronDown className="w-2.5 h-2.5 transition-transform group-open/adv:rotate-180" />
                                                Advanced options
                                            </summary>
                                            <div className="mt-2 grid grid-cols-3 gap-2">
                                                <div>
                                                    <label className="block text-[10px] text-slate-400 mb-1">Branch</label>
                                                    <input value={repo.branch} onChange={e => updateRepo(idx, 'branch', e.target.value)}
                                                        placeholder="master"
                                                        className="w-full text-[11px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 outline-none transition-all" />
                                                </div>
                                                <div>
                                                    <label className="block text-[10px] text-slate-400 mb-1">Port</label>
                                                    <input type="number" value={repo.port || ''} onChange={e => updateRepo(idx, 'port', parseInt(e.target.value) || 0)}
                                                        placeholder={"Automatic"}
                                                        className="w-full text-[11px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 outline-none transition-all" />
                                                </div>
                                                <div>
                                                    <label className="block text-[10px] text-slate-400 mb-1">Technology stack</label>
                                                    <input value={repo.tech_stack} onChange={e => updateRepo(idx, 'tech_stack', e.target.value)}
                                                        placeholder={"Auto-detect"}
                                                        className="w-full text-[11px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 outline-none transition-all" />
                                                </div>
                                                <div>
                                                    <label className="block text-[10px] text-slate-400 mb-1">Install command</label>
                                                    <input value={repo.install_cmd} onChange={e => updateRepo(idx, 'install_cmd', e.target.value)}
                                                        placeholder={"Auto-detect"}
                                                        className="w-full text-[11px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 outline-none font-mono transition-all" />
                                                </div>
                                                <div className="col-span-2">
                                                    <label className="block text-[10px] text-slate-400 mb-1">Start command</label>
                                                    <input value={repo.start_cmd} onChange={e => updateRepo(idx, 'start_cmd', e.target.value)}
                                                        placeholder={"Auto-detect"}
                                                        className="w-full text-[11px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1.5 outline-none font-mono transition-all" />
                                                </div>
                                            </div>
                                        </details>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="rounded-lg bg-cyan-50 dark:bg-cyan-900/20 border border-cyan-200 dark:border-cyan-800 px-3 py-2 text-[11px] text-cyan-700 dark:text-cyan-300">
                            💡 Each repository only requires a <b>Git URL</b>. Its technology stack and commands are detected after cloning.<b>Git token</b>applies to all repositories in this project.
                        </div>
                    </div>

                    <div className="flex justify-end gap-2 px-6 py-4 border-t border-slate-100 dark:border-slate-800 shrink-0">
                        <button type="button" onClick={onClose}
                            className="px-4 py-2 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                            Cancel
                        </button>
                        <button type="submit"
                            className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 text-white text-xs font-semibold shadow-sm transition-all">
                            {mode === 'add' ? "Add project" : "Save changes"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

const ProjectDialog: React.FC<DialogProps> = ({ open, ...props }) => {
    if (!open) return null;

    const dialogKey = JSON.stringify({
        mode: props.mode,
        initialName: props.initialName || '',
        initialToken: props.initialToken || '',
        initialRepos: props.initialRepos || [],
    });

    return <ProjectDialogForm key={dialogKey} {...props} />;
};

export default ProjectDialog;
