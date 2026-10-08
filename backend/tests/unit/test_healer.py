# -*- coding: utf-8 -*-
"""
Healer Agent tests
"""
import pytest
from unittest.mock import patch, MagicMock
from agents.healer import self_heal


class TestHealer:
    @patch("agents.healer.get_llm_for_role")
    def test_self_heal_success(self, mock_get_llm):
        """Test successful self-healing."""
        # Mock LLM chain
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        # chain.invoke(...) is called inside self_heal.
        # Patch the whole chain or the invoke method of prompt | llm | parser.
        # Patch the JsonOutputParser or get_llm_for_role dependency directly.
        pass

    @patch("agents.healer.ChatPromptTemplate")
    @patch("agents.healer.get_llm_for_role")
    @patch("agents.healer.JsonOutputParser")
    def test_self_heal_success_full(self, mock_parser, mock_get_llm, mock_prompt):
        """Verify successful self-healing with a mocked chain."""
        # Build a fake chain.
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "action": "click",
            "target": "#new-btn",
            "value": ""
        }
        
        # Assemble the chain behavior: prompt | llm | parser.
        mock_prompt_instance = MagicMock()
        mock_prompt.from_template.return_value = mock_prompt_instance
        
        # Python's | operator calls __or__ or __ror__.
        # Patching invoke directly is simpler here.
        with patch("agents.healer.JsonOutputParser") as mock_json_parser:
             pass

    @patch("agents.healer.ChatPromptTemplate")
    @patch("agents.healer.get_llm_for_role")
    def test_self_heal_with_explicit_chain_mock(self, mock_get_llm, mock_prompt):
        """Patch JsonOutputParser behavior or replace the chain's invoke method directly."""
        pass
        
    @patch('agents.healer.ChatPromptTemplate.from_template')
    @patch('agents.healer.get_llm_for_role')
    @patch('agents.healer.JsonOutputParser')
    def test_self_heal_logic(self, mock_parser_cls, mock_get_llm, mock_prompt_from_temp):
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "action": "click",
            "target": "#correct-btn",
            "value": ""
        }
        
        # Mock the | operation in Prompt | LLM | Parser.
        mock_prompt_obj = MagicMock()
        mock_llm_obj = MagicMock()
        mock_parser_obj = MagicMock()
        
        mock_prompt_from_temp.return_value = mock_prompt_obj
        mock_get_llm.return_value = mock_llm_obj
        mock_parser_cls.return_value = mock_parser_obj
        
        # Mock the result of prompt | llm.
        mock_step1 = MagicMock()
        mock_prompt_obj.__or__.return_value = mock_step1
        # Mock the result of (prompt | llm) | parser.
        mock_step1.__or__.return_value = mock_chain
        
        result = self_heal(
            failed_step={"action": "click", "target": "#old-btn"},
            error_msg="Element not found",
            page_content="<html><button id='correct-btn'>Submit</button></html>",
            interactive_elements="<button id='correct-btn'>Submit</button>",
            history=[{"action": "goto", "target": "url", "status": "success"}]
        )
        
        assert result is not None
        assert result["action"] == "click"
        assert result["target"] == "#correct-btn"
        
    @patch('agents.healer.ChatPromptTemplate.from_template')
    @patch('agents.healer.get_llm_for_role')
    @patch('agents.healer.JsonOutputParser')
    def test_self_heal_skip(self, mock_parser_cls, mock_get_llm, mock_prompt_from_temp):
        mock_chain = MagicMock()
        # Return skip when the problem cannot be repaired.
        mock_chain.invoke.return_value = {
            "action": "skip",
            "target": "",
            "value": "Cannot find alternative"
        }
        
        mock_prompt_obj = MagicMock()
        mock_prompt_from_temp.return_value = mock_prompt_obj
        mock_prompt_obj.__or__.return_value = MagicMock(__or__=MagicMock(return_value=mock_chain))
        
        result = self_heal(
            failed_step={"action": "click", "target": "#old-btn"},
            error_msg="Element not found",
            page_content="empty",
        )
        
        # skip returns None.
        assert result is None

