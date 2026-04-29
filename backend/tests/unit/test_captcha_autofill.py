from unittest.mock import MagicMock, patch

from core import auth_interceptor
from agents.action_handlers import handle_click, handle_fill


def test_sanitize_captcha_code_from_json_payload():
    assert auth_interceptor._sanitize_captcha_code('{"code":" aB-12 "}') == 'AB12'



def test_fill_captcha_if_present_prefers_existing_value():
    locator = MagicMock()
    locator.input_value.return_value = 'X9K2'

    with patch.object(auth_interceptor, 'find_captcha_input', return_value=locator), \
         patch.object(auth_interceptor, 'solve_captcha_from_page') as mock_solver:
        result = auth_interceptor.fill_captcha_if_present(MagicMock())

    assert result == 'X9K2'
    mock_solver.assert_not_called()
    locator.fill.assert_not_called()



def test_fill_captcha_if_present_uses_solver_for_blank_field():
    page = MagicMock()
    locator = MagicMock()
    locator.input_value.return_value = ''

    with patch.object(auth_interceptor, 'find_captcha_input', return_value=locator), \
         patch.object(auth_interceptor, 'solve_captcha_from_page', return_value='ABCD'):
        result = auth_interceptor.fill_captcha_if_present(page)

    assert result == 'ABCD'
    locator.fill.assert_called_once_with('ABCD', timeout=5000)



def test_handle_fill_supports_captcha_macro():
    page = MagicMock()
    dom_indexer = MagicMock()

    with patch('core.auth_interceptor.fill_captcha_if_present', return_value='A1B2') as mock_fill:
        result = handle_fill(page, '验证码输入框', '$CAPTCHA', dom_indexer, MagicMock())

    assert result == "Filled '验证码输入框' with 'A1B2'"
    mock_fill.assert_called_once_with(page)
    dom_indexer.resolve_target.assert_not_called()



def test_handle_click_autofills_captcha_before_login():
    page = MagicMock()
    element = MagicMock()
    locator = MagicMock()
    locator.first = element
    page.locator.return_value = locator

    dom_indexer = MagicMock()
    dom_indexer.resolve_target.return_value = ('#login', 'selector')

    with patch('core.auth_interceptor.fill_captcha_if_present', return_value='A1B2') as mock_fill:
        result = handle_click(page, '登录按钮', '', dom_indexer, MagicMock())

    assert result == 'Clicked 登录按钮'
    mock_fill.assert_called_once_with(page)
    dom_indexer.scan.assert_called()
    element.click.assert_called_once_with(timeout=10000)


def test_handle_click_dismisses_blocking_dialog_before_login():
    page = MagicMock()
    element = MagicMock()
    locator = MagicMock()
    locator.first = element
    page.locator.return_value = locator

    dom_indexer = MagicMock()
    dom_indexer.resolve_target.return_value = ('#login', 'selector')

    with patch('agents.action_handlers._dismiss_blocking_dialog_if_present', return_value='登录状态已过期'), \
         patch('core.auth_interceptor.fill_captcha_if_present', return_value='A1B2') as mock_fill:
        result = handle_click(page, '登录按钮', '', dom_indexer, MagicMock())

    assert result == 'Clicked 登录按钮'
    mock_fill.assert_called_once_with(page)
    assert dom_indexer.scan.call_count >= 1
    element.click.assert_called_once_with(timeout=10000)
