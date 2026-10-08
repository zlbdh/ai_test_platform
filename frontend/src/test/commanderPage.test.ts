import { describe, expect, it } from 'vitest';

import {
    buildCommanderBatchActionFeedback,
    buildCommanderBugBoardItems,
    buildCommanderSelectedMissionSummary,
    collectCommanderBugBoardMissionIds,
    collectCommanderPendingReportMissionIds,
    buildCommanderBugHotspots,
    buildCommanderBugHotspotKey,
    buildCommanderHistoryOverview,
    buildCommanderExecutionHistoryPath,
    filterCommanderMissions,
    filterCommanderMissionsByBugHotspot,
    filterCommanderMissionsBySelection,
    filterCommanderMissionsByStatus,
    getCommanderMissionExecutionMetrics,
    getCommanderMissionMetaBadges,
    getMissionBugSummaryItems,
    searchCommanderMissions,
    sortCommanderMissions,
} from '../pages/CommanderPage';

describe('CommanderPage bug summary helpers', () => {
    it('should prefer report bug summary when available', () => {
        const items = getMissionBugSummaryItems({
            bug_summary: [],
            report: {
                bug_summary: [
                    {
                        test_type: 'security',
                        title: "Security scanning",
                        status: 'error',
                        summary: "High-severity vulnerability found",
                        execution_record_id: 'security_demo',
                    },
                ],
            },
        });

        expect(items).toHaveLength(1);
        expect(items[0].title).toBe("Security scanning");
        expect(items[0].execution_record_id).toBe('security_demo');
    });

    it('should fall back to mission level bug summary', () => {
        const items = getMissionBugSummaryItems({
            bug_summary: [
                {
                    test_type: 'ui_e2e',
                    title: '',
                    status: 'error',
                    summary: "The login button cannot be clicked",
                },
            ],
            report: null,
        });

        expect(items).toHaveLength(1);
        expect(items[0].title).toBe("UI automation");
        expect(items[0].summary).toBe("The login button cannot be clicked");
    });

    it('should build execution center path for group and record deep link', () => {
        expect(buildCommanderExecutionHistoryPath({ execution_group_id: 'mission_123' }, 'record_456'))
            .toBe('/history?group=mission_123&record=record_456');
        expect(buildCommanderExecutionHistoryPath({ execution_group_id: 'mission_123' }))
            .toBe('/history?group=mission_123');
        expect(buildCommanderExecutionHistoryPath({ execution_group_id: '' }, 'record_456'))
            .toBeNull();
    });

    it('should summarize mission meta badges for report and bug visibility', () => {
        const badges = getCommanderMissionMetaBadges({
            test_results_count: 3,
            bug_summary: [
                {
                    test_type: 'security',
                    title: "Security scanning",
                    status: 'error',
                    summary: "High-severity vulnerability found",
                },
            ],
            report: null,
        }, false);

        expect(badges.map(item => item.label)).toEqual(["3 test tracks", "Report pending", "1 issue"]);
        expect(badges.map(item => item.tone)).toEqual(['neutral', 'amber', 'red']);
    });

    it('should derive mission execution metrics from report summary', () => {
        const metrics = getCommanderMissionExecutionMetrics({
            test_results_count: 5,
            report: {
                summary: {
                    total_tests: 5,
                    completed: 4,
                    failed: 1,
                    success_rate: 80,
                },
            },
        } as never);

        expect(metrics).toEqual({
            totalTests: 5,
            passedTests: 4,
            failedTests: 1,
            successRate: 80,
        });
    });

    it('should build history overview for the current visible missions', () => {
        const missions = [
            {
                mission_id: 'm1',
                execution_group_id: 'm1',
                status: 'completed',
                test_results_count: 4,
                bug_summary: [
                    {
                        test_type: 'security',
                        title: "Security scanning",
                        status: 'error',
                        summary: "Issues found",
                    },
                ],
                report: {
                    summary: {
                        total_tests: 4,
                        completed: 3,
                        failed: 1,
                        success_rate: 75,
                    },
                },
            },
            {
                mission_id: 'm2',
                execution_group_id: 'm2',
                status: 'executing',
                test_results_count: 2,
                bug_summary: [],
                report: {
                    summary: {
                        total_tests: 2,
                        completed: 2,
                        failed: 0,
                        success_rate: 100,
                    },
                },
            },
        ] as never as Parameters<typeof buildCommanderHistoryOverview>[0];

        const overview = buildCommanderHistoryOverview(missions, {
            m1: {
                task_id: 'm1',
                timestamp: '2026-03-17T00:00:00',
                report_url: '/api/report/view/m1',
            },
        });

        expect(overview).toEqual({
            missionCount: 2,
            completedCount: 1,
            runningCount: 1,
            bugMissionCount: 1,
            bugItemCount: 1,
            reportReadyCount: 1,
            pendingReportCount: 1,
            totalTestLines: 6,
            failedTestLines: 1,
            averageSuccessRate: 87.5,
            averageSuccessRateSamples: 2,
        });
    });

    it('should aggregate top bug hotspots across visible missions', () => {
        const hotspots = buildCommanderBugHotspots([
            {
                mission_id: 'm1',
                bug_summary: [
                    {
                        test_type: 'security',
                        title: "Security scanning",
                        status: 'error',
                        summary: "High-severity vulnerability found",
                    },
                    {
                        test_type: 'api_rest',
                        title: "API testing",
                        status: 'error',
                        summary: "The health endpoint returned 500",
                    },
                ],
                report: null,
            },
            {
                mission_id: 'm2',
                bug_summary: [
                    {
                        test_type: 'api_rest',
                        title: "API testing",
                        status: 'error',
                        summary: "The health endpoint returned 500",
                    },
                ],
                report: null,
            },
        ] as never, 4);

        expect(hotspots).toHaveLength(2);
        expect(hotspots[0]).toMatchObject({
            testType: 'api_rest',
            title: "API testing",
            summary: "The health endpoint returned 500",
            status: 'error',
            count: 2,
            missionIds: ['m1', 'm2'],
            primaryMissionId: 'm1',
        });
        expect(hotspots[1]).toMatchObject({
            testType: 'security',
            title: "Security scanning",
            summary: "High-severity vulnerability found",
            count: 1,
            missionIds: ['m1'],
            primaryMissionId: 'm1',
        });
    });

    it('should build hotspot key using test type, title and summary', () => {
        expect(buildCommanderBugHotspotKey({
            test_type: 'api_rest',
            title: "API testing",
            summary: "The health endpoint returned 500",
        })).toBe("api_rest::API testing::The health endpoint returned 500");
    });

    it('should filter missions by the selected hotspot key', () => {
        const missions = [
            {
                mission_id: 'm1',
                bug_summary: [
                    {
                        test_type: 'security',
                        title: "Security scanning",
                        status: 'error',
                        summary: "High-severity vulnerability found",
                    },
                ],
                report: null,
            },
            {
                mission_id: 'm2',
                bug_summary: [
                    {
                        test_type: 'api_rest',
                        title: "API testing",
                        status: 'error',
                        summary: "The health endpoint returned 500",
                    },
                ],
                report: null,
            },
        ] as never as Parameters<typeof filterCommanderMissionsByBugHotspot>[0];

        expect(filterCommanderMissionsByBugHotspot(missions, "security::Security scanning::High-severity vulnerability found").map(item => item.mission_id)).toEqual(['m1']);
        expect(filterCommanderMissionsByBugHotspot(missions, "api_rest::API testing::The health endpoint returned 500").map(item => item.mission_id)).toEqual(['m2']);
        expect(filterCommanderMissionsByBugHotspot(missions, null).map(item => item.mission_id)).toEqual(['m1', 'm2']);
    });

    it('should build bug board items with severity and report state', () => {
        const missions = [
            {
                mission_id: 'm1',
                execution_group_id: 'm1',
                user_input: "Test the login workflow",
                created_at: '2026-03-17T10:00:00',
                status: 'completed',
                bug_summary: [
                    {
                        test_type: 'security',
                        title: "Security scanning",
                        status: 'error',
                        summary: "High-severity vulnerability found",
                        execution_record_id: 'record_security',
                    },
                    {
                        test_type: 'api_rest',
                        title: "API testing",
                        status: 'warning',
                        summary: "API response is too slow",
                    },
                ],
                report: null,
            },
            {
                mission_id: 'm2',
                execution_group_id: 'm2',
                user_input: "Test the payment workflow",
                created_at: '2026-03-17T09:00:00',
                status: 'failed',
                bug_summary: [
                    {
                        test_type: 'ui_e2e',
                        title: "UI automation",
                        status: 'recovered',
                        summary: "Dialog obstruction resolved",
                    },
                ],
                report: null,
            },
        ] as never as Parameters<typeof buildCommanderBugBoardItems>[0];

        const reportMap = {
            m1: {
                task_id: 'm1',
                timestamp: '2026-03-17T10:05:00',
                report_url: '/api/report/view/m1',
            },
        };

        const allItems = buildCommanderBugBoardItems(missions, reportMap, 'all', 8);
        expect(allItems).toHaveLength(3);
        expect(allItems[0]).toMatchObject({
            missionId: 'm1',
            title: "Security scanning",
            summary: "High-severity vulnerability found",
            severityKey: 'error',
            hasReport: true,
            executionRecordId: 'record_security',
        });
        expect(allItems[1]).toMatchObject({
            missionId: 'm1',
            title: "API testing",
            severityKey: 'warning',
        });
        expect(allItems[2]).toMatchObject({
            missionId: 'm2',
            title: "UI automation",
            severityKey: 'recovered',
            hasReport: false,
        });

        expect(buildCommanderBugBoardItems(missions, reportMap, 'warning', 8).map(item => item.title)).toEqual(["API testing"]);
        expect(buildCommanderBugBoardItems(missions, reportMap, 'recovered', 8).map(item => item.title)).toEqual(["UI automation"]);
    });

    it('should collect unique mission ids from bug board items in order', () => {
        expect(collectCommanderBugBoardMissionIds([
            {
                key: 'a',
                missionId: 'm1',
            },
            {
                key: 'b',
                missionId: 'm2',
            },
            {
                key: 'c',
                missionId: 'm1',
            },
        ] as never)).toEqual(['m1', 'm2']);
    });

    it('should collect pending report mission ids for the current bug board scope', () => {
        const missions = [
            {
                mission_id: 'm1',
                execution_group_id: 'm1',
            },
            {
                mission_id: 'm2',
                execution_group_id: 'm2',
            },
            {
                mission_id: 'm3',
                execution_group_id: 'm3',
            },
        ] as never as Parameters<typeof collectCommanderPendingReportMissionIds>[0];

        const reportMap = {
            m1: {
                task_id: 'm1',
                timestamp: '2026-03-17T10:05:00',
                report_url: '/api/report/view/m1',
            },
        };

        expect(collectCommanderPendingReportMissionIds(missions, reportMap, ['m1', 'm2', 'm2', 'm3']))
            .toEqual(['m2', 'm3']);
    });

    it('should summarize selected missions for batch handling', () => {
        const missions = [
            {
                mission_id: 'm1',
                execution_group_id: 'm1',
                bug_summary: [
                    {
                        test_type: 'security',
                        title: "Security scanning",
                        status: 'error',
                        summary: "Issues found",
                    },
                ],
                report: null,
            },
            {
                mission_id: 'm2',
                execution_group_id: 'm2',
                bug_summary: [],
                report: null,
            },
            {
                mission_id: 'm3',
                execution_group_id: 'm3',
                bug_summary: [
                    {
                        test_type: 'api_rest',
                        title: "API testing",
                        status: 'warning',
                        summary: "Response slowed down",
                    },
                ],
                report: null,
            },
        ] as never as Parameters<typeof buildCommanderSelectedMissionSummary>[0];

        const reportMap = {
            m1: {
                task_id: 'm1',
                timestamp: '2026-03-17T10:05:00',
                report_url: '/api/report/view/m1',
            },
        };

        expect(buildCommanderSelectedMissionSummary(missions, reportMap, ['m1', 'm3'])).toEqual({
            total: 2,
            withBugs: 2,
            reportReady: 1,
            pendingReport: 1,
        });
    });

    it('should build batch action feedback for commander bug board flows', () => {
        expect(buildCommanderBatchActionFeedback('bulk_report', {
            generated: 1,
            skipped: 2,
            failed: 0,
            missionIds: ['m1', 'm2'],
        })).toMatchObject({
            tone: 'success',
            message: "Batch processing completed: generated 1, already existed 2, failed 0.",
            missionIds: ['m1', 'm2'],
            actionKind: 'focus_selected',
        });

        expect(buildCommanderBatchActionFeedback('bug_board_report', {
            generated: 0,
            skipped: 1,
            failed: 1,
            missionIds: ['m3'],
        })).toMatchObject({
            tone: 'warning',
            message: "Issue list processing completed: generated 0, already existed 1, failed 1.",
            missionIds: ['m3'],
            actionKind: 'focus_selected',
        });

        expect(buildCommanderBatchActionFeedback('clear', { count: 3, missionIds: ['m1', 'm3'] })).toMatchObject({
            tone: 'info',
            message: "Cleared 3 selected tasks.",
            missionIds: ['m1', 'm3'],
            actionKind: 'restore_selected',
        });
    });

    it('should filter missions by selected mission scope', () => {
        const missions = [
            { mission_id: 'm1' },
            { mission_id: 'm2' },
            { mission_id: 'm3' },
        ] as never as Parameters<typeof filterCommanderMissionsBySelection>[0];

        expect(filterCommanderMissionsBySelection(missions, ['m2', 'm3'], 'selected').map(item => item.mission_id))
            .toEqual(['m2', 'm3']);
        expect(filterCommanderMissionsBySelection(missions, [], 'selected')).toEqual([]);
        expect(filterCommanderMissionsBySelection(missions, ['m2'], 'all').map(item => item.mission_id))
            .toEqual(['m1', 'm2', 'm3']);
    });

    it('should filter missions by bug and report state', () => {
        const missions = [
            {
                mission_id: 'm1',
                execution_group_id: 'm1',
                test_results_count: 2,
                bug_summary: [],
                report: null,
            },
            {
                mission_id: 'm2',
                execution_group_id: 'm2',
                test_results_count: 3,
                bug_summary: [
                    {
                        test_type: 'security',
                        title: "Security scanning",
                        status: 'error',
                        summary: "Issues found",
                    },
                ],
                report: null,
            },
        ] as never as Parameters<typeof filterCommanderMissions>[0];

        const reportMap = {
            m1: {
                task_id: 'm1',
                timestamp: '2026-03-17T00:00:00',
                report_url: '/api/report/view/demo',
            },
        };

        expect(filterCommanderMissions(missions, reportMap, 'all').map(item => item.mission_id)).toEqual(['m1', 'm2']);
        expect(filterCommanderMissions(missions, reportMap, 'has_report').map(item => item.mission_id)).toEqual(['m1']);
        expect(filterCommanderMissions(missions, reportMap, 'pending_report').map(item => item.mission_id)).toEqual(['m2']);
        expect(filterCommanderMissions(missions, reportMap, 'has_bugs').map(item => item.mission_id)).toEqual(['m2']);
    });

    it('should search missions by id, requirement and url', () => {
        const missions = [
            {
                mission_id: 'm_alpha',
                user_input: "Test the login workflow",
                target_url: 'https://demo.example.com/login',
                execution_group_id: 'm_alpha',
            },
            {
                mission_id: 'm_beta',
                user_input: "Test the payment workflow",
                target_url: 'https://demo.example.com/pay',
                execution_group_id: 'm_beta',
            },
        ] as never as Parameters<typeof searchCommanderMissions>[0];

        expect(searchCommanderMissions(missions, "Login").map(item => item.mission_id)).toEqual(['m_alpha']);
        expect(searchCommanderMissions(missions, 'm_beta').map(item => item.mission_id)).toEqual(['m_beta']);
        expect(searchCommanderMissions(missions, 'demo.example.com/pay').map(item => item.mission_id)).toEqual(['m_beta']);
    });

    it('should sort missions by bug count and report priority', () => {
        const missions = [
            {
                mission_id: 'm1',
                execution_group_id: 'm1',
                created_at: '2026-03-17T10:00:00',
                bug_summary: [],
                report: null,
            },
            {
                mission_id: 'm2',
                execution_group_id: 'm2',
                created_at: '2026-03-17T09:00:00',
                bug_summary: [
                    {
                        test_type: 'security',
                        title: "Security scanning",
                        status: 'error',
                        summary: "Issues found",
                    },
                ],
                report: null,
            },
            {
                mission_id: 'm3',
                execution_group_id: 'm3',
                created_at: '2026-03-17T08:00:00',
                bug_summary: [],
                report: null,
            },
        ] as never as Parameters<typeof sortCommanderMissions>[0];

        const reportMap = {
            m3: {
                task_id: 'm3',
                timestamp: '2026-03-17T00:00:00',
                report_url: '/api/report/view/demo',
            },
        };

        expect(sortCommanderMissions(missions, reportMap, 'latest').map(item => item.mission_id)).toEqual(['m1', 'm2', 'm3']);
        expect(sortCommanderMissions(missions, reportMap, 'bugs_first').map(item => item.mission_id)).toEqual(['m2', 'm1', 'm3']);
        expect(sortCommanderMissions(missions, reportMap, 'pending_report_first').map(item => item.mission_id)).toEqual(['m1', 'm2', 'm3']);
        expect(sortCommanderMissions(missions, reportMap, 'report_ready_first').map(item => item.mission_id)).toEqual(['m3', 'm1', 'm2']);
    });

    it('should filter missions by execution status layer', () => {
        const missions = [
            { mission_id: 'm1', status: 'completed' },
            { mission_id: 'm2', status: 'failed' },
            { mission_id: 'm3', status: 'executing' },
            { mission_id: 'm4', status: 'cancelled' },
        ] as never as Parameters<typeof filterCommanderMissionsByStatus>[0];

        expect(filterCommanderMissionsByStatus(missions, 'all').map(item => item.mission_id)).toEqual(['m1', 'm2', 'm3', 'm4']);
        expect(filterCommanderMissionsByStatus(missions, 'completed').map(item => item.mission_id)).toEqual(['m1']);
        expect(filterCommanderMissionsByStatus(missions, 'failed').map(item => item.mission_id)).toEqual(['m2', 'm4']);
        expect(filterCommanderMissionsByStatus(missions, 'running').map(item => item.mission_id)).toEqual(['m3']);
    });
});
