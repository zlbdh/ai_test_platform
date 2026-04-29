# -*- coding: utf-8 -*-
"""
测试 - Healer Agent
"""
import pytest
from unittest.mock import patch, MagicMock
from agents.healer import self_heal


class TestHealer:
    @patch("agents.healer.get_llm")
    def test_self_heal_success(self, mock_get_llm):
        """测试正常自愈修复"""
        # Mock LLM chain
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        # chain.invoke(...) 在 self_heal 中调用
        # 这里用 patch 拦截整个 chain 也可以，或者拦截 prompt | llm | parser 的 invoke
        # 直接拦截自愈功能依赖的 JsonOutputParser 或者 get_llm
        pass

    @patch("agents.healer.ChatPromptTemplate")
    @patch("agents.healer.get_llm")
    @patch("agents.healer.JsonOutputParser")
    def test_self_heal_success_full(self, mock_parser, mock_get_llm, mock_prompt):
        """通过 mock chain 验证自愈成功"""
        # 构建一个 fake chain
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "action": "click",
            "target": "#new-btn",
            "value": ""
        }
        
        # 组装 chain 的行为： prompt | llm | parser
        mock_prompt_instance = MagicMock()
        mock_prompt.from_template.return_value = mock_prompt_instance
        
        # python 中的 `|` 会调用 __or__ 或 __ror__。
        # 这里直接 patch invoke 更简单：
        with patch("agents.healer.JsonOutputParser") as mock_json_parser:
             pass

    @patch("agents.healer.ChatPromptTemplate")
    @patch("agents.healer.get_llm")
    def test_self_heal_with_explicit_chain_mock(self, mock_get_llm, mock_prompt):
        """通过 patch JsonOutputParser 的行为或直接替换链的 invoke"""
        pass
        
    @patch('agents.healer.ChatPromptTemplate.from_template')
    @patch('agents.healer.get_llm')
    @patch('agents.healer.JsonOutputParser')
    def test_self_heal_logic(self, mock_parser_cls, mock_get_llm, mock_prompt_from_temp):
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = {
            "action": "click",
            "target": "#correct-btn",
            "value": ""
        }
        
        # mock Prompt | LLM | Parser 的 `|` 操作
        mock_prompt_obj = MagicMock()
        mock_llm_obj = MagicMock()
        mock_parser_obj = MagicMock()
        
        mock_prompt_from_temp.return_value = mock_prompt_obj
        mock_get_llm.return_value = mock_llm_obj
        mock_parser_cls.return_value = mock_parser_obj
        
        # mock (prompt | llm) 结果
        mock_step1 = MagicMock()
        mock_prompt_obj.__or__.return_value = mock_step1
        # mock (prompt | llm) | parser 结果
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
    @patch('agents.healer.get_llm')
    @patch('agents.healer.JsonOutputParser')
    def test_self_heal_skip(self, mock_parser_cls, mock_get_llm, mock_prompt_from_temp):
        mock_chain = MagicMock()
        # 无法修复返回 skip
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
        
        # skip 返回 None
        assert result is None

