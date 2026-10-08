# -*- coding: utf-8 -*-
"""
FastAPI authentication dependencies

Provide shared token extraction, session validation, and administrator checks for high-risk routes.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import Header, HTTPException, Query, Request

from services.auth_service import Permission, User, get_auth_service


def _is_dev_auth_bypass_enabled() -> bool:
    return os.getenv("DEV_AUTH_BYPASS", "false").strip().lower() == "true"


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        return ""

    prefix = "bearer "
    value = authorization.strip()
    if value.lower().startswith(prefix):
        return value[len(prefix):].strip()
    return ""


async def extract_request_token(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_auth_token: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> str:
    """Extract the token from query parameters, headers, or the body."""
    if token:
        return token.strip()

    if x_auth_token:
        return x_auth_token.strip()

    bearer_token = _extract_bearer_token(authorization)
    if bearer_token:
        return bearer_token

    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            body = await request.body()
            if body:
                payload = json.loads(body)
                if isinstance(payload, dict):
                    for key in ("token", "auth_token", "access_token"):
                        value = payload.get(key)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
        except Exception:
            return ""

    return ""


async def require_authenticated_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_auth_token: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> User:
    """Require a valid authenticated session."""
    auth = get_auth_service()
    token_value = await extract_request_token(
        request=request,
        authorization=authorization,
        x_auth_token=x_auth_token,
        token=token,
    )
    if token_value:
        user = auth.validate_token(token_value)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        request.state.authenticated_user = user
        request.state.auth_bypassed = False
        return user

    if _is_dev_auth_bypass_enabled():
        user = auth.get_dev_bypass_user()
        if not user:
            raise HTTPException(status_code=503, detail="No available user for development auth bypass")
        request.state.authenticated_user = user
        request.state.auth_bypassed = True
        return user

    raise HTTPException(status_code=401, detail="Authentication token required")



async def require_admin_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_auth_token: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> User:
    """Require administrator privileges."""
    user = await require_authenticated_user(
        request=request,
        authorization=authorization,
        x_auth_token=x_auth_token,
        token=token,
    )
    auth = get_auth_service()
    if not auth.check_permission(user, Permission.ADMIN):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def build_permission_dependency(permission: Permission, detail: str):
    """Build a dependency for granular permission checks."""

    async def _require_permission_user(
        request: Request,
        authorization: Optional[str] = Header(default=None),
        x_auth_token: Optional[str] = Header(default=None),
        token: Optional[str] = Query(default=None),
    ) -> User:
        user = await require_authenticated_user(
            request=request,
            authorization=authorization,
            x_auth_token=x_auth_token,
            token=token,
        )
        auth = get_auth_service()
        if not auth.check_permission(user, permission):
            raise HTTPException(status_code=403, detail=detail)
        return user

    return _require_permission_user


require_deploy_view_user = build_permission_dependency(
    Permission.DEPLOY_VIEW,
    "Deploy view access required",
)
require_deploy_request_user = build_permission_dependency(
    Permission.DEPLOY_REQUEST,
    "Deploy request access required",
)
require_deploy_approve_user = build_permission_dependency(
    Permission.DEPLOY_APPROVE,
    "Deploy approval access required",
)
