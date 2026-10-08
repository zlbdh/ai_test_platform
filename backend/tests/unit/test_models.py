"""
core/models.py unit tests.
Covers initialization, defaults, and enums for more than 30 Pydantic models,
plus APIResponse and APIError factory methods.
"""
import pytest
from core.models import (
    TestRequest, TestStep, TestPlanResponse, ExecuteStepRequest, ExecuteStepResponse,
    LogType, LogEntry,
    PlanGenerateRequest, AIConfigUpdate, DataGenerateRequest, BatchRunRequest,
    CICDConfigUpdateRequest, CICDWebhookPayload,
    DBConnectionRequest, DBInjectDataRequest, DBValidationRequest,
    DataFactoryRequest, StrategyRequest, KnowledgeRecordRequest,
    LoginRequest, RegisterRequest, CreateProjectRequest,
    RequirementParseRequest, FileParseRequest,
    GrpcTestRequest, EnhancedSecurityScanRequest, ContractCreateRequest,
    ReportRequest, ScheduleRequest, LoadTestRequest,
    OAuthConfigRequest, SaveTokenRequest,
    PerformanceTestRequest, SecurityScanRequest, PauseRequest,
    APIResponse, APIError,
)


# ═══════════════════════════════════════════════════
# LogType enum.
# ═══════════════════════════════════════════════════

class TestLogType:
    def test_enum_values(self):
        assert LogType.THOUGHT == "thought"
        assert LogType.ACTION == "action"
        assert LogType.ERROR == "error"
        assert LogType.SUCCESS == "success"
        assert LogType.INFO == "info"

    def test_enum_membership(self):
        assert "thought" in [e.value for e in LogType]
        assert "observation" in [e.value for e in LogType]

    def test_enum_count(self):
        assert len(LogType) == 7


# ═══════════════════════════════════════════════════
# Core request/response models.
# ═══════════════════════════════════════════════════

class TestTestRequest:
    def test_minimal(self):
        r = TestRequest(requirement="login test")
        assert r.requirement == "login test"
        assert r.target_url is None
        assert r.mode == "CLOUD"
        assert r.planner_mode == "smart"
        assert r.execution_mode == "default"
        assert r.interaction_policy == "default"

    def test_full(self):
        r = TestRequest(
            requirement="x",
            target_url="http://a.com",
            mode="LOCAL",
            planner_mode="quick",
            execution_mode="probe",
            interaction_policy="read_only",
        )
        assert r.mode == "LOCAL"
        assert r.planner_mode == "quick"
        assert r.execution_mode == "probe"
        assert r.interaction_policy == "read_only"


class TestTestStep:
    def test_defaults(self):
        s = TestStep(id="1", agent="ui", description="click", status="pending")
        assert s.logs == []
        assert s.retryCount == 0
        assert s.duration is None

    def test_all_fields(self):
        s = TestStep(id="1", agent="ui", description="x", status="done", logs=["a"], code="c", duration=100, retryCount=2)
        assert s.duration == 100
        assert len(s.logs) == 1


class TestTestPlanResponse:
    def test_create(self):
        step = TestStep(id="1", agent="ui", description="x", status="p")
        r = TestPlanResponse(steps=[step], mode="smart")
        assert len(r.steps) == 1
        assert r.mode == "smart"


class TestExecuteStepModels:
    def test_request(self):
        step = TestStep(id="1", agent="ui", description="d", status="s")
        req = ExecuteStepRequest(step=step)
        assert req.target_url is None

    def test_response(self):
        res = ExecuteStepResponse(success=True)
        assert res.error is None
        assert res.logs == []


class TestLogEntry:
    def test_defaults(self):
        e = LogEntry(step="1", type=LogType.ACTION, content="clicked")
        assert e.timestamp == 0.0
        assert e.screenshot is None
        assert e.details is None


# ═══════════════════════════════════════════════════
# Plan/configuration models.
# ═══════════════════════════════════════════════════

class TestPlanGenerate:
    def test_defaults(self):
        r = PlanGenerateRequest(requirement="test login")
        assert r.enable_rag is True
        assert r.target_url is None
        assert r.execution_mode == "default"
        assert r.interaction_policy == "default"


class TestAIConfigUpdate:
    def test_all_optional(self):
        c = AIConfigUpdate()
        assert c.provider is None
        assert c.model is None


class TestBatchRunRequest:
    def test_defaults(self):
        r = BatchRunRequest(instruction_template="t")
        assert r.count == 10
        assert r.max_concurrency == 3
        assert r.base_url == ""


# ═══════════════════════════════════════════════════
# Database models.
# ═══════════════════════════════════════════════════

class TestDBModels:
    def test_connection_defaults(self):
        c = DBConnectionRequest()
        assert c.db_type == "sqlite"
        assert c.host == "localhost"
        assert c.port == 3306

    def test_inject(self):
        r = DBInjectDataRequest(table="users", data=[{"name": "a"}])
        assert r.table == "users"

    def test_validation(self):
        r = DBValidationRequest(rules=[{"col": "id", "rule": "not_null"}])
        assert len(r.rules) == 1


# ═══════════════════════════════════════════════════
# CI/CD models.
# ═══════════════════════════════════════════════════

class TestCICDModels:
    def test_config_update(self):
        c = CICDConfigUpdateRequest()
        assert c.enabled is None
        assert c.regenerate_secret is False

    def test_webhook(self):
        w = CICDWebhookPayload()
        assert w.source == "manual"


# ═══════════════════════════════════════════════════
# Authentication models.
# ═══════════════════════════════════════════════════

class TestAuthModels:
    def test_login(self):
        r = LoginRequest(username="admin", password="pw")
        assert r.username == "admin"

    def test_register(self):
        r = RegisterRequest(username="u", email="e@e.com", password="p")
        assert r.email == "e@e.com"


# ═══════════════════════════════════════════════════
# Testing router models.
# ═══════════════════════════════════════════════════

class TestTestingModels:
    def test_performance(self):
        r = PerformanceTestRequest(target_url="http://a.com")
        assert r.users == 10
        assert r.spawn_rate == 1
        assert r.duration == 60

    def test_security_scan(self):
        r = SecurityScanRequest(target_url="http://a.com")
        assert r.scan_type == "standard"
        assert r.max_depth == 5

    def test_pause(self):
        r = PauseRequest()
        assert r.reason == "User Request"

    def test_grpc(self):
        r = GrpcTestRequest(host="localhost", service="Greeter", method="SayHello")
        assert r.port == 50051
        assert r.use_tls is False

    def test_enhanced_security(self):
        r = EnhancedSecurityScanRequest(target_url="http://a.com")
        assert "headers" in r.scan_types

    def test_load_test(self):
        r = LoadTestRequest(target_url="http://a.com")
        assert r.users == 10
        assert r.duration_seconds == 60

    def test_contract_create(self):
        r = ContractCreateRequest(consumer="c", provider="p", interactions=[{}])
        assert r.version == "1.0.0"

    def test_report_request(self):
        r = ReportRequest(suite_name="suite", tests=[{"name": "t1"}])
        assert r.format == "html"

    def test_schedule_request(self):
        r = ScheduleRequest(name="nightly", test_config={"mode": "full"})
        assert r.priority == 2

    def test_oauth_config(self):
        r = OAuthConfigRequest(provider="github", client_id="cid", client_secret="cs")
        assert "localhost:8020" in r.redirect_uri

    def test_save_token(self):
        r = SaveTokenRequest(name="mytoken", access_token="tok123")
        assert r.provider == "custom"
        assert r.expires_hours == 24


# ═══════════════════════════════════════════════════
# Miscellaneous models.
# ═══════════════════════════════════════════════════

class TestMiscModels:
    def test_data_factory(self):
        r = DataFactoryRequest(template={"name": "faker.name"})
        assert r.count == 1

    def test_data_generate(self):
        r = DataGenerateRequest(template={"email": "faker.email"})
        assert r.count == 1

    def test_strategy(self):
        r = StrategyRequest(requirement="login test")
        assert r.target_url is None

    def test_knowledge_record(self):
        r = KnowledgeRecordRequest(requirement="r", test_types=["ui"], result="success", duration_ms=500)
        assert r.error_message is None

    def test_create_project(self):
        r = CreateProjectRequest(name="proj")
        assert r.description == ""

    def test_requirement_parse(self):
        r = RequirementParseRequest(content="test login")
        assert r.title == "Untitled Requirement"

    def test_file_parse(self):
        r = FileParseRequest(file_path="/tmp/req.md")
        assert r.file_path == "/tmp/req.md"


# ═══════════════════════════════════════════════════
# APIResponse & APIError
# ═══════════════════════════════════════════════════

class TestAPIResponse:
    def test_ok(self):
        r = APIResponse.ok(data={"id": 1}, message="created")
        assert r.status == "success"
        assert r.data == {"id": 1}
        assert r.message == "created"

    def test_ok_no_args(self):
        r = APIResponse.ok()
        assert r.status == "success"
        assert r.data is None

    def test_error(self):
        r = APIResponse.error(message="not found", error_code="NOT_FOUND")
        assert r.status == "error"
        assert r.error_code == "NOT_FOUND"

    def test_error_with_data(self):
        r = APIResponse.error(message="fail", data={"detail": "abc"})
        assert r.data == {"detail": "abc"}

    def test_defaults(self):
        r = APIResponse()
        assert r.status == "success"
        assert r.message is None
        assert r.error_code is None


class TestAPIError:
    def test_basic(self):
        err = APIError("bad request")
        assert err.message == "bad request"
        assert err.status_code == 400
        assert err.error_code is None

    def test_custom(self):
        err = APIError("timeout", status_code=504, error_code="LLM_TIMEOUT")
        assert err.status_code == 504
        assert err.error_code == "LLM_TIMEOUT"

    def test_is_exception(self):
        err = APIError("err")
        assert isinstance(err, Exception)
        assert str(err) == "err"
