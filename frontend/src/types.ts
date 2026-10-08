
export enum AgentType {
    PLANNER = 'PLANNER',
    UI = 'UI_AGENT',
    API = 'API_AGENT',
    DATA = 'DATA_AGENT',
    RCA = 'RCA_AGENT'
}

export enum StepStatus {
    PENDING = 'PENDING',
    RUNNING = 'RUNNING',
    SUCCESS = 'SUCCESS',
    FAILED = 'FAILED',
    HEALING = 'HEALING', // Self-healing state
    HEALED = 'HEALED'    // Self-healed successfully
}

export enum ExecutionMode {
    LOCAL = 'LOCAL_SANDBOX', // Browser-side JS injection (TargetSUT)
    CLOUD = 'CLOUD_HEADLESS' // Server-side Node.js Playwright (Real Websites)
}

export enum ExecutionState {
    IDLE = 'IDLE',
    RUNNING = 'RUNNING',
    PAUSED = 'PAUSED',
    STOPPED = 'STOPPED'
}

export interface TestStep {
    id: string;
    agent: AgentType;
    description: string;
    status: StepStatus;
    logs: string[];
    action: string;           // Action type: goto, fill, click, assert, wait, key, hover, select, scroll, etc.
    target: string;           // Action target: URL, element description, assertion text, etc.
    value?: string;           // Input value (only for actions such as fill)
    priority?: string;        // Priority: P0/P1/P2
    scenario?: string;        // Parent scenario name
    code?: string; // Display code (Playwright/Python)
    executableScript?: string; // Real JS for execution (Local only)
    duration?: number;
    retryCount?: number; // Track retries
}

export interface TestPlan {
    requirement: string;
    targetUrl?: string; // Target URL for external testing
    mode: ExecutionMode;
    steps: TestStep[];
}

export interface LogEntry {
    timestamp: string;
    agent: AgentType;
    level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS' | 'HEAL';
    message: string;
}

export interface AgentStat {
    id: AgentType;
    name: string;
    role: string;
    status: 'IDLE' | 'BUSY' | 'ERROR' | 'HEALING';
    tasksCompleted: number;
    successRate: number;
}

// AI Configuration Types
export enum AIProvider {
    GEMINI = 'GEMINI',
    OPENAI = 'OPENAI', // ChatGPT
    DEEPSEEK = 'DEEPSEEK',
    CUSTOM = 'CUSTOM'  // New: Custom OpenAI-compatible provider
}

export interface AISettings {
    provider: AIProvider;
    apiKey: string;
    modelName: string;
    baseUrl?: string; // For DeepSeek, Custom, or OpenAI Proxies
}

export interface AIBackendConfig {
    provider: string;
    model: string;
    base_url: string;
    api_key_masked: string;
    vision_model: string;
    planner_model: string;
    executor_model: string;
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
    provider_locked?: boolean;
    model_locked?: boolean;
    allowed_models?: string[];
    profile_name?: string;
}
