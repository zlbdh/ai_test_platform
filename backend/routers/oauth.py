# -*- coding: utf-8 -*-
"""
OAuth authentication helper routes
"""
from fastapi import APIRouter
from core.models import OAuthConfigRequest, SaveTokenRequest
from services.oauth_helper import get_oauth_helper, OAuthProvider

router = APIRouter(prefix="/api/oauth", tags=["OAuth"])


@router.post("/configure")
async def configure_oauth(req: OAuthConfigRequest):
    """Configure an OAuth provider"""
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
    """Save a test token"""
    helper = get_oauth_helper()
    token = helper.save_test_token(req.name, req.access_token, req.provider, req.expires_hours)
    return {
        "status": "success",
        "name": req.name,
        "expires_at": token.expires_at
    }


@router.get("/token/{name}")
async def get_oauth_token(name: str):
    """Get a saved token"""
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
    """List all tokens"""
    return {
        "status": "success",
        "tokens": get_oauth_helper().list_tokens()
    }


@router.post("/cleanup")
async def cleanup_oauth_tokens():
    """Clean up expired tokens"""
    count = get_oauth_helper().clear_expired()
    return {"status": "success", "cleared": count}
