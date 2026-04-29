"""
平台配置
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    # Browser Debug Port
    CHROME_DEBUG_PORT: int = int(os.getenv("CHROME_DEBUG_PORT", "8030"))
    # 获取项目根目录（从 core/ 向上两级到项目根目录）
    _CORE_DIR = Path(__file__).resolve().parent
    _BACKEND_DIR = _CORE_DIR.parent
    _ROOT_DIR = _BACKEND_DIR.parent
    env_path = _ROOT_DIR / '.env'
    # 尝试加载根目录的 .env 文件
    load_dotenv(env_path, override=True) if env_path.exists() else load_dotenv(override=True)
except ImportError:
    # 如果 python-dotenv 未安装，跳过
    pass


class Config:
    """平台配置类"""
    
    # 项目根目录（复用顶部 Path 常量）
    PROJECT_ROOT: str = str(_BACKEND_DIR)
    _root_str: str = str(_ROOT_DIR)

    # 资源包锁定配置
    RESOURCE_PACK_PROVIDER: str = "openai"
    RESOURCE_PACK_MODEL: str = os.getenv("RESOURCE_PACK_MODEL", "claude-haiku-4-5-20251001")
    RESOURCE_PACK_BASE_URL: str = os.getenv("RESOURCE_PACK_BASE_URL", "https://api.openai.com/v1")
    LOCK_RESOURCE_PACK: bool = os.getenv("LOCK_RESOURCE_PACK", "true").lower() == "true"
    
    # LLM 配置
    USE_FAKE_LLM: bool = os.getenv("USE_FAKE_LLM", "false").lower() == "true"
    
    # LLM 提供商配置
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", RESOURCE_PACK_PROVIDER)  # openai, gemini, deepseek, chatglm, claude
    LLM_MODEL: str = os.getenv("LLM_MODEL", RESOURCE_PACK_MODEL)
    
    # 多智能体协同模型配置（默认继承 LLM_MODEL）
    PLANNER_MODEL: str = os.getenv("PLANNER_MODEL", "")
    EXECUTOR_MODEL: str = os.getenv("EXECUTOR_MODEL", "")
    
    # OpenAI 配置 (Gateway Override)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")  # 必须通过环境变量或 .env 配置
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", RESOURCE_PACK_MODEL)  # 向后兼容
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL", RESOURCE_PACK_BASE_URL)
    
    # Google Gemini 配置
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    # Browser-Use (Fallback)
    BROWSER_USE_API_KEY: Optional[str] = os.getenv("BROWSER_USE_API_KEY")
    
    # DeepSeek 配置
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # ChatGLM (智谱AI) 配置
    CHATGLM_API_KEY: Optional[str] = os.getenv("CHATGLM_API_KEY")
    CHATGLM_MODEL: str = os.getenv("CHATGLM_MODEL", "glm-4")
    CHATGLM_BASE_URL: Optional[str] = os.getenv("CHATGLM_BASE_URL")
    
    # Anthropic Claude 配置
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
    

    # LangSmith / LangChain 可观测性配置
    LANGCHAIN_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "ai-test-platform")
    
    # 测试目标配置
    TARGET_URL: str = os.getenv("TARGET_URL", "http://localhost:3000")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8020")
    PUBLIC_API_BASE_URL: str = os.getenv("PUBLIC_API_BASE_URL", os.getenv("API_BASE_URL", "http://localhost:8020"))
    PUBLIC_API_BASE_URL_UPDATED_AT: str = os.getenv("PUBLIC_API_BASE_URL_UPDATED_AT", "").strip()
    NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN: str = os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "").strip()
    NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT: str = os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "").strip()
    NOTIFICATION_PLATFORM_APP_ID: str = os.getenv("NOTIFICATION_PLATFORM_APP_ID", "").strip()
    NOTIFICATION_PLATFORM_APP_SECRET: str = os.getenv("NOTIFICATION_PLATFORM_APP_SECRET", "").strip()
    NOTIFICATION_PLATFORM_APP_BOT_UPDATED_AT: str = os.getenv("NOTIFICATION_PLATFORM_APP_BOT_UPDATED_AT", "").strip()
    
    # 数据库配置
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "test_db")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_CONNECTION_STRING: str = os.getenv("DB_CONNECTION_STRING", "")

    # UI 测试配置
    BROWSER_TYPE: str = os.getenv("BROWSER_TYPE", "chromium")  # chromium, firefox, webkit
    # HEADLESS: 从环境变量读取，默认 false 以便调试
    HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"
    # 截图目录：如果配置为相对路径，相对于项目根目录
    _screenshot_dir = os.getenv("SCREENSHOT_DIR", "./screenshots")
    SCREENSHOT_DIR: str = _screenshot_dir if os.path.isabs(_screenshot_dir) else os.path.join(
        str(_ROOT_DIR), _screenshot_dir.lstrip('./')
    )

    # 日志配置
    _log_dir = os.getenv("LOG_DIR", "./logs")
    LOG_DIR: str = _log_dir if os.path.isabs(_log_dir) else os.path.join(
        str(_ROOT_DIR), _log_dir.lstrip('./')
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Vision Config
    ENABLE_VISION: bool = os.getenv("ENABLE_VISION", "true").lower() == "true"
    VISION_MODEL: str = os.getenv("VISION_MODEL", RESOURCE_PACK_MODEL)
    # Inspector 视觉质检配置
    INSPECTOR_CONFIDENCE_THRESHOLD: float = float(os.getenv("INSPECTOR_CONFIDENCE_THRESHOLD", "0.7"))
    INSPECTOR_ENABLE_RAG: bool = os.getenv("INSPECTOR_ENABLE_RAG", "true").lower() == "true"

    # 超时配置
    UI_TIMEOUT: int = int(os.getenv("UI_TIMEOUT", "30000"))  # 毫秒
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "120"))  # 秒
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "600"))  # LLM 调用超时(秒)，Thinking 模型需更长
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    LLM_TOP_P: float = float(os.getenv("LLM_TOP_P", "1"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    
    # Vector DB 配置
    _vector_db_path = os.getenv("VECTOR_DB_PATH", "./vector_db")
    VECTOR_DB_PATH: str = _vector_db_path if os.path.isabs(_vector_db_path) else os.path.join(
        str(_ROOT_DIR), _vector_db_path.lstrip('./')
    )
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")  # OpenAI 默认
    
    # RAG 知识库配置
    ENABLE_RAG: bool = os.getenv("ENABLE_RAG", "true").lower() == "true"
    _chroma_path = os.getenv("CHROMA_PATH", "./data/chroma_db")
    CHROMA_PATH: str = _chroma_path if os.path.isabs(_chroma_path) else os.path.join(
        str(_BACKEND_DIR),
        _chroma_path.lstrip('./')
    )
    
    # Git 配置
    _git_repo_path = os.getenv("GIT_REPO_PATH", ".")
    GIT_REPO_PATH: str = _git_repo_path if os.path.isabs(_git_repo_path) else os.path.join(
        str(_ROOT_DIR), _git_repo_path.lstrip('./')
    )

    @classmethod
    def _normalize_provider(cls, provider: Optional[str] = None) -> str:
        if cls.LOCK_RESOURCE_PACK:
            return cls.RESOURCE_PACK_PROVIDER
        normalized = (provider or cls.LLM_PROVIDER or cls.RESOURCE_PACK_PROVIDER).strip().lower()
        return normalized or cls.RESOURCE_PACK_PROVIDER

    @classmethod
    def _normalize_model_name(cls, model: Optional[str], fallback: Optional[str] = None) -> str:
        if cls.LOCK_RESOURCE_PACK:
            return cls.RESOURCE_PACK_MODEL
        normalized = (model or fallback or cls.LLM_MODEL or cls.RESOURCE_PACK_MODEL).strip()
        return normalized or cls.RESOURCE_PACK_MODEL

    @classmethod
    def _normalize_base_url(cls, provider: str, base_url: Optional[str] = None) -> str:
        if cls.LOCK_RESOURCE_PACK or provider in ("openai", "custom"):
            normalized = (base_url or cls.OPENAI_BASE_URL or cls.RESOURCE_PACK_BASE_URL).strip()
            return normalized.rstrip("/") or cls.RESOURCE_PACK_BASE_URL
        if provider == "chatglm":
            normalized = (base_url or cls.CHATGLM_BASE_URL or "https://open.bigmodel.cn/api/paas/v4").strip()
            return normalized.rstrip("/")
        return (base_url or "").strip().rstrip("/")

    @classmethod
    def _normalize_float(cls, value: Optional[float], current: float, minimum: float, maximum: float) -> float:
        if value is None:
            return current
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return current
        return max(minimum, min(parsed, maximum))

    @classmethod
    def _normalize_int(cls, value: Optional[int], current: int, minimum: int, maximum: int) -> int:
        if value is None:
            return current
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return current
        return max(minimum, min(parsed, maximum))

    @classmethod
    def get_model_for_role(cls, role: str = "default") -> str:
        if role == "planner":
            return cls.PLANNER_MODEL or cls.LLM_MODEL
        if role == "executor":
            return cls.EXECUTOR_MODEL or cls.LLM_MODEL
        if role == "vision":
            return cls.VISION_MODEL or cls.LLM_MODEL
        return cls.LLM_MODEL

    @classmethod
    def get_active_api_key(cls, provider: Optional[str] = None) -> Optional[str]:
        active_provider = cls._normalize_provider(provider or cls.LLM_PROVIDER)
        if active_provider in ("openai", "custom"):
            return cls.OPENAI_API_KEY
        if active_provider == "gemini":
            return cls.GEMINI_API_KEY
        if active_provider == "deepseek":
            return cls.DEEPSEEK_API_KEY
        if active_provider in ("chatglm", "zhipu"):
            return cls.CHATGLM_API_KEY
        if active_provider in ("claude", "anthropic"):
            return cls.ANTHROPIC_API_KEY
        return None

    @classmethod
    def get_active_base_url(cls, provider: Optional[str] = None) -> str:
        active_provider = cls._normalize_provider(provider or cls.LLM_PROVIDER)
        if active_provider in ("openai", "custom"):
            return cls.OPENAI_BASE_URL or cls.RESOURCE_PACK_BASE_URL
        if active_provider in ("chatglm", "zhipu"):
            return cls.CHATGLM_BASE_URL or "https://open.bigmodel.cn/api/paas/v4"
        if active_provider == "deepseek":
            return "https://api.deepseek.com/v1"
        return ""

    @classmethod
    def normalize_runtime_config(cls):
        """进程启动时统一收敛模型配置，避免旧值残留。"""
        cls.LLM_PROVIDER = cls._normalize_provider(cls.LLM_PROVIDER)
        cls.LLM_MODEL = cls._normalize_model_name(cls.LLM_MODEL, cls.RESOURCE_PACK_MODEL)
        cls.OPENAI_MODEL = cls._normalize_model_name(cls.OPENAI_MODEL, cls.LLM_MODEL)
        cls.OPENAI_BASE_URL = cls._normalize_base_url(cls.LLM_PROVIDER, cls.OPENAI_BASE_URL)
        cls.VISION_MODEL = cls._normalize_model_name(cls.VISION_MODEL, cls.LLM_MODEL)
        cls.PLANNER_MODEL = cls._normalize_model_name(cls.PLANNER_MODEL, cls.LLM_MODEL)
        cls.EXECUTOR_MODEL = cls._normalize_model_name(cls.EXECUTOR_MODEL, cls.LLM_MODEL)
        cls.LLM_TEMPERATURE = cls._normalize_float(cls.LLM_TEMPERATURE, 0.0, 0.0, 2.0)
        cls.LLM_TOP_P = cls._normalize_float(cls.LLM_TOP_P, 1.0, 0.1, 1.0)
        cls.LLM_MAX_TOKENS = cls._normalize_int(cls.LLM_MAX_TOKENS, 4096, 256, 32768)

    @classmethod
    def update_llm_config(cls, provider: str = None, model: str = None,
                          api_key: str = None, base_url: str = None,
                          planner_model: str = None, executor_model: str = None,
                          vision_model: str = None, temperature: float = None,
                          top_p: float = None, max_tokens: int = None):
        """
        动态更新 LLM 配置（由前端 Settings UI 调用）。
        资源包锁定开启时，会强制收敛到统一的 Claude Haiku 配置，
        避免前后端配置漂移导致误扣费。
        """
        updates = {}
        effective_provider = cls._normalize_provider(provider or cls.LLM_PROVIDER)
        effective_model = cls._normalize_model_name(model, cls.LLM_MODEL)
        effective_base_url = cls._normalize_base_url(effective_provider, base_url or cls.OPENAI_BASE_URL)
        effective_vision_model = cls._normalize_model_name(vision_model, cls.VISION_MODEL or effective_model)
        effective_planner_model = cls._normalize_model_name(planner_model, cls.PLANNER_MODEL or effective_model)
        effective_executor_model = cls._normalize_model_name(executor_model, cls.EXECUTOR_MODEL or effective_model)
        effective_temperature = cls._normalize_float(temperature, cls.LLM_TEMPERATURE, 0.0, 2.0)
        effective_top_p = cls._normalize_float(top_p, cls.LLM_TOP_P, 0.1, 1.0)
        effective_max_tokens = cls._normalize_int(max_tokens, cls.LLM_MAX_TOKENS, 256, 32768)

        cls.LLM_PROVIDER = effective_provider
        cls.LLM_MODEL = effective_model
        cls.VISION_MODEL = effective_vision_model
        cls.PLANNER_MODEL = effective_planner_model
        cls.EXECUTOR_MODEL = effective_executor_model
        cls.LLM_TEMPERATURE = effective_temperature
        cls.LLM_TOP_P = effective_top_p
        cls.LLM_MAX_TOKENS = effective_max_tokens

        updates["LLM_PROVIDER"] = effective_provider
        updates["LLM_MODEL"] = effective_model
        updates["VISION_MODEL"] = effective_vision_model
        updates["PLANNER_MODEL"] = effective_planner_model
        updates["EXECUTOR_MODEL"] = effective_executor_model
        updates["LLM_TEMPERATURE"] = effective_temperature
        updates["LLM_TOP_P"] = effective_top_p
        updates["LLM_MAX_TOKENS"] = effective_max_tokens

        if effective_provider in ("openai", "custom"):
            cls.OPENAI_MODEL = effective_model
            cls.OPENAI_BASE_URL = effective_base_url
            updates["OPENAI_MODEL"] = effective_model
            updates["OPENAI_BASE_URL"] = effective_base_url
            if api_key is not None and api_key.strip():
                cls.OPENAI_API_KEY = api_key.strip()
                updates["OPENAI_API_KEY"] = api_key.strip()
        elif effective_provider == "gemini":
            cls.GEMINI_MODEL = effective_model
            updates["GEMINI_MODEL"] = effective_model
            if api_key is not None and api_key.strip():
                cls.GEMINI_API_KEY = api_key.strip()
                updates["GEMINI_API_KEY"] = api_key.strip()
        elif effective_provider == "deepseek":
            cls.DEEPSEEK_MODEL = effective_model
            updates["DEEPSEEK_MODEL"] = effective_model
            if api_key is not None and api_key.strip():
                cls.DEEPSEEK_API_KEY = api_key.strip()
                updates["DEEPSEEK_API_KEY"] = api_key.strip()
        elif effective_provider in ("chatglm", "zhipu"):
            cls.CHATGLM_MODEL = effective_model
            cls.CHATGLM_BASE_URL = cls._normalize_base_url("chatglm", base_url or cls.CHATGLM_BASE_URL)
            updates["CHATGLM_MODEL"] = effective_model
            updates["CHATGLM_BASE_URL"] = cls.CHATGLM_BASE_URL
            if api_key is not None and api_key.strip():
                cls.CHATGLM_API_KEY = api_key.strip()
                updates["CHATGLM_API_KEY"] = api_key.strip()
        elif effective_provider in ("claude", "anthropic"):
            cls.ANTHROPIC_MODEL = effective_model
            updates["ANTHROPIC_MODEL"] = effective_model
            if api_key is not None and api_key.strip():
                cls.ANTHROPIC_API_KEY = api_key.strip()
                updates["ANTHROPIC_API_KEY"] = api_key.strip()

        # 将配置覆写到 .env 文件中
        if updates:
            cls._write_env_file(updates)

        # 清除 LLM 缓存，下次调用时重新创建
        try:
            from core.llm_manager import LLMManager
            LLMManager.invalidate_cache()
        except Exception:
            pass

    @classmethod
    def _write_env_file(cls, updates: dict):
        """将更新的配置写入到项目根目录的 .env 文件中（与 load_dotenv 读取路径一致）"""
        import re
        
        # 统一使用根目录的 .env（复用模块顶部常量）
        env_path = str(_ROOT_DIR / ".env")
        
        if not os.path.exists(env_path):
            lines = ["# AI Test Platform - Environment Configuration\n"]
        else:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
        # 覆写已有的配置，或者追加新的配置
        for key, value in updates.items():
            if value is None:
                continue
            
            key_pattern = re.compile(rf"^{key}\s*=")
            found = False
            for i, line in enumerate(lines):
                if key_pattern.match(line):
                    lines[i] = f"{key}={value}\n"
                    found = True
                    break
            
            if not found:
                lines.append(f"{key}={value}\n")
                
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    @classmethod
    def update_runtime_env(cls, updates: dict):
        """更新运行时环境变量并同步持久化到根目录 .env。"""
        normalized_updates = {}
        for key, value in updates.items():
            if value is None:
                continue
            text = str(value)
            normalized_updates[key] = text
            os.environ[key] = text
            if hasattr(cls, key):
                setattr(cls, key, text)
        if normalized_updates:
            cls._write_env_file(normalized_updates)

    @classmethod
    def set_notification_platform_event_verification_token(cls, token: str) -> dict:
        """设置通知平台事件订阅 verification token，并记录更新时间。"""
        normalized_token = (token or "").strip()
        # commander_chatops_events.created_at 由 SQLite datetime('now') 生成，使用 UTC。
        # 这里统一落成相同时区/格式，避免自检事件与 token 更新时间比较时出现错判。
        updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cls.update_runtime_env({
            "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN": normalized_token,
            "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT": updated_at,
        })
        return {
            "verification_token_configured": bool(normalized_token),
            "verification_token_updated_at": updated_at,
        }

    @classmethod
    def set_notification_platform_app_bot_credentials(cls, app_id: str, app_secret: str) -> dict:
        """设置通知平台应用机器人凭据，并记录更新时间。"""
        normalized_app_id = (app_id or "").strip()
        normalized_app_secret = (app_secret or "").strip()
        updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cls.update_runtime_env({
            "NOTIFICATION_PLATFORM_APP_ID": normalized_app_id,
            "NOTIFICATION_PLATFORM_APP_SECRET": normalized_app_secret,
            "NOTIFICATION_PLATFORM_APP_BOT_UPDATED_AT": updated_at,
        })
        return {
            "app_bot_configured": bool(normalized_app_id and normalized_app_secret),
            "app_bot_updated_at": updated_at,
        }

    @classmethod
    def get_llm_config(cls) -> dict:
        """返回当前 LLM 配置（脱敏）"""
        def mask(key: str) -> str:
            if not key:
                return ""
            if len(key) <= 8:
                return "***"
            return key[:4] + "***" + key[-4:]

        return {
            "provider": cls.LLM_PROVIDER,
            "model": cls.LLM_MODEL,
            "base_url": cls.get_active_base_url(),
            "api_key_masked": mask(cls.get_active_api_key() or ""),
            "vision_model": cls.VISION_MODEL,
            "planner_model": cls.PLANNER_MODEL or cls.LLM_MODEL,
            "executor_model": cls.EXECUTOR_MODEL or cls.LLM_MODEL,
            "temperature": cls.LLM_TEMPERATURE,
            "top_p": cls.LLM_TOP_P,
            "max_tokens": cls.LLM_MAX_TOKENS,
            "provider_locked": cls.LOCK_RESOURCE_PACK,
            "model_locked": cls.LOCK_RESOURCE_PACK,
            "allowed_models": [cls.RESOURCE_PACK_MODEL] if cls.LOCK_RESOURCE_PACK else [],
            "profile_name": "接口AI资源包" if cls.LOCK_RESOURCE_PACK else "自定义模型配置",
        }


Config.normalize_runtime_config()

