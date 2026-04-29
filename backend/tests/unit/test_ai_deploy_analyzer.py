import asyncio
import builtins
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

from services.ai_deploy_analyzer import (
    _fallback_detect,
    _get_dir_tree,
    _merge_context_fallback,
    _parse_llm_response,
    _read_key_files,
    analyze_project,
    detect_pom_suggestions,
    refine_deploy_config,
)


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ('{"tech_stack":"React","port":3000}', {"tech_stack": "React", "port": 3000}),
        ("```json\n{\"tech_stack\":\"Vue\",\"port\":5173}\n```", {"tech_stack": "Vue", "port": 5173}),
        ("分析结果如下：{\"tech_stack\":\"Python\",\"port\":8000}", {"tech_stack": "Python", "port": 8000}),
    ],
)
def test_parse_llm_response_supports_multiple_payload_shapes(raw_text: str, expected: dict):
    assert _parse_llm_response(raw_text) == expected


def test_get_dir_tree_skips_ignored_directories(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("export {};\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("", encoding="utf-8")

    tree = _get_dir_tree(tmp_path)

    assert "app.py" in tree
    assert "src/" in tree
    assert "index.ts" in tree
    assert "node_modules/" not in tree


def test_read_key_files_truncates_large_known_files(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"demo"}\n' + "x" * 2000, encoding="utf-8")
    (tmp_path / "README.md").write_text("not included", encoding="utf-8")

    content = _read_key_files(tmp_path)

    assert "### package.json" in content
    assert "...(截断)" in content
    assert "README.md" not in content


def test_fallback_detect_returns_rule_based_config(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"scripts":{"dev":"vite"},"dependencies":{"vue":"^3.5.0"},"devDependencies":{"vite":"^7.0.0"}}',
        encoding="utf-8",
    )

    result = _fallback_detect(tmp_path)

    assert result["source"] == "rule_fallback"
    assert "Vue" in result["tech_stack"]
    assert result["start_cmd"] == "npm run dev"


def test_analyze_project_appends_memory_hint_and_normalizes_ai_output(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
    captured = {}

    fake_llm_manager = ModuleType("core.llm_manager")
    fake_llm_manager.get_llm = lambda: object()
    fake_llm_manager.get_llm_for_role = lambda _role: object()

    def traced_invoke(_llm, messages, *, agent_name: str, action: str):
        captured["agent_name"] = agent_name
        captured["action"] = action
        captured["human_content"] = messages[1].content
        return type(
            "Result",
            (),
            {
                "content": (
                    '{"tech_stack":"React + Vite","install_cmd":"npm install",'
                    '"start_cmd":"npm run dev -- --host 0.0.0.0","build_cmd":"npm run build",'
                    '"port":"3000","env_vars":{"MODE":"test"},"notes":"已识别","confidence":"0.95"}'
                )
            },
        )()

    fake_llm_manager.traced_invoke = traced_invoke

    fake_messages = ModuleType("langchain_core.messages")

    class _Message:
        def __init__(self, content: str):
            self.content = content

    fake_messages.SystemMessage = _Message
    fake_messages.HumanMessage = _Message

    with patch.dict(sys.modules, {
        "core.llm_manager": fake_llm_manager,
        "langchain_core.messages": fake_messages,
    }):
        result = asyncio.run(
            analyze_project(
                tmp_path,
                label="前端",
                repo_url="https://example.com/demo.git",
                memory_hint="上次成功命令: npm run dev",
                current_env_text="SPRING_PROFILES_ACTIVE=test\nNACOS_GROUP=TEST",
            )
        )

    assert captured["agent_name"] == "deploy_analyzer"
    assert captured["action"] == "analyze_project"
    assert "上次成功命令" in captured["human_content"]
    assert "SPRING_PROFILES_ACTIVE=test" in captured["human_content"]
    assert result["source"] == "ai"
    assert result["port"] == 3000
    assert result["confidence"] == pytest.approx(0.95)
    assert result["env_vars"] == {"MODE": "test"}


def test_analyze_project_falls_back_when_llm_response_is_not_json(tmp_path: Path):
    fake_llm_manager = ModuleType("core.llm_manager")
    fake_llm_manager.get_llm = lambda: object()
    fake_llm_manager.get_llm_for_role = lambda _role: object()
    fake_llm_manager.traced_invoke = lambda *_args, **_kwargs: type("Result", (), {"content": "not json"})()

    fake_messages = ModuleType("langchain_core.messages")

    class _Message:
        def __init__(self, content: str):
            self.content = content

    fake_messages.SystemMessage = _Message
    fake_messages.HumanMessage = _Message

    with patch.dict(sys.modules, {
        "core.llm_manager": fake_llm_manager,
        "langchain_core.messages": fake_messages,
    }):
        with patch("services.ai_deploy_analyzer._fallback_detect", return_value={"source": "rule_fallback", "port": 81}):
            result = asyncio.run(analyze_project(tmp_path))

    assert result == {"source": "rule_fallback", "port": 81}


def test_detect_pom_suggestions_finds_problematic_module(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    module_dir = tmp_path / "sample-modules"
    module_dir.mkdir()
    (module_dir / "pom.xml").write_text(
        """
<project>
  <modules>
    <module>sample-aigc</module>
    <module>sample-system</module>
  </modules>
</project>
""".strip(),
        encoding="utf-8",
    )

    suggestions = detect_pom_suggestions(tmp_path)

    assert len(suggestions) == 1
    assert suggestions[0]["file"] == "sample-modules\\pom.xml"
    assert suggestions[0]["module"] == "sample-aigc"
    assert suggestions[0]["new_modules"] == ["sample-system"]


def test_refine_deploy_config_falls_back_to_context_merge():
    initial_config = {"notes": "基础配置", "env_vars": {"MODE": "dev"}}
    deploy_context = {
        "server_address": "10.0.0.8",
        "db_connection": "mysql://demo",
        "env_vars": "REDIS_URL=redis://127.0.0.1:6379/0",
        "user_notes": "启用测试环境",
    }
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "core.llm_manager":
            raise ImportError("LLM unavailable")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        result = asyncio.run(refine_deploy_config(initial_config, deploy_context))

    assert result["source"] == "context_merged"
    assert result["env_vars"]["MODE"] == "dev"
    assert result["env_vars"]["DATABASE_URL"] == "mysql://demo"
    assert result["env_vars"]["REDIS_URL"] == "redis://127.0.0.1:6379/0"
    assert "10.0.0.8" in result["notes"]
    assert "启用测试环境" in result["notes"]


def test_merge_context_fallback_keeps_existing_notes():
    result = _merge_context_fallback(
        {"notes": "已有说明", "env_vars": {}},
        {"user_notes": "补充说明"},
    )

    assert result["notes"] == "已有说明 | 补充说明"
