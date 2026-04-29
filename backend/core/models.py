from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

# === Original AI Test Platform Models ===
class TestRequest(BaseModel):
    __test__ = False
    requirement: str
    target_url: Optional[str] = None
    mode: Optional[str] = "CLOUD"  # LOCAL or CLOUD
    planner_mode: Optional[str] = "smart"  # smart or quick
    execution_mode: Optional[str] = "default"
    interaction_policy: Optional[str] = "default"
    swagger_url: Optional[str] = None
    log_path: Optional[str] = None
    session_id: Optional[str] = "default_session"
    browser_mode: Optional[str] = "chromium"
    execution_group_id: Optional[str] = None

class TestStep(BaseModel):
    __test__ = False
    id: str
    agent: str
    description: str
    status: str
    logs: List[str] = []
    code: Optional[str] = None
    executableScript: Optional[str] = None
    duration: Optional[int] = None
    retryCount: Optional[int] = 0

class TestPlanResponse(BaseModel):
    __test__ = False
    steps: List[TestStep]
    mode: str

class ExecuteStepRequest(BaseModel):
    step: TestStep
    target_url: Optional[str] = None

class ExecuteStepResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    logs: List[str] = []
    code: Optional[str] = None

# === Migrated Log Models ===
class LogType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action" 
    OBSERVATION = "observation"
    SYSTEM = "system"
    ERROR = "error"
    SUCCESS = "success"
    INFO = "info" # Added for compatibility

class LogEntry(BaseModel):
    step: str
    type: LogType
    content: str
    tool_name: Optional[str] = None
    screenshot: Optional[str] = None # Base64
    timestamp: float = 0.0
    details: Optional[Dict[str, Any]] = None


# === Models extracted from main.py ===

class PlanGenerateRequest(BaseModel):
    requirement: str
    target_url: Optional[str] = None
    enable_rag: bool = True
    execution_mode: Optional[str] = "default"
    interaction_policy: Optional[str] = "default"

class AIConfigUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    vision_model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    planner_model: Optional[str] = None
    executor_model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None

class DataGenerateRequest(BaseModel):
    template: Dict[str, Any]
    count: int = 1

class BatchRunRequest(BaseModel):
    instruction_template: str
    data_template: Optional[Dict[str, Any]] = None
    count: int = 10
    max_concurrency: int = 3
    base_url: str = ""

class CICDConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    default_task_template: Optional[str] = None
    notify_on_complete: Optional[bool] = None
    regenerate_secret: bool = False

class CICDWebhookPayload(BaseModel):
    source: str = "manual"
    ref: str = ""
    commit: str = ""

class DeployActionRequest(BaseModel):
    branch: str = ""
    git_token: str = ""

class DBConnectionRequest(BaseModel):
    name: str = "New Connection"
    db_type: str = "sqlite"
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""
    connection_string: Optional[str] = None
    read_only: bool = True

class DBInjectDataRequest(BaseModel):
    table: str
    data: List[Dict[str, Any]]

class DBValidationRequest(BaseModel):
    rules: List[Dict[str, Any]]

class DataFactoryRequest(BaseModel):
    template: Dict[str, Any]
    count: int = 1

class StrategyRequest(BaseModel):
    requirement: str
    target_url: Optional[str] = None

class KnowledgeRecordRequest(BaseModel):
    requirement: str
    target_url: Optional[str] = None
    test_types: List[str]
    result: str  # success, failure
    duration_ms: int
    error_message: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""

class DocumentReference(BaseModel):
    title: str = ""
    content: str

class RequirementParseRequest(BaseModel):
    content: str
    title: str = "Untitled Requirement"
    references: List[DocumentReference] = Field(default_factory=list)

class FileParseRequest(BaseModel):
    file_path: str

class GrpcTestRequest(BaseModel):
    host: str
    port: int = 50051
    service: str
    method: str
    data: Dict[str, Any] = {}
    use_tls: bool = False

class EnhancedSecurityScanRequest(BaseModel):
    target_url: str
    scan_types: List[str] = ["headers", "sqli", "xss", "ssl", "sensitive"]

class ContractCreateRequest(BaseModel):
    consumer: str
    provider: str
    interactions: List[Dict[str, Any]]
    version: str = "1.0.0"

class ReportRequest(BaseModel):
    suite_name: str
    tests: List[Dict[str, Any]]
    format: str = "html"


class ReportGenerateRequest(BaseModel):
    task_id: Optional[str] = None
    execution_group_id: Optional[str] = None


class MaintenanceRunRequest(BaseModel):
    force: bool = False
    reason: str = "manual"


class MaintenanceArchiveRequest(BaseModel):
    reason: str = "ops_archive"
    limit: int = 0


class MaintenanceArchiveExportRequest(BaseModel):
    reason: str = "ops_export_archive"
    format: str = "json"


class MaintenanceArchiveCleanupRequest(BaseModel):
    reason: str = "ops_cleanup_archive"
    retention_days: int = 30
    dry_run: bool = True


class ShadowDbQuarantineRequest(BaseModel):
    reason: str = "ops_quarantine"


class CommanderChatOpsSimulateRequest(BaseModel):
    message: str = "状态"
    from_user: str = "debug_console"
    chat_id: str = "debug_chat"
    deliver: bool = True


class CommanderChatOpsTokenConfigRequest(BaseModel):
    verification_token: Optional[str] = None
    regenerate: bool = False


class CommanderChatOpsCallbackConfigRequest(BaseModel):
    public_api_base_url: str = ""


class CommanderChatOpsAppBotConfigRequest(BaseModel):
    app_id: str = ""
    app_secret: str = ""


class CommanderChatOpsAppBotUnbindRequest(BaseModel):
    purge_history: bool = True


class CommanderChatOpsSubscriptionSelfCheckRequest(BaseModel):
    challenge: str = "codex-self-check"


class ScheduleRequest(BaseModel):
    name: str
    test_config: Dict[str, Any]
    priority: int = 2
    scheduled_at: Optional[str] = None

class LoadTestRequest(BaseModel):
    target_url: str
    users: int = 10
    spawn_rate: float = 1.0
    duration_seconds: int = 60

class OAuthConfigRequest(BaseModel):
    provider: str
    client_id: str
    client_secret: str
    redirect_uri: str = "http://localhost:8020/oauth/callback"

class SaveTokenRequest(BaseModel):
    name: str
    access_token: str
    provider: str = "custom"
    expires_hours: int = 24

# === Testing Router Models ===
class PerformanceTestRequest(BaseModel):
    target_url: str
    users: int = 10
    spawn_rate: int = 1
    duration: int = 60
    endpoints: Optional[List[Dict[str, Any]]] = None
    headers: Optional[Dict[str, str]] = None
    session_id: Optional[str] = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None

class SecurityScanRequest(BaseModel):
    target_url: str
    scan_type: str = "standard"
    max_depth: int = 5
    session_id: Optional[str] = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None

class PauseRequest(BaseModel):
    reason: str = "User Request"
    session_id: Optional[str] = "default_session"


# =============================================================================
# Inspector 视觉质检结果
# =============================================================================

class InspectionResult(BaseModel):
    """Inspector 视觉审查结果 — 判定每步执行后的业务正确性"""
    passed: bool
    confidence: float = 1.0
    reason: str = ""
    anomalies: List[str] = []


# =============================================================================
# 统一 API 响应模型 & 异常类
# 所有新增/重构的 router 应使用这些类型实现一致的错误处理
# =============================================================================

class APIResponse(BaseModel):
    """统一 API 响应格式"""
    status: str = "success"               # "success" | "error"
    message: Optional[str] = None         # 人类可读消息
    data: Optional[Any] = None            # 业务数据
    error_code: Optional[str] = None      # 机器可读错误码 (e.g. "LLM_TIMEOUT")

    @classmethod
    def ok(cls, data: Any = None, message: str = None):
        return cls(status="success", data=data, message=message)

    @classmethod
    def error(cls, message: str, error_code: str = None, data: Any = None):
        return cls(status="error", message=message, error_code=error_code, data=data)


class APIError(Exception):
    """统一业务异常 — 可在路由中 raise，由全局异常处理器捕获"""
    def __init__(self, message: str, status_code: int = 400, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)
