from unittest.mock import MagicMock, patch

import pytest

from core.session_bootstrap import apply_auth_bootstrap, normalize_base_url, resolve_url


class FakeContext:
    def __init__(self):
        self.cookies = None

    def add_cookies(self, cookies):
        self.cookies = cookies


class FakePage:
    def __init__(self):
        self.context = FakeContext()
        self.goto_calls = []
        self.evaluate_calls = []

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append(url)

    def wait_for_load_state(self, state, timeout=None):
        return None

    def evaluate(self, script, data):
        self.evaluate_calls.append(data)
        return list(data.keys())


def test_normalize_base_url_returns_origin_only():
    assert normalize_base_url('http://127.0.0.1:81/qyLogin') == 'http://127.0.0.1:81'


def test_resolve_url_handles_relative_and_absolute():
    assert resolve_url('http://127.0.0.1:81', '/auth/login1') == 'http://127.0.0.1:81/auth/login1'
    assert resolve_url('http://127.0.0.1:81', 'http://127.0.0.1:8080/code') == 'http://127.0.0.1:8080/code'


@patch('core.session_bootstrap.http_request')
def test_apply_auth_bootstrap_logs_in_switches_station_and_injects_storage(mock_http):
    mock_http.side_effect = [
        {'status_code': 200, 'content': {'code': 200, 'data': {'access_token': 'token-1'}}},
        {'status_code': 200, 'content': {'code': 200, 'msg': 'ok'}},
    ]
    page = FakePage()

    result = apply_auth_bootstrap(page, {
        'base_url': 'http://127.0.0.1:81/qyLogin',
        'username': 'example-org',
        'password': '123456',
        'station_id': '528',
        'city': '北京市',
        'target_path': '/unifiedGoodService/uniProductService',
    })

    assert result['target_url'].endswith('/unifiedGoodService/uniProductService')
    assert page.context.cookies[0]['name'] == 'Admin-Token'
    assert page.context.cookies[0]['value'] == 'token-1'
    assert 'path' not in page.context.cookies[0]
    assert page.goto_calls[-1] == 'http://127.0.0.1:81/unifiedGoodService/uniProductService'
    assert page.evaluate_calls[-1]['currentStation'] == '528'
    assert page.evaluate_calls[-1]['currentCity'] == '北京市'


@patch('core.session_bootstrap.http_request')
def test_apply_auth_bootstrap_uses_existing_token_without_login(mock_http):
    page = FakePage()

    result = apply_auth_bootstrap(page, {
        'base_url': 'http://127.0.0.1:81',
        'access_token': 'ready-token',
        'target_path': '/unifiedGoodService/uniProductService',
        'local_storage': {'currentCity': '北京市'},
    })

    assert result['token_cookie_name'] == 'Admin-Token'
    assert page.context.cookies[0]['value'] == 'ready-token'
    mock_http.assert_not_called()


@patch('core.session_bootstrap.http_request', return_value={'status_code': 200, 'content': {'code': 200, 'data': {}}})
def test_apply_auth_bootstrap_raises_when_token_missing(mock_http):
    page = FakePage()

    with pytest.raises(RuntimeError, match='access_token'):
        apply_auth_bootstrap(page, {
            'base_url': 'http://127.0.0.1:81',
            'username': 'example-org',
            'password': '123456',
        })
