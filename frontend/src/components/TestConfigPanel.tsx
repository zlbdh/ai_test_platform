import React, { useState } from 'react';
import { BrainCircuit, Link, Loader2, Eye, Bookmark, ChevronDown, Settings2 } from './icons';
import type { AISettings } from '../types';
import { RESOURCE_PACK_MODEL } from '../config/aiModelConfig';

interface TestConfigPanelProps {
    requirement: string;
    setRequirement: (val: string) => void;
    targetUrl: string;
    setTargetUrl: (val: string) => void;
    probeMode: boolean;
    setProbeMode: (val: boolean) => void;
    useMultiAgent: boolean;
    setUseMultiAgent: (val: boolean) => void;
    aiSettings: AISettings;
    isPlanning: boolean;
    isExecuting: boolean;
    onGeneratePlan: () => void;
    onQuickDiagnose?: () => void;
    onOpenSettings?: () => void;
}

const TestConfigPanel: React.FC<TestConfigPanelProps> = ({
    requirement, setRequirement, targetUrl, setTargetUrl,
    probeMode, setProbeMode, useMultiAgent, setUseMultiAgent, aiSettings,
    isPlanning, isExecuting, onGeneratePlan, onQuickDiagnose, onOpenSettings
}) => {
    const extractUrl = () => {
        const urlMatch = requirement.match(/(https?:\/\/[a-zA-Z0-9\-._~:/?#[\]@!$&'*+,;=%]+)/);
        if (urlMatch) {
            const cleaned = urlMatch[0].replace(/[)}\]，。、；]+$/, '');
            setTargetUrl(cleaned);
        } else {
            alert("No valid URL was found in the requirements.");
        }
    };

    const [showTemplates, setShowTemplates] = useState(false);

    const TEMPLATES = [
        { name: "Login flow", prompt: "Test login: sign in with valid credentials and verify the redirect; check incorrect-password feedback and empty-field validation; test password visibility." },
        { name: "Form validation", prompt: "Test form validation: required-field errors, email and phone formats, password strength feedback, and successful submission feedback." },
        { name: "Shopping flow", prompt: "Test the shopping flow: browse and search products, add items to the cart, change quantities, enter a shipping address, choose a payment method, and submit the order." },
        { name: "Search", prompt: "Test search: keyword matching and result relevance, empty searches, special characters, pagination, and sorting." },
        { name: "User registration", prompt: "Test registration: complete the form, check duplicate email handling and matching passwords, accept the terms, and verify the successful registration and email verification prompt." },
        { name: "Page navigation", prompt: "Test navigation: clickable navigation links, correct destinations, breadcrumbs, browser back/forward buttons, and 404 handling." },
    ];

    return (
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 p-6 backdrop-blur-md">
            {/* Header: Title + Controls */}
            <div className="mb-4 space-y-3">
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <BrainCircuit className="w-5 h-5 text-indigo-400" />
                        Test configuration
                    </h2>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={onQuickDiagnose}
                            disabled={isPlanning || isExecuting || !targetUrl}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 text-xs font-medium hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors whitespace-nowrap disabled:opacity-50"
                        >
                            <Eye className="w-3 h-3" />
                            Quick diagnostics
                        </button>
                        <button
                            onClick={extractUrl}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 text-xs font-medium hover:bg-indigo-100 dark:hover:bg-indigo-900/30 transition-colors whitespace-nowrap"
                        >
                            <Link className="w-3 h-3" />
                            Extract URL
                        </button>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Model Configuration Button */}
                    <button
                        type="button"
                        onClick={onOpenSettings}
                        disabled={isPlanning || isExecuting}
                            className={`flex-1 flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg text-xs border shadow-sm transition-all focus-within:ring-1 focus-within:ring-indigo-500
                            ${isPlanning || isExecuting ? 'opacity-50 cursor-not-allowed bg-slate-100/50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700' : 'cursor-pointer bg-slate-100 dark:bg-slate-700/50 border-slate-200 dark:border-slate-600 hover:border-indigo-300 dark:hover:border-indigo-500 hover:bg-white dark:hover:bg-slate-800'}
                        `}
                        title={"Configure the system's core models"}
                    >
                        <div className="flex items-center gap-2 overflow-hidden">
                            <span className="font-bold text-slate-500 text-[10px] uppercase shrink-0">Current model</span>
                            <span className="font-mono text-indigo-600 dark:text-indigo-400 font-semibold truncate" title={aiSettings.modelName || RESOURCE_PACK_MODEL}>
                                {aiSettings.modelName || RESOURCE_PACK_MODEL}
                            </span>
                        </div>
                        <Settings2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    </button>

                    {/* Multi-Agent Toggle */}
                    <label className="flex items-center gap-2 cursor-pointer bg-slate-100 dark:bg-slate-700/50 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 transition-all hover:bg-slate-200 dark:hover:bg-slate-600 shrink-0 shadow-sm">
                        <span className="text-xs font-medium text-slate-600 dark:text-slate-300 select-none">Multi-agent collaboration</span>
                        <div className="relative">
                            <input
                                type="checkbox"
                                className="peer sr-only"
                                checked={useMultiAgent}
                                onChange={(e) => setUseMultiAgent(e.target.checked)}
                            />
                            <div className="w-8 h-4 bg-slate-300 dark:bg-slate-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-600"></div>
                        </div>
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer bg-emerald-50 dark:bg-emerald-900/20 px-3 py-1.5 rounded-lg border border-emerald-200 dark:border-emerald-700 transition-all hover:bg-emerald-100 dark:hover:bg-emerald-900/30 shrink-0 shadow-sm">
                        <span className="text-xs font-medium text-emerald-700 dark:text-emerald-300 select-none">Read-only probe</span>
                        <div className="relative">
                            <input
                                type="checkbox"
                                className="peer sr-only"
                                checked={probeMode}
                                onChange={(e) => setProbeMode(e.target.checked)}
                            />
                            <div className="w-8 h-4 bg-emerald-200 dark:bg-emerald-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-emerald-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all dark:border-emerald-700 peer-checked:bg-emerald-600"></div>
                        </div>
                    </label>
                </div>
            </div>

            <div className="space-y-4">
                {/* Test Templates */}
                <div>
                    <button
                        onClick={() => setShowTemplates(!showTemplates)}
                        className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-indigo-500 font-medium mb-2 transition-colors"
                    >
                        <Bookmark className="w-3 h-3" />
                        Test templates
                        <ChevronDown className={`w-3 h-3 transition-transform ${showTemplates ? 'rotate-180' : ''}`} />
                    </button>
                    {showTemplates && (
                        <div className="grid grid-cols-2 gap-1.5 mb-3 animate-in slide-in-from-top-2 duration-200">
                            {TEMPLATES.map(t => (
                                <button
                                    key={t.name}
                                    onClick={() => { setRequirement(t.prompt); setShowTemplates(false); }}
                                    disabled={isPlanning || isExecuting}
                                    className="text-left px-2.5 py-2 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-all disabled:opacity-50 truncate"
                                    title={t.prompt}
                                >
                                    {t.name}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Prompt Input */}
                <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 font-medium mb-1.5 block ml-1">Test requirements (prompt)</label>
                    <textarea
                        className="w-full h-24 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-3 text-sm text-slate-900 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none placeholder-slate-400 dark:placeholder-slate-500 custom-scrollbar"
                        placeholder={"Example: Sign in and check the account page..."}
                        value={requirement}
                        onChange={(e) => setRequirement(e.target.value)}
                        disabled={isPlanning || isExecuting}
                    />
                </div>

                {/* Target URL Input */}
                <div>
                    <label className="text-xs text-slate-600 dark:text-slate-400 font-medium mb-1.5 block ml-1">Target website URL (optional)</label>
                    <input
                        type="text"
                        className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-slate-200 focus:ring-2 focus:ring-indigo-500 focus:outline-none placeholder-slate-400 dark:placeholder-slate-500"
                        placeholder="https://example.com"
                        value={targetUrl}
                        onChange={(e) => setTargetUrl(e.target.value)}
                    />
                </div>

                {probeMode && (
                    <div className="rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/80 dark:bg-emerald-950/30 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
                        Read-only probe enabled: the platform checks page accessibility and initial viewport visibility only. It will not attempt to sign in, enter data, submit forms, or write data.
                    </div>
                )}

                <div className="pt-4">
                    <button
                        onClick={onGeneratePlan}
                        disabled={isPlanning || isExecuting || !requirement}
                        className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white py-2.5 px-6 rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]"
                    >
                        {isPlanning ? <Loader2 className="animate-spin w-4 h-4" /> : <BrainCircuit className="w-4 h-4" />}
                        Generate test plan
                    </button>
                </div>
            </div>
        </div>
    );
};

export default TestConfigPanel;
