# -*- coding: utf-8 -*-
"""
测试 - LLM Manager 模块
"""
import pytest
from unittest.mock import patch, MagicMock


class TestLLMManager:
    """LLM Manager 单元测试"""

    def test_get_llm_default_provider(self):
        """测试默认提供商获取"""
        from core.llm_manager import LLMManager
        
        with patch.object(LLMManager, '_get_openai_llm') as mock_openai:
            mock_openai.return_value = MagicMock()
            # 默认使用 openai
            with patch('core.config.Config.LLM_PROVIDER', 'openai'):
                llm = LLMManager.get_llm()
                assert llm is not None

    def test_get_llm_gemini_provider(self):
        """测试 Gemini 提供商"""
        from core.llm_manager import LLMManager
        
        with patch.object(LLMManager, '_get_gemini_llm') as mock_gemini:
            mock_gemini.return_value = MagicMock()
            llm = LLMManager._create_llm_instance('gemini', 'gemini-pro', 0, 1, 4096, None)
            mock_gemini.assert_called_once()

    def test_get_llm_unsupported_provider(self):
        """测试不支持的提供商"""
        from core.llm_manager import LLMManager
        
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMManager._create_llm_instance('unsupported', 'model', 0, 1, 4096, None)

    def test_get_vision_llm_gemini(self):
        """测试视觉模型获取 (Gemini 路径)"""
        from core.llm_manager import LLMManager
        
        # 清除缓存
        LLMManager._cached_vision_llm = None
        
        with patch('core.config.Config.VISION_MODEL', 'gemini-1.5-flash'):
            with patch('core.config.Config.GEMINI_API_KEY', 'test-key'):
                with patch('langchain_google_genai.ChatGoogleGenerativeAI') as mock_gemini:
                    mock_gemini.return_value = MagicMock()
                    vision_llm = LLMManager.get_vision_llm()
                    # 应该调用 Gemini
                    mock_gemini.assert_called_once()

    def test_get_vision_llm_gateway(self):
        """测试视觉模型获取 (OpenAI Gateway 路径)"""
        from core.llm_manager import LLMManager
        
        # 清除缓存
        LLMManager._cached_vision_llm = None
        
        with patch('core.config.Config.VISION_MODEL', 'claude-sonnet-4-5'):
            with patch('core.config.Config.OPENAI_API_KEY', 'test-key'):
                with patch('core.config.Config.OPENAI_BASE_URL', 'http://localhost:8045/v1'):
                    with patch('langchain_openai.ChatOpenAI') as mock_openai:
                        mock_openai.return_value = MagicMock()
                        vision_llm = LLMManager.get_vision_llm()
                        # 应该通过 OpenAI Gateway
                        mock_openai.assert_called_once()

    def test_llm_caching(self):
        """测试 LLM 缓存机制"""
        from core.llm_manager import LLMManager
        
        # 清除缓存
        LLMManager._cached_llm = None
        
        mock_llm = MagicMock()
        with patch.object(LLMManager, '_create_llm_instance', return_value=mock_llm):
            llm1 = LLMManager.get_llm()
            llm2 = LLMManager.get_llm()
            # 应该使用缓存
            assert llm1 is llm2

    def test_get_llm_uses_configured_sampling_params(self):
        """测试默认 LLM 调用会带上配置中的采样参数"""
        from core.llm_manager import LLMManager

        LLMManager._cached_llm = None
        with patch.object(LLMManager, '_create_llm_instance') as mock_create:
            mock_create.return_value = MagicMock()
            with patch('core.config.Config.LLM_TEMPERATURE', 0.25):
                with patch('core.config.Config.LLM_TOP_P', 0.8):
                    with patch('core.config.Config.LLM_MAX_TOKENS', 3072):
                        LLMManager.get_llm()
            _, kwargs = mock_create.call_args
            assert kwargs == {}
            args = mock_create.call_args.args
            assert args[2] == 0.25
            assert args[3] == 0.8
            assert args[4] == 3072

    def test_claude_sampling_options_drop_top_p_when_temperature_present(self):
        """测试 Claude 路由下同时配置 temperature/top_p 时会自动忽略 top_p"""
        from core.llm_manager import LLMManager

        options = LLMManager._resolve_sampling_options(
            'claude-haiku-4-5-20251001',
            0.35,
            0.85,
        )

        assert options["temperature"] == 0.35
        assert "top_p" not in options
