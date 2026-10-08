import { create } from 'zustand';
import { AISettings, AIProvider } from '../types';
import { DEFAULT_AI_SETTINGS, normalizeAISettings } from '../config/aiModelConfig';

// ============================================================================
// AI settings store: AI configuration and localStorage persistence
// ============================================================================

const STORAGE_KEY = 'ai-test-ai-settings';

function loadSettings(): AISettings {
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const parsed = JSON.parse(saved) as Partial<AISettings>;
            return normalizeAISettings(parsed);
        }
    } catch { /* ignore */ }
    return { ...DEFAULT_AI_SETTINGS };
}

function persistSettings(settings: AISettings) {
    const persisted = {
        provider: AIProvider.OPENAI,
        apiKey: '',
        modelName: settings.modelName,
        baseUrl: settings.baseUrl,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
}

interface AISettingsState {
    aiSettings: AISettings;
    setAiSettings: (settings: AISettings) => void;
    updateField: <K extends keyof AISettings>(key: K, value: AISettings[K]) => void;
}

export const useAISettingsStore = create<AISettingsState>((set) => ({
    aiSettings: loadSettings(),

    setAiSettings: (settings) => {
        const normalized = normalizeAISettings(settings);
        persistSettings(normalized);
        set({ aiSettings: normalized });
    },

    updateField: (key, value) => set((state) => {
        const updated = normalizeAISettings({ ...state.aiSettings, [key]: value });
        persistSettings(updated);
        return { aiSettings: updated };
    }),
}));
