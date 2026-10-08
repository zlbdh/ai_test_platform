/**
 * Application Configuration
 * 
 * Centralizes all configuration values to avoid hardcoding.
 * Uses Vite environment variables with fallbacks.
 */

// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8020';

// WebSocket Configuration  
export const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8020';

// API Endpoints
export const API_ENDPOINTS = {
    // Core
    status: (sessionId: string) => `${API_BASE_URL}/api/status?session_id=${sessionId}`,
    start: `${API_BASE_URL}/api/start`,
    stop: (sessionId: string) => `${API_BASE_URL}/api/stop?session_id=${sessionId}`,
    stream: (sessionId: string) => `${API_BASE_URL}/api/stream?session_id=${sessionId}`,

    // Config
    config: {
        ai: `${API_BASE_URL}/api/config/ai`,
    },

    // Control
    control: {
        pause: (sessionId: string) => `${API_BASE_URL}/api/control/pause?session_id=${sessionId}`,
        resume: (sessionId: string) => `${API_BASE_URL}/api/control/resume?session_id=${sessionId}`,
        suspend: `${API_BASE_URL}/api/control/suspend`,
        stop: (sessionId: string) => `${API_BASE_URL}/api/control/stop?session_id=${sessionId}`,
    },

    // History & Gallery
    history: {
        list: `${API_BASE_URL}/api/history`,
        delete: (taskId: string) => `${API_BASE_URL}/api/history/${taskId}`,
        clear: `${API_BASE_URL}/api/history`,
    },
    gallery: (taskId: string) => `${API_BASE_URL}/api/gallery/${taskId}`,

    // Knowledge
    knowledge: {
        status: `${API_BASE_URL}/api/knowledge/status`,
        add: `${API_BASE_URL}/api/knowledge/add`,
        query: `${API_BASE_URL}/api/knowledge/query`,
        list: `${API_BASE_URL}/api/knowledge/list`,
        upload: `${API_BASE_URL}/api/knowledge/upload`,
        content: (docId: string) => `${API_BASE_URL}/api/knowledge/${docId}/content`,
        delete: (docId: string) => `${API_BASE_URL}/api/knowledge/${docId}`,
        clear: `${API_BASE_URL}/api/knowledge/clear`,
    },

    // Data Factory
    data: {
        generate: `${API_BASE_URL}/api/data/generate`,
        types: `${API_BASE_URL}/api/data/types`,
    },

    // Batch Testing
    batch: {
        run: `${API_BASE_URL}/api/batch/run`,
    },

    // Performance Testing
    performance: {
        run: `${API_BASE_URL}/api/performance/run`,
        status: `${API_BASE_URL}/api/performance/status`,
        history: `${API_BASE_URL}/api/performance/history`,
        delete: (testId: string) => `${API_BASE_URL}/api/performance/history/${testId}`,
        clear: `${API_BASE_URL}/api/performance/history`,
        stop: `${API_BASE_URL}/api/performance/stop`,
    },

    // Security Scanning
    security: {
        scan: `${API_BASE_URL}/api/security/scan`,
        status: `${API_BASE_URL}/api/security/status`,
        history: `${API_BASE_URL}/api/security/history`,
        delete: (scanId: string) => `${API_BASE_URL}/api/security/history/${scanId}`,
        clear: `${API_BASE_URL}/api/security/history`,
        report: (scanId: string) => `${API_BASE_URL}/api/security/report/${scanId}`,
        stop: `${API_BASE_URL}/api/security/stop`,
    },

    // API Workbench
    workbench: {
        collections: `${API_BASE_URL}/api/workbench/collections`,
        collection: (id: string) => `${API_BASE_URL}/api/workbench/collections/${id}`,
        collectionRequests: (collId: string) => `${API_BASE_URL}/api/workbench/collections/${collId}/requests`,
        request: (collId: string, reqId: string) => `${API_BASE_URL}/api/workbench/collections/${collId}/requests/${reqId}`,
        environments: `${API_BASE_URL}/api/workbench/environments`,
        execute: `${API_BASE_URL}/api/workbench/execute`,
    },

    // GraphQL Testing
    graphql: {
        execute: `${API_BASE_URL}/api/graphql/execute`,
        introspect: `${API_BASE_URL}/api/graphql/introspect`,
        testSuite: `${API_BASE_URL}/api/graphql/test-suite`,
        generateQuery: `${API_BASE_URL}/api/graphql/generate-query`,
    },

    // WebSocket Testing
    wsTest: {
        scenario: `${API_BASE_URL}/api/ws-test/scenario`,
        quickTest: `${API_BASE_URL}/api/ws-test/quick-test`,
    },

    // gRPC Testing
    grpc: {
        call: `${API_BASE_URL}/api/grpc/call`,
        services: `${API_BASE_URL}/api/grpc/services`,
        describe: `${API_BASE_URL}/api/grpc/describe`,
        testSuite: `${API_BASE_URL}/api/grpc/test-suite`,
    },

    // Report
    report: {
        generate: `${API_BASE_URL}/api/report/generate`,
        history: `${API_BASE_URL}/api/report/history`,
        clear: `${API_BASE_URL}/api/report/clear`,
        delete: (id: string) => `${API_BASE_URL}/api/report/${id}`,
    },

    // CI/CD
    ci: {
        config: `${API_BASE_URL}/api/ci/config`,
        secret: `${API_BASE_URL}/api/ci/secret`,
        webhook: `${API_BASE_URL}/api/ci/webhook`,
        history: `${API_BASE_URL}/api/ci/history`,
        trigger: (id: string) => `${API_BASE_URL}/api/ci/trigger/${id}`,
        reportJunit: (id: string) => `${API_BASE_URL}/api/ci/report/${id}/junit.xml`,
        reportHtml: (id: string) => `${API_BASE_URL}/api/ci/report/${id}/summary.html`,
    },

    // Database
    db: {
        connections: `${API_BASE_URL}/api/db/connections`,
        connection: (id: string) => `${API_BASE_URL}/api/db/connections/${id}`,
        test: (id: string) => `${API_BASE_URL}/api/db/connections/${id}/test`,
        tables: `${API_BASE_URL}/api/db/tables`,
        tablesForConn: (id: string) => `${API_BASE_URL}/api/db/connections/${id}/tables`,
        schemaForConn: (id: string) => `${API_BASE_URL}/api/db/connections/${id}/schema`,
        query: (id: string) => `${API_BASE_URL}/api/db/connections/${id}/query`,
        validate: (id: string) => `${API_BASE_URL}/api/db/connections/${id}/validate`,
        execute: `${API_BASE_URL}/api/db/execute`,
        schema: `${API_BASE_URL}/api/db/schema`,
        snapshot: `${API_BASE_URL}/api/db/snapshot`,
        diff: `${API_BASE_URL}/api/db/diff`,
        backup: `${API_BASE_URL}/api/db/backup`,
    },

    // Accessibility Testing
    accessibility: {
        audit: `${API_BASE_URL}/api/accessibility/audit`,
        quickCheck: `${API_BASE_URL}/api/accessibility/quick-check`,
    },

    // i18n Testing
    i18n: {
        test: `${API_BASE_URL}/api/i18n/test`,
        quickCheck: `${API_BASE_URL}/api/i18n/quick-check`,
    },

    // Compliance Testing
    compliance: {
        audit: `${API_BASE_URL}/api/compliance/audit`,
    },

    // Requirement Parsing
    requirement: {
        analyze: `${API_BASE_URL}/api/requirement/analyze`,
        parse: `${API_BASE_URL}/api/requirement/parse`,
        parseFile: `${API_BASE_URL}/api/requirement/parse-file`,
        parseUpload: `${API_BASE_URL}/api/requirement/parse-upload`,
        generateTests: `${API_BASE_URL}/api/requirement/generate-tests`,
        playbooks: `${API_BASE_URL}/api/requirement/playbooks`,
        playbook: (playbookId: string) => `${API_BASE_URL}/api/requirement/playbooks/${playbookId}`,
    },

    // Chaos Engineering
    chaos: {
        run: `${API_BASE_URL}/api/chaos/run`,
        scenarios: `${API_BASE_URL}/api/chaos/scenarios`,
    },

    // Mobile Emulation
    mobile: {
        test: `${API_BASE_URL}/api/mobile/test`,
        devices: `${API_BASE_URL}/api/mobile/devices`,
    },

    // Data Factory (new)
    dataFactory: {
        types: `${API_BASE_URL}/api/data-factory/types`,
        generate: `${API_BASE_URL}/api/data-factory/generate`,
    },

    // System Management
    system: {
        dbReset: `${API_BASE_URL}/api/system/db/reset`,
        dbBackup: `${API_BASE_URL}/api/system/db/backup`,
    },
    // Commander
    commander: {
        run: `${API_BASE_URL}/api/commander/run`,
        status: (missionId: string) => `${API_BASE_URL}/api/commander/status/${missionId}`,
        cancel: `${API_BASE_URL}/api/commander/cancel`,
        missions: `${API_BASE_URL}/api/commander/missions`,
        stream: (missionId: string) => `${API_BASE_URL}/api/commander/stream/${missionId}`,
        architect: `${API_BASE_URL}/api/commander/architect`,
        agents: `${API_BASE_URL}/api/commander/agents`,
        tracing: `${API_BASE_URL}/api/commander/tracing`,
        prototype: {
            run: `${API_BASE_URL}/api/commander/prototype/run`,
            status: (missionId: string) => `${API_BASE_URL}/api/commander/prototype/status/${missionId}`,
            missions: `${API_BASE_URL}/api/commander/prototype/missions`,
            stream: (missionId: string) => `${API_BASE_URL}/api/commander/prototype/stream/${missionId}`,
        },
    },
    // Project deployment
    deploy: {
        projects: `${API_BASE_URL}/api/deploy/projects`,
        project: (key: string) => `${API_BASE_URL}/api/deploy/projects/${key}`,
        token: `${API_BASE_URL}/api/deploy/token`,
        logs: (repoId: string) => `${API_BASE_URL}/api/deploy/logs/${repoId}`,
        history: `${API_BASE_URL}/api/deploy/history`,
    },
    // Evaluation
    evaluation: {
        metrics: `${API_BASE_URL}/api/evaluation/metrics`,
        scenarios: `${API_BASE_URL}/api/evaluation/scenarios`,
        run: `${API_BASE_URL}/api/evaluation/run`,
        results: `${API_BASE_URL}/api/evaluation/results`,
        compare: `${API_BASE_URL}/api/evaluation/compare`,
        trend: `${API_BASE_URL}/api/evaluation/trend`,
    },
    // Scenario Chain
    scenario: {
        list: `${API_BASE_URL}/api/scenarios`,
        detail: (id: string) => `${API_BASE_URL}/api/scenarios/${id}`,
        execute: (id: string) => `${API_BASE_URL}/api/scenarios/${id}/execute`,
        importPlaybook: (playbookId: string) => `${API_BASE_URL}/api/scenarios/import-playbook/${playbookId}`,
    },
    // Notification
    notification: {
        webhooks: `${API_BASE_URL}/api/notify/webhooks`,
        webhook: (id: string) => `${API_BASE_URL}/api/notify/webhooks/${id}`,
        test: (id: string) => `${API_BASE_URL}/api/notify/webhooks/${id}/test`,
        send: `${API_BASE_URL}/api/notify/send`,
    },
    // Scheduler
    scheduler: {
        tasks: `${API_BASE_URL}/api/scheduler/tasks`,
        task: (id: string) => `${API_BASE_URL}/api/scheduler/tasks/${id}`,
        toggle: (id: string) => `${API_BASE_URL}/api/scheduler/tasks/${id}/toggle`,
        runNow: (id: string) => `${API_BASE_URL}/api/scheduler/tasks/${id}/run-now`,
    },
    // Semantic Testing
    semantic: {
        startBrowser: `${API_BASE_URL}/api/semantic/start-browser`,
        stopBrowser: `${API_BASE_URL}/api/semantic/stop-browser`,
        sessions: `${API_BASE_URL}/api/semantic/sessions`,
        execute: (type: string) => `${API_BASE_URL}/api/semantic/${type}`,
    },
    // Visual Regression
    visual: {
        baselines: `${API_BASE_URL}/api/visual/baselines`,
        baseline: (name: string) => `${API_BASE_URL}/api/visual/baselines/${name}`,
        approve: (name: string) => `${API_BASE_URL}/api/visual/baselines/${name}/approve`,
        compare: `${API_BASE_URL}/api/visual/compare`,
    },
    // Plan
    plan: {
        generate: `${API_BASE_URL}/api/plan/generate`,
    },
    // Quality Gate
    qualityGate: {
        check: `${API_BASE_URL}/api/quality-gate/check`,
        history: `${API_BASE_URL}/api/quality-gate/history`,
        rules: `${API_BASE_URL}/api/quality-gate/rules`,
        importRules: (playbookId: string) => `${API_BASE_URL}/api/quality-gate/rules/import/${playbookId}`,
    },
} as const;

// WebSocket endpoints
export const WS_ENDPOINTS = {
    sandbox: `${WS_BASE_URL}/ws/sandbox`,
} as const;

// Helper to resolve image URLs
export const resolveImageUrl = (src: string): string => {
    if (src.startsWith('http') || src.startsWith('data:')) {
        return src;
    }
    return `${API_BASE_URL}${src}`;
};

// Default configuration values
export const DEFAULT_CONFIG = {
    performanceTestUrl: 'http://localhost:8020',
    securityScanUrl: 'http://localhost:8020',
} as const;
