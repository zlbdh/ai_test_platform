import { describe, expect, it } from 'vitest';

import { resolveFocusedGroupPage, resolveFocusedRecordId } from '../components/ExecutionHistory';

const MODE_LABELS = {
    commander: "Agent hub",
    smart: 'Smart Agent',
    quick: 'Quick Plan',
    api_rest: "API testing",
    api_graphql: "GraphQL testing",
    performance: "Performance testing",
    security: "Security scanning",
    accessibility: "Accessibility testing",
    i18n: "Internationalization testing",
    compliance: "Compliance audit",
    database: "Database testing",
    api_workbench: "API workbench",
    graphql: "GraphQL testing",
    grpc: "gRPC testing",
    websocket: "WebSocket testing",
    chaos: "Chaos testing",
    mobile: "Mobile testing",
};

describe('ExecutionHistory mode labels', () => {
    it('should cover newly grouped specialized modes', () => {
        expect(MODE_LABELS.commander).toBe("Agent hub");
        expect(MODE_LABELS.api_rest).toBe("API testing");
        expect(MODE_LABELS.api_graphql).toBe("GraphQL testing");
        expect(MODE_LABELS.api_workbench).toBe("API workbench");
        expect(MODE_LABELS.graphql).toBe("GraphQL testing");
        expect(MODE_LABELS.grpc).toBe("gRPC testing");
        expect(MODE_LABELS.websocket).toBe("WebSocket testing");
        expect(MODE_LABELS.chaos).toBe("Chaos testing");
        expect(MODE_LABELS.mobile).toBe("Mobile testing");
    });

    it('should resolve focused group page from query target', () => {
        const groups = Array.from({ length: 14 }, (_, index) => ({
            group_id: `batch_${index + 1}`,
            records: [],
        }));

        expect(resolveFocusedGroupPage(groups, 'batch_1', 12)).toBe(1);
        expect(resolveFocusedGroupPage(groups, 'batch_13', 12)).toBe(2);
        expect(resolveFocusedGroupPage(groups, 'missing', 12)).toBeNull();
    });

    it('should resolve focused record id within a target group', () => {
        const groups = [
            {
                group_id: 'batch_1',
                records: [
                    { task_id: 'record_1' },
                    { task_id: 'record_2' },
                ],
            },
            {
                group_id: 'batch_2',
                records: [
                    { task_id: 'record_3' },
                ],
            },
        ];

        expect(resolveFocusedRecordId(groups, 'batch_1', 'record_2')).toBe('record_2');
        expect(resolveFocusedRecordId(groups, 'batch_1', 'record_9')).toBeNull();
        expect(resolveFocusedRecordId(groups, 'missing', 'record_2')).toBeNull();
    });
});
