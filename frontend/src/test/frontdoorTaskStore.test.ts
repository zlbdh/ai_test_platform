import { describe, expect, it } from 'vitest';
import { useFrontdoorTaskStore } from '../stores';

describe('frontdoorTaskStore', () => {
    it('should update draft, filters and current task state', () => {
        useFrontdoorTaskStore.setState({
            draft: {
                taskKind: 'general',
                userGoal: '',
                targetUrl: '',
                sourceType: 'url',
                source: '',
                compareSource: '',
                playbookId: 'sample-platform-prototype',
            },
            tasks: [],
            currentTask: null,
            currentTaskId: null,
            filters: { taskKind: '', status: '' },
            streamConnected: false,
        });

        useFrontdoorTaskStore.getState().setDraft({ userGoal: '检查首页主链路', targetUrl: 'https://demo.example.com' });
        useFrontdoorTaskStore.getState().setFilters({ taskKind: 'general', status: 'completed' });
        useFrontdoorTaskStore.getState().setCurrentTask({
            task_id: 'task001',
            mission_kind: 'commander',
            task_kind: 'general',
            user_goal: '检查首页主链路',
            status: 'completed',
            created_at: '2026-04-02T15:00:00',
            started_at: '2026-04-02T15:00:01',
            completed_at: '2026-04-02T15:00:03',
            source_context: {},
            strategy: {},
            agent_states: {},
            evidence_summary: {
                log_count: 0,
                finding_count: 0,
                has_report: false,
                execution_group_id: 'task001',
                summary_keys: [],
                evidence_ids: [],
                latest_log_at: null,
                static_unprovable_count: 0,
            },
            findings: [],
            gate_summary: { status: 'passed', summary: 'ok', metrics: {} },
            verification_state: {
                status: 'verified_passed',
                label: '已验证通过',
                summary: '当前任务没有发现阻断问题。',
            },
            recommendations: [],
            result_summary: {},
            logs: [],
            execution_group_id: 'task001',
            lineage_root_id: 'task001',
            rerun_from_task_id: '',
            execution_center_path: '/history?group=task001',
            quality_gate_path: '/quality-gate?task_id=task001&run_id=task001&focus=history',
            expert_path: '/orchestrator',
            raw_report: {},
        });

        const state = useFrontdoorTaskStore.getState();
        expect(state.draft.userGoal).toBe('检查首页主链路');
        expect(state.filters.taskKind).toBe('general');
        expect(state.currentTaskId).toBe('task001');
    });
});
