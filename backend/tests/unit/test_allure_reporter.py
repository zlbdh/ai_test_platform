import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from core.allure_reporter import AllureReporter, _classify_issue_source, _parse_execution_steps


class TestAllureReporter:
    def test_calc_stats_keeps_run_counts_and_aggregates_step_counts(self, tmp_path):
        reporter = AllureReporter(
            results_dir=str(tmp_path / "results"),
            report_dir=str(tmp_path / "reports"),
        )
        runs = [
            {
                "status": "success",
                "duration_ms": 1200,
                "log_count": 99,
                "error_count": 5,
                "logs": [
                    {"event": "step_result", "status": "success", "content": "✅ success"},
                    {"event": "step_result", "status": "success", "content": "✅ success"},
                    {"event": "step_result", "status": "failed", "content": "❌ failed"},
                ],
            },
            {
                "status": "failed",
                "duration_ms": 800,
                "log_count": 4,
                "error_count": 1,
                "logs": [],
            },
        ]

        stats = reporter._calc_stats(runs)

        assert stats["total"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["total_steps"] == 7
        assert stats["step_passed"] == 5
        assert stats["step_failed"] == 2
        assert stats["case_total"] == 0
        assert stats["platform_issue_total"] == 0
        assert stats["duration_ms"] == 2000

    def test_generate_report_with_task_id_saves_record_case_and_issue_counts_to_history(self, tmp_path):
        reporter = AllureReporter(
            results_dir=str(tmp_path / "results"),
            report_dir=str(tmp_path / "reports"),
        )
        runs = [
            {
                "task_id": "task-123",
                "requirement": "验证服务商品中心",
                "status": "success",
                "log_count": 6,
                "error_count": 0,
                "duration_ms": 1234,
                "target_url": "http://127.0.0.1:81/unifiedGoodService/uniProductService",
                "mode": "quick",
                "created_at": "2026-03-12 11:05:06",
                "logs": [
                    {"event": "step_result", "type": "result", "action": "goto", "step": "goto(...)", "status": "success", "content": "✅ success"},
                    {
                        "type": "assertion",
                        "event": "assertion_pass",
                        "action": "assert",
                        "step": "assert(服务商品)",
                        "target": "服务商品",
                        "status": "pass",
                        "step_index": 1,
                        "content": "Assert Passed (Text Match)",
                    },
                    {"event": "step_result", "type": "result", "action": "assert", "step": "assert(服务商品)", "status": "success", "content": "✅ success"},
                    {
                        "type": "error",
                        "event": "step_error",
                        "action": "click",
                        "step": "click(分类管理)",
                        "target": "分类管理",
                        "status": "error",
                        "content": "Could not find element: 分类管理",
                    },
                ],
            }
        ]

        with patch.object(reporter, "_load_test_runs", return_value=runs) as mock_load:
            record = reporter.generate_report(task_id="task-123")

        mock_load.assert_called_once_with(task_id="task-123")
        assert record["status"] == "success"
        assert record["report_scope"] == "record"
        assert record["record_count"] == 1
        assert record["case_count"] == 1
        assert record["platform_issue_count"] == 1
        assert record["total_steps"] == 2
        assert record["passed"] == 1
        assert record["failed"] == 0
        assert record["report_url"].endswith(record["id"])

        history = reporter.get_history(limit=1)
        assert len(history) == 1
        assert history[0]["id"] == record["id"]
        assert history[0]["record_count"] == 1
        assert history[0]["case_count"] == 1
        assert history[0]["platform_issue_count"] == 1
        assert history[0]["total_steps"] == 2
        assert history[0]["passed"] == 1
        assert history[0]["failed"] == 0
        snapshot_file = Path(tmp_path / "reports") / f"{record['id']}.html"
        assert snapshot_file.exists()
        html = snapshot_file.read_text(encoding="utf-8")
        assert "Test Record" in html
        assert "Tested Platform Issues" in html

    def test_build_report_record_treats_group_target_as_targeted_report(self, tmp_path):
        reporter = AllureReporter(
            results_dir=str(tmp_path / "results"),
            report_dir=str(tmp_path / "reports"),
        )
        stats = {
            "total": 2,
            "case_total": 3,
            "platform_issue_total": 1,
            "execution_issue_total": 0,
            "total_steps": 8,
            "case_passed": 2,
            "case_failed": 1,
            "duration_ms": 2400,
        }
        record = reporter._build_report_record(
            stats,
            datetime(2026, 3, 14, 9, 30, 0),
            "rid12345",
            [
                {
                    "task_id": "task_root",
                    "requirement": "服务商品中心全链路测试",
                    "target_url": "http://127.0.0.1:3000/qyLogin",
                },
                {
                    "task_id": "security_child",
                    "requirement": "安全扫描 · http://127.0.0.1:3000/qyLogin",
                    "target_url": "http://127.0.0.1:3000/qyLogin",
                },
            ],
            selected_id="batch_task_1",
        )

        assert record["report_scope"] == "batch"
        assert record["task_id"] == "batch_task_1"
        assert record["record_count"] == 2
        assert "Batch Report" in record["title"]

    def test_get_history_repairs_broken_titles(self, tmp_path):
        reporter = AllureReporter(
            results_dir=str(tmp_path / "results"),
            report_dir=str(tmp_path / "reports"),
        )
        history_file = Path(tmp_path / "reports" / "report_history.json")
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.write_text(
            json.dumps(
                [
                    {
                        "id": "bad001",
                        "title": "???? ? ry_cloud · 批次报告",
                        "report_scope": "batch",
                        "task_id": "batch_retry_live_demo",
                        "target_url": "ry_cloud",
                        "timestamp": "2026-03-14T12:00:00",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        history = reporter.get_history(limit=5)

        assert history[0]["title"] == "Specialized Test · ry_cloud · Batch Report"

    def test_get_history_repairs_batch_suffix_mismatch(self, tmp_path):
        reporter = AllureReporter(
            results_dir=str(tmp_path / "results"),
            report_dir=str(tmp_path / "reports"),
        )
        history_file = Path(tmp_path / "reports" / "report_history.json")
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.write_text(
            json.dumps(
                [
                    {
                        "id": "batch001",
                        "title": "专项测试 · ry_cloud · 专属报告",
                        "report_scope": "batch",
                        "task_id": "batch_demo",
                        "target_url": "ry_cloud",
                        "timestamp": "2026-03-14T12:30:00",
                    },
                    {
                        "id": "record001",
                        "title": "专项测试 · ry_cloud · 专属报告",
                        "report_scope": "record",
                        "task_id": "record_demo",
                        "target_url": "ry_cloud",
                        "timestamp": "2026-03-14T12:31:00",
                    },
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        history = reporter.get_history(limit=5)

        assert history[0]["title"] == "Specialized Test · ry_cloud · Batch Report"
        assert history[1]["title"] == "Test Record · ry_cloud · Record Report"

    def test_get_history_keeps_natural_summary_title(self, tmp_path):
        reporter = AllureReporter(
            results_dir=str(tmp_path / "results"),
            report_dir=str(tmp_path / "reports"),
        )
        history_file = Path(tmp_path / "reports" / "report_history.json")
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.write_text(
            json.dumps(
                [
                    {
                        "id": "summary001",
                        "title": "最近 20 条测试记录汇总",
                        "report_scope": "summary",
                        "record_count": 20,
                        "timestamp": "2026-03-14T12:32:00",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        history = reporter.get_history(limit=5)

        assert history[0]["title"] == "Recent 20 Test Records Summary"

    def test_get_history_repairs_mechanical_summary_title(self, tmp_path):
        reporter = AllureReporter(
            results_dir=str(tmp_path / "results"),
            report_dir=str(tmp_path / "reports"),
        )
        history_file = Path(tmp_path / "reports" / "report_history.json")
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.write_text(
            json.dumps(
                [
                    {
                        "id": "summary002",
                        "title": "测试报告 · 测试记录 · 汇总报告",
                        "report_scope": "summary",
                        "record_count": 8,
                        "timestamp": "2026-03-14T12:33:00",
                    }
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        history = reporter.get_history(limit=5)

        assert history[0]["title"] == "Recent 8 Test Records Summary"


@pytest.mark.parametrize('content', [
    'Reasoning failed: no plan',
    '推理失败: no plan',
    'Session preauthentication failed',
    '会话预认证失败',
    'Could not find element: sign-in button',
    'Could not find element: 登录按钮',
])
def test_issue_classifier_preserves_english_and_legacy_execution_diagnostics(content):
    assert _classify_issue_source({'type': 'error'}, content) == 'execution'


@pytest.mark.parametrize('content', ['Step 1: Reasoning...', 'Step 1: 正在推理'])
def test_reasoning_steps_accept_english_and_legacy_logs(content):
    steps = _parse_execution_steps([{'type': 'thought', 'content': content}])
    assert len(steps) == 1
    assert steps[0]['label'] == 'AI Reasoning'
    assert steps[0]['content'] == content


def test_empty_report_uses_american_english(tmp_path):
    reporter = AllureReporter(results_dir=str(tmp_path / 'results'), report_dir=str(tmp_path / 'reports'))
    with patch.object(reporter, '_load_test_runs', return_value=[]):
        result = reporter.generate_report()
    html = (tmp_path / 'reports' / (result['id'] + '.html')).read_text()
    assert '<html lang="en-US"' in html
    assert 'No test records yet' in html
    assert not re.search(r'[\u3400-\u9fff]', html)
