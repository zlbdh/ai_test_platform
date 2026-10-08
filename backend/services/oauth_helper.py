"""
OAuth authentication helper.

Automates OAuth sign-in flows:
- Multiple OAuth providers
- Token retrieval and refresh
- Token caching and management
- Automated browser sign-in
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
    """OAuth configuration"""
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
    """OAuth helper"""

    __test__ = False
    
    # Preconfigured OAuth providers
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
        """Generate a cache key"""
        content = f"{provider}:{client_id}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _load_cached_tokens(self):
        """Load cached tokens"""
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
        """Save the token cache"""
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
        """Configure an OAuth provider"""
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
        """Get the authorization URL"""
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
        """Request an OAuth token endpoint"""
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
        """Exchange an authorization code for a token"""
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
        """Refresh a token"""
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
        """Get a cached token"""
        cache_key = self._get_cache_key(provider.value, client_id)
        token = self.tokens.get(cache_key)
        
        if token:
            # Check expiration
            expires_at = datetime.fromisoformat(token.expires_at)
            if datetime.now() < expires_at:
                return token
            self.tokens.pop(cache_key, None)

        return None
    
    async def get_valid_token(
        self,
        config: OAuthConfig
    ) -> Optional[OAuthToken]:
        """Get a valid token with automatic refresh"""
        token = self.get_cached_token(config.provider, config.client_id)
        
        if token:
            # Check whether the token expires soon; refresh five minutes early
            expires_at = datetime.fromisoformat(token.expires_at)
            if datetime.now() + timedelta(minutes=5) < expires_at:
                return token
            
            # Attempt refresh
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
        """Save a manually configured test token"""
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
        """Get a test token"""
        cache_key = f"test_{name}"
        return self.tokens.get(cache_key)
    
    def list_tokens(self) -> List[Dict[str, Any]]:
        """List all cached tokens"""
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
        """Remove expired tokens"""
        now = datetime.now()
        expired_keys = [
            key for key, token in self.tokens.items()
            if datetime.fromisoformat(token.expires_at) < now
        ]
        
        for key in expired_keys:
            del self.tokens[key]
        
        self._save_tokens()
        return len(expired_keys)


# Singleton
_oauth_helper: Optional[OAuthHelper] = None

def get_oauth_helper() -> OAuthHelper:
    """Get the OAuth helper"""
    global _oauth_helper
    if _oauth_helper is None:
        _oauth_helper = OAuthHelper()
    return _oauth_helper
