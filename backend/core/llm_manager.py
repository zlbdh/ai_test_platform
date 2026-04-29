"""
LLM 管理器 - 统一管理多提供商 LLM
支持：OpenAI, Gemini, DeepSeek, ChatGLM 等
"""
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_community.llms import FakeListLLM
from core.config import Config
import logging

logger = logging.getLogger(__name__)

# ── OpenAI SDK 兼容性修复 ─────────────────────────────────────────────────────
# langchain-openai >= 1.x 将 max_tokens 硬编码转为 max_completion_tokens (OpenAI 新 API),
# 但部分网关 (one-api / new-api 等) 不支持该字段，导致 400 INVALID_ARGUMENT。
# 通过 monkey-patch Completions.create 在调用前自动替换回 max_tokens。
try:
    from openai.resources.chat import completions as _oai_completions
    _original_create = _oai_completions.Completions.create

    def _patched_create(self, **kwargs):
        if "max_completion_tokens" in kwargs and "max_tokens" not in kwargs:
            kwargs["max_tokens"] = kwargs.pop("max_completion_tokens")
        return _original_create(self, **kwargs)

    _oai_completions.Completions.create = _patched_create
    logger.info("✅ OpenAI SDK patched: max_completion_tokens → max_tokens")
except Exception:
    pass  # openai SDK 不可用时跳过


class LLMManager:
    """LLM 管理器 - 统一接口管理多提供商"""
    
    # Caching
    _cached_llm: Optional[BaseChatModel] = None
    _cached_vision_llm: Optional[BaseChatModel] = None

    @staticmethod
    def invalidate_cache():
        """清除缓存的 LLM 实例（配置变更后调用）"""
        LLMManager._cached_llm = None
        LLMManager._cached_vision_llm = None
        logger.info("LLM cache invalidated — next call will create new instances")

    @staticmethod
    def _resolve_sampling_options(
        model: Optional[str],
        temperature: Optional[float],
        top_p: Optional[float],
    ) -> dict:
        """
        统一处理不同模型族对采样参数的兼容性。
        接口AI 的 Claude 路由不允许同时传 temperature 和 top_p，
        因此这里优先保留 temperature，避免 AI 分析/规划链路被 400 打断。
        """
        options = {"temperature": temperature}
        model_lower = (model or "").lower()
        normalized_top_p = top_p

        if model_lower.startswith("claude-") and temperature is not None and top_p is not None:
            normalized_top_p = None
            logger.info("[LLM] Claude 路由不支持同时指定 temperature 和 top_p，已自动忽略 top_p")

        if normalized_top_p is not None:
            options["top_p"] = normalized_top_p
        return options

    @staticmethod
    def get_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        fake_responses: Optional[list] = None
    ) -> BaseChatModel:
        """
        获取 LLM 实例 (Lazy Loaded Singleton by default if no custom params)
        """
        resolved_temperature = Config.LLM_TEMPERATURE if temperature is None else temperature
        resolved_top_p = Config.LLM_TOP_P if top_p is None else top_p
        resolved_max_tokens = Config.LLM_MAX_TOKENS if max_tokens is None else max_tokens
        # 判断是否使用默认参数（缓存条件）
        # model 等于 Config 默认值时也算默认调用，可以命中缓存
        is_default_call = (
            provider is None
            and temperature is None
            and top_p is None
            and max_tokens is None
            and fake_responses is None
            and (model is None or model == Config.LLM_MODEL or model == Config.PLANNER_MODEL or model == Config.EXECUTOR_MODEL)
        )
        
        if is_default_call and LLMManager._cached_llm:
            return LLMManager._cached_llm

        # 如果使用模拟 LLM
        if Config.USE_FAKE_LLM or (provider and provider.lower() == "fake"):
            pass # Logic continues below
            
        instance = LLMManager._create_llm_instance(
            provider,
            model,
            resolved_temperature,
            resolved_top_p,
            resolved_max_tokens,
            fake_responses,
        )
        
        # Cache if default call
        if is_default_call:
            LLMManager._cached_llm = instance
            
        return instance

    @staticmethod
    def _create_llm_instance(provider, model, temperature, top_p, max_tokens, fake_responses):
        # PROVIDER LOGIC:
        if Config.USE_FAKE_LLM or (provider and provider.lower() == "fake"):
             fake_plan_json = """{ "steps": [] }""" # Simplified
             responses = fake_responses or [fake_plan_json]
             return LLMManager._get_fake_chat_llm(responses)

        provider = provider or Config.LLM_PROVIDER
        model = model or Config.LLM_MODEL
        provider_lower = provider.lower()
        
        if provider_lower in ("openai", "custom"):
            instance = LLMManager._get_openai_llm(model, temperature, top_p, max_tokens)
        elif provider_lower == "gemini":
            instance = LLMManager._get_gemini_llm(model, temperature, top_p, max_tokens)
        elif provider_lower == "deepseek":
            instance = LLMManager._get_deepseek_llm(model, temperature, top_p, max_tokens)
        elif provider_lower in ["chatglm", "zhipu"]:
            instance = LLMManager._get_chatglm_llm(model, temperature, top_p, max_tokens)
        elif provider_lower in ["claude", "anthropic"]:
            instance = LLMManager._get_claude_llm(model, temperature, top_p, max_tokens)
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

        # 注入 Tracing Callback — 使得 chain 管道中的 invoke 也能被自动追踪
        try:
            from core.tracing import Tracing
            tracer = Tracing.get_instance()

            from langchain_core.callbacks import BaseCallbackHandler

            class _TracingCallback(BaseCallbackHandler):
                """自动 Tracing 回调：记录每次 LLM 调用到 Tracing 系统"""

                def on_llm_start(self, serialized, prompts, **kwargs):
                    pass  # 起始钩子 — 暂不记录

                def on_llm_end(self, response, **kwargs):
                    try:
                        token_usage = {}
                        if hasattr(response, "llm_output") and response.llm_output:
                            token_usage = response.llm_output.get("token_usage", {})
                        tracer.record_llm_call(
                            agent_name="chain",
                            model_name=model or "unknown",
                            input_tokens=token_usage.get("prompt_tokens", 0),
                            output_tokens=token_usage.get("completion_tokens", 0),
                            duration_ms=0,
                            success=True,
                        )
                    except Exception:
                        pass

                def on_llm_error(self, error, **kwargs):
                    try:
                        tracer.record_llm_call(
                            agent_name="chain",
                            model_name=model or "unknown",
                            input_tokens=0,
                            output_tokens=0,
                            duration_ms=0,
                            success=False,
                        )
                    except Exception:
                        pass

            # 将 callback 挂载到实例
            if hasattr(instance, "callbacks") and instance.callbacks is None:
                instance.callbacks = [_TracingCallback()]
            elif hasattr(instance, "callbacks") and isinstance(instance.callbacks, list):
                instance.callbacks.append(_TracingCallback())
        except Exception as e:
            logger.debug(f"[LLM] Tracing callback 注入失败（不影响功能）: {e}")

        return instance

    @staticmethod
    def _get_fake_chat_llm(responses: list):
        """获取模拟 LLM"""
        from langchain_core.messages import AIMessage
        from langchain_core.language_models import BaseChatModel
        
        class FakeChatModel(BaseChatModel):
            responses: list = []
            idx: int = 0
            
            def _generate(self, messages, stop=None, **kwargs):
                from langchain_core.outputs import ChatResult, ChatGeneration
                resp = self.responses[self.idx % len(self.responses)]
                self.idx += 1
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=resp))])
            
            @property
            def _llm_type(self):
                return "fake"
        
        return FakeChatModel(responses=responses)

    @staticmethod
    def get_embeddings():
        """获取 Embedding 模型（通过 OpenAI Gateway）"""
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=Config.EMBEDDING_MODEL,
            api_key=Config.OPENAI_API_KEY,
            openai_api_base=Config.OPENAI_BASE_URL,
            timeout=30
        )

    @staticmethod
    def _get_openai_llm(model: str, temperature: float, top_p: float, max_tokens: int):
        """获取 OpenAI LLM (通过 Gateway)"""
        from langchain_openai import ChatOpenAI
        api_key = Config.get_active_api_key("openai")
        base_url = Config.get_active_base_url("openai")
        sampling_options = LLMManager._resolve_sampling_options(model, temperature, top_p)
        # thinking 模型通常要求 temperature=1
        if "thinking" in (model or "").lower():
            sampling_options["temperature"] = 1
        # langchain-openai >= 1.x 会将 max_tokens 转换为 max_completion_tokens,
        # 但部分网关不支持。顶部 monkey-patch 已修复此问题，可安全使用标准参数。
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **sampling_options,
            max_tokens=max_tokens,
            request_timeout=Config.LLM_TIMEOUT,
            max_retries=2,
        )

    @staticmethod
    def _get_gemini_llm(model: str, temperature: float, top_p: float, max_tokens: int):
        """获取 Gemini LLM"""
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_tokens,
            request_timeout=Config.LLM_TIMEOUT,
            max_retries=2
        )

    @staticmethod
    def _get_deepseek_llm(model: str, temperature: float, top_p: float, max_tokens: int):
        """获取 DeepSeek LLM (通过 OpenAI 兼容接口)"""
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=Config.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            request_timeout=Config.LLM_TIMEOUT,
            max_retries=3
        )

    @staticmethod
    def _get_chatglm_llm(model: str, temperature: float, top_p: float, max_tokens: int):
        """获取 ChatGLM/智谱 LLM"""
        from langchain_openai import ChatOpenAI
        base_url = Config.CHATGLM_BASE_URL or "https://open.bigmodel.cn/api/paas/v4"
        return ChatOpenAI(
            model=model,
            api_key=Config.CHATGLM_API_KEY,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            request_timeout=Config.LLM_TIMEOUT,
            max_retries=3
        )

    @staticmethod
    def _get_claude_llm(model: str, temperature: float, top_p: float, max_tokens: int):
        """获取 Anthropic Claude LLM"""
        from langchain_anthropic import ChatAnthropic
        sampling_options = LLMManager._resolve_sampling_options(model, temperature, top_p)
        return ChatAnthropic(
            model=model,
            anthropic_api_key=Config.ANTHROPIC_API_KEY,
            **sampling_options,
            max_tokens=max_tokens,
        )

    @staticmethod
    def get_vision_llm() -> Optional[BaseChatModel]:
        """获取视觉模型 (Cached, Multi-Provider)"""
        if LLMManager._cached_vision_llm:
            return LLMManager._cached_vision_llm
            
        try:
            model = Config.get_model_for_role("vision")
            model_lower = model.lower() if model else ""
            
            if "gemini" in model_lower:
                # Gemini 原生 API
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = Config.GEMINI_API_KEY
                if not api_key: 
                    logger.warning("Vision LLM: GEMINI_API_KEY missing for Gemini vision model.")
                    return None
                LLMManager._cached_vision_llm = ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=api_key,
                    temperature=0
                )
            else:
                # 通过 OpenAI Gateway 统一路由 (支持 Claude, DeepSeek, 自定义模型等)
                from langchain_openai import ChatOpenAI
                api_key = Config.get_active_api_key("openai")
                base_url = Config.get_active_base_url("openai")
                if not api_key:
                    logger.warning("Vision LLM: OPENAI_API_KEY missing for gateway vision model.")
                    return None
                LLMManager._cached_vision_llm = ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=0,
                    request_timeout=60,
                    max_retries=2
                )
            
            logger.info(f"Vision LLM initialized: {model}")
            return LLMManager._cached_vision_llm
        except Exception as e:
            logger.error(f"Vision model init failed: {e}")
            return None

# 便捷函数
def get_llm(fake_responses: Optional[list] = None, **kwargs) -> BaseChatModel:
    return LLMManager.get_llm(fake_responses=fake_responses, **kwargs)

def get_llm_for_role(role: str = "default", fake_responses: Optional[list] = None, **kwargs) -> BaseChatModel:
    model = kwargs.pop("model", None) or Config.get_model_for_role(role)
    return LLMManager.get_llm(model=model, fake_responses=fake_responses, **kwargs)

def get_vision_llm() -> Optional[BaseChatModel]:
    return LLMManager.get_vision_llm()


def invoke_with_fallback(primary_llm, messages, fallback_provider: str = "openai", fallback_model: str = None):
    """
    使用主模型调用，失败时自动降级到备用模型。
    自动接入 Tracing 链路追踪。
    """
    import time as _time

    # === 速率限制：custom provider 限制每 3 秒最多 1 次调用 (适配 20 req/min) ===
    if Config.LLM_PROVIDER in ("custom",):
        if not hasattr(invoke_with_fallback, '_last_call_time'):
            invoke_with_fallback._last_call_time = 0
        elapsed_since_last = _time.time() - invoke_with_fallback._last_call_time
        if elapsed_since_last < 3.0:
            _time.sleep(3.0 - elapsed_since_last)
        invoke_with_fallback._last_call_time = _time.time()

    # 获取模型名称（用于 tracing）
    model_name = getattr(primary_llm, 'model_name', None) or getattr(primary_llm, 'model', 'unknown')

    try:
        from core.tracing import get_tracer
        tracer = get_tracer()
    except Exception:
        tracer = None

    try:
        t0 = _time.time()
        result = primary_llm.invoke(messages)
        elapsed = _time.time() - t0
        logger.info(f"LLM invoke OK ({elapsed:.1f}s, {len(str(result.content))} chars)")

        # 记录 Tracing
        if tracer:
            try:
                usage = getattr(result, 'usage_metadata', None) or {}
                input_tokens = usage.get('input_tokens', 0) if isinstance(usage, dict) else 0
                output_tokens = usage.get('output_tokens', 0) if isinstance(usage, dict) else 0

                from core.tracing import TraceSpan
                tracer.record(TraceSpan(
                    trace_id=tracer.current_trace_id or "",
                    agent_name="llm",
                    action="invoke",
                    model=str(model_name),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    duration_ms=elapsed * 1000,
                    status="ok",
                ))
            except Exception:
                pass  # tracing 不影响主流程

        return result
    except Exception as primary_err:
        logger.warning(f"Primary LLM failed: {primary_err}. Trying fallback...")

        # 记录失败 tracing
        if tracer:
            try:
                from core.tracing import TraceSpan
                tracer.record(TraceSpan(
                    trace_id=tracer.current_trace_id or "",
                    agent_name="llm",
                    action="invoke_failed",
                    model=str(model_name),
                    status="error",
                    error_message=str(primary_err),
                ))
            except Exception:
                pass

        try:
            fallback_llm = LLMManager.get_llm(
                provider=fallback_provider,
                model=fallback_model or Config.LLM_MODEL
            )
            t0 = _time.time()
            result = fallback_llm.invoke(messages)
            elapsed = _time.time() - t0
            logger.info(f"Fallback LLM OK ({elapsed:.1f}s)")

            # 记录 fallback tracing
            if tracer:
                try:
                    from core.tracing import TraceSpan
                    tracer.record(TraceSpan(
                        trace_id=tracer.current_trace_id or "",
                        agent_name="llm",
                        action="invoke_fallback",
                        model=str(fallback_model or Config.LLM_MODEL),
                        duration_ms=elapsed * 1000,
                        status="ok",
                    ))
                except Exception:
                    pass

            return result
        except Exception as fallback_err:
            logger.error(f"Fallback LLM also failed: {fallback_err}")
            raise primary_err  # 抛出原始错误


def traced_invoke(llm, messages, agent_name: str = "unknown", action: str = "invoke"):
    """
    带链路追踪的 LLM 调用便捷函数。

    用法：
        from core.llm_manager import get_llm, traced_invoke
        llm = get_llm()
        result = traced_invoke(llm, messages, agent_name="planner", action="generate_plan")
    """
    import time as _time

    model_name = getattr(llm, 'model_name', None) or getattr(llm, 'model', 'unknown')

    try:
        from core.tracing import get_tracer, TraceSpan
        tracer = get_tracer()
    except Exception:
        tracer = None

    t0 = _time.time()
    try:
        result = llm.invoke(messages)
        elapsed = _time.time() - t0

        if tracer:
            try:
                usage = getattr(result, 'usage_metadata', None) or {}
                input_tokens = usage.get('input_tokens', 0) if isinstance(usage, dict) else 0
                output_tokens = usage.get('output_tokens', 0) if isinstance(usage, dict) else 0
                tracer.record(TraceSpan(
                    trace_id=tracer.current_trace_id or "",
                    agent_name=agent_name,
                    action=action,
                    model=str(model_name),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    duration_ms=elapsed * 1000,
                    status="ok",
                ))
            except Exception:
                pass

        return result
    except Exception as e:
        elapsed = _time.time() - t0
        if tracer:
            try:
                tracer.record(TraceSpan(
                    trace_id=tracer.current_trace_id or "",
                    agent_name=agent_name,
                    action=action,
                    model=str(model_name),
                    duration_ms=elapsed * 1000,
                    status="error",
                    error_message=str(e),
                ))
            except Exception:
                pass
        raise
