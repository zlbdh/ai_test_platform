# -*- coding: utf-8 -*-
"""
Tests for the LLM Manager module.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestLLMManager:
    """LLM Manager unit tests."""

    def test_get_llm_default_provider(self):
        """Test default provider selection."""
        from core.llm_manager import LLMManager
        
        with patch.object(LLMManager, '_get_openai_llm') as mock_openai:
            mock_openai.return_value = MagicMock()
            # Use OpenAI by default.
            with patch('core.config.Config.LLM_PROVIDER', 'openai'):
                llm = LLMManager.get_llm()
                assert llm is not None

    def test_get_llm_gemini_provider(self):
        """Test the Gemini provider."""
        from core.llm_manager import LLMManager
        
        with patch.object(LLMManager, '_get_gemini_llm') as mock_gemini:
            mock_gemini.return_value = MagicMock()
            llm = LLMManager._create_llm_instance('gemini', 'gemini-pro', 0, 1, 4096, None)
            mock_gemini.assert_called_once()

    def test_get_llm_unsupported_provider(self):
        """Test an unsupported provider."""
        from core.llm_manager import LLMManager
        
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMManager._create_llm_instance('unsupported', 'model', 0, 1, 4096, None)

    def test_get_vision_llm_gemini(self):
        """Test vision model selection through Gemini."""
        from core.llm_manager import LLMManager
        
        # Clear the cache.
        LLMManager._cached_vision_llm = None
        
        with patch('core.config.Config.VISION_MODEL', 'gemini-1.5-flash'):
            with patch('core.config.Config.GEMINI_API_KEY', 'test-key'):
                with patch('langchain_google_genai.ChatGoogleGenerativeAI') as mock_gemini:
                    mock_gemini.return_value = MagicMock()
                    vision_llm = LLMManager.get_vision_llm()
                    # Expect a Gemini call.
                    mock_gemini.assert_called_once()

    def test_get_vision_llm_gateway(self):
        """Test vision model selection through OpenAI Gateway."""
        from core.llm_manager import LLMManager
        
        # Clear the cache.
        LLMManager._cached_vision_llm = None
        
        with patch('core.config.Config.VISION_MODEL', 'claude-sonnet-4-5'):
            with patch('core.config.Config.OPENAI_API_KEY', 'test-key'):
                with patch('core.config.Config.OPENAI_BASE_URL', 'http://localhost:8045/v1'):
                    with patch('langchain_openai.ChatOpenAI') as mock_openai:
                        mock_openai.return_value = MagicMock()
                        vision_llm = LLMManager.get_vision_llm()
                        # Expect an OpenAI Gateway call.
                        mock_openai.assert_called_once()

    def test_llm_caching(self):
        """Test LLM caching."""
        from core.llm_manager import LLMManager
        
        # Clear the cache.
        LLMManager._cached_llm = None
        
        mock_llm = MagicMock()
        with patch.object(LLMManager, '_create_llm_instance', return_value=mock_llm):
            llm1 = LLMManager.get_llm()
            llm2 = LLMManager.get_llm()
            # Reuse the cached instance.
            assert llm1 is llm2

    def test_get_llm_uses_configured_sampling_params(self):
        """Default LLM calls should include the configured sampling parameters."""
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
        """Claude routing should omit top_p when both temperature and top_p are configured."""
        from core.llm_manager import LLMManager

        options = LLMManager._resolve_sampling_options(
            'claude-haiku-4-5-20251001',
            0.35,
            0.85,
        )

        assert options["temperature"] == 0.35
        assert "top_p" not in options
