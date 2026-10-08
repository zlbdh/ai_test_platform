from __future__ import annotations

import logging
from typing import Any, Dict
from urllib.parse import urlparse

from core.api_tools import http_request

logger = logging.getLogger(__name__)


def normalize_base_url(base_url: str) -> str:
    raw = (base_url or "").strip()
    if not raw:
        raise ValueError("base_url must not be empty")
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid base_url: {base_url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def resolve_url(base_url: str, path_or_url: str) -> str:
    raw = (path_or_url or "").strip()
    if not raw:
        return normalize_base_url(base_url)
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return raw
    origin = normalize_base_url(base_url)
    if raw.startswith("/"):
        return f"{origin}{raw}"
    return f"{origin}/{raw}"


def _extract_token(response: Dict[str, Any]) -> str:
    content = response.get("content")
    if not isinstance(content, dict):
        return ""
    data = content.get("data") or {}
    if not isinstance(data, dict):
        return ""
    return str(data.get("access_token") or "").strip()


def _ensure_success(response: Dict[str, Any], action: str) -> None:
    status_code = int(response.get("status_code") or -1)
    content = response.get("content")
    if status_code != 200:
        raise RuntimeError(f"{action} failed: HTTP {status_code}")
    if isinstance(content, dict):
        code = content.get("code")
        if code not in (None, 200):
            msg = content.get("msg") or content.get("message") or "Unknown error"
            raise RuntimeError(f"{action} failed: {msg}")


def apply_auth_bootstrap(page, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sign in and switch sites through real APIs, then inject authentication into the current browser context.
    """
    if not isinstance(payload, dict):
        raise ValueError("bootstrap payload must be a dictionary")

    base_url = normalize_base_url(str(payload.get("base_url") or ""))
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    access_token = str(payload.get("access_token") or "").strip()

    if not access_token and (not username or not password):
        raise ValueError("Preauthentication requires access_token or username/password")

    login_path = str(payload.get("login_path") or "/auth/login1").strip() or "/auth/login1"
    token_cookie_name = str(payload.get("token_cookie_name") or "Admin-Token").strip() or "Admin-Token"

    if not access_token:
        login_body = dict(payload.get("login_body") or {})
        login_body.setdefault("username", username)
        login_body.setdefault("password", password)
        login_body.setdefault("code", "")
        login_body.setdefault("uuid", "")

        login_response = http_request(
            "POST",
            resolve_url(base_url, login_path),
            headers={"Content-Type": "application/json"},
            json_body=login_body,
        )
        _ensure_success(login_response, "Sign-in")
        access_token = _extract_token(login_response)
        if not access_token:
            raise RuntimeError("Sign-in failed: the response did not include access_token")

    station_id = payload.get("station_id")
    city = payload.get("city")
    switch_station_path = str(payload.get("switch_station_path") or "/system/user/switchCityStation").strip()
    if station_id and city:
        switch_response = http_request(
            "POST",
            resolve_url(base_url, switch_station_path),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json_body={"stationId": str(station_id), "city": str(city)},
        )
        _ensure_success(switch_response, "Switch site")

    page.context.add_cookies([{
        "name": token_cookie_name,
        "value": access_token,
        "url": base_url,
        "httpOnly": False,
        "secure": False,
        "sameSite": "Lax",
    }])

    bootstrap_landing_path = str(payload.get("bootstrap_landing_path") or "/qyLogin").strip()
    bootstrap_url = resolve_url(base_url, bootstrap_landing_path)
    page.goto(bootstrap_url, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass

    storage_items = dict(payload.get("local_storage") or {})
    if station_id is not None:
        storage_items.setdefault("currentStation", str(station_id))
        storage_items.setdefault("currentStationId", str(station_id))
    if city:
        storage_items.setdefault("currentCity", str(city))

    if storage_items:
        page.evaluate(
            """(items) => {
                Object.entries(items).forEach(([key, value]) => {
                    localStorage.setItem(key, String(value));
                });
                return Object.keys(items);
            }""",
            storage_items,
        )

    target_url = resolve_url(
        base_url,
        str(payload.get("target_path") or payload.get("target_url") or "").strip(),
    )
    if target_url:
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

    return {
        "base_url": base_url,
        "bootstrap_url": bootstrap_url,
        "target_url": target_url,
        "token_cookie_name": token_cookie_name,
        "storage_keys": sorted(storage_items.keys()),
        "station_id": str(station_id) if station_id is not None else "",
        "city": str(city or ""),
        "applied": True,
    }

