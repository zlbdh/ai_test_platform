"""
OAuthHelper unit tests.
Covers configuration, caching, authorization URLs, code-to-token exchange, token
refresh, automatic refresh, and the singleton.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from services.oauth_helper import (
    OAuthConfig,
    OAuthHelper,
    OAuthProvider,
    OAuthToken,
    get_oauth_helper,
)


class FakeResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def post(self, url, data=None, headers=None):
        self.calls.append({"url": url, "data": data, "headers": headers})
        return self.response


@pytest.fixture
def helper(tmp_path):
    return OAuthHelper(cache_dir=str(tmp_path))


class TestOAuthProvider:
    def test_values(self):
        assert OAuthProvider.GOOGLE.value == "google"
        assert OAuthProvider.CUSTOM.value == "custom"


class TestOAuthConfig:
    def test_creation(self):
        config = OAuthConfig(
            provider=OAuthProvider.GOOGLE,
            client_id="cid",
            client_secret="sec",
            auth_url="https://auth",
            token_url="https://token",
            redirect_uri="http://cb",
            scope="openid",
        )
        assert config.client_id == "cid"


class TestOAuthToken:
    def test_creation(self):
        token = OAuthToken(
            access_token="at",
            refresh_token="rt",
            token_type="Bearer",
            expires_at="2099-01-01T00:00:00",
            scope="openid",
            provider="google",
        )
        assert token.token_type == "Bearer"


class TestProviderConfigs:
    def test_has_google(self):
        assert OAuthProvider.GOOGLE in OAuthHelper.PROVIDER_CONFIGS

    def test_has_github(self):
        assert OAuthProvider.GITHUB in OAuthHelper.PROVIDER_CONFIGS


class TestConfigureProvider:
    def test_google(self, helper):
        config = helper.configure_provider(OAuthProvider.GOOGLE, "cid", "sec")
        assert "google" in config.auth_url
        assert config.scope == "openid email profile"

    def test_custom(self, helper):
        config = helper.configure_provider(
            OAuthProvider.CUSTOM,
            "cid",
            "sec",
            custom_config={
                "auth_url": "https://custom/auth",
                "token_url": "https://custom/token",
                "scope": "custom",
            },
        )
        assert config.auth_url == "https://custom/auth"

    def test_custom_config_does_not_mutate_provider_defaults(self, helper):
        original_scope = OAuthHelper.PROVIDER_CONFIGS[OAuthProvider.GOOGLE]["scope"]

        helper.configure_provider(
            OAuthProvider.GOOGLE,
            "cid",
            "sec",
            custom_config={"scope": "custom-scope"},
        )

        assert OAuthHelper.PROVIDER_CONFIGS[OAuthProvider.GOOGLE]["scope"] == original_scope


class TestGetAuthorizationUrl:
    def test_url_contains_params(self, helper):
        config = helper.configure_provider(OAuthProvider.GITHUB, "cid", "sec")
        url = helper.get_authorization_url(config, state="test_state")
        assert "client_id=cid" in url
        assert "state=test_state" in url
        assert "response_type=code" in url

    def test_google_has_access_type(self, helper):
        config = helper.configure_provider(OAuthProvider.GOOGLE, "cid", "sec")
        url = helper.get_authorization_url(config)
        assert "access_type=offline" in url


class TestCacheKey:
    def test_deterministic(self, helper):
        assert helper._get_cache_key("google", "cid") == helper._get_cache_key("google", "cid")

    def test_different_inputs(self, helper):
        assert helper._get_cache_key("google", "cid1") != helper._get_cache_key("google", "cid2")


class TestCachePersistence:
    def test_load_ignores_invalid_json(self, tmp_path):
        cache_file = tmp_path / "tokens.json"
        cache_file.write_text("{invalid", encoding="utf-8")

        helper = OAuthHelper(cache_dir=str(tmp_path))

        assert helper.tokens == {}

    def test_load_ignores_invalid_token_entry(self, tmp_path):
        cache_file = tmp_path / "tokens.json"
        cache_file.write_text('{"bad":{"access_token":"x"}}', encoding="utf-8")

        helper = OAuthHelper(cache_dir=str(tmp_path))

        assert helper.tokens == {}


class TestTestTokens:
    def test_save_and_get(self, helper):
        with patch.object(helper, "_save_tokens"):
            token = helper.save_test_token("demo", "access123")
        assert token.access_token == "access123"
        assert helper.get_test_token("demo") is token

    def test_get_nonexistent(self, helper):
        assert helper.get_test_token("missing") is None


class TestListTokens:
    def test_list(self, helper):
        with patch.object(helper, "_save_tokens"):
            helper.save_test_token("a", "tok", expires_hours=24)
        tokens = helper.list_tokens()
        assert len(tokens) == 1
        assert tokens[0]["is_valid"] is True


class TestClearExpired:
    def test_clears_expired(self, helper):
        helper.tokens["expired_key"] = OAuthToken(
            "at",
            None,
            "Bearer",
            (datetime.now() - timedelta(hours=1)).isoformat(),
            "",
            "custom",
        )
        with patch.object(helper, "_save_tokens"):
            count = helper.clear_expired()
        assert count == 1
        assert "expired_key" not in helper.tokens

    def test_keeps_valid(self, helper):
        helper.tokens["valid_key"] = OAuthToken(
            "at",
            None,
            "Bearer",
            (datetime.now() + timedelta(hours=24)).isoformat(),
            "",
            "custom",
        )
        with patch.object(helper, "_save_tokens"):
            count = helper.clear_expired()
        assert count == 0
        assert "valid_key" in helper.tokens


class TestGetCachedToken:
    def test_returns_valid(self, helper):
        token = OAuthToken(
            "at",
            None,
            "Bearer",
            (datetime.now() + timedelta(hours=24)).isoformat(),
            "",
            "google",
        )
        key = helper._get_cache_key("google", "cid")
        helper.tokens[key] = token
        assert helper.get_cached_token(OAuthProvider.GOOGLE, "cid") is token

    def test_returns_none_and_removes_expired(self, helper):
        token = OAuthToken(
            "at",
            None,
            "Bearer",
            (datetime.now() - timedelta(hours=1)).isoformat(),
            "",
            "google",
        )
        key = helper._get_cache_key("google", "cid")
        helper.tokens[key] = token

        result = helper.get_cached_token(OAuthProvider.GOOGLE, "cid")

        assert result is None
        assert key not in helper.tokens


class TestOAuthFlow:
    @pytest.mark.asyncio
    async def test_exchange_code_caches_token(self, helper):
        config = helper.configure_provider(OAuthProvider.GOOGLE, "cid", "sec")
        fake_session = FakeSession(
            FakeResponse(
                200,
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "token_type": "Bearer",
                    "expires_in": 1800,
                    "scope": "openid profile",
                },
            )
        )

        with patch("services.oauth_helper.aiohttp.ClientSession", return_value=fake_session):
            with patch.object(helper, "_save_tokens") as save_mock:
                token = await helper.exchange_code(config, "auth-code")

        cache_key = helper._get_cache_key(config.provider.value, config.client_id)
        assert token.access_token == "access-token"
        assert helper.tokens[cache_key] is token
        assert fake_session.calls[0]["headers"] == {"Accept": "application/json"}
        save_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_exchange_code_raises_on_error_response(self, helper):
        config = helper.configure_provider(OAuthProvider.GITHUB, "cid", "sec")
        fake_session = FakeSession(FakeResponse(400, {"error": "bad_verification_code"}))

        with patch("services.oauth_helper.aiohttp.ClientSession", return_value=fake_session):
            with pytest.raises(RuntimeError, match="bad_verification_code"):
                await helper.exchange_code(config, "bad-code")

    @pytest.mark.asyncio
    async def test_refresh_token_uses_existing_refresh_token_as_fallback(self, helper):
        config = helper.configure_provider(OAuthProvider.GOOGLE, "cid", "sec")
        fake_session = FakeSession(
            FakeResponse(
                200,
                {
                    "access_token": "new-access-token",
                    "token_type": "Bearer",
                    "expires_in": 1800,
                },
            )
        )

        with patch("services.oauth_helper.aiohttp.ClientSession", return_value=fake_session):
            with patch.object(helper, "_save_tokens") as save_mock:
                token = await helper.refresh_token(config, "existing-refresh-token")

        assert token.refresh_token == "existing-refresh-token"
        assert token.scope == config.scope
        save_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_valid_token_refreshes_near_expiry_token(self, helper):
        config = helper.configure_provider(OAuthProvider.GOOGLE, "cid", "sec")
        cache_key = helper._get_cache_key(config.provider.value, config.client_id)
        helper.tokens[cache_key] = OAuthToken(
            access_token="old-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            expires_at=(datetime.now() + timedelta(minutes=4)).isoformat(),
            scope=config.scope,
            provider=config.provider.value,
        )
        refreshed_token = OAuthToken(
            access_token="new-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            expires_at=(datetime.now() + timedelta(hours=1)).isoformat(),
            scope=config.scope,
            provider=config.provider.value,
        )

        with patch.object(helper, "refresh_token", new=AsyncMock(return_value=refreshed_token)) as refresh_mock:
            token = await helper.get_valid_token(config)

        assert token is refreshed_token
        refresh_mock.assert_awaited_once_with(config, "refresh-token")

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_when_refresh_fails(self, helper):
        config = helper.configure_provider(OAuthProvider.GOOGLE, "cid", "sec")
        cache_key = helper._get_cache_key(config.provider.value, config.client_id)
        helper.tokens[cache_key] = OAuthToken(
            access_token="old-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            expires_at=(datetime.now() + timedelta(minutes=1)).isoformat(),
            scope=config.scope,
            provider=config.provider.value,
        )

        with patch.object(helper, "refresh_token", new=AsyncMock(side_effect=RuntimeError("boom"))):
            token = await helper.get_valid_token(config)

        assert token is None


class TestSingleton:
    def test_same_instance(self):
        import services.oauth_helper as mod

        mod._oauth_helper = None
        with patch("os.makedirs"), patch("os.path.exists", return_value=False):
            s1 = get_oauth_helper()
            s2 = get_oauth_helper()
        assert s1 is s2
        mod._oauth_helper = None
