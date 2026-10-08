import React, { useEffect, useState } from 'react';
import { X, Save, Key, Database, Settings2, Trash2, ChevronDown, ChevronRight, Sliders, Bot } from './icons';
import { AIProvider, AISettings, AIBackendConfig } from '../types';
import { API_ENDPOINTS } from '../config';
import {
    RESOURCE_PACK_BASE_URL,
    RESOURCE_PACK_MODEL,
    RESOURCE_PACK_MODEL_LABEL,
    normalizeAISettings,
    normalizeBackendConfig,
} from '../config/aiModelConfig';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (settings: AISettings) => void;
    initialSettings: AISettings;
}

const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, onSave, initialSettings }) => {
    const [apiKey, setApiKey] = useState('');
    const [modelName, setModelName] = useState(RESOURCE_PACK_MODEL);
    const [baseUrl, setBaseUrl] = useState(RESOURCE_PACK_BASE_URL);
    const [visionModel, setVisionModel] = useState(RESOURCE_PACK_MODEL);
    const [plannerModel, setPlannerModel] = useState(RESOURCE_PACK_MODEL);
    const [executorModel, setExecutorModel] = useState(RESOURCE_PACK_MODEL);
    const [temperature, setTemperature] = useState(0);
    const [topP, setTopP] = useState(1);
    const [maxTokens, setMaxTokens] = useState(4096);
    const [isSaving, setIsSaving] = useState(false);
    const [saveError, setSaveError] = useState('');
    const [showAgentModels, setShowAgentModels] = useState(false);
    const [showLLMParams, setShowLLMParams] = useState(false);
    const [runtimeConfig, setRuntimeConfig] = useState<AIBackendConfig>(normalizeBackendConfig());

    const applyRuntimeConfig = (config?: Partial<AIBackendConfig>) => {
        const nextConfig = normalizeBackendConfig(config);
        setRuntimeConfig(nextConfig);
        setModelName(nextConfig.model);
        setBaseUrl(nextConfig.base_url);
        setVisionModel(nextConfig.vision_model || nextConfig.model);
        setPlannerModel(nextConfig.planner_model || nextConfig.model);
        setExecutorModel(nextConfig.executor_model || nextConfig.model);
        setTemperature(nextConfig.temperature ?? 0);
        setTopP(nextConfig.top_p ?? 1);
        setMaxTokens(nextConfig.max_tokens ?? 4096);
    };

    useEffect(() => {
        if (!isOpen) {
            return;
        }

        const normalizedSettings = normalizeAISettings(initialSettings);
        setApiKey('');
        setSaveError('');
        setModelName(normalizedSettings.modelName || RESOURCE_PACK_MODEL);
        setBaseUrl(normalizedSettings.baseUrl || RESOURCE_PACK_BASE_URL);
        setVisionModel(RESOURCE_PACK_MODEL);
        setPlannerModel(RESOURCE_PACK_MODEL);
        setExecutorModel(RESOURCE_PACK_MODEL);
        setTemperature(0);
        setTopP(1);
        setMaxTokens(4096);

        let cancelled = false;

        (async () => {
            try {
                const res = await fetch(API_ENDPOINTS.config.ai);
                const data = await res.json();
                if (!cancelled && data?.config) {
                    applyRuntimeConfig(data.config);
                }
            } catch {
                if (!cancelled) {
                    applyRuntimeConfig();
                }
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [isOpen, initialSettings]);

    const handleSave = async () => {
        setIsSaving(true);
        setSaveError('');

        try {
            const response = await fetch(API_ENDPOINTS.config.ai, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    provider: 'openai',
                    model: RESOURCE_PACK_MODEL,
                    vision_model: RESOURCE_PACK_MODEL,
                    api_key: apiKey.trim() || undefined,
                    base_url: RESOURCE_PACK_BASE_URL,
                    planner_model: RESOURCE_PACK_MODEL,
                    executor_model: RESOURCE_PACK_MODEL,
                    temperature,
                    top_p: topP,
                    max_tokens: maxTokens,
                }),
            });

            const data = await response.json().catch(() => null);
            if (!response.ok || data?.status === 'error' || !data?.config) {
                throw new Error(data?.message || "Failed to save configuration. Check the backend service and API key.");
            }

            const nextConfig = normalizeBackendConfig(data.config);
            applyRuntimeConfig(nextConfig);
            onSave(normalizeAISettings({
                provider: AIProvider.OPENAI,
                apiKey: '',
                modelName: nextConfig.model,
                baseUrl: nextConfig.base_url,
            }));
            onClose();
        } catch (error) {
            setSaveError(error instanceof Error ? error.message : "Failed to save configuration. Try again later.");
        } finally {
            setIsSaving(false);
        }
    };

    if (!isOpen) return null;

    const allowedModels = runtimeConfig.allowed_models?.length ? runtimeConfig.allowed_models : [RESOURCE_PACK_MODEL];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4 animate-in fade-in duration-300">
            <div className="w-full max-w-md bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/80 rounded-2xl shadow-2xl shadow-black/20 dark:shadow-black/50 overflow-hidden text-slate-900 dark:text-white transition-colors duration-200 animate-in zoom-in-95 duration-300">
                <div className="flex items-center justify-between p-4 border-b border-slate-200/80 dark:border-slate-700/60 bg-gradient-to-r from-slate-50/90 to-slate-100/80 dark:from-slate-800/50 dark:to-slate-800/30 rounded-t-2xl">
                    <div className="flex items-center gap-2">
                        <Settings2 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                        <h2 className="font-semibold text-lg">System model configuration</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-200/80 dark:hover:bg-slate-700/80 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-6 space-y-5">
                    <div className="rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                        <div className="font-semibold">{runtimeConfig.profile_name || "JieKou AI resource package"} Locked</div>
                        <div className="mt-1">
                            This environment is locked to <code className="px-1 py-0.5 rounded bg-amber-100/80 dark:bg-amber-500/20 font-mono">{RESOURCE_PACK_MODEL}</code>and cannot switch to another provider or a cash-billed model.
                        </div>
                    </div>

                    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/40 p-4 space-y-3">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <div className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Runtime configuration</div>
                                <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                                    <Database className="w-4 h-4 text-indigo-500" />
                                    {runtimeConfig.profile_name || "JieKou AI resource package"}
                                </div>
                                <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                                    The provider is fixed to <code className="font-mono">openai</code>, and the gateway is fixed to the JieKou AI OpenAI-compatible endpoint.
                                </div>
                            </div>
                            <div className="rounded-lg bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300 px-2 py-1 text-[10px] font-semibold">
                                {runtimeConfig.provider_locked !== false && runtimeConfig.model_locked !== false ? "Locked" : "Controlled"}
                            </div>
                        </div>

                        <div className="grid grid-cols-1 gap-2 text-[11px] text-slate-600 dark:text-slate-300">
                            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/60 px-3 py-2">
                                <div className="text-slate-400 dark:text-slate-500">Allowed models</div>
                                <div className="mt-1 font-mono break-all">{allowedModels.join(', ')}</div>
                            </div>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider flex justify-between items-center">
                            <span>Model ID</span>
                            <span className="text-[10px] text-emerald-600 dark:text-emerald-400">Resource package models only</span>
                        </label>
                        <input
                            type="text"
                            value={modelName}
                            readOnly
                            className="w-full bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-white focus:outline-none font-mono cursor-not-allowed"
                        />
                        <p className="text-[10px] text-slate-500">Display name: {RESOURCE_PACK_MODEL_LABEL}</p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">API Key</label>
                        <div className="relative">
                            <Key className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
                            <input
                                type="password"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500 transition-colors placeholder-slate-400 dark:placeholder-slate-600"
                                placeholder={runtimeConfig.api_key_masked || 'sk-...'}
                            />
                        </div>
                        <p className="text-[10px] text-slate-500">
                            Leave blank to keep the key saved on the backend. Plaintext API keys are no longer persisted in browser storage.
                        </p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider flex justify-between">
                            <span>API Base URL</span>
                            <span className="text-indigo-600 dark:text-indigo-400 text-[10px]">Locked</span>
                        </label>
                        <input
                            type="text"
                            value={baseUrl}
                            readOnly
                            className="w-full bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-900 dark:text-slate-300 focus:outline-none font-mono cursor-not-allowed"
                        />
                    </div>

                    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
                        <button
                            onClick={() => setShowAgentModels(!showAgentModels)}
                            className="w-full flex items-center justify-between p-3 text-left text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                        >
                            <span className="flex items-center gap-2"><Bot className="w-4 h-4" /> Multi-agent collaboration models</span>
                            {showAgentModels ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                        {showAgentModels && (
                            <div className="p-3 pt-0 space-y-3 border-t border-slate-200 dark:border-slate-700">
                                <p className="text-[10px] text-slate-500 dark:text-slate-500 mt-2">
                                    The current policy forces the primary, vision, Planner, and Executor models to use the same resource package model, preventing any step from switching independently.
                                </p>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Vision model</label>
                                    <input
                                        type="text"
                                        value={visionModel}
                                        readOnly
                                        className="w-full bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-900 dark:text-white font-mono cursor-not-allowed"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Planner model</label>
                                    <input
                                        type="text"
                                        value={plannerModel}
                                        readOnly
                                        className="w-full bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-900 dark:text-white font-mono cursor-not-allowed"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Executor model</label>
                                    <input
                                        type="text"
                                        value={executorModel}
                                        readOnly
                                        className="w-full bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-900 dark:text-white font-mono cursor-not-allowed"
                                    />
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
                        <button
                            onClick={() => setShowLLMParams(!showLLMParams)}
                            className="w-full flex items-center justify-between p-3 text-left text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                        >
                            <span className="flex items-center gap-2"><Sliders className="w-4 h-4" /> LLM parameter tuning</span>
                            {showLLMParams ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                        {showLLMParams && (
                            <div className="p-3 pt-0 space-y-4 border-t border-slate-200 dark:border-slate-700">
                                <p className="text-[10px] text-slate-500 dark:text-slate-500 mt-2">
                                    These parameters are saved to the backend runtime configuration and used in actual Claude Haiku 4.5 calls.
                                </p>
                                <div className="space-y-1">
                                    <div className="flex items-center justify-between">
                                        <label className="text-xs text-slate-500 dark:text-slate-400">Temperature</label>
                                        <span className="text-xs font-mono text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-1.5 py-0.5 rounded">{temperature.toFixed(2)}</span>
                                    </div>
                                    <input
                                        type="range"
                                        min="0"
                                        max="2"
                                        step="0.05"
                                        value={temperature}
                                        onChange={(e) => setTemperature(Number(e.target.value))}
                                        className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                                    />
                                    <div className="flex justify-between text-[9px] text-slate-400"><span>0 Precise</span><span>1 Balanced</span><span>2 Creative</span></div>
                                </div>
                                <div className="space-y-1">
                                    <div className="flex items-center justify-between">
                                        <label className="text-xs text-slate-500 dark:text-slate-400">Top P</label>
                                        <span className="text-xs font-mono text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-1.5 py-0.5 rounded">{topP.toFixed(2)}</span>
                                    </div>
                                    <input
                                        type="range"
                                        min="0.1"
                                        max="1"
                                        step="0.05"
                                        value={topP}
                                        onChange={(e) => setTopP(Number(e.target.value))}
                                        className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                                    />
                                    <div className="flex justify-between text-[9px] text-slate-400"><span>0.1 Focused</span><span>0.9 Diverse</span><span>1.0 Full range</span></div>
                                </div>
                                <div className="space-y-1">
                                    <div className="flex items-center justify-between">
                                        <label className="text-xs text-slate-500 dark:text-slate-400">Max Tokens</label>
                                        <span className="text-xs font-mono text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-1.5 py-0.5 rounded">{maxTokens}</span>
                                    </div>
                                    <input
                                        type="range"
                                        min="256"
                                        max="32768"
                                        step="256"
                                        value={maxTokens}
                                        onChange={(e) => setMaxTokens(Number(e.target.value))}
                                        className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                                    />
                                    <div className="flex justify-between text-[9px] text-slate-400"><span>256</span><span>4096</span><span>32768</span></div>
                                </div>
                            </div>
                        )}
                    </div>

                    {saveError && (
                        <div className="rounded-xl border border-rose-200 bg-rose-50/90 px-4 py-3 text-xs text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
                            {saveError}
                        </div>
                    )}
                </div>

                <div className="p-4 border-t border-slate-200/80 dark:border-slate-700/60 bg-gradient-to-r from-slate-50/90 to-slate-100/80 dark:from-slate-800/50 dark:to-slate-800/30 flex items-center justify-between gap-3 rounded-b-2xl">
                    <div className="flex items-center gap-2">
                        <button
                            onClick={async () => {
                                if (!confirm("Clear all history? This cannot be undone.")) return;
                                try {
                                    await fetch(API_ENDPOINTS.system.dbReset, { method: 'POST' });
                                    alert("Database reset");
                                } catch {
                                    alert("Reset failed");
                                }
                            }}
                            title={"Clear database"}
                            className="p-2 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                        >
                            <Trash2 className="w-4 h-4" />
                        </button>
                        <button
                            onClick={async () => {
                                try {
                                    const res = await fetch(API_ENDPOINTS.system.dbBackup, { method: 'POST' });
                                    const data = await res.json();
                                    alert(data.message || "Backup completed");
                                } catch {
                                    alert("Failed to start backup");
                                }
                            }}
                            title={"Back up database"}
                            className="p-2 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                        >
                            <Database className="w-4 h-4" />
                        </button>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={isSaving}
                            className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-500/25 active:scale-95 transform disabled:opacity-50"
                        >
                            <Save className="w-4 h-4" />
                            {isSaving ? "Syncing..." : "Save and sync"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SettingsModal;
