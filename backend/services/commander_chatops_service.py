# -*- coding: utf-8 -*-
"""
Commander ChatOps Service

Compute a consistent status for the bidirectional notification command channel, shared by:
- Notification settings
- Platform information, readiness, and remediation
- Future operational monitoring
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
            "summary": "This environment is not Windows; the local reverse tunnel script is unavailable."
            if os.name != "nt"
            else "Local reverse tunnel script not found."
            if not script_path.exists()
            else "No local OpenSSH reverse tunnel process detected.",
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
            result["summary"] = "Local reverse tunnel status check timed out."
            return result
        except OSError as exc:
            result["status"] = "unknown"
            result["summary"] = f"Failed to check local reverse tunnel status: {exc.__class__.__name__}"
            return result

        if completed.returncode != 0:
            stderr = str(completed.stderr or "").strip()
            result["status"] = "unknown"
            result["summary"] = f"Failed to check local reverse tunnel status: {stderr or 'PowerShell returned an error'}"
            return result

        payload = str(completed.stdout or "").strip()
        if not payload:
            if result["stderr_tail"]:
                result["summary"] = f"No tunnel process detected. Latest error: {result['stderr_tail']}"
            return result

        try:
            proc = json.loads(payload)
        except json.JSONDecodeError:
            result["status"] = "unknown"
            result["summary"] = "Could not parse the local reverse tunnel status output."
            return result

        pid = proc.get("ProcessId")
        result.update({
            "running": True,
            "pid": int(pid) if pid is not None else None,
            "created_at": str(proc.get("CreationDate") or ""),
            "command_line": str(proc.get("CommandLine") or ""),
            "status": "running",
            "summary": f"Local OpenSSH reverse tunnel process detected (PID {pid})." if pid is not None else "Local OpenSSH reverse tunnel process detected.",
        })
        return result

    def restart_local_tunnel(self) -> Dict[str, Any]:
        before = self._get_local_tunnel_status()
        if not before.get("supported"):
            return {
                "ok": False,
                "message": before.get("summary") or "This environment does not support a local reverse tunnel.",
                "tunnel": before,
                "overview": self.get_overview(),
            }
        script_path = Path(str(before.get("script_path") or self._local_tunnel_script_path()))
        if not script_path.exists():
            return {
                "ok": False,
                "message": "Local reverse tunnel script not found; restart is unavailable.",
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
                "message": "Local reverse tunnel restart timed out.",
                "stdout": "",
                "stderr": "",
                "tunnel": after,
                "overview": self.get_overview(),
            }
        except OSError as exc:
            after = self._get_local_tunnel_status()
            return {
                "ok": False,
                "message": f"Failed to restart the local reverse tunnel: {exc.__class__.__name__}",
                "stdout": "",
                "stderr": str(exc),
                "tunnel": after,
                "overview": self.get_overview(),
            }

        after = self._get_local_tunnel_status()
        ok = completed.returncode == 0 and bool(after.get("running"))
        message = (
            "Local reverse tunnel restarted."
            if ok
            else str(completed.stderr or "").strip()
            or str(after.get("summary") or "Local reverse tunnel has not recovered.")
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
        if "Platform public endpoint self-test passed" in response:
            return True
        return False

    @staticmethod
    def _build_probe_result_from_response(
        *,
        status_code: int,
        content_type: str,
        excerpt: str,
        response_json: Any,
        summary_prefix: str = "Public callback URL",
    ) -> Dict[str, Any]:
        lowered_excerpt = str(excerpt or "").lower()
        lowered_type = str(content_type or "").lower()
        success = False
        issue = ""

        if status_code == 200 and isinstance(response_json, dict) and response_json.get("challenge") == "chatops-probe":
            success = True
            summary = f"{summary_prefix} passed an active probe; the current endpoint is publicly reachable."
        elif "pinggy" in lowered_excerpt or "caution" in lowered_excerpt:
            issue = "interstitial_page"
            summary = f"{summary_prefix} returned a tunnel warning page; the notification provider will likely be unable to reach the platform callback directly."
        elif "tunnel unavailable" in lowered_excerpt or status_code == 503:
            issue = "tunnel_unavailable"
            summary = f"{summary_prefix} currently returns Tunnel Unavailable; the tunnel is not stable."
        elif "text/html" in lowered_type:
            issue = "html_response"
            summary = f"{summary_prefix} returned an HTML page instead of challenge JSON; the external callback channel is unavailable."
        else:
            issue = "unexpected_response"
            summary = f"{summary_prefix} responded, but the response does not match the notification provider's expected challenge (HTTP {status_code})."

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
                summary="Public callback probe timed out (curl fallback); the notification provider will likely be unable to reach this endpoint reliably.",
            )
        except OSError as exc:
            return CommanderChatOpsService._build_probe_result(
                attempted=True,
                success=False,
                issue="connect_error",
                summary=f"Public callback probe failed (curl fallback): {exc.__class__.__name__}",
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
                summary=f"Public callback probe failed (curl fallback): {excerpt or 'Unknown error'}",
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
            summary_prefix="Public callback URL (curl fallback)",
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
                "label": "Unknown",
                "host": "",
            }
        try:
            host = (urlsplit(text).hostname or "").strip().lower()
        except Exception:
            host = ""
        if not host:
            return {
                "key": "unknown",
                "label": "Unknown",
                "host": "",
            }
        if host in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}:
            return {
                "key": "local",
                "label": "Local URL",
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
                "label": "Temporary LHR tunnel",
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
            "label": "Custom public URL",
            "host": host,
        }

    @staticmethod
    def _build_provider_recommendation(provider: Dict[str, str], issue: str, callback_public: bool) -> str:
        provider_label = provider.get("label") or "Current public endpoint"
        provider_key = provider.get("key") or "unknown"
        if not callback_public:
            return "First set PUBLIC_API_BASE_URL to a public URL reachable by the notification provider, then run the challenge probe."
        if not issue:
            return f"{provider_label} passed the challenge probe. Complete event subscription in the notification provider's developer console and test with real group messages."
        if issue == "tunnel_unavailable":
            if provider_key == "localtunnel":
                return f"{provider_label} is no longer valid. Create a new LocalTunnel or switch to a more stable fixed public endpoint."
            if provider_key == "cloudflare_quick_tunnel":
                return f"{provider_label} is unavailable. Rebuild the tunnel and prefer your own domain or fixed reverse proxy over a temporary Quick Tunnel."
            return f"{provider_label} currently returns Tunnel Unavailable. Rebuild the tunnel, then run the probe again."
        if issue == "interstitial_page":
            return f"{provider_label} returned an intermediate warning page, preventing the notification challenge from reaching the platform directly. Use a public reverse proxy or tunnel without an intermediate page."
        if issue == "html_response":
            return f"{provider_label} currently returns HTML instead of challenge JSON, indicating that the outer proxy is not forwarding directly to the platform callback API."
        if issue == "timeout":
            return f"{provider_label} probe timed out. Use a public endpoint with more stable latency, or check whether network policies are blocking the tunnel."
        if issue == "connect_error":
            return f"{provider_label} connection failed. Check that the tunnel process is running and the public domain still forwards to local port 8020."
        if issue == "unexpected_response":
            return f"{provider_label} responded, but the response format does not match the notification challenge. Check whether the outer proxy is rewriting requests or responses."
        if provider_key == "local":
            return "The URL is still local and cannot be reached directly by the notification provider. Configure a public endpoint first."
        return f"{provider_label} needs further integration testing. Confirm that the challenge probe passes before completing event subscription in the notification provider's console."

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
                summary="The callback URL is still local or private; skipping the public probe.",
            )
        if not verification_token:
            return self._build_probe_result(
                attempted=False,
                success=False,
                issue="token_missing",
                summary="The verification token is not configured; skipping the public probe.",
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
                summary="Public callback probe timed out; the notification provider will likely be unable to reach this endpoint reliably.",
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
                summary=f"Public callback probe failed: {exc.__class__.__name__}",
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
                summary="Reusing the most recent public probe result. To verify immediately, run \"Retry probe now\" or \"Run public channel self-test\" manually.",
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
        # external_connected means the current endpoint is healthy and real group-message delivery was verified previously.
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
            "Expose only the notification app bot dedicated to this project. Prefer the app bot for group command replies, with Webhook as a fallback notification channel."
            if app_bot_ready and webhook_ready
            else "Only the app bot dedicated to this project is configured. Group commands can gradually use one bot identity, but the Webhook fallback is still missing."
            if app_bot_ready
            else "Credentials for this project's dedicated app bot are saved, but the latest validation failed. It cannot yet be treated as a stable primary channel."
            if app_bot_configured
            else "Notifications still primarily rely on a Webhook bot; a single-bot experience is not yet established."
            if webhook_ready
            else "Notification bot channels are not fully configured."
        )

        if recent_external_success_on_current_callback and probe_timeout_like and not bool(callback_probe.get("success")):
            callback_recommendation = (
                "The current public URL received real notification group messages within the last 15 minutes, indicating that the channel remains available; "
                "this appears to be temporary tunnel instability. Continue testing in the group; switch to a more stable public endpoint if timeouts persist."
            )
        elif recent_subscription_check_on_current_callback and external_history_observed:
            callback_recommendation = (
                "The current public URL recently passed the notification challenge, and the platform previously received real notification group messages; "
                "the bidirectional channel remains usable. Consider a more stable public endpoint if timeouts persist."
            )
        elif recent_subscription_check_on_current_callback and not external_history_observed:
            callback_recommendation = (
                "The current public URL recently passed the notification challenge, confirming that the provider can reach the callback endpoint; "
                "send a real message in the target group or direct chat to complete integration testing."
            )
        elif recent_external_self_check_on_current_callback and external_history_observed:
            callback_recommendation = (
                "The current public URL recently passed the platform public endpoint self-test, and the platform previously received real notification group messages; "
                "the bidirectional channel remains usable. Consider a more stable public endpoint if timeouts persist."
            )
        elif recent_external_self_check_on_current_callback and not external_history_observed:
            callback_recommendation = (
                "The current public URL passed the platform public endpoint self-test, confirming that challenge and text messages can reach the callback endpoint; "
                "complete event subscription in the notification provider's developer console, then send a real message in the target group for final integration testing."
            )

        if not webhook_ready:
            summary = "The notification event callback endpoint is available, but there is no healthy reply channel yet."
        elif not verification_token_configured:
            summary = "The notification reply channel is healthy, but the event subscription verification token is missing; group messages cannot reliably reach the platform yet."
        elif not subscription_endpoint_verified:
            summary = "The verification token is configured, but the platform has not completed the event subscription challenge self-check. Run platform callback verification first."
        elif not callback_url_public:
            summary = (
                "The platform previously received real notification group messages, but the callback URL has reverted to a local or private address. Configure a public callback URL reachable by the notification provider."
                if external_history_observed
                else "Platform event subscription is ready, but the callback URL is still local or private. Configure a public callback URL reachable by the notification provider."
            )
        elif recent_external_success_on_current_callback and probe_timeout_like and not bool(callback_probe.get("success")):
            summary = (
                f"{str(callback_probe.get('summary') or 'Public callback probe timed out.')} "
                "However, the current public URL received real notification group messages within the last 15 minutes, indicating that the bidirectional channel remains available. This appears to be temporary tunnel instability."
            )
        elif recent_external_self_check_on_current_callback and external_history_observed:
            summary = (
                "The latest platform public endpoint self-test passed, and the platform previously received real notification group messages; "
                "the bidirectional channel remains usable."
            )
        elif recent_subscription_check_on_current_callback and external_history_observed:
            summary = (
                "The latest notification challenge passed, and the platform previously received real notification group messages; "
                "the bidirectional channel remains usable."
            )
        elif recent_subscription_check_on_current_callback and not external_history_observed:
            summary = (
                "The latest notification challenge passed, confirming that the current public callback endpoint is reachable; "
                "send a real message in the target group or direct chat to complete integration testing."
            )
        elif callback_probe.get("attempted") and not callback_probe.get("success"):
            if external_history_observed:
                summary = (
                    f"{str(callback_probe.get('summary') or 'Public callback probe failed. Restore public endpoint reachability first.')} "
                    "The platform previously received real notification group messages, indicating degradation of the public endpoint rather than a channel that never worked."
                )
            elif recent_external_self_check_on_current_callback:
                summary = (
                    f"{str(callback_probe.get('summary') or 'Public callback probe failed. Restore public endpoint reachability first.')} "
                    "However, the latest platform public endpoint self-test passed, confirming that challenge and text messages still reach the platform; "
                    "this appears to be temporary probe instability. Repeat integration testing with real notification group messages."
                )
            else:
                summary = str(callback_probe.get("summary") or "Public callback probe failed. Restore public endpoint reachability first.")
        elif recent_external_self_check_on_current_callback and not external_history_observed:
            summary = (
                "The latest platform public endpoint self-test passed, confirming that the public callback endpoint, challenge, and text-message channel are available; "
                "this does not yet establish connectivity for real notification group messages. Confirm that event subscription is enabled in the provider's developer console, "
                "add the app bot to the target group, and send a real message in the group to complete integration testing."
            )
        elif not external_history_observed:
            summary = (
                "This project's dedicated notification app bot is configured, and the platform and public callback are ready; "
                "expose only this bot and use Webhook as a fallback. "
                "However, no real group messages have arrived yet. Add the app bot to the target group and send a test message."
            )
        elif latest and latest["status"] == "ignored" and latest_successful:
            summary = "A recent event was unhandled, but the latest text command was still successfully sent back."
        elif latest_external_success is not None:
            summary = (
                "The latest notification text command arrived through the public callback and was successfully sent back to the group."
                if app_bot_configured
                else "The latest notification text command arrived through the public callback and was successfully sent back to the group. The platform has no saved App Bot credentials, but the existing bidirectional channel is usable."
            )
        elif not latest:
            summary = "The bidirectional notification command endpoint is ready; no new events have arrived yet."
        elif latest["status"] == "ok" and latest["delivery_delivered"] > 0:
            summary = "The latest notification command was received and successfully sent back to the group."
        elif latest["status"] == "ok":
            summary = "The latest notification command was received but could not be sent back to the group."
        else:
            summary = "The latest notification event did not complete normally. Check the message format and reply channel."

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
                "status",
                "report <mission_id>",
                "test <url/requirement>",
                "findings <session_id>",
                "risk <assessment_id>",
                "stop <mission_id>",
                "approve <run_id> [note]",
                "reject <run_id> [note]",
                "bind <code>",
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
