"""
MasterAgent unit tests
Coverage: plan_test, _extract_agents, _extract_steps, generate_report,
          _calculate_success_rate, _generate_recommendations.
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Test _extract_agents: pure logic, with no LLM mock needed.
# ---------------------------------------------------------------------------
class TestExtractAgents:
    """Test the MasterAgent._extract_agents keyword matching logic."""

    @pytest.fixture(autouse=True)
    def _agent(self):
        with patch("agents.master_agent.get_llm_for_role") as mock_llm:
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
        agents = self.agent._extract_agents("This text contains no matching keywords xyz")
        assert agents == ["ui_agent", "api_agent"]


# ---------------------------------------------------------------------------
# Test _extract_steps.
# ---------------------------------------------------------------------------
class TestExtractSteps:
    @pytest.fixture(autouse=True)
    def _agent(self):
        with patch("agents.master_agent.get_llm_for_role") as mock_llm:
            mock_llm.return_value = MagicMock()
            from agents.master_agent import MasterAgent
            self.agent = MasterAgent()

    def test_numbered_steps(self):
        plan = "1. Open the browser\n2. Log in\n3. Run tests"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 3
        assert "Open the browser" in steps[0]

    def test_chinese_keyword_steps(self):
        plan = "步骤一：配置环境\n步骤二：运行测试"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 2

    def test_english_keyword_steps(self):
        plan = "step 1: setup\nstep 2: execute"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 2

    def test_default_steps_when_no_match(self):
        plan = "Plain text without numbering"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 4  # Four default steps
        assert "UI Agent" in steps[0]

    def test_mixed_format(self):
        plan = "Preparation\n1. Login\nOther notes\n2. Test"
        steps = self.agent._extract_steps(plan)
        assert len(steps) == 2


# ---------------------------------------------------------------------------
# Test generate_report / _calculate_success_rate / _generate_recommendations.
# ---------------------------------------------------------------------------
class TestReportGeneration:
    @pytest.fixture(autouse=True)
    def _agent(self):
        with patch("agents.master_agent.get_llm_for_role") as mock_llm:
            mock_llm.return_value = MagicMock()
            from agents.master_agent import MasterAgent
            self.agent = MasterAgent()

    def _make_state(self, **overrides):
        """Create a minimal QAState dictionary; TypedDict does not enforce runtime validation."""
        base = {
            "task_description": "Test task",
            "test_scenario": "Login workflow",
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
        assert any("errors" in r for r in recs)

    def test_recommendations_with_failed_steps(self):
        state = self._make_state(failed_steps=["Step A"])
        recs = self.agent._generate_recommendations(state)
        assert any("Step A" in r for r in recs)

    def test_recommendations_all_pass(self):
        state = self._make_state()
        recs = self.agent._generate_recommendations(state)
        assert any("passed" in r for r in recs)

    def test_generate_report_structure(self):
        state = self._make_state(
            completed_steps=["s1", "s2"],
            errors=[{"msg": "e1"}],
            warnings=["w1"],
        )
        report = self.agent.generate_report(state)
        assert report["test_scenario"] == "Login workflow"
        assert report["summary"]["total_steps"] == 2
        assert report["summary"]["failed_steps"] == 0
        assert report["summary"]["success_rate"] == 100.0
        assert len(report["errors"]) == 1
        assert len(report["warnings"]) == 1
        assert isinstance(report["recommendations"], list)


# ---------------------------------------------------------------------------
# Test plan_test with mocked LLM chain and vector database.
# ---------------------------------------------------------------------------
class TestPlanTest:
    @pytest.fixture(autouse=True)
    def _setup(self):
        with patch("agents.master_agent.get_llm_for_role") as mock_llm, \
             patch("agents.master_agent.get_similar_test_plans") as mock_similar, \
             patch("agents.master_agent.get_prd_context") as mock_prd:

            # Mock LLM to return a deterministic plan
            fake_llm = MagicMock()
            fake_llm.__or__ = MagicMock(return_value=fake_llm)
            fake_llm.invoke = MagicMock(return_value="1. UI tests\n2. API tests\n3. Data validation")
            mock_llm.return_value = fake_llm

            # Mock Vector DB tools
            mock_similar.invoke = MagicMock(return_value=[
                {"content": "Historical test plan 1"}
            ])
            mock_prd.invoke = MagicMock(return_value=[
                {"content": "PRD requirements document 1"}
            ])

            from agents.master_agent import MasterAgent
            self.agent = MasterAgent()
            self.mock_similar = mock_similar
            self.mock_prd = mock_prd
            yield

    def test_plan_test_basic(self):
        # The chain invoke requires prompt_template | llm | parser.
        # Mock prompt_template directly to make the chain usable.
        with patch.object(self.agent, 'prompt_template') as mock_prompt:
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(return_value="1. UI frontend tests\n2. API validation")
            mock_prompt.__or__ = MagicMock(return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)))

            plan = self.agent.plan_test("Login functionality test")
            assert plan["scenario"] == "Login functionality test"
            assert "plan_text" in plan
            assert "required_agents" in plan
            assert "steps" in plan
            assert isinstance(plan["similar_plans_referenced"], int)

    def test_plan_test_vector_db_failure(self):
        """A vector database failure should not prevent plan generation."""
        self.mock_similar.invoke.side_effect = Exception("Vector DB down")

        with patch.object(self.agent, 'prompt_template') as mock_prompt:
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(return_value="1. Run tests")
            mock_prompt.__or__ = MagicMock(return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)))

            plan = self.agent.plan_test("Any scenario")
            assert plan["similar_plans_referenced"] == 0
