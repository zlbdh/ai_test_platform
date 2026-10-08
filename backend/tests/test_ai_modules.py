"""
Unit Tests for AI Enhancement Modules
Covers strategy selection, self-healing, and the knowledge base.
"""

import pytest
import asyncio
from datetime import datetime

# Tests for Strategy Selector
class TestStrategySelector:
    """Test the strategy selector."""
    
    def test_import(self):
        from core.strategy_selector import get_strategy_selector, AITestStrategySelector
        selector = get_strategy_selector()
        assert isinstance(selector, AITestStrategySelector)
    
    def test_analyze_ui_requirement(self):
        from core.strategy_selector import get_strategy_selector, TestType
        selector = get_strategy_selector()
        
        # UI testing requirement.
        strategy = selector.select_strategy("测试登录页面的表单提交功能")
        assert TestType.UI_E2E in strategy.test_types
        assert strategy.ai_confidence > 0
    
    def test_analyze_api_requirement(self):
        from core.strategy_selector import get_strategy_selector, TestType
        selector = get_strategy_selector()
        
        # API testing requirement.
        strategy = selector.select_strategy("测试用户接口的 REST API 响应")
        assert TestType.API_REST in strategy.test_types
    
    def test_analyze_db_requirement(self):
        from core.strategy_selector import get_strategy_selector, TestType
        selector = get_strategy_selector()
        
        # Database testing requirement.
        strategy = selector.select_strategy("验证数据库中用户表的数据一致性")
        assert TestType.DATABASE in strategy.test_types
    
    def test_analyze_security_requirement(self):
        from core.strategy_selector import get_strategy_selector, TestType
        selector = get_strategy_selector()
        
        # Security testing requirement.
        strategy = selector.select_strategy("检查 XSS 和 SQL 注入漏洞")
        assert TestType.SECURITY in strategy.test_types
    
    def test_strategy_has_agents(self):
        from core.strategy_selector import get_strategy_selector
        selector = get_strategy_selector()
        
        strategy = selector.select_strategy("测试登录功能")
        assert len(strategy.recommended_agents) > 0
    
    def test_target_url_analysis(self):
        from core.strategy_selector import get_strategy_selector
        selector = get_strategy_selector()
        
        target = selector.analyze_target("http://api.example.com/api/v1/users")
        assert target["is_url"] == True
        assert target["is_api_endpoint"] == True


# Tests for Self-Healing Engine
class TestSelfHealingEngine:
    """Test the self-healing engine."""
    
    def test_import(self):
        from core.self_healing import get_healing_engine, SelfHealingEngine
        engine = get_healing_engine()
        assert isinstance(engine, SelfHealingEngine)
    
    def test_classify_element_not_found(self):
        from core.self_healing import get_healing_engine, FailureType
        engine = get_healing_engine()
        
        error = Exception("Element not found: #login-button")
        failure_type = engine.classify_failure(error, {})
        assert failure_type == FailureType.ELEMENT_NOT_FOUND
    
    def test_classify_timeout(self):
        from core.self_healing import get_healing_engine, FailureType
        engine = get_healing_engine()
        
        error = Exception("Request timeout after 30s")
        failure_type = engine.classify_failure(error, {})
        assert failure_type == FailureType.TIMEOUT
    
    def test_classify_network(self):
        from core.self_healing import get_healing_engine, FailureType
        engine = get_healing_engine()
        
        error = Exception("Connection refused")
        failure_type = engine.classify_failure(error, {})
        assert failure_type == FailureType.NETWORK
    
    def test_suggest_healing_actions(self):
        from core.self_healing import get_healing_engine, FailureType
        engine = get_healing_engine()
        
        error = Exception("Element not found")
        actions = engine.suggest_healing_actions(
            FailureType.ELEMENT_NOT_FOUND, error, {}
        )
        assert len(actions) > 0
        assert all(a.success_probability >= 0 for a in actions)
    
    @pytest.mark.asyncio
    async def test_execute_with_healing_success(self):
        from core.self_healing import get_healing_engine
        engine = get_healing_engine()
        
        async def success_func():
            return "success"
        
        result = await engine.execute_with_healing(success_func)
        assert result.success == True
        assert result.retry_count == 0
    
    @pytest.mark.asyncio
    async def test_execute_with_healing_retry(self):
        from core.self_healing import get_healing_engine
        engine = get_healing_engine()
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"
        
        result = await engine.execute_with_healing(flaky_func)
        assert result.success == True
        assert result.retry_count > 0
    
    def test_get_statistics(self):
        from core.self_healing import get_healing_engine
        engine = get_healing_engine()
        
        stats = engine.get_statistics()
        assert "total_healings" in stats
        assert "success_rate" in stats


# Tests for Knowledge Base
class TestKnowledgeBase:
    """Test the knowledge base."""
    
    def test_import(self):
        from core.knowledge_base import get_knowledge_base, TestKnowledgeBase
        kb = get_knowledge_base()
        assert isinstance(kb, TestKnowledgeBase)
    
    def test_record_test(self):
        from core.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        
        case = kb.record_test(
            requirement="测试登录功能",
            target_url="http://example.com",
            test_types=["ui_e2e"],
            result="success",
            duration_ms=1500
        )
        
        assert case.case_id is not None
        assert case.result == "success"
    
    def test_find_similar_patterns(self):
        from core.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        
        # Record some tests first.
        kb.record_test(
            requirement="测试登录表单",
            target_url=None,
            test_types=["ui_e2e"],
            result="success",
            duration_ms=1000
        )
        
        # Find similar tests.
        patterns = kb.find_similar_patterns("登录验证测试")
        # Results depend on the available history.
        assert isinstance(patterns, list)
    
    def test_recommend_test_types(self):
        from core.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        
        recommendations = kb.recommend_test_types("API 接口测试")
        assert isinstance(recommendations, dict)
    
    def test_get_statistics(self):
        from core.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        
        stats = kb.get_statistics()
        assert "total_patterns" in stats
        assert "total_cases" in stats
        assert "success_rate" in stats
    
    def test_export_report(self):
        from core.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        
        report = kb.export_report()
        assert "statistics" in report
        assert "top_patterns" in report


# Tests for Auth Service
class TestAuthService:
    """Test the authentication service."""

    @staticmethod
    def _build_auth_service(tmp_path, monkeypatch):
        from services.auth_service import AuthenticationService
        monkeypatch.setenv("ADMIN_DEFAULT_PASSWORD", "public-test-passphrase")
        return AuthenticationService(str(tmp_path / "auth"))
    
    def test_import(self):
        from services.auth_service import get_auth_service, AuthenticationService
        auth = get_auth_service()
        assert isinstance(auth, AuthenticationService)
    
    def test_default_admin_exists(self):
        from services.auth_service import get_auth_service, UserRole
        auth = get_auth_service()
        
        has_admin = any(u.role == UserRole.ADMIN for u in auth.users.values())
        assert has_admin == True
    
    def test_create_user(self):
        from services.auth_service import get_auth_service
        auth = get_auth_service()
        
        user = auth.create_user(
            username=f"testuser_{datetime.now().timestamp()}",
            email="test@test.com",
            password="test123"
        )
        
        assert user.user_id is not None
        assert user.api_key is not None
    
    def test_authenticate(self, tmp_path, monkeypatch):
        auth = self._build_auth_service(tmp_path, monkeypatch)
        
        # Sign in as the default administrator.
        session = auth.authenticate("admin", "public-test-passphrase")
        assert session is not None
        assert session.token is not None
    
    def test_authenticate_fail(self):
        from services.auth_service import get_auth_service
        auth = get_auth_service()
        
        session = auth.authenticate("wrong", "wrong")
        assert session is None
    
    def test_validate_token(self, tmp_path, monkeypatch):
        auth = self._build_auth_service(tmp_path, monkeypatch)
        
        session = auth.authenticate("admin", "public-test-passphrase")
        user = auth.validate_token(session.token)
        
        assert user is not None
        assert user.username == "admin"
    
    def test_check_permission(self, tmp_path, monkeypatch):
        from services.auth_service import Permission
        auth = self._build_auth_service(tmp_path, monkeypatch)
        
        session = auth.authenticate("admin", "public-test-passphrase")
        user = auth.validate_token(session.token)
        
        has_admin = auth.check_permission(user, Permission.ADMIN)
        assert has_admin == True
    
    def test_create_project(self, tmp_path, monkeypatch):
        auth = self._build_auth_service(tmp_path, monkeypatch)
        
        session = auth.authenticate("admin", "public-test-passphrase")
        user = auth.validate_token(session.token)
        
        project = auth.create_project(
            name=f"Test Project {datetime.now().timestamp()}",
            description="Test",
            owner_id=user.user_id
        )
        
        assert project.project_id is not None


# Tests for GraphQL Service
class TestGraphQLService:
    """Test the GraphQL service."""
    
    def test_import(self):
        from services.graphql_testing import create_graphql_service
        service = create_graphql_service("http://example.com/graphql")
        assert service is not None
    
    def test_get_value_by_path(self):
        from services.graphql_testing import GraphQLTestService
        service = GraphQLTestService("http://example.com/graphql")
        
        data = {"user": {"name": "John", "age": 30}}
        
        assert service._get_value_by_path(data, "user.name") == "John"
        assert service._get_value_by_path(data, "user.age") == 30
        assert service._get_value_by_path(data, "user.email") is None


# Tests for WebSocket Service  
class TestWebSocketService:
    """Test the WebSocket service."""
    
    def test_import(self):
        from services.websocket_testing import create_ws_test_service
        service = create_ws_test_service("ws://example.com/ws")
        assert service is not None
    
    def test_get_value_by_path(self):
        from services.websocket_testing import WebSocketTestService
        service = WebSocketTestService("ws://example.com/ws")
        
        data = {"type": "message", "payload": {"text": "hello"}}
        
        assert service._get_value_by_path(data, "type") == "message"
        assert service._get_value_by_path(data, "payload.text") == "hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
