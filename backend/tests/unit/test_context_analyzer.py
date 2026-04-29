"""
ContextAnalyzer 单元测试
覆盖: TDD / EXPLORER / VERIFICATION 分支与空输入健壮性
"""
from services.context_analyzer import ContextAnalyzer


class TestContextAnalyzer:
    def test_no_url_returns_tdd(self):
        result = ContextAnalyzer.analyze("测试登录功能", "", "")
        assert result["strategy"] == "TDD"
        assert "TDD" in result["reasoning"]

    def test_url_with_empty_requirement_prefers_explorer(self):
        result = ContextAnalyzer.analyze("", "https://example.com", "")
        assert result["strategy"] == "EXPLORER"

    def test_url_with_vague_requirement_prefers_explorer(self):
        result = ContextAnalyzer.analyze("帮我测试一下", "https://example.com", "")
        assert result["strategy"] == "EXPLORER"

    def test_url_with_english_vague_requirement_prefers_explorer(self):
        result = ContextAnalyzer.analyze("test login", "https://example.com", "")
        assert result["strategy"] == "EXPLORER"

    def test_url_with_detailed_requirement_returns_verification(self):
        result = ContextAnalyzer.analyze(
            "请验证登录、退出、权限控制和异常提示是否符合预期",
            "https://example.com",
            "",
        )
        assert result["strategy"] == "VERIFICATION"

    def test_url_with_long_rag_context_returns_verification(self):
        rag_context = "系统说明" * 30
        result = ContextAnalyzer.analyze("测试一下", "https://example.com", rag_context)
        assert result["strategy"] == "VERIFICATION"

    def test_none_inputs_are_handled_safely(self):
        result = ContextAnalyzer.analyze(None, None, None)
        assert result["strategy"] == "TDD"
