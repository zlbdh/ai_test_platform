import json

from core.knowledge_base import TestKnowledgeBase


class TestKnowledgeBaseUnit:
    def test_record_test_copies_mutable_test_types(self, tmp_path):
        kb = TestKnowledgeBase(storage_path=str(tmp_path))
        test_types = ["ui_e2e"]

        case = kb.record_test(
            requirement="测试 登录 表单",
            target_url=None,
            test_types=test_types,
            result="success",
            duration_ms=1200,
        )
        test_types.append("api")

        pattern = next(iter(kb.patterns.values()))
        assert case.test_types == ["ui_e2e"]
        assert pattern.test_types == ["ui_e2e"]

    def test_update_pattern_merges_unique_test_types_and_dedupes_index(self, tmp_path):
        kb = TestKnowledgeBase(storage_path=str(tmp_path))

        kb.record_test(
            requirement="测试 登录 表单",
            target_url=None,
            test_types=["ui_e2e"],
            result="success",
            duration_ms=1000,
        )
        kb.record_test(
            requirement="登录 表单 测试",
            target_url=None,
            test_types=["api", "ui_e2e"],
            result="failure",
            duration_ms=2000,
        )

        pattern = next(iter(kb.patterns.values()))
        assert pattern.success_count == 1
        assert pattern.failure_count == 1
        assert pattern.test_types == ["ui_e2e", "api"]
        assert len(kb.keyword_index["登录"]) == 1

    def test_load_rebuilds_index_with_requirement_hash_keys(self, tmp_path):
        patterns_file = tmp_path / "patterns.json"
        cases_file = tmp_path / "cases.json"
        patterns_file.write_text(
            json.dumps(
                [
                    {
                        "pattern_id": "pat_demo_hash",
                        "requirement_hash": "demo_hash",
                        "requirement_keywords": ["登录", "登录", "表单"],
                        "test_types": ["ui_e2e"],
                        "success_count": 2,
                        "failure_count": 0,
                        "avg_duration_ms": 800,
                        "last_used": "2026-03-11T12:00:00",
                        "metadata": {},
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        cases_file.write_text("[]", encoding="utf-8")

        kb = TestKnowledgeBase(storage_path=str(tmp_path))
        patterns = kb.find_similar_patterns("登录 页面")

        assert kb.keyword_index["登录"] == ["demo_hash"]
        assert patterns[0].requirement_hash == "demo_hash"

    def test_recommend_test_types_normalizes_scores(self, tmp_path):
        kb = TestKnowledgeBase(storage_path=str(tmp_path))

        kb.record_test(
            requirement="登录 表单",
            target_url=None,
            test_types=["ui_e2e"],
            result="success",
            duration_ms=900,
        )
        kb.record_test(
            requirement="登录 接口",
            target_url=None,
            test_types=["api"],
            result="success",
            duration_ms=1100,
        )
        kb.record_test(
            requirement="登录 接口",
            target_url=None,
            test_types=["api"],
            result="failure",
            duration_ms=1300,
        )

        recommendations = kb.recommend_test_types("登录 测试")

        assert recommendations["ui_e2e"] == 1.0
        assert recommendations["api"] == 0.5

    def test_export_report_limits_recent_failures_to_last_ten(self, tmp_path):
        kb = TestKnowledgeBase(storage_path=str(tmp_path))

        for index in range(12):
            kb.record_test(
                requirement=f"登录 失败 {index}",
                target_url=None,
                test_types=["ui_e2e"],
                result="failure",
                duration_ms=500 + index,
                error_message=f"err-{index}",
            )

        report = kb.export_report()
        failures = report["recent_failures"]

        assert len(failures) == 10
        assert failures[0]["error_message"] == "err-2"
        assert failures[-1]["error_message"] == "err-11"
