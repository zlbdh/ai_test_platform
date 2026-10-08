"""
TestGenerationService (planner_service) 单元测试
覆盖: generate_plan 全流程, _discover_scenarios, _generate_steps,
      plan_next_step 单步推理, semantic_verify 语义验证
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
import asyncio




# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _patch_externals():
    """Mock planner_service 的所有重量级依赖 (LLM, KB, Scout, ContextAnalyzer)"""
    with patch("services.planner_service.get_llm_for_role") as mock_get_llm, \
         patch("services.planner_service.kb") as mock_kb, \
         patch("services.planner_service.Config") as mock_config:
        # 默认 LLM mock
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        # 默认 KB mock
        mock_kb.enabled = False
        mock_kb.initialize = MagicMock()
        # 默认 Config mock
        mock_config.PLANNER_MODEL = None
        yield {
            "get_llm": mock_get_llm,
            "llm": mock_llm,
            "kb": mock_kb,
            "config": mock_config,
        }


def _make_service():
    """创建一个干净的 TestGenerationService 实例"""
    from services.planner_service import TestGenerationService
    return TestGenerationService()


# ---------------------------------------------------------------------------
# generate_plan 测试
# ---------------------------------------------------------------------------
class TestGeneratePlan:
    """测试 generate_plan() 全流程"""

    @pytest.mark.asyncio
    async def test_empty_requirement_returns_error(self, _patch_externals):
        """空需求应直接返回错误"""
        svc = _make_service()
        result = await svc.generate_plan("")
        assert result["error"] == "Requirement cannot be empty"
        assert result["test_cases"] == []
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_whitespace_requirement_returns_error(self, _patch_externals):
        """纯空格需求应直接返回错误"""
        svc = _make_service()
        result = await svc.generate_plan("   ")
        assert result["error"] == "Requirement cannot be empty"

    @pytest.mark.asyncio
    async def test_rag_disabled(self, _patch_externals):
        """RAG 禁用时不应调用知识库"""
        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "No URL"}
            result = await svc.generate_plan("测试登录", enable_rag=False)
            _patch_externals["kb"].initialize.assert_not_called()
            assert result["test_cases"] == []
            assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_rag_enabled_with_kb(self, _patch_externals):
        """RAG 启用且 KB 可用时应检索知识"""
        kb_mock = _patch_externals["kb"]
        kb_mock.enabled = True
        # 模拟向量搜索结果
        mock_doc = MagicMock()
        mock_doc.page_content = "测试知识文档内容"
        mock_doc.metadata = {"filename": "prd.md"}
        mock_vs = MagicMock()
        mock_vs.similarity_search_with_score = MagicMock(return_value=[(mock_doc, 0.5)])
        kb_mock.vector_store = mock_vs

        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]) as mock_disc, \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "test"}
            result = await svc.generate_plan("测试登录", enable_rag=True)
            assert "prd.md" in result["sources"]

    @pytest.mark.asyncio
    async def test_rag_retrieval_failure_is_graceful(self, _patch_externals):
        """RAG 检索失败时应优雅降级，不影响主流程"""
        kb_mock = _patch_externals["kb"]
        kb_mock.enabled = True
        mock_vs = MagicMock()
        mock_vs.similarity_search_with_score = MagicMock(side_effect=Exception("Vector DB 连接失败"))
        kb_mock.vector_store = mock_vs

        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]) as mock_disc, \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "test"}
            result = await svc.generate_plan("测试异常处理", enable_rag=True)
            # 不应因 RAG 失败而抛异常
            assert "error" not in result
            assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_with_target_url_dispatches_scout(self, _patch_externals):
        """提供 URL 时应调用 ScoutAgent"""
        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]) as mock_disc, \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca, \
             patch("agents.scout_agent.ScoutAgent") as mock_scout:
            mock_ca.analyze.return_value = {"strategy": "VERIFICATION", "reasoning": "test"}
            mock_scout.scout = AsyncMock(return_value={
                "status": "success",
                "title": "百度",
                "visible_text": "搜索框",
                "interactive_summary": "button, input"
            })
            result = await svc.generate_plan("测试百度搜索", target_url="https://baidu.com")
            mock_scout.scout.assert_called_once_with("https://baidu.com")

    @pytest.mark.asyncio
    async def test_scout_failure_is_graceful(self, _patch_externals):
        """Scout 失败不应影响计划生成"""
        svc = _make_service()
        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=[]) as mock_disc, \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca, \
             patch("agents.scout_agent.ScoutAgent") as mock_scout:
            mock_ca.analyze.return_value = {"strategy": "VERIFICATION", "reasoning": "test"}
            mock_scout.scout = AsyncMock(side_effect=Exception("Scout 超时"))
            result = await svc.generate_plan("测试", target_url="https://example.com")
            # 不应抛异常
            assert "test_cases" in result

    @pytest.mark.asyncio
    async def test_parallel_step_generation(self, _patch_externals):
        """多个场景应并行生成步骤"""
        svc = _make_service()
        scenarios = [
            {"name": "场景A", "description": "描述A", "priority": "P0", "dimension": "核心流程", "precondition": "", "test_data": []},
            {"name": "场景B", "description": "描述B", "priority": "P1", "dimension": "异常流程", "precondition": "", "test_data": []},
        ]
        steps_a = [{"action": "goto", "target": "https://example.com"}]
        steps_b = [{"action": "click", "target": "button"}]

        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=scenarios), \
             patch.object(svc, "_generate_steps_for_scenario", new_callable=AsyncMock, side_effect=[steps_a, steps_b]), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "test"}
            result = await svc.generate_plan("测试功能", enable_rag=False)
            assert len(result["test_cases"]) == 2
            assert result["test_cases"][0]["scenario"] == "场景A"
            assert result["test_cases"][0]["priority"] == "P0"
            assert result["test_cases"][1]["scenario"] == "场景B"
            assert result["coverage_summary"]["total_scenarios"] == 2
            assert result["coverage_summary"]["by_priority"]["P0"] == 1
            assert "核心流程" in result["coverage_summary"]["dimensions_covered"]

    @pytest.mark.asyncio
    async def test_step_generation_error_is_isolated(self, _patch_externals):
        """单个场景步骤生成失败不应影响其他场景"""
        svc = _make_service()
        scenarios = [
            {"name": "成功场景", "description": "ok", "priority": "P0", "dimension": "核心", "precondition": "", "test_data": []},
            {"name": "失败场景", "description": "fail", "priority": "P1", "dimension": "边界", "precondition": "", "test_data": []},
        ]

        with patch.object(svc, "_discover_scenarios", new_callable=AsyncMock, return_value=scenarios), \
             patch.object(svc, "_generate_steps_for_scenario", new_callable=AsyncMock, 
                          side_effect=[[{"action": "click"}], Exception("LLM 超时")]), \
             patch("services.context_analyzer.ContextAnalyzer") as mock_ca:
            mock_ca.analyze.return_value = {"strategy": "TDD", "reasoning": "test"}
            result = await svc.generate_plan("测试", enable_rag=False)
            # 只有一个场景成功
            assert len(result["test_cases"]) == 1
            assert result["test_cases"][0]["scenario"] == "成功场景"

    @pytest.mark.asyncio
    async def test_step_generation_error_uses_local_fallback(self, _patch_externals):
        """当 URL 已知且步骤生成失败时，应退回到本地 fallback 步骤"""
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
# _discover_scenarios 测试
# ---------------------------------------------------------------------------
class TestDiscoverScenarios:
    """测试 _discover_scenarios() 场景发现"""

    @pytest.mark.asyncio
    async def test_successful_discovery(self, _patch_externals):
        """LLM 正常返回场景列表"""
        svc = _make_service()
        expected_scenarios = [
            {"name": "登录成功", "description": "用正确密码登录", "priority": "P0", "dimension": "核心", "precondition": "", "test_data": []}
        ]
        # Mock LangChain chain
        mock_chain = MagicMock()
        mock_chain.__or__ = MagicMock(return_value=mock_chain)
        mock_chain.ainvoke = AsyncMock(return_value=expected_scenarios)

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser") as mock_jp:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            # 模拟 prompt | llm | parser 链
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = await svc._discover_scenarios("测试登录", "知识上下文")
            assert result == expected_scenarios
            _patch_externals["get_llm"].assert_called_once_with("planner")

    @pytest.mark.asyncio
    async def test_discovery_failure_returns_default(self, _patch_externals):
        """LLM 调用失败应返回默认场景"""
        svc = _make_service()
        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(
                return_value=MagicMock(ainvoke=AsyncMock(side_effect=Exception("LLM 不可达")))
            )
            result = await svc._discover_scenarios("测试", "")
            assert len(result) == 1
            assert result[0]["name"] == "Default Scenario"
            assert result[0]["priority"] == "P1"

    @pytest.mark.asyncio
    async def test_url_hint_injected(self, _patch_externals):
        """提供 target_url 时应在 prompt 中注入 URL 提示"""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=[])

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            await svc._discover_scenarios("测试百度", "", target_url="https://baidu.com")
            # 验证 ainvoke 被调用时传入了包含 url_hint 的参数
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "baidu.com" in call_args.get("url_hint", "")


# ---------------------------------------------------------------------------
# _generate_steps 测试
# ---------------------------------------------------------------------------
class TestGenerateSteps:
    """测试 _generate_steps() 步骤生成核心逻辑"""

    @pytest.mark.asyncio
    async def test_successful_generation(self, _patch_externals):
        """正常生成步骤"""
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

            scenario = {"name": "登录", "description": "用正确密码登录"}
            result = await svc._generate_steps(scenario, "")
            assert result == expected_steps

    @pytest.mark.asyncio
    async def test_generation_with_url_rule(self, _patch_externals):
        """提供 target_url 时应注入 URL 规则"""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=[])

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            scenario = {"name": "搜索", "description": "测试搜索功能"}
            await svc._generate_steps(scenario, "", target_url="https://baidu.com")
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "baidu.com" in call_args.get("url_rule", "")

    @pytest.mark.asyncio
    async def test_generation_failure_raises(self, _patch_externals):
        """步骤生成失败应抛出异常 (供 gather 捕获)"""
        svc = _make_service()
        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(
                return_value=MagicMock(ainvoke=AsyncMock(side_effect=Exception("解析失败")))
            )
            with pytest.raises(Exception, match="解析失败"):
                await svc._generate_steps({"name": "x", "description": "y"}, "")


# ---------------------------------------------------------------------------
# _generate_steps_for_scenario 测试
# ---------------------------------------------------------------------------
class TestGenerateStepsForScenario:
    """测试 _generate_steps_for_scenario() — thin wrapper"""

    @pytest.mark.asyncio
    async def test_delegates_to_generate_steps(self, _patch_externals):
        """应委托给 _generate_steps 并返回其结果"""
        svc = _make_service()
        expected = [{"action": "click"}]
        with patch.object(svc, "_generate_steps", new_callable=AsyncMock, return_value=expected):
            result = await svc._generate_steps_for_scenario(
                {"name": "测试", "description": "d"}, "ctx", "https://x.com"
            )
            assert result == expected
            svc._generate_steps.assert_called_once_with(
                {"name": "测试", "description": "d"}, "ctx", "https://x.com"
            )


# ---------------------------------------------------------------------------
# plan_next_step 测试
# ---------------------------------------------------------------------------
class TestPlanNextStep:
    """测试 plan_next_step() 单步推理"""

    def _make_llm_response(self, data: dict):
        """构造 LLM 返回的 Message 对象（content 为 JSON 字符串）"""
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
        """正常推理下一步"""
        svc = _make_service()
        expected = {"thinking": "需要点击登录按钮", "action": "click", "target": "[1]", "value": ""}
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=self._make_llm_response(expected))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            result = await svc.plan_next_step(
                goal="登录测试",
                page_state={"url": "https://example.com", "title": "登录页", "interactive_elements": "[1] button \"登录\"", "visible_text": "请输入用户名"},
                history=[]
            )
            assert result["action"] == "click"
            assert result["target"] == "[1]"

    @pytest.mark.asyncio
    async def test_with_history(self, _patch_externals):
        """有操作历史时应正确构建历史摘要"""
        svc = _make_service()
        expected = {"thinking": "已输入用户名，需输入密码", "action": "fill", "target": "[2]", "value": "123456"}
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=self._make_llm_response(expected))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            history = [
                {"action": "goto", "target": "https://example.com", "status": "success", "message": "导航成功"},
                {"action": "fill", "target": "#username", "status": "success", "message": "输入admin"},
            ]
            result = await svc.plan_next_step(
                goal="登录测试",
                page_state={"url": "https://example.com/login", "title": "登录", "interactive_elements": "[2] input (type='password')", "visible_text": "密码"},
                history=history
            )
            # 验证 ainvoke 被调用时传入了 history
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "goto" in call_args.get("history", "")
            assert "fill" in call_args.get("history", "")

    @pytest.mark.asyncio
    async def test_empty_page_state(self, _patch_externals):
        """page_state 缺失字段时应使用默认值"""
        svc = _make_service()
        expected = {"thinking": "页面未加载", "action": "goto", "target": "https://x.com", "value": ""}
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=self._make_llm_response(expected))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            result = await svc.plan_next_step(
                goal="测试",
                page_state={},  # 空 page_state
                history=[]
            )
            call_args = mock_chain.ainvoke.call_args[0][0]
            assert "(Page not loaded or no interactive elements)" in call_args["snapshot"]
            assert "URL: (Unknown)" in call_args["snapshot"]

    @pytest.mark.asyncio
    async def test_llm_failure_returns_error_action(self, _patch_externals):
        """LLM 推理失败应返回 error action"""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("API 429 Too Many Requests"))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            # 传入非空 history 以避免 goto 降级路径
            result = await svc.plan_next_step(
                goal="测试",
                page_state={"url": "x", "title": "t"},
                history=[{"action": "goto", "target": "x", "status": "success", "message": "ok"}]
            )
            assert result["action"] == "error"
            assert "Reasoning failed" in result["thinking"]

    @pytest.mark.asyncio
    async def test_history_truncation(self, _patch_externals):
        """超过 20 步的历史应只保留最近 20 步"""
        svc = _make_service()
        expected = {"thinking": "", "action": "done", "target": "", "value": ""}
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=self._make_llm_response(expected))

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            # 创建 25 步历史
            long_history = [
                {"action": f"step_{i}", "target": f"t{i}", "status": "success", "message": f"msg{i}"}
                for i in range(25)
            ]
            await svc.plan_next_step(goal="测试", page_state={}, history=long_history)
            call_args = mock_chain.ainvoke.call_args[0][0]
            # 只应包含 step_5 到 step_24 (最后20步)
            assert "step_5" in call_args["history"]
            assert "step_24" in call_args["history"]
            # step_0 到 step_4 不应出现
            assert "step_0" not in call_args["history"]

    @pytest.mark.asyncio
    async def test_markdown_codeblock_json(self, _patch_externals):
        """LLM 返回 markdown 代码块包裹的 JSON 应能正确解析"""
        svc = _make_service()
        msg = MagicMock()
        msg.content = '```json\n{"thinking": "分析完毕", "action": "click", "target": "[3]", "value": ""}\n```'
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=msg)

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt:
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)

            result = await svc.plan_next_step(
                goal="测试", page_state={"url": "x"}, history=[]
            )
            assert result["action"] == "click"
            assert result["target"] == "[3]"


# ---------------------------------------------------------------------------
# semantic_verify 测试
# ---------------------------------------------------------------------------
class TestSemanticVerify:
    """测试 semantic_verify() 语义验证"""

    def test_verify_pass(self, _patch_externals):
        """验证通过"""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.invoke = MagicMock(return_value={"passed": True, "reason": "页面包含预期内容"})

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = svc.semantic_verify("页面应显示欢迎字样", "欢迎回来，admin！")
            assert result["passed"] is True
            assert result["reason"] == "页面包含预期内容"

    def test_verify_fail(self, _patch_externals):
        """验证失败"""
        svc = _make_service()
        mock_chain = MagicMock()
        mock_chain.invoke = MagicMock(return_value={"passed": False, "reason": "页面无错误提示"})

        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = svc.semantic_verify("应提示密码错误", "登录成功")
            assert result["passed"] is False

    def test_dict_page_context(self, _patch_externals):
        """page_context 为 dict 时应正确解析 url 和 visible_text"""
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
                "首页正常",
                {"url": "https://example.com", "visible_text": "欢迎"}
            )
            call_args = mock_chain.invoke.call_args[0][0]
            assert call_args["url"] == "https://example.com"
            assert "欢迎" in call_args["visible_text"]

    def test_llm_failure_returns_false(self, _patch_externals):
        """LLM 调用失败应返回 passed=False"""
        svc = _make_service()
        with patch("services.planner_service.ChatPromptTemplate") as mock_pt, \
             patch("services.planner_service.JsonOutputParser"):
            mock_prompt = MagicMock()
            mock_pt.from_template.return_value = mock_prompt
            mock_prompt.__or__ = MagicMock(return_value=MagicMock())
            mock_prompt.__or__.return_value.__or__ = MagicMock(
                return_value=MagicMock(invoke=MagicMock(side_effect=Exception("API 错误")))
            )
            result = svc.semantic_verify("检查内容", "页面文本")
            assert result["passed"] is False
            assert "Semantic verification error" in result["reason"]
            _patch_externals["get_llm"].assert_called_once_with("executor")

    def test_long_page_context_is_truncated(self, _patch_externals):
        """超长页面文本应被截断到 2000 字符"""
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
            svc.semantic_verify("检查", long_text)
            call_args = mock_chain.invoke.call_args[0][0]
            assert len(call_args["visible_text"]) == 2000


# ---------------------------------------------------------------------------
# 模块级单例测试
# ---------------------------------------------------------------------------
class TestModuleSingleton:
    """测试模块级 planner_service 单例"""

    def test_singleton_instance_exists(self, _patch_externals):
        """模块级 planner_service 实例应存在"""
        from services.planner_service import planner_service
        assert planner_service is not None

    def test_singleton_is_correct_type(self, _patch_externals):
        """planner_service 应是 TestGenerationService 的实例"""
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

