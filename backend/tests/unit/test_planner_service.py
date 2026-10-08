"""
TestGenerationService (planner_service) unit tests
Coverage: the complete generate_plan flow, _discover_scenarios, _generate_steps,
          plan_next_step reasoning, and semantic_verify validation.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
import asyncio




# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _patch_externals():
    """Mock all heavyweight planner_service dependencies (LLM, KB, Scout, ContextAnalyzer)."""
    with patch("services.planner_service.get_llm_for_role") as mock_get_llm, \
         patch("services.planner_service.kb") as mock_kb, \
         patch("services.planner_service.Config") as mock_config:
        # Default LLM mock
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        # Default KB mock
        mock_kb.enabled = False
        mock_kb.initialize = MagicMock()
        # Default Config mock
        mock_config.PLANNER_MODEL = None
        yield {
            "get_llm": mock_get_llm,
            "llm": mock_llm,
            "kb": mock_kb,
            "config": mock_config,
        }


def _make_service():
    """Create a clean TestGenerationService instance."""
    from services.planner_service import TestGenerationService
    return TestGenerationService()


# ---------------------------------------------------------------------------
# generate_plan tests
# ---------------------------------------------------------------------------
class TestGeneratePlan:
    """Test the complete generate_plan() flow."""

    @pytest.mark.asyncio
    async def test_empty_requirement_returns_error(self, _patch_externals):
        """An empty requirement should return an error immediately."""
        svc = _make_service()
        result = await svc.generate_plan("")
        assert result["error"] == "Requirement cannot be empty"
        assert result["test_cases"] == []
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_whitespace_requirement_returns_error(self, _patch_externals):
        """A whitespace-only requirement should return an error immediately."""
        svc = _make_service()
        result = await svc.generate_plan("   ")
        assert result["error"] == "Requirement cannot be empty"

    @pytest.mark.asyncio
    async def test_rag_disabled(self, _patch_externals):
        """Do not call the knowledge base when RAG is disabled."""
        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "No URL"}
            result = await svc.generate_plan("Test login", enable_rag=False)
            _patch_externals["kb"].initialize.assert_not_called()
            assert result["test_cases"] == []
            assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_rag_enabled_with_kb(self, _patch_externals):
        """Retrieve knowledge when RAG is enabled and the KB is available."""
        kb_mock = _patch_externals["kb"]
        kb_mock.enabled = True
        # Simulate vector search results.
        mock_doc = MagicMock()
        mock_doc.page_content = "Test knowledge document content"
        mock_doc.metadata = {"filename": "prd.md"}
        mock_vs = MagicMock()
        mock_vs.similarity_search_with_score = MagicMock(return_value=[(mock_doc, 0.5)])
        kb_mock.vector_store = mock_vs

        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]) as mock_disc, \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "test"}
            result = await svc.generate_plan("Test login", enable_rag=True)
            assert "prd.md" in result["sources"]

    @pytest.mark.asyncio
    async def test_rag_retrieval_failure_is_graceful(self, _patch_externals):
        """A RAG retrieval failure should degrade gracefully without interrupting the main flow."""
        kb_mock = _patch_externals["kb"]
        kb_mock.enabled = True
        mock_vs = MagicMock()
        mock_vs.similarity_search_with_score = MagicMock(side_effect=Exception("Vector DB connection failed"))
        kb_mock.vector_store = mock_vs

        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]) as mock_disc, \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "test"}
            result = await svc.generate_plan("Test exception handling", enable_rag=True)
            # A RAG failure should not raise an exception.
            assert "error" not in result
            assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_with_target_url_dispatches_scout(self, _patch_externals):
        """Call ScoutAgent when a URL is provided."""
        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]) as mock_disc, \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca, \
             patch("agents.scout_agent.ScoutAgent") as mock_scout:
            mock_ca.analyze.return_value = {"strategy": "VERIFICATION", "reasoning": "test"}
            mock_scout.scout = AsyncMock(return_value={
                "status": "success",
                "title": "Baidu",
                "visible_text": "Search field",
                "interactive_summary": "button, input"
            })
            result = await svc.generate_plan("Test Baidu search", target_url="https://baidu.com")
            mock_scout.scout.assert_called_once_with("https://baidu.com")

    @pytest.mark.asyncio
    async def test_scout_failure_is_graceful(self, _patch_externals):
        """A Scout failure should not prevent plan generation."""
        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]) as mock_disc, \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca, \
             patch("agents.scout_agent.ScoutAgent") as mock_scout:
            mock_ca.analyze.return_value = {"strategy": "VERIFICATION", "reasoning": "test"}
            mock_scout.scout = AsyncMock(side_effect=Exception("Scout timed out"))
            result = await svc.generate_plan("Test", target_url="https://example.com")
            # Do not raise an exception.
            assert "test_cases" in result

    @pytest.mark.asyncio
    async def test_parallel_step_generation(self, _patch_externals):
        """Generate steps for multiple scenarios concurrently."""
        svc = _make_service()
        scenarios = [
            {"name": "Scenario A", "description": "Description A", "priority": "P0", "dimension": "Core workflow", "precondition": "", "test_data": []},
            {"name": "Scenario B", "description": "Description B", "priority": "P1", "dimension": "Error workflow", "precondition": "", "test_data": []},
        ]
        steps_a = [{"action": "goto", "target": "https://example.com"}]
        steps_b = [{"action": "click", "target": "button"}]

        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=scenarios), \
             patch.object(svc, "_generate_steps_for_scenario", new_callable=AsyncMock, side_effect=[steps_a, steps_b]), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "test"}
            result = await svc.generate_plan("Test functionality", enable_rag=False)
            assert len(result["test_cases"]) == 2
            assert result["test_cases"][0]["scenario"] == "Scenario A"
            assert result["test_cases"][0]["priority"] == "P0"
            assert result["test_cases"][1]["scenario"] == "Scenario B"
            assert result["coverage_summary"]["total_scenarios"] == 2
            assert result["coverage_summary"]["by_priority"]["P0"] == 1
            assert "Core workflow" in result["coverage_summary"]["dimensions_covered"]

    @pytest.mark.asyncio
    async def test_step_generation_error_is_isolated(self, _patch_externals):
        """Step generation failure for one scenario should not affect other scenarios."""
        svc = _make_service()
        scenarios = [
            {"name": "Successful scenario", "description": "ok", "priority": "P0", "dimension": "Core", "precondition": "", "test_data": []},
            {"name": "Failed scenario", "description": "fail", "priority": "P1", "dimension": "Boundary", "precondition": "", "test_data": []},
        ]

        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=scenarios), \
             patch.object(svc, "_generate_steps_for_scenario", new_callable=AsyncMock, 
                          side_effect=[[{"action": "click"}], Exception("LLM timed out")]), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "test"}
            result = await svc.generate_plan("Test", enable_rag=False)
            # Only one scenario succeeds.
            assert len(result["test_cases"]) == 1
            assert result["test_cases"][0]["scenario"] == "Successful scenario"

    @pytest.mark.asyncio
    async def test_step_generation_error_uses_local_fallback(self, _patch_externals):
        """Use local fallback steps when the URL is known and step generation fails."""
        svc = _make_service()
        scenarios = [
            {"name": "首页检查", "description": "确认登录入口存在", "priority": "P0", "dimension": "核心", "precondition": "", "test_data": []},
        ]

        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=scenarios), \
             patch.object(svc, "_generate_steps_for_scenario", new_callable=AsyncMock, side_effect=Exception("LLM 403")), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca, \
             patch("agents.scout_agent.ScoutAgent") as mock_scout:
            mock_ca.analyze.return_value = {"strategy": "VERIFICATION", "reasoning": "test"}
            mock_scout.scout = AsyncMock(return_value={
                "status": "success",
                "title": "示例项目管理系统",
                "visible_text": "账号密码登录 登录",
                "interactive_summary": "[button] 登录, [text] 账号",
            })
            result = await svc.generate_plan("访问首页并检查登录入口", target_url="http://127.0.0.1:81")

        assert len(result["test_cases"]) == 1
        steps = result["test_cases"][0]["steps"]
        assert steps[0]["action"] == "goto"
        assert steps[0]["target"] == "http://127.0.0.1:81"
        assert steps[1]["action"] == "assert"
        assert steps[1]["target"] == "示例项目管理系统"

    @pytest.mark.asyncio
    async def test_probe_mode_returns_local_minimal_plan(self, _patch_externals):
        svc = _make_service()

        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock) as mock_discover:
            result = await svc.generate_plan(
                "打开登录页，不要登录，不要输入，只验证可访问性",
                enable_rag=False,
                target_url="https://example.com/login",
                execution_mode="probe",
                interaction_policy="read_only",
            )

        mock_discover.assert_not_called()
        assert len(result["test_cases"]) == 1
        steps = result["test_cases"][0]["steps"]
        assert [step["action"] for step in steps] == ["goto", "wait", "screenshot"]
        assert result["coverage_summary"]["dimensions_covered"] == ["Read-only Probe"]

    def test_build_fallback_steps_expands_login_business_flow(self, _patch_externals):
        svc = _make_service()

        requirement = (
            "使用账号 example-org 和密码 123456 登录，先确认重新登录弹窗，"
            "勾选我已阅读并同意用户协议，选择 北京市 -> 朝阳区综合养老服务站，"
            "进入 统一商品服务中心 -> 服务商品中心，"
            "校验总商品20、服务商品13、在售16、下架3、草稿1、待审核5，"
            "并确认 SERVICE 和分类树入口。"
        )
        scenario = {"name": "服务商品中心", "description": "验证登录后业务统计"}

        steps = svc._build_fallback_steps(
            requirement=requirement,
            scenario=scenario,
            target_url="http://127.0.0.1:81/qyLogin",
            scout_result={"title": "示例项目管理系统"},
        )

        targets = [(step["action"], step["target"], step["value"]) for step in steps]

        assert ("goto", "http://127.0.0.1:81/qyLogin", "") in targets
        assert ("click", "重新登录", "") in targets
        assert ("fill", "用户名", "example-org") in targets
        assert ("fill", "密码", "123456") in targets
        assert ("click", "我已阅读并同意用户协议", "") in targets
        assert ("click", "登录", "") in targets
        assert ("click", "北京市", "") in targets
        assert ("click", "朝阳区综合养老服务站", "") in targets
        assert ("assert", "商品总数", "") in targets
        assert ("assert", "20", "") in targets
        assert ("assert", "分类名称", "") in targets
        assert ("assert", "SERVICE", "") in targets
    def test_build_fallback_steps_skips_site_clicks_for_authenticated_module_entry(self, _patch_externals):
        svc = _make_service()

        requirement = (
            "在已登录且站点为北京市朝阳区综合养老服务站的情况下，"
            "测试统一商品服务中心-服务商品中心，"
            "校验商品总数20、服务商品13。"
        )
        scenario = {"name": "服务商品中心", "description": "验证模块页"}

        steps = svc._build_fallback_steps(
            requirement=requirement,
            scenario=scenario,
            target_url="http://127.0.0.1:81/unifiedGoodService/uniProductService",
            scout_result={"title": "示例项目管理系统"},
        )

        targets = [(step["action"], step["target"], step["value"]) for step in steps]

        assert ("goto", "http://127.0.0.1:81/unifiedGoodService/uniProductService", "") in targets
        assert ("click", "北京市", "") not in targets
        assert ("click", "朝阳区综合养老服务站", "") not in targets
        assert ("assert", "商品总数", "") in targets
        assert ("assert", "服务商品", "") in targets
        assert ("click", "分类管理", "") in targets

    def test_extract_site_targets_supports_authenticated_context(self, _patch_externals):
        svc = _make_service()

        targets = svc._extract_site_targets(
            "在已登录且已切换到北京市-朝阳区综合养老服务站的上下文中，进入统一商品服务中心-服务商品中心。"
        )

        assert targets == ["北京市", "朝阳区综合养老服务站"]

    def test_should_skip_site_selection_for_authenticated_station_context(self, _patch_externals):
        svc = _make_service()

        assert svc._should_skip_site_selection(
            "在已登录且已切换到北京市-朝阳区综合养老服务站的上下文中，进入统一商品服务中心-服务商品中心。",
            "http://127.0.0.1:81/unifiedGoodService/uniProductService",
        ) is True

    def test_should_skip_login_steps_for_authenticated_module_entry(self, _patch_externals):
        svc = _make_service()

        assert svc._should_skip_login_steps(
            "在已登录且已切换到北京市-朝阳区综合养老服务站的上下文中，进入统一商品服务中心-服务商品中心。"
            "【会话预认证已完成：当前已登录且已切换到北京市-528。除非需求明确要求重新登录或切换站点，否则不要再执行登录、点击城市/站点或切换站点动作。】",
            "http://127.0.0.1:81/unifiedGoodService/uniProductService",
        ) is True

        assert svc._should_skip_login_steps(
            "使用账号 example-org 和密码 123456 登录系统。",
            "http://127.0.0.1:81/qyLogin",
        ) is False

    @pytest.mark.asyncio
    async def test_generate_plan_prunes_redundant_authenticated_site_clicks(self, _patch_externals):
        svc = _make_service()
        requirement = (
            "在已登录且已切换到北京市-朝阳区综合养老服务站的上下文中，"
            "进入统一商品服务中心-服务商品中心并校验搜索能力。"
        )
        scenarios = [
            {"name": "服务商品中心", "description": "验证模块页", "priority": "P0", "dimension": "核心流程", "precondition": "", "test_data": []},
        ]
        generated_steps = [
            {"action": "goto", "target": "http://127.0.0.1:81/unifiedGoodService/uniProductService", "value": ""},
            {"action": "click", "target": "北京市", "value": ""},
            {"action": "click", "target": "朝阳区综合养老服务站", "value": ""},
            {"action": "wait", "target": "2", "value": ""},
            {"action": "click", "target": "搜索", "value": ""},
        ]

        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=scenarios), \
             patch.object(svc, "_generate_steps_for_scenario", new_callable=AsyncMock, return_value=generated_steps), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "VERIFICATION", "reasoning": "authenticated module entry"}
            result = await svc.generate_plan(
                requirement,
                enable_rag=False,
                target_url="http://127.0.0.1:81/unifiedGoodService/uniProductService",
            )

        steps = result["test_cases"][0]["steps"]
        targets = [(step["action"], step["target"]) for step in steps]
        assert ("click", "北京市") not in targets
        assert ("click", "朝阳区综合养老服务站") not in targets
        assert ("wait", "2") not in targets
        assert ("click", "搜索") in targets

    @pytest.mark.asyncio
    async def test_generate_plan_prunes_redundant_authenticated_login_steps(self, _patch_externals):
        svc = _make_service()
        requirement = (
            "在已登录且已切换到北京市-朝阳区综合养老服务站的上下文中，"
            "进入统一商品服务中心-服务商品中心并校验搜索能力。"
        )
        scenarios = [
            {"name": "服务商品中心", "description": "验证模块页", "priority": "P0", "dimension": "核心流程", "precondition": "", "test_data": []},
        ]
        generated_steps = [
            {"action": "goto", "target": "http://127.0.0.1:81/unifiedGoodService/uniProductService", "value": ""},
            {"action": "click", "target": "重新登录", "value": ""},
            {"action": "click", "target": "登录", "value": ""},
            {"action": "wait", "target": "2", "value": ""},
            {"action": "click", "target": "搜索", "value": ""},
        ]

        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=scenarios), \
             patch.object(svc, "_generate_steps_for_scenario", new_callable=AsyncMock, return_value=generated_steps), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "VERIFICATION", "reasoning": "authenticated module entry"}
            result = await svc.generate_plan(
                requirement,
                enable_rag=False,
                target_url="http://127.0.0.1:81/unifiedGoodService/uniProductService",
            )

        steps = result["test_cases"][0]["steps"]
        targets = [(step["action"], step["target"]) for step in steps]
        assert ("click", "重新登录") not in targets
        assert ("click", "登录") not in targets
        assert ("wait", "2") not in targets
        assert ("click", "搜索") in targets

    def test_extract_product_search_keyword_supports_quoted_text(self, _patch_externals):
        svc = _make_service()

        assert svc._extract_product_search_keyword("搜索“老人陪护服务”并断言结果出现") == "老人陪护服务"



# ---------------------------------------------------------------------------
# _discover_scenarios tests
# ---------------------------------------------------------------------------
class TestDiscoverScenarios:
    """Test _discover_scenarios() scenario discovery."""

    @pytest.mark.asyncio
    async def test_successful_discovery(self, _patch_externals):
        """The LLM returns a valid scenario list."""
        svc = _make_service()
        expected_scenarios = [
            {"name": "Successful login", "description": "Log in with the correct password", "priority": "P0", "dimension": "Core", "precondition": "", "test_data": []}
        ]
        # Mock LangChain chain
        mock_chain = MagicMock()
        mock_chain.__or__ = MagicMock(return_value=mock_chain)
        mock_chain.ainvoke = AsyncMock(return_value=expected_scenarios)

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser") as mock_jp:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            # Mock the prompt | llm | parser chain.
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = await svc._discover_scenarios("Test login", "Knowledge context")
            assert result == expected_scenarios
            _patch_externals["get_llm"].assert_called_once_with("planner")

    @pytest.mark.asyncio
    async def test_discovery_failure_returns_default(self, _patch_externals):
        """Return a default scenario when the LLM call fails."""
        svc = _make_service()
        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(
                return_value=MagicMock(ainvoke=AsyncMock(side_effect=Exception("LLM unavailable")))
            )
            result = await svc._discover_scenarios("Test", "")
            assert len(result) == 1
            assert result[0]["name"] == "Default Scenario"
            assert result[0]["priority"] == "P1"

    @pytest.mark.asyncio
    async def test_url_hint_injected(self, _patch_externals):
        """Inject a URL hint into the prompt when target_url is provided."""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=[])

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            await svc._discover_scenarios("Test Baidu", "", target_url="https://baidu.com")
            # Verify that the ainvoke arguments include url_hint.
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "baidu.com" in call_args.get("url_hint", "")


# ---------------------------------------------------------------------------
# _generate_steps tests
# ---------------------------------------------------------------------------
class TestGenerateSteps:
    """Test the core _generate_steps() logic."""

    @pytest.mark.asyncio
    async def test_successful_generation(self, _patch_externals):
        """Generate steps normally."""
        svc = _make_service()
        expected_steps = [
            {"action": "goto", "target": "https://example.com", "value": ""},
            {"action": "fill", "target": "#username", "value": "admin"},
        ]
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=expected_steps)

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            scenario = {"name": "Login", "description": "Log in with the correct password"}
            result = await svc._generate_steps(scenario, "")
            assert result == expected_steps

    @pytest.mark.asyncio
    async def test_generation_with_url_rule(self, _patch_externals):
        """Inject URL rules when target_url is provided."""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=[])

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            scenario = {"name": "Search", "description": "Test search functionality"}
            await svc._generate_steps(scenario, "", target_url="https://baidu.com")
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "baidu.com" in call_args.get("url_rule", "")

    @pytest.mark.asyncio
    async def test_generation_failure_raises(self, _patch_externals):
        """Step generation failure should raise an exception for gather to capture."""
        svc = _make_service()
        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(
                return_value=MagicMock(ainvoke=AsyncMock(side_effect=Exception("Parsing failed")))
            )
            with pytest.raises(Exception, match="Parsing failed"):
                await svc._generate_steps({"name": "x", "description": "y"}, "")


# ---------------------------------------------------------------------------
# _generate_steps_for_scenario tests
# ---------------------------------------------------------------------------
class TestGenerateStepsForScenario:
    """Test the _generate_steps_for_scenario() wrapper."""

    @pytest.mark.asyncio
    async def test_delegates_to_generate_steps(self, _patch_externals):
        """Delegate to _generate_steps and return its result."""
        svc = _make_service()
        expected = [{"action": "click"}]
        with patch.object(svc, "_generate_steps", new_callable=AsyncMock, return_value=expected):
            result = await svc._generate_steps_for_scenario(
                {"name": "Test", "description": "d"}, "ctx", "https://x.com"
            )
            assert result == expected
            svc._generate_steps.assert_called_once_with(
                {"name": "Test", "description": "d"}, "ctx", "https://x.com"
            )


# ---------------------------------------------------------------------------
# plan_next_step tests
# ---------------------------------------------------------------------------
class TestPlanNextStep:
    """Test plan_next_step() reasoning."""

    def _make_llm_response(self, data: dict):
        """Build an LLM Message response with a JSON string as its content."""
        import json
        msg = MagicMock()
        msg.content = json.dumps(data, ensure_ascii=False)
        return msg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("target_url", ["(Not navigated)", "（未导航）", "https://example.com"])
    async def test_failed_reasoning_never_navigates_to_a_sentinel(self, _patch_externals, target_url):
        """Only a real URL may become the initial navigation fallback."""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=ValueError("Model unavailable"))
        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            mock_pt.from_template.return_value.__or__.return_value = mock_chain
            result = await svc.plan_next_step(goal="Open the target page", page_state={"url": target_url}, history=[])
        assert mock_chain.ainvoke.await_count == 3
        assert result["action"] == ("goto" if target_url == "https://example.com" else "error")
        if result["action"] == "goto":
            assert result["target"] == target_url

    @pytest.mark.asyncio
    async def test_successful_planning(self, _patch_externals):
        """Infer the next step normally."""
        svc = _make_service()
        expected = {"thinking": "Click the Login button", "action": "click", "target": "[1]", "value": ""}
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=self._make_llm_response(expected))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            result = await svc.plan_next_step(
                goal="Login test",
                page_state={"url": "https://example.com", "title": "Login page", "interactive_elements": "[1] button \"Login\"", "visible_text": "Enter a username"},
                history=[]
            )
            assert result["action"] == "click"
            assert result["target"] == "[1]"

    @pytest.mark.asyncio
    async def test_with_history(self, _patch_externals):
        """Build the history summary correctly when prior actions are present."""
        svc = _make_service()
        expected = {"thinking": "The username is entered; enter the password next", "action": "fill", "target": "[2]", "value": "123456"}
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=self._make_llm_response(expected))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            history = [
                {"action": "goto", "target": "https://example.com", "status": "success", "message": "Navigation succeeded"},
                {"action": "fill", "target": "#username", "status": "success", "message": "Entered admin"},
            ]
            result = await svc.plan_next_step(
                goal="Login test",
                page_state={"url": "https://example.com/login", "title": "Login", "interactive_elements": "[2] input (type='password')", "visible_text": "Password"},
                history=history
            )
            # Verify that the ainvoke arguments include history.
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "goto" in call_args.get("history", "")
            assert "fill" in call_args.get("history", "")

    @pytest.mark.asyncio
    async def test_empty_page_state(self, _patch_externals):
        """Use defaults when page_state fields are missing."""
        svc = _make_service()
        expected = {"thinking": "Page not loaded", "action": "goto", "target": "https://x.com", "value": ""}
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=self._make_llm_response(expected))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            result = await svc.plan_next_step(
                goal="Test",
                page_state={},  # Empty page_state
                history=[]
            )
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "(Page not loaded or no interactive elements)" in call_args["snapshot"]
            assert "URL: (Unknown)" in call_args["snapshot"]

    @pytest.mark.asyncio
    async def test_llm_failure_returns_error_action(self, _patch_externals):
        """Return an error action when LLM reasoning fails."""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("API 429 Too Many Requests"))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            # Pass nonempty history to avoid the goto fallback path.
            result = await svc.plan_next_step(
                goal="Test",
                page_state={"url": "x", "title": "t"},
                history=[{"action": "goto", "target": "x", "status": "success", "message": "ok"}]
            )
            assert result["action"] == "error"
            assert "Reasoning failed" in result["thinking"]

    @pytest.mark.asyncio
    async def test_history_truncation(self, _patch_externals):
        """Retain only the 20 most recent steps when history exceeds 20 steps."""
        svc = _make_service()
        expected = {"thinking": "", "action": "done", "target": "", "value": ""}
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=self._make_llm_response(expected))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            # Create a 25-step history.
            long_history = [
                {"action": f"step_{i}", "target": f"t{i}", "status": "success", "message": f"msg{i}"}
                for i in range(25)
            ]
            await svc.plan_next_step(goal="Test", page_state={}, history=long_history)
            call_args = mock_chain.ainvoke.call_args[0][0]
            # Only step_5 through step_24 should remain (the last 20 steps).
            assert "step_5" in call_args["history"]
            assert "step_24" in call_args["history"]
            # step_0 through step_4 should be absent.
            assert "step_0" not in call_args["history"]

    @pytest.mark.asyncio
    async def test_markdown_codeblock_json(self, _patch_externals):
        """Parse LLM JSON wrapped in a Markdown code block."""
        svc = _make_service()
        msg = MagicMock()
        msg.content = '```json\n{"thinking": "Analysis complete", "action": "click", "target": "[3]", "value": ""}\n```'
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=msg)

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            result = await svc.plan_next_step(
                goal="Test", page_state={"url": "x"}, history=[]
            )
            assert result["action"] == "click"
            assert result["target"] == "[3]"


# ---------------------------------------------------------------------------
# semantic_verify tests
# ---------------------------------------------------------------------------
class TestSemanticVerify:
    """Test semantic_verify() validation."""

    def test_verify_pass(self, _patch_externals):
        """Verification passes."""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.invoke = MagicMock(return_value={"passed": True, "reason": "The page contains the expected content"})

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = svc.semantic_verify("The page should display a welcome message", "Welcome back, admin!")
            assert result["passed"] is True
            assert result["reason"] == "The page contains the expected content"

    def test_verify_fail(self, _patch_externals):
        """Verification fails."""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.invoke = MagicMock(return_value={"passed": False, "reason": "The page has no error message"})

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = svc.semantic_verify("An incorrect-password message should appear", "Login successful")
            assert result["passed"] is False

    def test_dict_page_context(self, _patch_externals):
        """Extract url and visible_text correctly when page_context is a dictionary."""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.invoke = MagicMock(return_value={"passed": True, "reason": "ok"})

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = svc.semantic_verify(
                "The home page works",
                {"url": "https://example.com", "visible_text": "Welcome"}
            )
            call_args = mock_chain.invoke.call_args[0][0]
            assert call_args["url"] == "https://example.com"
            assert "Welcome" in call_args["visible_text"]

    def test_llm_failure_returns_false(self, _patch_externals):
        """Return passed=False when the LLM call fails."""
        svc = _make_service()
        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(
                return_value=MagicMock(invoke=MagicMock(side_effect=Exception("API error")))
            )
            result = svc.semantic_verify("Check the content", "Page text")
            assert result["passed"] is False
            assert "Semantic verification error" in result["reason"]
            _patch_externals["get_llm"].assert_called_once_with("executor")

    def test_long_page_context_is_truncated(self, _patch_externals):
        """Truncate page text longer than 2000 characters."""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.invoke = MagicMock(return_value={"passed": True, "reason": "ok"})

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            long_text = "x" * 5000
            svc.semantic_verify("Check", long_text)
            call_args = mock_chain.invoke.call_args[0][0]
            assert len(call_args["visible_text"]) == 2000


# ---------------------------------------------------------------------------
# Module-level singleton tests
# ---------------------------------------------------------------------------
class TestModuleSingleton:
    """Test the module-level planner_service singleton."""

    def test_singleton_instance_exists(self, _patch_externals):
        """The module-level planner_service instance should exist."""
        from services.planner_service import planner_service
        assert planner_service is not None

    def test_singleton_is_correct_type(self, _patch_externals):
        """planner_service should be a TestGenerationService instance."""
        from services.planner_service import planner_service, TestGenerationService
        assert isinstance(planner_service, TestGenerationService)

    def test_build_fallback_steps_for_service_product_center_module(self, _patch_externals):
        svc = _make_service()

        requirement = (
            "在已登录且站点为 北京市 朝阳区综合养老服务站 的情况下，"
            "测试 统一商品服务中心 - 服务商品中心，"
            "校验总商品20、服务商品13、在售16、下架3、草稿1，"
            "搜索商品名称 老人陪护服务，并检查分类管理弹窗。"
        )
        scenario = {"name": "服务商品中心模块", "description": "验证模块级渲染与搜索"}

        steps = svc._build_fallback_steps(
            requirement=requirement,
            scenario=scenario,
            target_url="http://127.0.0.1:81/unifiedGoodService/uniProductService",
            scout_result={"title": "服务商品中心"},
        )

        targets = [(step["action"], step["target"], step["value"]) for step in steps]

        assert ("goto", "http://127.0.0.1:81/unifiedGoodService/uniProductService", "") in targets
        assert ("assert", "商品总数", "") in targets
        assert ("assert", "上架商品", "") in targets
        assert ("fill", "商品名称", "老人陪护服务") in targets
        assert ("click", "搜索", "") in targets
        assert ("assert", "老人陪护服务", "") in targets
        assert ("click", "分类管理", "") in targets
        assert ("assert", "新增一级分类", "") in targets

