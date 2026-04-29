"""
OAuth Authentication Helper - OAuth 认证助手

自动处理 OAuth 登录流程：
- 支持多种 OAuth 提供商
- 自动获取和刷新 Token
- Token 缓存和管理
- 浏览器自动登录
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import os
import hashlib
import logging
import aiohttp


class OAuthProvider(Enum):
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    FACEBOOK = "facebook"
    CUSTOM = "custom"


@dataclass
class OAuthConfig:
    """OAuth 配置"""
    provider: OAuthProvider
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    redirect_uri: str
    scope: str


@dataclass
class OAuthToken:
    """OAuth Token"""
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_at: str
    scope: str
    provider: str


class OAuthHelper:
    """OAuth 助手"""

    __test__ = False
    
    # 预配置的 OAuth 提供商
    PROVIDER_CONFIGS = {
        OAuthProvider.GOOGLE: {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scope": "openid email profile"
        },
        OAuthProvider.GITHUB: {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "scope": "read:user user:email"
        },
        OAuthProvider.MICROSOFT: {
            "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "scope": "openid email profile"
        }
    }
    
    def __init__(self, cache_dir: str = "./data/oauth_cache"):
        self.cache_dir = cache_dir
        self.tokens: Dict[str, OAuthToken] = {}
        os.makedirs(cache_dir, exist_ok=True)
        self._load_cached_tokens()
    
    def _get_cache_key(self, provider: str, client_id: str) -> str:
        """生成缓存键"""
        content = f"{provider}:{client_id}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _load_cached_tokens(self):
        """加载缓存的 Token"""
        cache_file = os.path.join(self.cache_dir, "tokens.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, token_data in data.items():
                    try:
                        self.tokens[key] = OAuthToken(**token_data)
                    except TypeError as exc:
                        logging.getLogger(__name__).warning("Ignored invalid OAuth token cache entry %s: %s", key, exc)
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                logging.getLogger(__name__).warning("Failed to load OAuth token cache: %s", exc)
    
    def _save_tokens(self):
        """保存 Token 缓存"""
        cache_file = os.path.join(self.cache_dir, "tokens.json")
        data = {
            key: {
                "access_token": t.access_token,
                "refresh_token": t.refresh_token,
                "token_type": t.token_type,
                "expires_at": t.expires_at,
                "scope": t.scope,
                "provider": t.provider
            }
            for key, t in self.tokens.items()
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def configure_provider(
        self,
        provider: OAuthProvider,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8020/oauth/callback",
        custom_config: Optional[Dict[str, str]] = None
    ) -> OAuthConfig:
        """配置 OAuth 提供商"""
        base_config = dict(self.PROVIDER_CONFIGS.get(provider, {}))

        if custom_config:
            base_config.update(custom_config)
        
        return OAuthConfig(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            auth_url=base_config.get("auth_url", ""),
            token_url=base_config.get("token_url", ""),
            redirect_uri=redirect_uri,
            scope=base_config.get("scope", "")
        )
    
    def get_authorization_url(self, config: OAuthConfig, state: Optional[str] = None) -> str:
        """获取授权 URL"""
        import urllib.parse
        
        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scope": config.scope,
            "response_type": "code",
            "state": state or hashlib.md5(str(datetime.now()).encode()).hexdigest()[:16]
        }
        
        if config.provider == OAuthProvider.GOOGLE:
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        
        query = urllib.parse.urlencode(params)
        return f"{config.auth_url}?{query}"

    async def _request_token(
        self,
        token_url: str,
        data: Dict[str, str],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """请求 OAuth Token 端点"""
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data, headers=headers or {}) as resp:
                result = await resp.json(content_type=None)
                if resp.status >= 400:
                    error = result.get("error_description") or result.get("error") or "unknown_error"
                    raise RuntimeError(f"OAuth token request failed: {error}")
                if "access_token" not in result:
                    raise RuntimeError("OAuth token response missing access_token")
                return result
    
    async def exchange_code(
        self,
        config: OAuthConfig,
        code: str
    ) -> OAuthToken:
        """用授权码换取 Token"""
        data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "redirect_uri": config.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        headers = {"Accept": "application/json"}
        
        result = await self._request_token(config.token_url, data, headers=headers)

        expires_in = result.get("expires_in", 3600)
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

        token = OAuthToken(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            token_type=result.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=result.get("scope", config.scope),
            provider=config.provider.value
        )

        cache_key = self._get_cache_key(config.provider.value, config.client_id)
        self.tokens[cache_key] = token
        self._save_tokens()

        return token
    
    async def refresh_token(
        self,
        config: OAuthConfig,
        refresh_token: str
    ) -> OAuthToken:
        """刷新 Token"""
        data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        result = await self._request_token(
            config.token_url,
            data,
            headers={"Accept": "application/json"}
        )

        expires_in = result.get("expires_in", 3600)
        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

        token = OAuthToken(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token", refresh_token),
            token_type=result.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=result.get("scope", config.scope),
            provider=config.provider.value
        )

        cache_key = self._get_cache_key(config.provider.value, config.client_id)
        self.tokens[cache_key] = token
        self._save_tokens()

        return token
    
    def get_cached_token(
        self,
        provider: OAuthProvider,
        client_id: str
    ) -> Optional[OAuthToken]:
        """获取缓存的 Token"""
        cache_key = self._get_cache_key(provider.value, client_id)
        token = self.tokens.get(cache_key)
        
        if token:
            # 检查是否过期
            expires_at = datetime.fromisoformat(token.expires_at)
            if datetime.now() < expires_at:
                return token
            self.tokens.pop(cache_key, None)

        return None
    
    async def get_valid_token(
        self,
        config: OAuthConfig
    ) -> Optional[OAuthToken]:
        """获取有效 Token（自动刷新）"""
        token = self.get_cached_token(config.provider, config.client_id)
        
        if token:
            # 检查是否快过期（提前 5 分钟刷新）
            expires_at = datetime.fromisoformat(token.expires_at)
            if datetime.now() + timedelta(minutes=5) < expires_at:
                return token
            
            # 尝试刷新
            if token.refresh_token:
                try:
                    return await self.refresh_token(config, token.refresh_token)
                except Exception:
                    pass
        
        return None
    
    def save_test_token(
        self,
        name: str,
        access_token: str,
        provider: str = "custom",
        expires_hours: int = 24
    ) -> OAuthToken:
        """保存测试用 Token（手动配置）"""
        expires_at = (datetime.now() + timedelta(hours=expires_hours)).isoformat()
        
        token = OAuthToken(
            access_token=access_token,
            refresh_token=None,
            token_type="Bearer",
            expires_at=expires_at,
            scope="",
            provider=provider
        )
        
        cache_key = f"test_{name}"
        self.tokens[cache_key] = token
        self._save_tokens()
        
        return token
    
    def get_test_token(self, name: str) -> Optional[OAuthToken]:
        """获取测试用 Token"""
        cache_key = f"test_{name}"
        return self.tokens.get(cache_key)
    
    def list_tokens(self) -> List[Dict[str, Any]]:
        """列出所有缓存的 Token"""
        return [
            {
                "key": key,
                "provider": token.provider,
                "expires_at": token.expires_at,
                "is_valid": datetime.fromisoformat(token.expires_at) > datetime.now()
            }
            for key, token in self.tokens.items()
        ]
    
    def clear_expired(self) -> int:
        """清理过期 Token"""
        now = datetime.now()
        expired_keys = [
            key for key, token in self.tokens.items()
            if datetime.fromisoformat(token.expires_at) < now
        ]
        
        for key in expired_keys:
            del self.tokens[key]
        
        self._save_tokens()
        return len(expired_keys)


# 单例
_oauth_helper: Optional[OAuthHelper] = None

def get_oauth_helper() -> OAuthHelper:
    """获取 OAuth 助手"""
    global _oauth_helper
    if _oauth_helper is None:
        _oauth_helper = OAuthHelper()
    return _oauth_helper
