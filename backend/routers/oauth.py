# -*- coding: utf-8 -*-
"""
OAuth 认证助手路由
"""
from fastapi import APIRouter
from core.models import OAuthConfigRequest, SaveTokenRequest
from services.oauth_helper import get_oauth_helper, OAuthProvider

router = APIRouter(prefix="/api/oauth", tags=["OAuth"])


@router.post("/configure")
async def configure_oauth(req: OAuthConfigRequest):
    """配置 OAuth 提供商"""
    helper = get_oauth_helper()
    provider = OAuthProvider(req.provider) if req.provider in [p.value for p in OAuthProvider] else OAuthProvider.CUSTOM
    config = helper.configure_provider(provider, req.client_id, req.client_secret, req.redirect_uri)
    auth_url = helper.get_authorization_url(config)
    return {
        "status": "success",
        "authorization_url": auth_url
    }


@router.post("/token/save")
async def save_oauth_token(req: SaveTokenRequest):
    """保存测试用 Token"""
    helper = get_oauth_helper()
    token = helper.save_test_token(req.name, req.access_token, req.provider, req.expires_hours)
    return {
        "status": "success",
        "name": req.name,
        "expires_at": token.expires_at
    }


@router.get("/token/{name}")
async def get_oauth_token(name: str):
    """获取已保存的 Token"""
    helper = get_oauth_helper()
    token = helper.get_test_token(name)
    if token:
        return {
            "status": "success",
            "access_token": token.access_token[:20] + "...",
            "expires_at": token.expires_at,
            "provider": token.provider
        }
    return {"status": "not_found"}


@router.get("/tokens")
async def list_oauth_tokens():
    """列出所有 Token"""
    return {
        "status": "success",
        "tokens": get_oauth_helper().list_tokens()
    }


@router.post("/cleanup")
async def cleanup_oauth_tokens():
    """清理过期 Token"""
    count = get_oauth_helper().clear_expired()
    return {"status": "success", "cleared": count}
