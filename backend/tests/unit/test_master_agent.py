"""
MasterAgent 单元测试
覆盖: plan_test, _extract_agents, _extract_steps, generate_report,
       _calculate_success_rate, _generate_recommendations
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 测试 _extract_agents —— 纯逻辑，不需要 mock LLM
# ---------------------------------------------------------------------------
class TestExtractAgents:
    """测试 MasterAgent._extract_agents 关键词匹配逻辑"""

    @pytest.fixture(autouse=True)
    def _agent(self):
        with patch("agents.master_agent.get_llm") as mock_llm:
            mock_llm.return_value = MagicMock()
            from agents.master_agent import MasterAgent
            self.agent = MasterAgent()

    def test_ui_keywords(self):
        for text in ["测试UI界面", "前端功能验证", "界面截图对比"]:
            assert "ui_agent" in self.agent._extract_agents(text)

    def test_api_keywords(self):
        for text in ["API接口测试", "后端接口", "验证接口返回"]:
            assert "api_agent" in self.agent._extract_agents(text)

    def test_data_keywords(self):
        for text in ["数据一致性检查", "验证数据库", "data migration"]:
            assert "data_agent" in self.agent._extract_agents(text)

    def test_ops_keywords(self):
        for text in ["检查日志", "ops诊断", "运维监控"]:
            assert "ops_agent" in self.agent._extract_agents(text)

    def test_multiple_agents(self):
        text = "UI前端测试 + API接口 + 数据库验证"
        agents = self.agent._extract_agents(text)
        assert "ui_agent" in agents
        assert "api_agent" in agents
        assert "data_agent" in agents

    def test_default_agents_when_no_match(self):
        agents = self.agent._extract_agents("这段文字不包含任何关键词xyz")
        assert agents == ["ui_agent", "api_agent"]


# ---------------------------------------------------------------------------
# 测试 _extract_steps
# ---------------------------------------------------------------------------
class TestExtractSteps:
    @pytest.fixture(autouse=True)
    def _agent(self):
        with patch("agents.master_agent.get_llm") as mock_llm:
            mock_llm.return_value = MagicMock()
            from agents.master_agent import MasterAgent
            self.agent = MasterAgent()

    def test_numbered_steps(self):
        plan = "1. 打开浏览器\n2. 登录系统\n3. 执行测试"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 3
        assert "打开浏览器" in steps[0]

    def test_chinese_keyword_steps(self):
        plan = "步骤一：配置环境\n步骤二：运行测试"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 2

    def test_english_keyword_steps(self):
        plan = "step 1: setup\nstep 2: execute"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 2

    def test_default_steps_when_no_match(self):
        plan = "这段不包含编号的纯文本"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 4  # 默认 4 步
        assert "UI Agent" in steps[0]

    def test_mixed_format(self):
        plan = "准备工作\n1. 登录\n其他说明\n2. 测试"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 2


# ---------------------------------------------------------------------------
# 测试 generate_report / _calculate_success_rate / _generate_recommendations
# ---------------------------------------------------------------------------
class TestReportGeneration:
    @pytest.fixture(autouse=True)
    def _agent(self):
        with patch("agents.master_agent.get_llm") as mock_llm:
            mock_llm.return_value = MagicMock()
            from agents.master_agent import MasterAgent
            self.agent = MasterAgent()

    def _make_state(self, **overrides):
        """创建一个最小 QAState dict（TypedDict 不强制运行时检查）"""
        base = {
            "task_description": "测试任务",
            "test_scenario": "登录流程",
            "ui_results": [],
            "api_results": [],
            "data_results": [],
            "ops_results": [],
            "current_step": "",
            "completed_steps": [],
            "failed_steps": [],
            "messages": [],
            "errors": [],
            "warnings": [],
            "test_data": {},
            "final_report": None,
            "subgraph_states": {},
            "healing_context": None,
        }
        base.update(overrides)
        return base

    def test_success_rate_all_pass(self):
        state = self._make_state(completed_steps=["s1", "s2", "s3"], failed_steps=[])
        assert self.agent._calculate_success_rate(state) == 100.0

    def test_success_rate_all_fail(self):
        state = self._make_state(completed_steps=[], failed_steps=["s1", "s2"])
        assert self.agent._calculate_success_rate(state) == 0.0

    def test_success_rate_mixed(self):
        state = self._make_state(completed_steps=["s1"], failed_steps=["s2"])
        assert self.agent._calculate_success_rate(state) == 50.0

    def test_success_rate_zero_total(self):
        state = self._make_state()
        assert self.agent._calculate_success_rate(state) == 0.0

    def test_recommendations_with_errors(self):
        state = self._make_state(errors=[{"msg": "error1"}])
        recs = self.agent._generate_recommendations(state)
        assert any("错误" in r for r in recs)

    def test_recommendations_with_failed_steps(self):
        state = self._make_state(failed_steps=["步骤A"])
        recs = self.agent._generate_recommendations(state)
        assert any("步骤A" in r for r in recs)

    def test_recommendations_all_pass(self):
        state = self._make_state()
        recs = self.agent._generate_recommendations(state)
        assert any("通过" in r for r in recs)

    def test_generate_report_structure(self):
        state = self._make_state(
            completed_steps=["s1", "s2"],
            errors=[{"msg": "e1"}],
            warnings=["w1"],
        )
        report = self.agent.generate_report(state)
        assert report["test_scenario"] == "登录流程"
        assert report["summary"]["total_steps"] == 2
        assert report["summary"]["failed_steps"] == 0
        assert report["summary"]["success_rate"] == 100.0
        assert len(report["errors"]) == 1
        assert len(report["warnings"]) == 1
        assert isinstance(report["recommendations"], list)


# ---------------------------------------------------------------------------
# 测试 plan_test（需要 mock LLM chain + Vector DB）
# ---------------------------------------------------------------------------
class TestPlanTest:
    @pytest.fixture(autouse=True)
    def _setup(self):
        with patch("agents.master_agent.get_llm") as mock_llm, \
             patch("agents.master_agent.get_similar_test_plans") as mock_similar, \
             patch("agents.master_agent.get_prd_context") as mock_prd:

            # Mock LLM to return a deterministic plan
            fake_llm = MagicMock()
            fake_llm.__or__ = MagicMock(return_value=fake_llm)
            fake_llm.invoke = MagicMock(return_value="1. UI测试\n2. API测试\n3. 数据验证")
            mock_llm.return_value = fake_llm

            # Mock Vector DB tools
            mock_similar.invoke = MagicMock(return_value=[
                {"content": "历史测试计划1"}
            ])
            mock_prd.invoke = MagicMock(return_value=[
                {"content": "PRD需求文档1"}
            ])

            from agents.master_agent import MasterAgent
            self.agent = MasterAgent()
            self.mock_similar = mock_similar
            self.mock_prd = mock_prd
            yield

    def test_plan_test_basic(self):
        # 由于 chain invoke 需要 prompt_template | llm | parser，
        # 直接 mock prompt_template 使 chain 可用
        with patch.object(self.agent, 'prompt_template') as mock_prompt:
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(return_value="1. UI前端测试\n2. API接口验证")
            mock_prompt.__or__ = MagicMock(return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)))

            plan = self.agent.plan_test("登录功能测试")
            assert plan["scenario"] == "登录功能测试"
            assert "plan_text" in plan
            assert "required_agents" in plan
            assert "steps" in plan
            assert isinstance(plan["similar_plans_referenced"], int)

    def test_plan_test_vector_db_failure(self):
        """Vector DB 失败不应阻止计划生成"""
        self.mock_similar.invoke.side_effect = Exception("Vector DB down")

        with patch.object(self.agent, 'prompt_template') as mock_prompt:
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(return_value="1. 执行测试")
            mock_prompt.__or__ = MagicMock(return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)))

            plan = self.agent.plan_test("任何场景")
            assert plan["similar_plans_referenced"] == 0
