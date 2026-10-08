import { AIProvider, type AISettings, type AIBackendConfig } from '../types';

export const RESOURCE_PACK_MODEL = 'claude-haiku-4-5-20251001';
export const RESOURCE_PACK_MODEL_LABEL = 'Claude Haiku 4.5';
export const RESOURCE_PACK_BASE_URL = 'https://api.openai.com/v1';

export const RESOURCE_PACK_MODELS = [
    { id: RESOURCE_PACK_MODEL, name: RESOURCE_PACK_MODEL_LABEL },
];

export const DEFAULT_AI_SETTINGS: AISettings = {
    provider: AIProvider.OPENAI,
    apiKey: '',
    modelName: RESOURCE_PACK_MODEL,
    baseUrl: RESOURCE_PACK_BASE_URL,
};

export function normalizeAISettings(settings?: Partial<AISettings>): AISettings {
    return {
        provider: AIProvider.OPENAI,
        apiKey: settings?.apiKey || '',
        modelName: RESOURCE_PACK_MODEL,
        baseUrl: RESOURCE_PACK_BASE_URL,
    };
}

export function normalizeBackendConfig(config?: Partial<AIBackendConfig>): AIBackendConfig {
    return {
        provider: 'openai',
        model: RESOURCE_PACK_MODEL,
        base_url: RESOURCE_PACK_BASE_URL,
        api_key_masked: config?.api_key_masked || '',
        vision_model: RESOURCE_PACK_MODEL,
        planner_model: RESOURCE_PACK_MODEL,
        executor_model: RESOURCE_PACK_MODEL,
        temperature: typeof config?.temperature === 'number' ? config.temperature : 0,
        top_p: typeof config?.top_p === 'number' ? config.top_p : 1,
        max_tokens: typeof config?.max_tokens === 'number' ? config.max_tokens : 4096,
        provider_locked: config?.provider_locked ?? true,
        model_locked: config?.model_locked ?? true,
        allowed_models: config?.allowed_models?.length ? config.allowed_models : [RESOURCE_PACK_MODEL],
        profile_name: config?.profile_name || "JieKou AI resource package",
    };
}
