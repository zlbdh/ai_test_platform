"""
Unit Tests for New Modules
测试 gRPC、增强安全、API 文档生成、探索性测试模块
"""

import pytest
import asyncio


# Tests for gRPC Testing
class TestGrpcTesting:
    """测试 gRPC 模块"""
    
    def test_import(self):
        from services.grpc_testing import create_grpc_service
        service = create_grpc_service("localhost", 50051)
        assert service is not None
    
    def test_build_command(self):
        from services.grpc_testing import GrpcTestService
        service = GrpcTestService("localhost", 50051)
        cmd = service._build_command(
            "test.Service",
            "TestMethod",
            {"key": "value"}
        )
        assert "grpcurl" in cmd
        assert "-plaintext" in cmd
        assert "localhost:50051" in cmd


# Tests for Enhanced Security
class TestEnhancedSecurity:
    """测试增强安全扫描"""
    
    def test_import(self):
        from services.enhanced_security import get_enhanced_scanner
        scanner = get_enhanced_scanner()
        assert scanner is not None
    
    def test_generate_vuln_id(self):
        from services.enhanced_security import EnhancedSecurityScanner
        scanner = EnhancedSecurityScanner()
        id1 = scanner._generate_vuln_id()
        id2 = scanner._generate_vuln_id()
        assert id1 != id2
        assert id1.startswith("VULN-")
    
    def test_calculate_risk_score(self):
        from services.enhanced_security import EnhancedSecurityScanner, ScanResult
        scanner = EnhancedSecurityScanner()
        result = ScanResult(
            target_url="http://test.com",
            scan_time=1.0,
            total_requests=10,
            vulnerabilities=[],
            headers_check={},
            ssl_check={},
            summary={"critical": 1, "high": 2, "medium": 0, "low": 0, "info": 0}
        )
        score = scanner._calculate_risk_score(result)
        assert score > 0


# Tests for API Doc Generator
class TestApiDocGenerator:
    """测试 API 文档生成"""
    
    def test_import(self):
        from core.api_doc_generator import ApiDocGenerator
        gen = ApiDocGenerator()
        assert gen is not None
    
    def test_extract_tags(self):
        from core.api_doc_generator import ApiDocGenerator
        gen = ApiDocGenerator()
        tags = gen._extract_tags("/api/auth/login")
        assert "auth" in tags
    
    def test_method_badge(self):
        from core.api_doc_generator import ApiDocGenerator
        gen = ApiDocGenerator()
        badge = gen._method_badge("GET")
        assert "GET" in badge
        assert "🟢" in badge
    
    def test_generate_openapi(self):
        from core.api_doc_generator import ApiDocGenerator
        gen = ApiDocGenerator()
        gen.endpoints = []
        openapi = gen.generate_openapi("Test API")
        assert openapi["openapi"] == "3.0.0"
        assert openapi["info"]["title"] == "Test API"


# Tests for Exploratory Agent
class TestExploratoryAgent:
    """测试探索性测试 Agent"""
    
    def test_import(self):
        from agents.exploratory_agent import create_exploratory_agent
        agent = create_exploratory_agent()
        assert agent is not None
    
    def test_compute_state_hash(self):
        from agents.exploratory_agent import ExploratoryTestAgent
        agent = ExploratoryTestAgent()
        hash1 = agent._compute_state_hash("<html>test</html>", "http://test.com")
        hash2 = agent._compute_state_hash("<html>test</html>", "http://test.com")
        assert hash1 == hash2
    
    def test_calculate_coverage(self):
        from agents.exploratory_agent import ExploratoryTestAgent
        agent = ExploratoryTestAgent()
        agent.visited_states.add("state1")
        agent.visited_states.add("state2")
        coverage = agent._calculate_coverage()
        assert coverage == 0  # 无动作历史时为 0
    
    def test_generate_report(self):
        from agents.exploratory_agent import ExploratoryTestAgent
        agent = ExploratoryTestAgent()
        report = agent.generate_report()
        assert "summary" in report
        assert "visited_urls" in report
        assert "anomalies" in report


# Tests for Requirement Parser (existing)
class TestRequirementParserExtended:
    """扩展测试需求解析器"""
    
    def test_security_requirement(self):
        from core.requirement_parser import get_requirement_parser, RuleType
        parser = get_requirement_parser()
        result = parser.parse_text("必须验证用户密码强度，确保安全")
        assert any(r.rule_type == RuleType.VALIDATION for r in result.rules)
    
    def test_performance_requirement(self):
        from core.requirement_parser import get_requirement_parser, RuleType
        parser = get_requirement_parser()
        result = parser.parse_text("页面响应时间必须小于3秒")
        assert any(r.rule_type == RuleType.PERFORMANCE for r in result.rules)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
