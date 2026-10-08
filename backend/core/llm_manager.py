"""
LLM manager - unified management across providers
Supports OpenAI, Gemini, DeepSeek, ChatGLM, and other providers
"""
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_community.llms import FakeListLLM
from core.config import Config
import logging

logger = logging.getLogger(__name__)

# ── OpenAI SDK compatibility fix ─────────────────────────────────────────────────────
# langchain-openai >= 1.x unconditionally converts max_tokens to max_completion_tokens for the new OpenAI API,
# but some gateways, including one-api and new-api, reject this field with 400 INVALID_ARGUMENT.
# Patch Completions.create to restore max_tokens before each call.
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
    pass  # Skip when the OpenAI SDK is unavailable


class LLMManager:
    """LLM manager with a unified provider interface"""

    # Caching
    _cached_llm: Optional[BaseChatModel] = None
    _cached_vision_llm: Optional[BaseChatModel] = None

    @staticmethod
    def invalidate_cache():
        """Clear cached LLM instances after configuration changes"""
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
        Handle sampling-parameter compatibility across model families consistently.
        JieKou AI's Claude route does not accept temperature and top_p together,
        so prefer temperature to prevent HTTP 400 errors in AI analysis and planning.
        """
        options = {"temperature": temperature}
        model_lower = (model or "").lower()
        normalized_top_p = top_p

        if model_lower.startswith("claude-") and temperature is not None and top_p is not None:
            normalized_top_p = None
            logger.info("[LLM] The Claude route does not support temperature and top_p together; ignoring top_p")

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
        Get an LLM instance (Lazy Loaded Singleton by default if no custom params)
        """
        resolved_temperature = Config.LLM_TEMPERATURE if temperature is None else temperature
        resolved_top_p = Config.LLM_TOP_P if top_p is None else top_p
        resolved_max_tokens = Config.LLM_MAX_TOKENS if max_tokens is None else max_tokens
        # Determine whether default parameters are in use for caching
        # A model matching the Config default also qualifies for the cache
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

        # When using a fake LLM
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
            raise ValueError(f"Unsupported LLM provider: {provider}")

        # Inject a tracing callback to trace invoke calls within chains automatically
        try:
            from core.tracing import Tracing
            tracer = Tracing.get_instance()

            from langchain_core.callbacks import BaseCallbackHandler

            class _TracingCallback(BaseCallbackHandler):
                """Automatic tracing callback: record each LLM call in the tracing system"""

                def on_llm_start(self, serialized, prompts, **kwargs):
                    pass  # Start hook: no recording yet

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

            # Attach the callback to the instance
            if hasattr(instance, "callbacks") and instance.callbacks is None:
                instance.callbacks = [_TracingCallback()]
            elif hasattr(instance, "callbacks") and isinstance(instance.callbacks, list):
                instance.callbacks.append(_TracingCallback())
        except Exception as e:
            logger.debug(f"[LLM] Failed to attach the tracing callback (nonblocking): {e}")

        return instance

    @staticmethod
    def _get_fake_chat_llm(responses: list):
        """Get a fake LLM"""
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
        """Get an embedding model through the OpenAI gateway"""
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=Config.EMBEDDING_MODEL,
            api_key=Config.OPENAI_API_KEY,
            openai_api_base=Config.OPENAI_BASE_URL,
            timeout=30
        )

    @staticmethod
    def _get_openai_llm(model: str, temperature: float, top_p: float, max_tokens: int):
        """Get an OpenAI LLM through the gateway"""
        from langchain_openai import ChatOpenAI
        api_key = Config.get_active_api_key("openai")
        base_url = Config.get_active_base_url("openai")
        sampling_options = LLMManager._resolve_sampling_options(model, temperature, top_p)
        # Thinking models typically require temperature=1
        if "thinking" in (model or "").lower():
            sampling_options["temperature"] = 1
        # langchain-openai >= 1.x converts max_tokens to max_completion_tokens,
        # which some gateways do not support. The patch above lets us use the standard parameter safely.
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
        """Get a Gemini LLM"""
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
        """Get a DeepSeek LLM through the OpenAI-compatible API"""
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
        """Get a ChatGLM/Zhipu LLM"""
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
        """Get an Anthropic Claude LLM"""
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
        """Get a vision model (Cached, Multi-Provider)"""
        if LLMManager._cached_vision_llm:
            return LLMManager._cached_vision_llm

        try:
            model = Config.get_model_for_role("vision")
            model_lower = model.lower() if model else ""

            if "gemini" in model_lower:
                # Native Gemini API
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
                # Route through the OpenAI gateway, supporting Claude, DeepSeek, custom models, and others
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

# Convenience functions
def get_llm(fake_responses: Optional[list] = None, **kwargs) -> BaseChatModel:
    return LLMManager.get_llm(fake_responses=fake_responses, **kwargs)

def get_llm_for_role(role: str = "default", fake_responses: Optional[list] = None, **kwargs) -> BaseChatModel:
    model = kwargs.pop("model", None) or Config.get_model_for_role(role)
    return LLMManager.get_llm(model=model, fake_responses=fake_responses, **kwargs)

def get_vision_llm() -> Optional[BaseChatModel]:
    return LLMManager.get_vision_llm()


def invoke_with_fallback(primary_llm, messages, fallback_provider: str = "openai", fallback_model: str = None):
    """
    Call the primary model and fall back to the backup model on failure.
    Automatically integrate request tracing.
    """
    import time as _time

    # === Rate limit: allow at most one custom-provider call every three seconds (20 requests/minute) ===
    if Config.LLM_PROVIDER in ("custom",):
        if not hasattr(invoke_with_fallback, '_last_call_time'):
            invoke_with_fallback._last_call_time = 0
        elapsed_since_last = _time.time() - invoke_with_fallback._last_call_time
        if elapsed_since_last < 3.0:
            _time.sleep(3.0 - elapsed_since_last)
        invoke_with_fallback._last_call_time = _time.time()

    # Get the model name for tracing
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

        # Record tracing information
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
                pass  # Tracing must not interrupt the main workflow

        return result
    except Exception as primary_err:
        logger.warning(f"Primary LLM failed: {primary_err}. Trying fallback...")

        # Record failed-call tracing
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

            # Record fallback tracing
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
            raise primary_err  # Raise the original error


def traced_invoke(llm, messages, agent_name: str = "unknown", action: str = "invoke"):
    """
    Convenience function for traced LLM calls.

    Usage:
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
