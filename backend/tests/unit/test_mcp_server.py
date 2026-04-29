# -*- coding: utf-8 -*-
import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PROJECT_ROOT / "mcp" / "server.py"


def _load_mcp_server_module():
    spec = importlib.util.spec_from_file_location("test_mcp_server_module", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_write_message_line_supports_text_stdout(monkeypatch):
    module = _load_mcp_server_module()

    class DummyStdout:
        def __init__(self):
            self.writes = []
            self.flushed = False

        def write(self, value):
            if isinstance(value, bytes):
                raise TypeError("text stream only")
            self.writes.append(value)

        def flush(self):
            self.flushed = True

    dummy_stdout = DummyStdout()
    monkeypatch.setattr(module, "_stdio_writer", lambda: dummy_stdout)

    await module._write_message_line('{"ok": true}')

    assert dummy_stdout.writes == ['{"ok": true}\n']
    assert dummy_stdout.flushed is True


@pytest.mark.asyncio
async def test_main_accepts_bom_prefixed_initialize(monkeypatch):
    module = _load_mcp_server_module()
    written = []
    lines = iter(
        [
            b'\xef\xbb\xbf{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n',
            b"",
        ]
    )

    async def fake_read_message_line():
        return next(lines)

    async def fake_write_message_line(payload: str):
        written.append(payload)

    monkeypatch.setattr(module, "_read_message_line", fake_read_message_line)
    monkeypatch.setattr(module, "_write_message_line", fake_write_message_line)

    await module.main()

    assert len(written) == 1
    response = json.loads(written[0])
    assert response["id"] == 1
    assert response["result"]["serverInfo"]["name"] == "ai-test-platform"
    assert response["result"]["serverInfo"]["version"] == module.APP_VERSION
