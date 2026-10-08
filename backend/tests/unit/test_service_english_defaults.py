"""US English service defaults retain explicit locale choices."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.data_factory import create_data_factory
from services.i18n_testing import I18nTestService


def _async_context(value):
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=value)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


def test_data_factory_bridge_defaults_to_us_english_and_forwards_overrides():
    with patch("services.data_factory.get_data_factory") as factory:
        create_data_factory()
        factory.assert_called_once_with("en_US")
        factory.reset_mock()
        create_data_factory("fr_FR")
        factory.assert_called_once_with("fr_FR")


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", [None, "fr-CA", "zh-CN"])
async def test_i18n_quick_check_uses_default_or_explicit_accept_language(locale):
    response = MagicMock()
    response.text = AsyncMock(return_value='<html lang="en-US"><head><meta charset="utf-8"></head></html>')
    session = MagicMock()
    session.get.return_value = _async_context(response)
    expected = locale or "en-US"
    with patch("aiohttp.ClientSession", return_value=_async_context(session)):
        service = I18nTestService()
        result = await service.quick_check("https://example.com", **({"locale": locale} if locale else {}))
    assert result["status"] == "success"
    assert result["locale"] == expected
    assert session.get.call_args.kwargs["headers"] == {"Accept-Language": expected}
