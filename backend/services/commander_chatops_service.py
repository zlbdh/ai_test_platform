# -*- coding: utf-8 -*-
"""
Commander ChatOps Service

统一计算通知平台双向指令链路的当前状态，供：
- 通知配置页
- 平台信息 / 就绪度 / 整改项
- 后续运维观测
复用同一份口径。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Dict, Optional
import threading

import requests

from core.db_helper import get_connection, query_all
from core.config import Config


class CommanderChatOpsService:
    def __init__(self) -> None:
        self._probe_cache: Dict[str, Any] = {}
        self._probe_lock = threading.Lock()
        self._probe_ttl_seconds = 120
        self._probe_history_ttl_seconds = 300
        self._init_probe_table()
        self._init_chat_binding_table()
        self._init_app_bot_check_table()

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @classmethod
    def _local_tunnel_script_path(cls) -> Path:
        return cls._repo_root() / "data" / "tools" / "start_native_reverse_tunnel.ps1"

    @classmethod
    def _local_tunnel_log_paths(cls) -> Dict[str, Path]:
        log_dir = cls._repo_root() / "data"
        return {
            "stdout": log_dir / "native_ssh_reverse_tunnel_stdout.log",
            "stderr": log_dir / "native_ssh_reverse_tunnel_stderr.log",
        }

    @staticmethod
    def _read_log_tail(path: Path, max_chars: int = 320) -> str:
        try:
            if not path.exists():
                return ""
            text = path.read_text(encoding="utf-8", errors="replace")
            text = text.strip()
            if len(text) <= max_chars:
                return text
            return text[-max_chars:]
        except OSError:
            return ""

    @classmethod
    def _get_local_tunnel_status(cls) -> Dict[str, Any]:
        script_path = cls._local_tunnel_script_path()
        log_paths = cls._local_tunnel_log_paths()
        checked_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        result: Dict[str, Any] = {
            "supported": os.name == "nt",
            "script_path": str(script_path),
            "script_exists": script_path.exists(),
            "stdout_log": str(log_paths["stdout"]),
            "stderr_log": str(log_paths["stderr"]),
            "running": False,
            "pid": None,
            "status": "unsupported" if os.name != "nt" else "missing_script" if not script_path.exists() else "stopped",
            "summary": "当前环境不是 Windows，本机反向隧道脚本不可用。"
            if os.name != "nt"
            else "未找到本机反向隧道脚本。"
            if not script_path.exists()
            else "未检测到本机 OpenSSH 反向隧道进程。",
            "checked_at": checked_at,
            "stdout_tail": cls._read_log_tail(log_paths["stdout"]),
            "stderr_tail": cls._read_log_tail(log_paths["stderr"]),
        }
        if os.name != "nt" or not script_path.exists():
            return result

        ps_script = r"""
$match = '127\.0\.0\.1:18020:127\.0\.0\.1:8020'
$proc = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq 'ssh.exe' -and $_.CommandLine -match $match } |
    Sort-Object CreationDate -Descending |
    Select-Object -First 1 ProcessId, CreationDate, CommandLine
if ($null -eq $proc) { '' } else { $proc | ConvertTo-Json -Compress }
""".strip()
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
        except subprocess.TimeoutExpired:
            result["status"] = "unknown"
            result["summary"] = "检测本机反向隧道状态超时。"
            return result
        except OSError as exc:
            result["status"] = "unknown"
            result["summary"] = f"检测本机反向隧道状态失败：{exc.__class__.__name__}"
            return result

        if completed.returncode != 0:
            stderr = str(completed.stderr or "").strip()
            result["status"] = "unknown"
            result["summary"] = f"检测本机反向隧道状态失败：{stderr or 'PowerShell 返回异常'}"
            return result

        payload = str(completed.stdout or "").strip()
        if not payload:
            if result["stderr_tail"]:
                result["summary"] = f"未检测到隧道进程。最近错误：{result['stderr_tail']}"
            return result

        try:
            proc = json.loads(payload)
        except json.JSONDecodeError:
            result["status"] = "unknown"
            result["summary"] = "本机反向隧道状态输出无法解析。"
            return result

        pid = proc.get("ProcessId")
        result.update({
            "running": True,
            "pid": int(pid) if pid is not None else None,
            "created_at": str(proc.get("CreationDate") or ""),
            "command_line": str(proc.get("CommandLine") or ""),
            "status": "running",
            "summary": f"检测到本机 OpenSSH 反向隧道进程（PID {pid}）。" if pid is not None else "检测到本机 OpenSSH 反向隧道进程。",
        })
        return result

    def restart_local_tunnel(self) -> Dict[str, Any]:
        before = self._get_local_tunnel_status()
        if not before.get("supported"):
            return {
                "ok": False,
                "message": before.get("summary") or "当前环境不支持本机反向隧道。",
                "tunnel": before,
                "overview": self.get_overview(),
            }
        script_path = Path(str(before.get("script_path") or self._local_tunnel_script_path()))
        if not script_path.exists():
            return {
                "ok": False,
                "message": "未找到本机反向隧道脚本，无法执行重启。",
                "tunnel": before,
                "overview": self.get_overview(),
            }

        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired:
            after = self._get_local_tunnel_status()
            return {
                "ok": False,
                "message": "重启本机反向隧道超时。",
                "stdout": "",
                "stderr": "",
                "tunnel": after,
                "overview": self.get_overview(),
            }
        except OSError as exc:
            after = self._get_local_tunnel_status()
            return {
                "ok": False,
                "message": f"重启本机反向隧道失败：{exc.__class__.__name__}",
                "stdout": "",
                "stderr": str(exc),
                "tunnel": after,
                "overview": self.get_overview(),
            }

        after = self._get_local_tunnel_status()
        ok = completed.returncode == 0 and bool(after.get("running"))
        message = (
            "本机反向隧道已重启。"
            if ok
            else str(completed.stderr or "").strip()
            or str(after.get("summary") or "本机反向隧道仍未恢复。")
        )
        return {
            "ok": ok,
            "message": message,
            "stdout": str(completed.stdout or "").strip(),
            "stderr": str(completed.stderr or "").strip(),
            "tunnel": after,
            "overview": self.get_overview(),
        }

    @staticmethod
    def _init_probe_table() -> None:
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commander_chatops_callback_probes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    callback_url TEXT DEFAULT '',
                    attempted INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 0,
                    issue TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    status_code INTEGER,
                    content_type TEXT DEFAULT '',
                    response_excerpt TEXT DEFAULT '',
                    source TEXT DEFAULT 'overview',
                    force_refresh INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
                """
            )

    @staticmethod
    def _init_chat_binding_table() -> None:
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commander_chatops_chat_bindings (
                    chat_id TEXT PRIMARY KEY,
                    channel TEXT DEFAULT 'notification_platform',
                    source TEXT DEFAULT 'event_subscription',
                    last_from_user TEXT DEFAULT '',
                    last_message TEXT DEFAULT '',
                    last_seen_at TEXT DEFAULT (datetime('now')),
                    last_reply_mode TEXT DEFAULT '',
                    last_delivery_ok INTEGER DEFAULT 0,
                    last_run_id TEXT DEFAULT '',
                    last_command_id TEXT DEFAULT '',
                    last_requester_id TEXT DEFAULT '',
                    binding_status TEXT DEFAULT ''
                )
                """
            )
            existing_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(commander_chatops_chat_bindings)").fetchall()
            }
            for column_name, column_sql in (
                ("last_run_id", "TEXT DEFAULT ''"),
                ("last_command_id", "TEXT DEFAULT ''"),
                ("last_requester_id", "TEXT DEFAULT ''"),
                ("binding_status", "TEXT DEFAULT ''"),
            ):
                if column_name not in existing_columns:
                    conn.execute(
                        f"ALTER TABLE commander_chatops_chat_bindings ADD COLUMN {column_name} {column_sql}"
                    )

    @staticmethod
    def _init_app_bot_check_table() -> None:
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commander_chatops_app_bot_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    success INTEGER DEFAULT 0,
                    message TEXT DEFAULT '',
                    status_code INTEGER,
                    source TEXT DEFAULT 'manual',
                    app_id_masked TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                )
                """
            )

    @staticmethod
    def _parse_time(value: str) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace(" ", "T"))
        except ValueError:
            return None

    @staticmethod
    def _mask_token(token: str) -> str:
        token = str(token or "").strip()
        if not token:
            return ""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}...{token[-4:]}"

    @staticmethod
    def _mask_app_id(app_id: str) -> str:
        app_id = str(app_id or "").strip()
        if not app_id:
            return ""
        if len(app_id) <= 6:
            return "*" * len(app_id)
        return f"{app_id[:3]}...{app_id[-3:]}"

    def _serialize_event(self, row: dict) -> Dict[str, Any]:
        return {
            "id": row.get("id"),
            "channel": row.get("channel", "generic"),
            "source": row.get("source", "manual"),
            "event_type": row.get("event_type", "message"),
            "message": row.get("message", ""),
            "from_user": row.get("from_user", ""),
            "chat_id": row.get("chat_id", ""),
            "response": row.get("response", ""),
            "status": row.get("status", "ok"),
            "delivery_configured": int(row.get("delivery_configured") or 0),
            "delivery_delivered": int(row.get("delivery_delivered") or 0),
            "delivery_failed": int(row.get("delivery_failed") or 0),
            "run_id": str(row.get("run_id") or ""),
            "command_id": str(row.get("command_id") or ""),
            "requester_id": str(row.get("requester_id") or ""),
            "binding_status": str(row.get("binding_status") or ""),
            "created_at": row.get("created_at", ""),
        }

    @staticmethod
    def _serialize_chat_binding_row(row: dict) -> Dict[str, Any]:
        return {
            "chat_id": str(row.get("chat_id") or ""),
            "channel": str(row.get("channel") or "notification_platform"),
            "source": str(row.get("source") or "event_subscription"),
            "last_from_user": str(row.get("last_from_user") or ""),
            "last_message": str(row.get("last_message") or ""),
            "last_seen_at": str(row.get("last_seen_at") or ""),
            "last_reply_mode": str(row.get("last_reply_mode") or ""),
            "last_delivery_ok": int(row.get("last_delivery_ok") or 0),
            "last_run_id": str(row.get("last_run_id") or ""),
            "last_command_id": str(row.get("last_command_id") or ""),
            "last_requester_id": str(row.get("last_requester_id") or ""),
            "binding_status": str(row.get("binding_status") or ""),
        }

    @staticmethod
    def _is_synthetic_chat_binding(item: Dict[str, Any]) -> bool:
        source = str(item.get("source") or "").strip().lower()
        if source in {"external_self_check", "subscription_self_check", "simulation"}:
            return True

        chat_id = str(item.get("chat_id") or "").strip().lower()
        synthetic_chat_markers = (
            "external_self_check",
            "pinggy_live",
            "live_probe",
            "live_status",
            "stage2_validation",
            "codex_",
            "oc_demo",
            "_demo",
        )
        if any(marker in chat_id for marker in synthetic_chat_markers):
            return True

        from_user = str(item.get("last_from_user") or "").strip().lower()
        synthetic_user_markers = (
            "external_self_check",
            "stage2_validation",
            "ops_live_",
            "live_validation",
            "codex",
            "demo",
        )
        return any(marker in from_user for marker in synthetic_user_markers)

    @staticmethod
    def _serialize_app_bot_check_row(row: dict) -> Dict[str, Any]:
        return {
            "id": row.get("id"),
            "success": bool(row.get("success")),
            "message": str(row.get("message") or ""),
            "status_code": row.get("status_code"),
            "source": str(row.get("source") or "manual"),
            "app_id_masked": str(row.get("app_id_masked") or ""),
            "created_at": str(row.get("created_at") or ""),
        }

    @staticmethod
    def _is_external_self_check_message(item: Dict[str, Any]) -> bool:
        if str(item.get("event_type") or "") != "message":
            return False
        source = str(item.get("source") or "").strip()
        if source == "external_self_check":
            return True
        chat_id = str(item.get("chat_id") or "").strip().lower()
        synthetic_chat_markers = (
            "external_self_check",
            "pinggy_live",
            "live_probe",
            "live_status",
            "stage2_validation",
            "codex_",
        )
        if chat_id == "oc_external_self_check" or any(marker in chat_id for marker in synthetic_chat_markers):
            return True
        from_user = str(item.get("from_user") or "").strip().lower()
        synthetic_user_markers = (
            "external_self_check",
            "stage2_validation",
            "ops_live_",
            "live_validation",
            "codex",
        )
        if any(marker in from_user for marker in synthetic_user_markers):
            return True
        response = str(item.get("response") or "")
        if "平台公网自测通过" in response:
            return True
        return False

    @staticmethod
    def _build_probe_result_from_response(
        *,
        status_code: int,
        content_type: str,
        excerpt: str,
        response_json: Any,
        summary_prefix: str = "公网回调地址",
    ) -> Dict[str, Any]:
        lowered_excerpt = str(excerpt or "").lower()
        lowered_type = str(content_type or "").lower()
        success = False
        issue = ""

        if status_code == 200 and isinstance(response_json, dict) and response_json.get("challenge") == "chatops-probe":
            success = True
            summary = f"{summary_prefix}已通过主动回探，当前入口对外可达。"
        elif "pinggy" in lowered_excerpt or "caution" in lowered_excerpt:
            issue = "interstitial_page"
            summary = f"{summary_prefix}返回了隧道警告页，通知平台云侧大概率无法直接命中平台回调。"
        elif "tunnel unavailable" in lowered_excerpt or status_code == 503:
            issue = "tunnel_unavailable"
            summary = f"{summary_prefix}当前返回 Tunnel Unavailable，隧道未稳定建立。"
        elif "text/html" in lowered_type:
            issue = "html_response"
            summary = f"{summary_prefix}返回了 HTML 页面，而不是 challenge JSON，当前外部回调链路不可用。"
        else:
            issue = "unexpected_response"
            summary = f"{summary_prefix}已响应，但返回内容不符合通知平台 challenge 预期（HTTP {status_code}）。"

        return CommanderChatOpsService._build_probe_result(
            attempted=True,
            success=success,
            issue=issue,
            summary=summary,
            status_code=status_code,
            content_type=content_type,
            response_excerpt=excerpt,
        )

    @staticmethod
    def _probe_callback_url_via_curl(callback_url: str, verification_token: str) -> Optional[Dict[str, Any]]:
        curl_path = shutil.which("curl.exe") or shutil.which("curl")
        if not curl_path:
            return None

        payload = json.dumps(
            {
                "type": "url_verification",
                "challenge": "chatops-probe",
                "token": verification_token,
            },
            ensure_ascii=False,
        )

        try:
            completed = subprocess.run(
                [
                    curl_path,
                    "-sS",
                    "-m",
                    "10",
                    "-X",
                    "POST",
                    callback_url,
                    "-H",
                    "Content-Type: application/json",
                    "-H",
                    "User-Agent: AI-Test-Platform-ChatOps-Probe/1.0 (curl-fallback)",
                    "-d",
                    payload,
                    "-w",
                    "\n%{http_code}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=12,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return CommanderChatOpsService._build_probe_result(
                attempted=True,
                success=False,
                issue="timeout",
                summary="公网回调地址回探超时（curl 回退），通知平台云侧当前大概率无法稳定访问该入口。",
            )
        except OSError as exc:
            return CommanderChatOpsService._build_probe_result(
                attempted=True,
                success=False,
                issue="connect_error",
                summary=f"公网回调地址回探失败（curl 回退）：{exc.__class__.__name__}",
                response_excerpt=str(exc)[:240],
            )

        stderr = str(completed.stderr or "").strip()
        stdout = str(completed.stdout or "")
        body_text = stdout
        status_code = None
        if "\n" in stdout:
            maybe_body, maybe_code = stdout.rsplit("\n", 1)
            if maybe_code.strip().isdigit():
                body_text = maybe_body
                status_code = int(maybe_code.strip())

        if completed.returncode != 0:
            excerpt = stderr[:240] or body_text[:240]
            lowered = excerpt.lower()
            issue = "timeout" if "timed out" in lowered or "timeout" in lowered else "connect_error"
            return CommanderChatOpsService._build_probe_result(
                attempted=True,
                success=False,
                issue=issue,
                summary=f"公网回调地址回探失败（curl 回退）：{excerpt or '未知错误'}",
                response_excerpt=excerpt,
                status_code=status_code,
            )

        content_type = ""
        excerpt = body_text[:240]
        try:
            response_json = json.loads(body_text) if body_text else None
        except Exception:
            response_json = None

        if status_code is None:
            status_code = 200 if isinstance(response_json, dict) else 0

        return CommanderChatOpsService._build_probe_result_from_response(
            status_code=status_code,
            content_type=content_type,
            excerpt=excerpt,
            response_json=response_json,
            summary_prefix="公网回调地址（curl 回退）",
        )

    @staticmethod
    def _serialize_probe_row(row: dict) -> Dict[str, Any]:
        return {
            "id": row.get("id"),
            "callback_url": row.get("callback_url", ""),
            "attempted": bool(row.get("attempted")),
            "success": bool(row.get("success")),
            "issue": row.get("issue", ""),
            "summary": row.get("summary", ""),
            "status_code": row.get("status_code"),
            "content_type": row.get("content_type", ""),
            "response_excerpt": row.get("response_excerpt", ""),
            "source": row.get("source", "overview"),
            "force_refresh": bool(row.get("force_refresh")),
            "created_at": row.get("created_at", ""),
        }

    @staticmethod
    def _is_public_callback_url(url: str) -> bool:
        text = str(url or "").strip()
        if not text:
            return False
        try:
            host = (urlsplit(text).hostname or "").strip().lower()
        except Exception:
            return False
        if not host:
            return False
        return host not in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}

    @staticmethod
    def _detect_callback_provider(url: str) -> Dict[str, str]:
        text = str(url or "").strip()
        if not text:
            return {
                "key": "unknown",
                "label": "未知",
                "host": "",
            }
        try:
            host = (urlsplit(text).hostname or "").strip().lower()
        except Exception:
            host = ""
        if not host:
            return {
                "key": "unknown",
                "label": "未知",
                "host": "",
            }
        if host in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}:
            return {
                "key": "local",
                "label": "本地地址",
                "host": host,
            }
        if host.endswith(".loca.lt"):
            return {
                "key": "localtunnel",
                "label": "LocalTunnel",
                "host": host,
            }
        if host.endswith(".trycloudflare.com"):
            return {
                "key": "cloudflare_quick_tunnel",
                "label": "Cloudflare Quick Tunnel",
                "host": host,
            }
        if "pinggy" in host:
            return {
                "key": "pinggy",
                "label": "Pinggy",
                "host": host,
            }
        if host.endswith(".lhr.life"):
            return {
                "key": "lhr_life_tunnel",
                "label": "LHR 临时隧道",
                "host": host,
            }
        if host.endswith("localhost.run"):
            return {
                "key": "localhost_run",
                "label": "localhost.run",
                "host": host,
            }
        if host.endswith("serveo.net"):
            return {
                "key": "serveo",
                "label": "Serveo",
                "host": host,
            }
        return {
            "key": "custom",
            "label": "自定义公网地址",
            "host": host,
        }

    @staticmethod
    def _build_provider_recommendation(provider: Dict[str, str], issue: str, callback_public: bool) -> str:
        provider_label = provider.get("label") or "当前公网入口"
        provider_key = provider.get("key") or "unknown"
        if not callback_public:
            return "先把 PUBLIC_API_BASE_URL 改成通知平台云侧可访问的公网地址，再执行 challenge 回探。"
        if not issue:
            return f"{provider_label} 已通过 challenge 回探，可以继续去通知平台开发者后台完成事件订阅和真实群测。"
        if issue == "tunnel_unavailable":
            if provider_key == "localtunnel":
                return f"{provider_label} 当前已失效，建议重新建立一条 LocalTunnel，或直接换成更稳定的固定公网入口。"
            if provider_key == "cloudflare_quick_tunnel":
                return f"{provider_label} 当前不可用，建议重建隧道并优先使用自有域名/固定反代，而不是临时 Quick Tunnel。"
            return f"{provider_label} 当前返回 Tunnel Unavailable，建议先重建隧道，再重新执行回探。"
        if issue == "interstitial_page":
            return f"{provider_label} 返回了中间警告页，通知平台 challenge 无法直接命中平台；建议换成无中间页的公网反向代理或隧道。"
        if issue == "html_response":
            return f"{provider_label} 当前回的是 HTML 页而不是 challenge JSON，说明外层代理还没直通到平台回调接口。"
        if issue == "timeout":
            return f"{provider_label} 回探超时，建议更换为时延更稳定的公网入口，或检查当前隧道是否被网络策略阻断。"
        if issue == "connect_error":
            return f"{provider_label} 当前连接失败，建议检查隧道进程是否存活，并确认公网域名仍指向本机 8020。"
        if issue == "unexpected_response":
            return f"{provider_label} 已有响应，但返回格式不符合通知平台 challenge 预期；请检查外层代理是否改写了请求或响应。"
        if provider_key == "local":
            return "当前还是本地地址，通知平台云侧无法直接访问；请先配置公网入口。"
        return f"{provider_label} 仍需进一步联调，建议先确认 challenge 回探成功，再去通知平台后台做最终事件订阅。"

    @staticmethod
    def _build_probe_result(
        *,
        attempted: bool,
        success: bool,
        issue: str = "",
        summary: str = "",
        status_code: Optional[int] = None,
        content_type: str = "",
        response_excerpt: str = "",
    ) -> Dict[str, Any]:
        return {
            "attempted": attempted,
            "success": success,
            "issue": issue,
            "summary": summary,
            "status_code": status_code,
            "content_type": content_type,
            "response_excerpt": response_excerpt,
            "probed_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _save_probe_history(
        callback_url: str,
        result: Dict[str, Any],
        *,
        source: str,
        force_refresh: bool,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO commander_chatops_callback_probes (
                    callback_url, attempted, success, issue, summary,
                    status_code, content_type, response_excerpt, source,
                    force_refresh
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(callback_url or ""),
                    1 if bool(result.get("attempted")) else 0,
                    1 if bool(result.get("success")) else 0,
                    str(result.get("issue") or ""),
                    str(result.get("summary") or ""),
                    result.get("status_code"),
                    str(result.get("content_type") or ""),
                    str(result.get("response_excerpt") or ""),
                    str(source or "overview"),
                    1 if force_refresh else 0,
                ),
            )

    @staticmethod
    def _load_recent_probe_history(limit: int = 6) -> list[Dict[str, Any]]:
        rows = query_all(
            """
            SELECT id, callback_url, attempted, success, issue, summary,
                   status_code, content_type, response_excerpt, source,
                   force_refresh, created_at
            FROM commander_chatops_callback_probes
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(int(limit or 0), 1),),
        )
        return [CommanderChatOpsService._serialize_probe_row(row) for row in rows]

    @staticmethod
    def _load_recent_chat_bindings(limit: int = 6) -> list[Dict[str, Any]]:
        rows = query_all(
            """
            SELECT chat_id, channel, source, last_from_user, last_message,
                   last_seen_at, last_reply_mode, last_delivery_ok,
                   last_run_id, last_command_id, last_requester_id, binding_status
            FROM commander_chatops_chat_bindings
            ORDER BY datetime(last_seen_at) DESC, chat_id DESC
            LIMIT ?
            """,
            (max(int(limit or 0), 1) * 4,),
        )
        items = [CommanderChatOpsService._serialize_chat_binding_row(row) for row in rows]
        real_items = [
            item
            for item in items
            if not CommanderChatOpsService._is_synthetic_chat_binding(item)
        ]
        return real_items[: max(int(limit or 0), 1)]

    @staticmethod
    def _load_latest_app_bot_check() -> Optional[Dict[str, Any]]:
        rows = query_all(
            """
            SELECT id, success, message, status_code, source, app_id_masked, created_at
            FROM commander_chatops_app_bot_checks
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if not rows:
            return None
        return CommanderChatOpsService._serialize_app_bot_check_row(rows[0])

    def _select_recent_probe_from_history(
        self,
        callback_url: str,
        probe_history: list[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        current_callback_url = str(callback_url or "").strip()
        if not current_callback_url:
            return None
        for item in probe_history:
            if str(item.get("callback_url") or "").strip() != current_callback_url:
                continue
            probe_at = self._parse_time(
                str(item.get("probed_at") or item.get("created_at") or "")
            )
            if not probe_at:
                continue
            if (datetime.now() - probe_at).total_seconds() > self._probe_history_ttl_seconds:
                continue
            hydrated = dict(item)
            hydrated["probed_at"] = str(item.get("probed_at") or item.get("created_at") or "")
            return hydrated
        return None

    def _probe_callback_url(
        self,
        callback_url: str,
        verification_token: str,
        *,
        force_refresh: bool = False,
        source: str = "overview",
        allow_curl_fallback: bool = True,
    ) -> Dict[str, Any]:
        callback_url = str(callback_url or "").strip()
        verification_token = str(verification_token or "").strip()
        if not callback_url or not self._is_public_callback_url(callback_url):
            return self._build_probe_result(
                attempted=False,
                success=False,
                issue="local_callback",
                summary="当前回调地址仍是本地或内网地址，暂不执行公网回探。",
            )
        if not verification_token:
            return self._build_probe_result(
                attempted=False,
                success=False,
                issue="token_missing",
                summary="verification token 尚未配置，暂不执行公网回探。",
            )

        cache_key = f"{callback_url}|{verification_token}"
        with self._probe_lock:
            cached = None if force_refresh else self._probe_cache.get(cache_key)
            if cached:
                cached_at = self._parse_time(cached.get("probed_at"))
                if cached_at and (datetime.now() - cached_at).total_seconds() < self._probe_ttl_seconds:
                    return dict(cached)

        payload = {
            "type": "url_verification",
            "challenge": "chatops-probe",
            "token": verification_token,
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AI-Test-Platform-ChatOps-Probe/1.0",
        }
        request_timeout = (2, 3) if allow_curl_fallback else (1.5, 1.5)
        session = requests.Session()
        session.trust_env = False
        try:
            response = session.post(
                callback_url,
                json=payload,
                headers=headers,
                timeout=request_timeout,
            )
            content_type = str(response.headers.get("content-type") or "")
            excerpt = (response.text or "")[:240]
            status_code = int(response.status_code)

            try:
                response_json = response.json()
            except Exception:
                response_json = None

            result = self._build_probe_result_from_response(
                status_code=status_code,
                content_type=content_type,
                excerpt=excerpt,
                response_json=response_json,
            )
        except requests.Timeout:
            result = (
                self._probe_callback_url_via_curl(callback_url, verification_token)
                if allow_curl_fallback
                else None
            ) or self._build_probe_result(
                attempted=True,
                success=False,
                issue="timeout",
                summary="公网回调地址回探超时，通知平台云侧当前大概率无法稳定访问该入口。",
            )
        except requests.RequestException as exc:
            result = (
                self._probe_callback_url_via_curl(callback_url, verification_token)
                if allow_curl_fallback
                else None
            ) or self._build_probe_result(
                attempted=True,
                success=False,
                issue="connect_error",
                summary=f"公网回调地址回探失败：{exc.__class__.__name__}",
                response_excerpt=str(exc)[:240],
            )
        finally:
            session.close()

        with self._probe_lock:
            self._probe_cache[cache_key] = dict(result)
        self._save_probe_history(
            callback_url,
            result,
            source=source,
            force_refresh=force_refresh,
        )
        return result

    def refresh_callback_probe(self) -> Dict[str, Any]:
        verification_token = (
            getattr(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "")
            or os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "")
        ).strip()
        callback_base_url = (
            getattr(Config, "PUBLIC_API_BASE_URL", "")
            or os.getenv("PUBLIC_API_BASE_URL", "")
            or getattr(Config, "API_BASE_URL", "")
            or os.getenv("API_BASE_URL", "")
        ).strip().rstrip("/")
        callback_url = (
            f"{callback_base_url}/api/commander/notification_platform/events"
            if callback_base_url
            else "/api/commander/notification_platform/events"
        )
        probe = self._probe_callback_url(
            callback_url,
            verification_token,
            force_refresh=True,
            source="manual_refresh",
        )
        return {
            "probe": probe,
            "overview": self.get_overview(allow_live_probe=False),
        }

    def get_overview(self, *, allow_live_probe: bool = True) -> Dict[str, Any]:
        events = query_all(
            """
            SELECT id, channel, source, event_type, message, from_user, chat_id, response,
                   status, delivery_configured, delivery_delivered, delivery_failed, created_at
            FROM commander_chatops_events
            ORDER BY id DESC
            LIMIT 200
            """
        )
        event_items = [self._serialize_event(row) for row in events]
        latest = event_items[0] if event_items else None
        token_updated_at = getattr(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "") or os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN_UPDATED_AT", "").strip()
        token_updated_at_dt = self._parse_time(token_updated_at)
        callback_updated_at = getattr(Config, "PUBLIC_API_BASE_URL_UPDATED_AT", "") or os.getenv("PUBLIC_API_BASE_URL_UPDATED_AT", "").strip()
        callback_updated_at_dt = self._parse_time(callback_updated_at)

        def _matches_since(item: Dict[str, Any]) -> bool:
            if token_updated_at_dt is None:
                return True
            item_dt = self._parse_time(item.get("created_at"))
            if item_dt is None:
                return False
            return item_dt >= token_updated_at_dt

        def _matches_current_callback(item: Dict[str, Any]) -> bool:
            if callback_updated_at_dt is None:
                return True
            item_dt = self._parse_time(item.get("created_at"))
            if item_dt is None:
                return False
            return item_dt >= callback_updated_at_dt

        latest_successful = next(
            (
                item for item in event_items
                if item.get("status") == "ok" and int(item.get("delivery_delivered") or 0) > 0
            ),
            None,
        )
        latest_external_success = next(
            (
                item for item in event_items
                if item.get("source") == "event_subscription"
                and item.get("event_type") == "message"
                and not self._is_external_self_check_message(item)
                and item.get("status") == "ok"
                and int(item.get("delivery_delivered") or 0) > 0
                and _matches_since(item)
                and _matches_current_callback(item)
            ),
            None,
        )
        latest_external_self_check = next(
            (
                item for item in event_items
                if self._is_external_self_check_message(item)
                and item.get("status") == "ok"
                and int(item.get("delivery_delivered") or 0) > 0
                and _matches_since(item)
                and _matches_current_callback(item)
            ),
            None,
        )
        latest_subscription_check = next(
            (
                item for item in event_items
                if item.get("source") in ("event_subscription", "subscription_self_check")
                and item.get("event_type") == "url_verification"
                and item.get("status") == "verified"
                and _matches_since(item)
                and _matches_current_callback(item)
            ),
            None,
        )

        notification_platform_webhooks = query_all(
            """
            SELECT id, name, enabled, last_test_success
            FROM notification_webhooks
            WHERE type='notification_platform'
            ORDER BY created_at DESC
            """
        )
        enabled_notification_platform = [row for row in notification_platform_webhooks if bool(row.get("enabled"))]
        healthy_notification_platform = [row for row in enabled_notification_platform if bool(row.get("last_test_success"))]
        verification_token = getattr(Config, "NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "") or os.getenv("NOTIFICATION_PLATFORM_EVENT_VERIFICATION_TOKEN", "").strip()
        verification_token_configured = bool(str(verification_token).strip())
        app_id = getattr(Config, "NOTIFICATION_PLATFORM_APP_ID", "") or os.getenv("NOTIFICATION_PLATFORM_APP_ID", "").strip()
        app_secret = getattr(Config, "NOTIFICATION_PLATFORM_APP_SECRET", "") or os.getenv("NOTIFICATION_PLATFORM_APP_SECRET", "").strip()
        app_bot_updated_at = getattr(Config, "NOTIFICATION_PLATFORM_APP_BOT_UPDATED_AT", "") or os.getenv("NOTIFICATION_PLATFORM_APP_BOT_UPDATED_AT", "").strip()
        app_bot_configured = bool(str(app_id).strip() and str(app_secret).strip())
        callback_base_url = (getattr(Config, "PUBLIC_API_BASE_URL", "") or os.getenv("PUBLIC_API_BASE_URL", "") or getattr(Config, "API_BASE_URL", "") or os.getenv("API_BASE_URL", "")).strip().rstrip("/")
        callback_url = f"{callback_base_url}/api/commander/notification_platform/events" if callback_base_url else "/api/commander/notification_platform/events"
        callback_url_public = self._is_public_callback_url(callback_url)
        callback_provider = self._detect_callback_provider(callback_url)
        webhook_ready = len(healthy_notification_platform) > 0
        subscription_endpoint_verified = latest_subscription_check is not None
        callback_probe_history = self._load_recent_probe_history()
        callback_probe = self._select_recent_probe_from_history(callback_url, callback_probe_history)
        if not callback_probe and allow_live_probe:
            callback_probe = self._probe_callback_url(
                callback_url,
                verification_token,
                source="overview",
                allow_curl_fallback=False,
            )
        elif not callback_probe:
            callback_probe = self._build_probe_result(
                attempted=False,
                success=False,
                issue="probe_skipped",
                summary="当前仅复用最近一次公网回探结果；如需立刻验证，请手动执行“立即重试回探”或“跑公网链路自测”。",
            )
        local_tunnel = self._get_local_tunnel_status()
        recent_chat_bindings = self._load_recent_chat_bindings()
        latest_app_bot_check = self._load_latest_app_bot_check()
        callback_recommendation = self._build_provider_recommendation(
            callback_provider,
            str(callback_probe.get("issue") or ""),
            callback_url_public,
        )
        latest_external_success_dt = self._parse_time((latest_external_success or {}).get("created_at", ""))
        latest_external_self_check_dt = self._parse_time((latest_external_self_check or {}).get("created_at", ""))
        latest_subscription_check_dt = self._parse_time((latest_subscription_check or {}).get("created_at", ""))
        recent_external_success_window_seconds = 15 * 60
        recent_external_success_on_current_callback = bool(
            latest_external_success_dt
            and (datetime.utcnow() - latest_external_success_dt).total_seconds() <= recent_external_success_window_seconds
        )
        recent_external_self_check_on_current_callback = bool(
            latest_external_self_check_dt
            and (datetime.utcnow() - latest_external_self_check_dt).total_seconds() <= recent_external_success_window_seconds
        )
        recent_subscription_check_on_current_callback = bool(
            latest_subscription_check_dt
            and (datetime.utcnow() - latest_subscription_check_dt).total_seconds() <= recent_external_success_window_seconds
        )
        probe_issue = str(callback_probe.get("issue") or "")
        probe_timeout_like = probe_issue in {"timeout", "connect_error"}
        current_callback_reachable = callback_url_public and (
            bool(callback_probe.get("success"))
            or (recent_external_success_on_current_callback and probe_timeout_like)
            or recent_external_self_check_on_current_callback
            or recent_subscription_check_on_current_callback
        )
        external_history_observed = latest_external_success is not None
        # external_connected 代表“当前入口仍健康，且历史上已验证过真实群消息回流”。
        external_connected = current_callback_reachable and external_history_observed
        external_connection_stale = external_history_observed and not external_connected
        platform_ready = webhook_ready and verification_token_configured and subscription_endpoint_verified
        external_callback_ready = platform_ready and current_callback_reachable
        direct_chat_ready = platform_ready and external_connected
        ready = direct_chat_ready
        unified_robot_target = app_bot_configured
        app_bot_ready = app_bot_configured and bool((latest_app_bot_check or {}).get("success"))
        unified_robot_platform_ready = app_bot_ready and external_callback_ready
        unified_robot_ready = app_bot_ready and direct_chat_ready
        delivery_strategy = (
            "single_robot_with_webhook_fallback"
            if app_bot_configured and webhook_ready
            else "app_bot_only"
            if app_bot_configured
            else "webhook_only"
            if webhook_ready
            else "unconfigured"
        )
        delivery_strategy_summary = (
            "对外建议只暴露当前项目专属的通知平台应用机器人，群内命令回复优先走应用机器人，Webhook 仅作为兜底通知通道。"
            if app_bot_ready and webhook_ready
            else "当前只有当前项目专属通知平台应用机器人配置，群内指令可以逐步统一到同一机器人身份，但还缺少 Webhook 兜底。"
            if app_bot_ready
            else "当前项目专属通知平台应用机器人凭据已保存，但最近一次校验未通过；当前还不能把它当成稳定主通道。"
            if app_bot_configured
            else "当前仍主要依赖通知平台 Webhook 机器人发通知，尚未形成“一个机器人”对外体验。"
            if webhook_ready
            else "通知平台机器人通道尚未完成配置。"
        )

        if recent_external_success_on_current_callback and probe_timeout_like and not bool(callback_probe.get("success")):
            callback_recommendation = (
                "当前公网地址在最近 15 分钟内已收到真实通知平台群消息回流，说明链路仍可用；"
                "当前更像是临时隧道抖动。可以继续在群里联调，如后续持续超时再更换更稳定的公网入口。"
            )
        elif recent_subscription_check_on_current_callback and external_history_observed:
            callback_recommendation = (
                "当前公网地址最近已通过通知平台 challenge 校验，且平台历史上已有真实通知平台群消息回流；"
                "说明当前双向链路仍可继续使用。若后续持续超时，再考虑更换更稳定的公网入口。"
            )
        elif recent_subscription_check_on_current_callback and not external_history_observed:
            callback_recommendation = (
                "当前公网地址最近已通过通知平台 challenge 校验，说明通知平台云侧可以打到回调入口；"
                "下一步请在目标群或单聊里发送一条真实消息，完成最终联调。"
            )
        elif recent_external_self_check_on_current_callback and external_history_observed:
            callback_recommendation = (
                "当前公网地址最近已通过平台公网自测，且平台历史上已有真实通知平台群消息回流；"
                "说明当前双向链路仍可继续使用。若后续持续超时，再考虑更换更稳定的公网入口。"
            )
        elif recent_external_self_check_on_current_callback and not external_history_observed:
            callback_recommendation = (
                "当前公网地址已通过平台公网自测，说明 challenge 与文本消息都能打到回调入口；"
                "下一步请在通知平台开发者后台完成事件订阅，并在目标群里发送一条真实消息做最终联调。"
            )

        if not webhook_ready:
            summary = "已提供通知平台事件回调入口，但还没有健康的通知平台回推通道。"
        elif not verification_token_configured:
            summary = "通知平台回推通道已健康，但还缺少事件订阅 verification token，群消息还不能稳定回流到平台。"
        elif not subscription_endpoint_verified:
            summary = "verification token 已配置，但平台侧还没完成事件订阅 challenge 自检；请先执行一次平台侧回调验证。"
        elif not callback_url_public:
            summary = (
                "平台历史上曾收到真实通知平台群消息回流，但当前回调地址已退回本地或内网；请重新配置一个通知平台可访问的公网回调地址。"
                if external_history_observed
                else "平台侧事件订阅已就绪，但当前回调地址仍是本地或内网地址；请先配置一个通知平台可访问的公网回调地址。"
            )
        elif recent_external_success_on_current_callback and probe_timeout_like and not bool(callback_probe.get("success")):
            summary = (
                f"{str(callback_probe.get('summary') or '公网回调地址回探超时。')} "
                "但当前公网地址在最近 15 分钟内已收到真实通知平台群消息回流，说明双向链路仍可用，当前更像是临时隧道抖动。"
            )
        elif recent_external_self_check_on_current_callback and external_history_observed:
            summary = (
                "最近一次平台公网自测已经通过，且平台历史上已收到过真实通知平台群消息回流；"
                "说明当前双向链路仍可继续使用。"
            )
        elif recent_subscription_check_on_current_callback and external_history_observed:
            summary = (
                "最近一次通知平台 challenge 校验已经通过，且平台历史上已收到过真实通知平台群消息回流；"
                "说明当前双向链路仍可继续使用。"
            )
        elif recent_subscription_check_on_current_callback and not external_history_observed:
            summary = (
                "最近一次通知平台 challenge 校验已经通过，说明当前公网回调入口可达；"
                "下一步请在目标群或单聊里发送一条真实消息完成最终联调。"
            )
        elif callback_probe.get("attempted") and not callback_probe.get("success"):
            if external_history_observed:
                summary = (
                    f"{str(callback_probe.get('summary') or '公网回调地址回探失败，请先修复公网入口可达性。')} "
                    "平台历史上曾收到过真实通知平台群消息回流，说明当前是公网入口退化，而不是平台完全没有打通过。"
                )
            elif recent_external_self_check_on_current_callback:
                summary = (
                    f"{str(callback_probe.get('summary') or '公网回调地址回探失败，请先修复公网入口可达性。')} "
                    "不过最近一次平台公网自测已经通过，说明 challenge 和文本消息仍能打到平台；"
                    "当前更像是临时探针抖动，仍需再做一次真实通知平台群聊联调。"
                )
            else:
                summary = str(callback_probe.get("summary") or "公网回调地址回探失败，请先修复公网入口可达性。")
        elif recent_external_self_check_on_current_callback and not external_history_observed:
            summary = (
                "最近一次平台公网自测已经通过，说明公网回调入口、challenge 和文本消息链路都可用；"
                "但这还不等同于真实通知平台群消息已经联通；下一步请在通知平台开放平台确认事件订阅已启用、"
                "把应用机器人加入目标群，并在群里发送一条真实消息完成最终联调。"
            )
        elif not external_history_observed:
            summary = (
                "当前项目专属通知平台应用机器人已配置，平台侧和公网回调都已就绪；"
                "当前建议对外只保留这一个机器人，Webhook 作为兜底。"
                "但还没收到真实群消息回流，请把应用机器人加入目标群并发一条测试消息。"
            )
        elif latest and latest["status"] == "ignored" and latest_successful:
            summary = "最近收到一条未处理事件，但最近一次文本指令仍然成功回推。"
        elif latest_external_success is not None:
            summary = (
                "最近一次通知平台文本指令已通过公网回调接入，并成功回推到群里。"
                if app_bot_configured
                else "最近一次通知平台文本指令已通过公网回调接入，并成功回推到群里。平台当前未保存 App Bot 凭据，但现有双向链路已可用。"
            )
        elif not latest:
            summary = "通知平台双向指令入口已就绪，尚未收到新的事件。"
        elif latest["status"] == "ok" and latest["delivery_delivered"] > 0:
            summary = "最近一条通知平台指令已接收并成功回推到群里。"
        elif latest["status"] == "ok":
            summary = "最近一条通知平台指令已接收，但未成功回推到群里。"
        else:
            summary = "最近一条通知平台事件未正常完成，请检查消息格式和回推通道。"

        return {
            "channel": "notification_platform",
            "event_endpoint": "/api/commander/notification_platform/events",
            "verification_token_configured": verification_token_configured,
            "verification_token_masked": self._mask_token(str(verification_token)),
            "verification_token_updated_at": token_updated_at,
            "app_bot_configured": app_bot_configured,
            "app_bot_ready": app_bot_ready,
            "app_bot_id_masked": self._mask_app_id(str(app_id)),
            "app_bot_updated_at": app_bot_updated_at,
            "app_bot_check": latest_app_bot_check,
            "unified_robot_target": unified_robot_target,
            "unified_robot_platform_ready": unified_robot_platform_ready,
            "unified_robot_ready": unified_robot_ready,
            "delivery_strategy": delivery_strategy,
            "delivery_strategy_summary": delivery_strategy_summary,
            "callback_url": callback_url,
            "callback_url_updated_at": callback_updated_at,
            "callback_url_public": callback_url_public,
            "callback_provider": callback_provider,
            "callback_recommendation": callback_recommendation,
            "enabled_notification_platform_webhook_count": len(enabled_notification_platform),
            "healthy_notification_platform_webhook_count": len(healthy_notification_platform),
            "webhook_ready": webhook_ready,
            "subscription_endpoint_verified": subscription_endpoint_verified,
            "external_connected": external_connected,
            "external_connected_current": external_connected,
            "external_connected_history_observed": external_history_observed,
            "external_connection_stale": external_connection_stale,
            "external_connected_via_recent_success": recent_external_success_on_current_callback and probe_timeout_like and not bool(callback_probe.get("success")),
            "external_self_check_recent_success": recent_external_self_check_on_current_callback,
            "subscription_check_recent_success": recent_subscription_check_on_current_callback,
            "external_callback_ready": external_callback_ready,
            "platform_ready": platform_ready,
            "direct_chat_ready": direct_chat_ready,
            "ready": ready,
            "callback_probe": callback_probe,
            "callback_probe_history": callback_probe_history,
            "local_tunnel": local_tunnel,
            "recent_chat_bindings": recent_chat_bindings,
            "summary": summary,
            "supported_commands": [
                "状态",
                "报告 <mission_id>",
                "测试 <url/需求>",
                "发现 <session_id>",
                "风险 <assessment_id>",
                "停止 <mission_id>",
                "批准 <run_id> [备注]",
                "驳回 <run_id> [备注]",
                "绑定 <code>",
            ],
            "latest_event": latest,
            "latest_successful_event": latest_successful,
            "latest_external_successful_event": latest_external_success,
            "latest_external_success_at": str((latest_external_success or {}).get("created_at") or ""),
            "latest_external_self_check_event": latest_external_self_check,
            "latest_external_self_check_at": str((latest_external_self_check or {}).get("created_at") or ""),
            "latest_subscription_check_event": latest_subscription_check,
            "recent_events": event_items[:10],
        }


_service: Optional[CommanderChatOpsService] = None


def get_commander_chatops_service() -> CommanderChatOpsService:
    global _service
    if _service is None:
        _service = CommanderChatOpsService()
    return _service
