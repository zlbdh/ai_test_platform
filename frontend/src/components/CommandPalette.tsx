/* CommandPalette: VS Code-style Ctrl+K navigation, actions, and fuzzy search.*/
import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Search, ArrowRight, Settings, Moon, Sun, Play, History,
    Layout, Zap, Database, Shield, Activity, FileText,
    Keyboard, Terminal
} from './icons';

interface Command {
    id: string;
    label: string;
    description?: string;
    icon: React.ReactNode;
    category: 'navigation' | 'action' | 'settings';
    shortcut?: string;
    action: () => void;
}

interface CommandPaletteProps {
    isOpen: boolean;
    onClose: () => void;
    onOpenSettings: () => void;
    onToggleTheme: () => void;
    isDark: boolean;
}

const CommandPalette: React.FC<CommandPaletteProps> = ({
    isOpen,
    onClose,
    onOpenSettings,
    onToggleTheme,
    isDark,
}) => {
    const [query, setQuery] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    // Command list
    const commands: Command[] = useMemo(() => [
        // Navigation commands
        { id: 'nav-home', label: "Dashboard", description: "Return home", icon: <Layout size={16} />, category: 'navigation', action: () => { navigate('/'); onClose(); } },
        { id: 'nav-orchestrator', label: "Test orchestration", description: "Generate and run tests", icon: <Play size={16} />, category: 'navigation', action: () => { navigate('/orchestrator'); onClose(); } },
        { id: 'nav-prototype-agents', label: "Prototype testing", description: "Seven-agent prototype acceptance workspace", icon: <Zap size={16} />, category: 'navigation', action: () => { navigate('/prototype-agents'); onClose(); } },
        { id: 'nav-history', label: "Execution center", description: "History and screenshots", icon: <History size={16} />, category: 'navigation', action: () => { navigate('/history'); onClose(); } },
        { id: 'nav-api', label: "API workbench", description: "REST and GraphQL testing", icon: <Terminal size={16} />, category: 'navigation', action: () => { navigate('/api'); onClose(); } },
        { id: 'nav-performance', label: "Performance testing", description: "Load and stress testing", icon: <Activity size={16} />, category: 'navigation', action: () => { navigate('/performance'); onClose(); } },
        { id: 'nav-security', label: "Security scanning", description: "Vulnerability detection", icon: <Shield size={16} />, category: 'navigation', action: () => { navigate('/security'); onClose(); } },
        { id: 'nav-database', label: "Database testing", description: "SQL query testing", icon: <Database size={16} />, category: 'navigation', action: () => { navigate('/database'); onClose(); } },
        { id: 'nav-quality', label: "Quality audit", description: "Code quality analysis", icon: <FileText size={16} />, category: 'navigation', action: () => { navigate('/quality'); onClose(); } },
        { id: 'nav-knowledge', label: "Knowledge base", description: "PRD and document management", icon: <FileText size={16} />, category: 'navigation', action: () => { navigate('/knowledge'); onClose(); } },
        { id: 'nav-batch', label: "Batch testing", description: "Batch execution", icon: <Zap size={16} />, category: 'navigation', action: () => { navigate('/batch'); onClose(); } },
        { id: 'nav-exploratory', label: "Exploratory testing", description: "Autonomous AI exploration", icon: <Zap size={16} />, category: 'navigation', action: () => { navigate('/exploratory'); onClose(); } },
        // Action commands
        { id: 'act-settings', label: "Open settings", description: "LLM configuration and connection parameters", icon: <Settings size={16} />, category: 'action', shortcut: 'Ctrl+.', action: () => { onOpenSettings(); onClose(); } },
        { id: 'act-theme', label: isDark ? "Switch to light theme" : "Switch to dark theme", description: "Change appearance", icon: isDark ? <Sun size={16} /> : <Moon size={16} />, category: 'action', action: () => { onToggleTheme(); onClose(); } },
        // Settings commands
        { id: 'set-shortcuts', label: "Keyboard shortcuts", description: "View all shortcuts", icon: <Keyboard size={16} />, category: 'settings', shortcut: '?', action: () => { /* TODO */ onClose(); } },
    ], [navigate, onClose, onOpenSettings, onToggleTheme, isDark]);

    // Fuzzy matching
    const filtered = useMemo(() => {
        if (!query.trim()) return commands;
        const q = query.toLowerCase();
        return commands.filter(
            cmd => cmd.label.toLowerCase().includes(q) || (cmd.description || '').toLowerCase().includes(q)
        );
    }, [query, commands]);

    // Group commands.
    const groups = useMemo(() => {
        const nav = filtered.filter(c => c.category === 'navigation');
        const act = filtered.filter(c => c.category === 'action');
        const set = filtered.filter(c => c.category === 'settings');
        const result: { label: string; items: Command[] }[] = [];
        if (nav.length) result.push({ label: "Page navigation", items: nav });
        if (act.length) result.push({ label: "Actions", items: act });
        if (set.length) result.push({ label: "Settings", items: set });
        return result;
    }, [filtered]);

    // Focus the search field automatically.
    useEffect(() => {
        if (isOpen) {
            setQuery('');
            setSelectedIndex(0);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [isOpen]);

    // Keyboard navigation
    useEffect(() => {
        if (!isOpen) return;

        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex(i => Math.min(i + 1, filtered.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex(i => Math.max(i - 1, 0));
            } else if (e.key === 'Enter') {
                e.preventDefault();
                filtered[selectedIndex]?.action();
            } else if (e.key === 'Escape') {
                onClose();
            }
        };

        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [isOpen, filtered, selectedIndex, onClose]);

    // Scroll the selected item into view.
    useEffect(() => {
        const el = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`);
        el?.scrollIntoView({ block: 'nearest' });
    }, [selectedIndex]);

    if (!isOpen) return null;

    let flatIndex = -1;

    return (
        <div className="fixed inset-0 z-[9999] flex items-start justify-center pt-[15vh]" onClick={onClose}>
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-md" />

            {/* Panel */}
            <div
                className="relative w-full max-w-lg rounded-xl border shadow-2xl overflow-hidden"
                style={{
                    background: 'var(--color-surface)',
                    borderColor: 'var(--color-border)',
                    animation: 'command-palette-in 0.15s ease-out',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Search Input */}
                <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
                    <Search size={18} className="text-slate-400 shrink-0" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0); }}
                        placeholder={"Search pages and actions..."}
                        className="flex-1 bg-transparent outline-none text-sm"
                        style={{ color: 'var(--color-text)' }}
                    />
                    <kbd className="text-[10px] px-1.5 py-0.5 rounded border font-mono" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
                        ESC
                    </kbd>
                </div>

                {/* Results */}
                <div ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
                    {groups.length === 0 ? (
                        <div className="py-8 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
                            No matching results
                        </div>
                    ) : (
                        groups.map((group) => (
                            <div key={group.label} className="mb-2">
                                <div className="px-2 py-1 text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                                    {group.label}
                                </div>
                                {group.items.map((cmd) => {
                                    flatIndex++;
                                    const idx = flatIndex;
                                    const isSelected = idx === selectedIndex;
                                    return (
                                        <button
                                            key={cmd.id}
                                            data-index={idx}
                                            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${isSelected ? 'bg-indigo-500/10' : 'hover:bg-slate-500/5'}`}
                                            style={{ color: isSelected ? 'var(--brand-primary)' : 'var(--color-text)' }}
                                            onClick={cmd.action}
                                            onMouseEnter={() => setSelectedIndex(idx)}
                                        >
                                            <span className="shrink-0 opacity-60">{cmd.icon}</span>
                                            <span className="flex-1 text-left">
                                                <span className="font-medium">{cmd.label}</span>
                                                {cmd.description && (
                                                    <span className="ml-2 opacity-50 text-xs">{cmd.description}</span>
                                                )}
                                            </span>
                                            {cmd.shortcut && (
                                                <kbd className="text-[10px] px-1.5 py-0.5 rounded border font-mono shrink-0" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
                                                    {cmd.shortcut}
                                                </kbd>
                                            )}
                                            <ArrowRight size={14} className="shrink-0 opacity-30" />
                                        </button>
                                    );
                                })}
                            </div>
                        ))
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center gap-4 px-4 py-2 border-t text-[11px]" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
                    <span>↑↓ Navigate</span>
                    <span>↵ Select</span>
                    <span>ESC Close</span>
                </div>
            </div>

            <style>{`
        @keyframes command-palette-in {
          0% { opacity: 0; transform: translateY(-10px) scale(0.98); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
        </div>
    );
};

export default CommandPalette;
