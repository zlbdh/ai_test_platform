"""
Platform configuration
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load the .env file if present
try:
    from dotenv import load_dotenv
    # Browser Debug Port
    CHROME_DEBUG_PORT: int = int(os.getenv("CHROME_DEBUG_PORT", "8030"))
    # Get the project root, two levels above core/
    _CORE_DIR = Path(__file__).resolve().parent
    _BACKEND_DIR = _CORE_DIR.parent
    _ROOT_DIR = _BACKEND_DIR.parent
    env_path = _ROOT_DIR / '.env'
    # Try loading the root .env file
    load_dotenv(env_path, override=True) if env_path.exists() else load_dotenv(override=True)
except ImportError:
    # Skip if python-dotenv is not installed
    pass


class Config:
    """Platform configuration class"""
    
    # Project root (reuse the Path constant above)
    PROJECT_ROOT: str = str(_BACKEND_DIR)
    _root_str: str = str(_ROOT_DIR)

    # Resource pack locking configuration
    RESOURCE_PACK_PROVIDER: str = "openai"
    RESOURCE_PACK_MODEL: str = os.getenv("RESOURCE_PACK_MODEL", "claude-haiku-4-5-20251001")
    RESOURCE_PACK_BASE_URL: str = os.getenv("RESOURCE_PACK_BASE_URL", "https://api.openai.com/v1")
    LOCK_RESOURCE_PACK: bool = os.getenv("LOCK_RESOURCE_PACK", "true").lower() == "true"
    
    # LLM configuration
    USE_FAKE_LLM: bool = os.getenv("USE_FAKE_LLM", "false").lower() == "true"
    
    # LLM provider configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", RESOURCE_PACK_PROVIDER)  # openai, gemini, deepseek, chatglm, claude
    LLM_MODEL: str = os.getenv("LLM_MODEL", RESOURCE_PACK_MODEL)
    
    # Multi-agent model configuration (inherits LLM_MODEL by default)
    PLANNER_MODEL: str = os.getenv("PLANNER_MODEL", "")
    EXECUTOR_MODEL: str = os.getenv("EXECUTOR_MODEL", "")
    
    # OpenAI configuration (Gateway Override)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")  # Must be configured through environment variables or .env
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", RESOURCE_PACK_MODEL)  # Backward compatibility
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL", RESOURCE_PACK_BASE_URL)
    
    # Google Gemini configuration
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

    # Browser-Use (Fallback)
    BROWSER_USE_API_KEY: Optional[str] = os.getenv("BROWSER_USE_API_KEY")
    
    # DeepSeek configuration
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # ChatGLM (Zhipu AI) configuration
    CHATGLM_API_KEY: Optional[str] = os.getenv("CHATGLM_API_KEY")
    CHATGLM_MODEL: str = os.getenv("CHATGLM_MODEL", "glm-4")
    CHATGLM_BASE_URL: Optional[str] = os.getenv("CHATGLM_BASE_URL")
    
    # Anthropic Claude configuration
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
    

    # LangSmith / LangChain observability configuration
    LANGCHAIN_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "ai-test-platform")
    
    # Test target configuration
    TARGET_URL: str = os.getenv("TARGET_URL", "http://localhost:3000")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8020")
    PUBLIC_API_BASE_URL: str = os.getenv("PUBLIC_API_BASE_URL", os.getenv("API_BASE_URL", "http://localhost:8020"))
    PUBLIC_API_BASE_URL_UPDATED_AT: str = os.getenv("PUBLIC_API_BASE_URL_UPDATED_AT", "").strip()
    NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN: str = os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "").strip()
    NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT: str = os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "").strip()
    NOTIFICATION_PLATFORM_APP_ID: str = os.getenv("NOTIFICATION_PLATFORM_APP_ID", "").strip()
    NOTIFICATION_PLATFORM_APP_SECRET: str = os.getenv("NOTIFICATION_PLATFORM_APP_SECRET", "").strip()
    NOTIFICATION_PLATFORM_APP_BOT_UPDATED_AT: str = os.getenv("NOTIFICATION_PLATFORM_APP_BOT_UPDATED_AT", "").strip()
    
    # Database configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "test_db")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_CONNECTION_STRING: str = os.getenv("DB_CONNECTION_STRING", "")

    # UI test configuration
    BROWSER_TYPE: str = os.getenv("BROWSER_TYPE", "chromium")  # chromium, firefox, webkit
    # HEADLESS: read from the environment; default to false for debugging
    HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"
    # Screenshot directory: relative paths resolve from the project root
    _screenshot_dir = os.getenv("SCREENSHOT_DIR", "./screenshots")
    SCREENSHOT_DIR: str = _screenshot_dir if os.path.isabs(_screenshot_dir) else os.path.join(
        str(_ROOT_DIR), _screenshot_dir.lstrip('./')
    )

    # Logging configuration
    _log_dir = os.getenv("LOG_DIR", "./logs")
    LOG_DIR: str = _log_dir if os.path.isabs(_log_dir) else os.path.join(
        str(_ROOT_DIR), _log_dir.lstrip('./')
    )
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Vision Config
    ENABLE_VISION: bool = os.getenv("ENABLE_VISION", "true").lower() == "true"
    VISION_MODEL: str = os.getenv("VISION_MODEL", RESOURCE_PACK_MODEL)
    # Inspector visual quality configuration
    INSPECTOR_CONFIDENCE_THRESHOLD: float = float(os.getenv("INSPECTOR_CONFIDENCE_THRESHOLD", "0.7"))
    INSPECTOR_ENABLE_RAG: bool = os.getenv("INSPECTOR_ENABLE_RAG", "true").lower() == "true"

    # Timeout configuration
    UI_TIMEOUT: int = int(os.getenv("UI_TIMEOUT", "30000"))  # Milliseconds
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "120"))  # Seconds
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "600"))  # LLM timeout in seconds; thinking models require more time
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    LLM_TOP_P: float = float(os.getenv("LLM_TOP_P", "1"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    
    # Vector DB configuration
    _vector_db_path = os.getenv("VECTOR_DB_PATH", "./vector_db")
    VECTOR_DB_PATH: str = _vector_db_path if os.path.isabs(_vector_db_path) else os.path.join(
        str(_ROOT_DIR), _vector_db_path.lstrip('./')
    )
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")  # OpenAI default
    
    # RAG knowledge base configuration
    ENABLE_RAG: bool = os.getenv("ENABLE_RAG", "true").lower() == "true"
    _chroma_path = os.getenv("CHROMA_PATH", "./data/chroma_db")
    CHROMA_PATH: str = _chroma_path if os.path.isabs(_chroma_path) else os.path.join(
        str(_BACKEND_DIR),
        _chroma_path.lstrip('./')
    )
    
    # Git configuration
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
        """Normalize model configuration at startup to prevent stale values."""
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
        Update LLM configuration dynamically from the frontend Settings UI.
        When resource pack locking is enabled, enforce the shared Claude Haiku configuration
        to prevent unexpected charges caused by frontend/backend configuration drift.
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

        # Write configuration updates to .env
        if updates:
            cls._write_env_file(updates)

        # Clear cached LLM clients so the next call creates new instances
        try:
            from core.llm_manager import LLMManager
            LLMManager.invalidate_cache()
        except Exception:
            pass

    @classmethod
    def _write_env_file(cls, updates: dict):
        """Write updated configuration to the project root .env, matching the load_dotenv path"""
        import re
        
        # Use the root .env consistently, reusing the module constant
        env_path = str(_ROOT_DIR / ".env")
        
        if not os.path.exists(env_path):
            lines = ["# AI Test Platform - Environment Configuration\n"]
        else:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
        # Overwrite existing values or append new ones
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
        """Update runtime environment variables and persist them to the root .env."""
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
        """Set the notification platform event verification token and record its update time."""
        normalized_token = (token or "").strip()
        # commander_chatops_events.created_at uses SQLite datetime('now'), which produces UTC.
        # Use the same timezone and format to compare self-check event and token update times correctly.
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
        """Set notification platform app-bot credentials and record the update time."""
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
        """Return current LLM configuration with secrets masked"""
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
            "profile_name": "JieKou AI resource pack" if cls.LOCK_RESOURCE_PACK else "Custom model configuration",
        }


Config.normalize_runtime_config()

