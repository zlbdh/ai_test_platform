# -*- coding: utf-8 -*-
"""
Action Handlers — 从 ExecutorAgent._execute_action 中拆分的动作处理函数

每个 handler 接收 (page, target, value, dom_indexer, session, logger) 并返回结果字符串。
ExecutorAgent 通过 ACTION_REGISTRY 查表调用。
"""
import time
import datetime
import logging
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 类型别名 ─────────────────────────────────────────────────────────────────
ActionResult = Optional[Any]


def _looks_like_login_submit_target(target: str) -> bool:
    lowered = (target or '').lower()
    keywords = ('登录', 'login', 'submit', '提交', '确认', 'sign in')
    return any(keyword in lowered for keyword in keywords)


def _looks_like_captcha_target(target: str) -> bool:
    lowered = (target or '').lower()
    keywords = ('验证码', 'captcha', 'code', '校验码')
    return any(keyword in lowered for keyword in keywords)


def _looks_like_agreement_target(target: str) -> bool:
    normalized = (target or '').replace(' ', '').replace('《', '').replace('》', '').lower()
    keywords = ('用户协议', '隐私政策', '我已阅读并同意', '同意协议', 'agreement', 'terms')
    return any(keyword in normalized for keyword in keywords)


def _click_agreement_checkbox_if_present(page, target: str) -> bool:
    """优先点击协议复选框，避免误点《用户协议》链接导致登录死循环。"""
    if not _looks_like_agreement_target(target):
        return False

    candidates = [
        page.locator("label.el-checkbox").filter(has_text="用户协议"),
        page.locator(".el-checkbox").filter(has_text="用户协议"),
        page.locator("label").filter(has_text="用户协议"),
        page.locator("label.el-checkbox").filter(has_text="同意"),
    ]

    for group in candidates:
        try:
            count = min(group.count(), 5)
        except Exception:
            continue

        for idx in range(count):
            label = group.nth(idx)
            try:
                if not label.is_visible():
                    continue
            except Exception:
                continue

            try:
                checkbox = label.locator("input[type='checkbox']").first
            except Exception:
                checkbox = None

            if checkbox is not None:
                try:
                    if checkbox.is_checked(timeout=1000):
                        return True
                except Exception:
                    pass

            for click_target in (
                label.locator(".el-checkbox__input").first,
                label,
                checkbox,
            ):
                if click_target is None:
                    continue
                try:
                    click_target.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                try:
                    click_target.click(timeout=5000, force=True)
                except Exception:
                    continue

                if checkbox is None:
                    return True

                try:
                    if checkbox.is_checked(timeout=1000):
                        return True
                except Exception:
                    return True

            if checkbox is not None:
                try:
                    checkbox.check(timeout=5000, force=True)
                    if checkbox.is_checked(timeout=1000):
                        return True
                except Exception:
                    continue

    return False


def _dismiss_blocking_dialog_if_present(page) -> Optional[str]:
    try:
        dialogs = page.locator("[role='dialog'], .el-overlay-message-box, .el-message-box")
        count = min(dialogs.count(), 3)
    except Exception:
        return None

    for idx in range(count):
        dialog = dialogs.nth(idx)
        try:
            if not dialog.is_visible():
                continue
        except Exception:
            continue

        try:
            text = (dialog.inner_text(timeout=1000) or "").strip()
        except Exception:
            text = ""

        if "登录状态已过期" not in text and "系统提示" not in text:
            continue

        for selector in (
            ".el-message-box__headerbtn",
            ".el-message-box__btns .el-button--default",
            ".el-message-box__btns .el-button--primary",
        ):
            try:
                button = dialog.locator(selector).first
                if button.is_visible():
                    button.click(timeout=5000)
                    return text or selector
            except Exception:
                continue

        for label in ("关闭此对话框", "取消", "确定", "继续", "关闭", "重新登录"):
            try:
                button = page.get_by_label(label).first
                if button.is_visible():
                    button.click(timeout=5000)
                    return text or label
            except Exception:
                continue

    return None


# ── 导航动作 ─────────────────────────────────────────────────────────────────
def handle_goto(page, target: str, value: str, dom_indexer, session, **_) -> ActionResult:
    """导航到指定 URL"""
    url = target
    if not url.startswith('http'):
        url = 'https://' + url
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_load_state('networkidle', timeout=15000)

    # DomIndexer: 导航后扫描元素
    try:
        dom_indexer.scan(page)
        count = len(dom_indexer._index_map)
        logger.debug(f"[ActionHandler] DomIndexer: Scanned {count} interactive elements.")
    except Exception as scan_err:
        logger.warning(f"[ActionHandler] DomIndexer scan failed: {scan_err}")

    return f"Navigated to {url}"


# ── 点击动作 ─────────────────────────────────────────────────────────────────
def handle_click(page, target: str, value: str, dom_indexer, session, **_) -> ActionResult:
    """4层容错点击，并在登录前尝试自动填写验证码。"""
    from core.browser import sync_analyze_with_som

    dismissed_dialog = _dismiss_blocking_dialog_if_present(page)
    if dismissed_dialog:
        logger.info(f"[ActionHandler] 点击前已处理阻塞对话框: {dismissed_dialog[:80]}")
        try:
            dom_indexer.scan(page)
        except Exception:
            pass

    if _looks_like_login_submit_target(target):
        try:
            from core.auth_interceptor import fill_captcha_if_present
            captcha_code = fill_captcha_if_present(page)
            if captcha_code:
                logger.info(f"[ActionHandler] 登录前已自动填写验证码: {captcha_code}")
                try:
                    dom_indexer.scan(page)
                except Exception:
                    pass
        except Exception as captcha_err:
            logger.warning(f"[ActionHandler] 登录前验证码自动处理失败: {captcha_err}")

    if _click_agreement_checkbox_if_present(page, target):
        logger.info(f"[ActionHandler] 已识别并勾选协议复选框: {target}")
        try:
            dom_indexer.scan(page)
        except Exception:
            pass
        return f"Clicked {target}"

    selector, method = dom_indexer.resolve_target(target)
    logger.debug(f"[ActionHandler] Resolved target: '{target}' → '{selector}' (via {method})")

    if method == 'index':
        el = page.locator(selector).first
        el.scroll_into_view_if_needed(timeout=5000)
        el.click(timeout=10000)
    elif method == 'selector':
        el = page.locator(selector).first
        el.scroll_into_view_if_needed(timeout=5000)
        el.click(timeout=10000)
    elif method == 'text':
        try:
            el = page.locator(selector).first
            el.scroll_into_view_if_needed(timeout=5000)
            el.click(timeout=10000)
        except Exception:
            page.get_by_role("button", name=target).or_(
                page.get_by_role("link", name=target)
            ).or_(
                page.get_by_text(target, exact=False)
            ).first.click(timeout=10000)
    else:
        try:
            page.get_by_role("button", name=target).or_(
                page.get_by_role("link", name=target)
            ).or_(
                page.get_by_text(target, exact=False)
            ).first.click(timeout=10000)
        except Exception:
            task_desc = f"click {target}"
            som_result = sync_analyze_with_som(page, task_desc)
            if som_result and 'id' in som_result:
                marker_selector = f'[data-ai-idx="{som_result["id"]}"]'
                page.locator(marker_selector).first.click(timeout=10000)
            else:
                raise Exception(f"Could not find element: {target}")

    time.sleep(0.3)

    try:
        dom_indexer.scan(page)
    except Exception:
        pass

    return f"Clicked {target}"


# ── 填充动作 ─────────────────────────────────────────────────────────────────
def handle_fill(page, target: str, value: str, dom_indexer, session, **_) -> ActionResult:
    """多层降级的表单填充（含 OTP/TOTP/CAPTCHA 自动生成）"""
    if value == "$CAPTCHA" or (_looks_like_captcha_target(target) and value in ("", "1234")):
        from core.auth_interceptor import fill_captcha_if_present
        extracted = fill_captcha_if_present(page)
        if extracted:
            logger.info(f"[ActionHandler] CAPTCHA 自动识别: {extracted}")
            return f"Filled '{target}' with '{extracted}'"
        if value == "$CAPTCHA":
            logger.warning("[ActionHandler] CAPTCHA 自动识别失败，回退为空值")
            value = ""

    # OTP/TOTP 自动填充：当 value 以 $TOTP{ 开头时，自动生成验证码
    if value and value.startswith("$TOTP{") and value.endswith("}"):
        totp_secret = value[6:-1]
        from core.auth_interceptor import totp_generator
        generated = totp_generator.generate(totp_secret)
        if generated:
            value = generated
            logger.info(f"[ActionHandler] TOTP 自动生成: {value}")

    # OTP 自动提取：当 value 为 $OTP 时，从页面提取验证码
    if value == "$OTP":
        from core.auth_interceptor import otp_interceptor
        extracted = otp_interceptor.extract_from_page(page)
        if extracted:
            value = extracted
            logger.info(f"[ActionHandler] OTP 自动提取: {value}")
        else:
            logger.warning("[ActionHandler] OTP 自动提取失败，使用空值")
            value = ""

    selector, method = dom_indexer.resolve_target(target)
    logger.debug(f"[ActionHandler] Resolved fill target: '{target}' → '{selector}' (via {method})")

    el = None
    if method in ('index', 'text', 'selector'):
        try:
            el = page.locator(selector).first
            el.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            el = None

    if el is None:
        el = page.get_by_role("textbox", name=target).or_(
            page.get_by_placeholder(target)
        ).or_(
            page.locator(f'input[name*="{target}" i], textarea[name*="{target}" i]')
        ).first

    try:
        el.fill(value, timeout=5000)
    except Exception:
        logger.warning("[ActionHandler] fill() failed, falling back to click+type")
        try:
            el.click(timeout=5000)
            page.keyboard.press('Control+a')
            page.keyboard.press('Delete')
            time.sleep(0.1)
            page.keyboard.type(value, delay=30)
        except Exception as fill_err:
            raise Exception(f"Fill failed (all methods): {fill_err}")

    time.sleep(0.2)
    return f"Filled '{target}' with '{value}'"


# ── 下拉选择 ─────────────────────────────────────────────────────────────────
def handle_select(page, target: str, value: str, dom_indexer, session, **_) -> ActionResult:
    """多层降级的下拉选择"""
    selector, method = dom_indexer.resolve_target(target)
    logger.debug(f"[ActionHandler] Resolved select target: '{target}' → '{selector}' (via {method})")

    # Tier 1-3: DomIndexer result
    if method in ('index', 'text', 'selector'):
        try:
            el = page.locator(selector).first
            el.select_option(value=value, timeout=5000)
            return f"Selected {value} in {target}"
        except Exception:
            logger.warning(f"[ActionHandler] select via {method} failed, trying fallback")

    # Tier 4: Role/Label fallback
    try:
        el = page.get_by_role("combobox", name=target).or_(
            page.get_by_label(target)
        ).or_(
            page.locator(f'select[name*="{target}" i]')
        ).first
        el.select_option(value=value, timeout=5000)
        return f"Selected {value} in {target}"
    except Exception:
        # Tier 5: Try by option text
        try:
            el = page.get_by_role("combobox", name=target).or_(
                page.get_by_label(target)
            ).or_(
                page.locator(f'select[name*="{target}" i]')
            ).first
            el.select_option(label=value, timeout=5000)
            return f"Selected '{value}' (by label) in {target}"
        except Exception as e:
            raise Exception(f"Select failed for '{target}' with value '{value}': {e}")


# ── 等待 ─────────────────────────────────────────────────────────────────────
def handle_wait(page, target: str, value: str, check_signal, **_) -> ActionResult:
    """信号感知的等待"""
    try:
        sleep_time = float(target) if target else 1.0
    except (ValueError, TypeError):
        sleep_time = 1.0
    end_time = time.time() + sleep_time
    while time.time() < end_time:
        check_signal()
        time.sleep(0.1)
    return "OK"


# ── 按键 ─────────────────────────────────────────────────────────────────────
def handle_key(page, target: str, value: str, **_) -> ActionResult:
    """键盘按键（含中文别名映射）"""
    key_name = target.strip() if target else 'Enter'
    key_aliases = {
        '回车': 'Enter', '确认': 'Enter', '换行': 'Enter',
        '退格': 'Backspace', '删除': 'Delete',
        '上': 'ArrowUp', '下': 'ArrowDown', '左': 'ArrowLeft', '右': 'ArrowRight',
        '空格': 'Space', '制表符': 'Tab',
    }
    key_name = key_aliases.get(key_name, key_name)
    page.keyboard.press(key_name)
    return "OK"


# ── 断言 ─────────────────────────────────────────────────────────────────────
def handle_assert(page, target: str, value: str, **_) -> ActionResult:
    """文本匹配 + 语义验证的双层断言"""
    time.sleep(0.5)
    content = page.content()

    if target in content:
        return "Assert Passed (Text Match)"

    logger.info(f"[ActionHandler] Exact match failed, starting semantic verification: '{target}'")
    try:
        visible_text = page.evaluate("""
        () => {
            const walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT,
                { acceptNode: function(node) {
                    const p = node.parentElement;
                    if (!p) return NodeFilter.FILTER_REJECT;
                    const tag = p.tagName.toLowerCase();
                    if (['script','style','noscript'].includes(tag)) return NodeFilter.FILTER_REJECT;
                    const s = window.getComputedStyle(p);
                    if (s.display === 'none' || s.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
                    if (!node.textContent.trim() || node.textContent.trim().length < 2) return NodeFilter.FILTER_REJECT;
                    return NodeFilter.FILTER_ACCEPT;
                }}
            );
            const texts = []; let total = 0;
            while (walker.nextNode() && total < 2000) {
                const t = walker.currentNode.textContent.trim();
                texts.push(t); total += t.length;
            }
            return texts.join(' | ');
        }
        """)

        from services.planner_service import planner_service
        result = planner_service.semantic_verify(
            assertion=target,
            page_context={"url": page.url, "visible_text": visible_text}
        )

        if result['passed']:
            return f"Assert Passed (Semantic: {result['reason']})"
        else:
            raise Exception(f"Assertion Failed: '{target}' — {result['reason']}")
    except ImportError:
        raise Exception(f"Assertion Failed: '{target}' not found in page content.")
    except Exception as e:
        if "Assertion Failed" in str(e):
            raise
        raise Exception(f"Assertion Failed: '{target}' — semantic verify error: {e}")


# ── 数据库操作 ────────────────────────────────────────────────────────────────
def handle_db_query(page, target: str, value: str, **_) -> ActionResult:
    from core.db_tools import execute_sql
    res = execute_sql(target)
    if res['status'] == 'error':
        raise Exception(res.get('message', 'SQL execution error'))
    return res.get('data', [])


def handle_snapshot_db(page, target: str, value: str, **_) -> ActionResult:
    from core.db_tools import snapshot_db
    res = snapshot_db(target, value)
    if res['status'] == 'error':
        raise Exception(res.get('message', 'Snapshot error'))
    return res.get('data', [])


def handle_backup_db(page, target: str, value: str, **_) -> ActionResult:
    from core.db_tools import backup_db
    res = backup_db(target)
    if res['status'] == 'error':
        raise Exception(res.get('message', 'Backup error'))
    return res.get('message', 'Backup completed')


# ── 数据提取 ─────────────────────────────────────────────────────────────────
def handle_extract(page, target: str, value: str, dom_indexer, session, **_) -> ActionResult:
    """多层降级的数据提取"""
    extracted_text = None

    # Tier 1: DomIndexer 智能定位
    try:
        selector, method = dom_indexer.resolve_target(target)
        logger.debug(f"[ActionHandler] Resolved extract target: '{target}' → '{selector}' (via {method})")
        el = page.locator(selector).first
        extracted_text = el.text_content(timeout=3000)
    except Exception:
        pass

    # Tier 2: 直接 CSS 选择器
    if extracted_text is None:
        try:
            extracted_text = page.locator(target).first.text_content(timeout=3000)
        except Exception:
            pass

    # Tier 3: Role/Text fallback
    if extracted_text is None:
        try:
            el = page.get_by_text(target, exact=False).first
            extracted_text = el.text_content(timeout=3000)
        except Exception as e:
            raise Exception(f"Failed to extract from '{target}': {e}")

    if extracted_text is not None:
        extracted_text = extracted_text.strip()
        session.set_context(value, extracted_text)
        logger.info(f"[ActionHandler] Extracted '{extracted_text}' -> ${{ {value} }}")
        return extracted_text
    else:
        raise Exception(f"Failed to extract from '{target}': element not found")


# ── 变量设置 ─────────────────────────────────────────────────────────────────
def handle_set_var(page, target: str, value: str, session, **_) -> ActionResult:
    session.set_context(target, value)
    logger.info(f"[ActionHandler] Set Variable: ${{ {target} }} = '{value}'")
    return value


# ── 视觉检查 ─────────────────────────────────────────────────────────────────
def handle_visual_check(page, target: str, value: str, bus, **_) -> ActionResult:
    from core.visual_tools import assert_visual_snapshot
    res = assert_visual_snapshot(page, target)

    bus.publish_log_sync({
        "type": "visual_result",
        "step": f"Visual Check: {target}",
        "content": res['message'],
        "status": "pass" if res['status'] == 'success' else "fail",
        "snapshots": res.get('details', {})
    })

    if res['status'] == 'error':
        bus.publish_log_sync({"type": "error", "content": f"Visual Mismatch: {res['message']}"})
        raise Exception(f"Visual Check Failed: {res['message']}")

    return "Visual Check Passed"


# ── Mock 路由 ────────────────────────────────────────────────────────────────
def handle_mock(page, target: str, value: str, **_) -> ActionResult:
    import json
    try:
        mock_data = json.loads(value) if isinstance(value, str) else value

        def handle_route(route):
            route.fulfill(status=200, body=json.dumps(mock_data), headers={'Content-Type': 'application/json'})

        page.route(target, handle_route)
        return f"Route mocked: {target}"
    except Exception as e:
        raise Exception(f"Mock failed: {e}")


# ── API 调用 ─────────────────────────────────────────────────────────────────
def handle_api_call(page, target: str, value: str, **_) -> ActionResult:
    import json
    from core.api_tools import http_request
    try:
        parts = target.split(' ', 1) if ' ' in target else [target, '']
        method = parts[0].upper()
        url = parts[1] if len(parts) > 1 else target

        body = None
        if value:
            try:
                body = json.loads(value)
            except Exception:
                body = {"data": value}

        res = http_request(method, url, json_body=body)
        return res
    except Exception as e:
        raise Exception(f"API Call failed: {e}")


# ── 滚动 ────────────────────────────────────────────────────────────────────
def handle_scroll(page, target: str, value: str, **_) -> ActionResult:
    raw_dir = (value or target or 'down').lower().strip()
    direction_map = {
        'down': 'down', '下': 'down', '向下': 'down',
        'up': 'up', '上': 'up', '向上': 'up',
        'bottom': 'bottom', '底部': 'bottom', '最下': 'bottom',
        'top': 'top', '顶部': 'top', '最上': 'top',
    }
    direction = direction_map.get(raw_dir, 'down')
    scroll_actions = {
        'down': "window.scrollBy(0, 500)",
        'up': "window.scrollBy(0, -500)",
        'bottom': "window.scrollTo(0, document.body.scrollHeight)",
        'top': "window.scrollTo(0, 0)",
    }
    page.evaluate(scroll_actions[direction])
    time.sleep(0.3)
    return f"Scrolled {direction}"


# ── 截图 ────────────────────────────────────────────────────────────────────
def handle_screenshot(page, target: str, value: str, bus, **_) -> ActionResult:
    import os
    screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'artifacts', 'screenshots')
    os.makedirs(screenshot_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"screenshot_{timestamp}.png"
    filepath = os.path.join(screenshot_dir, filename)
    page.screenshot(path=filepath, full_page=True, timeout=10000)
    logger.info(f"[ActionHandler] Screenshot saved: {filepath}")
    bus.publish_log_sync({"type": "screenshot", "content": f"📸 截图已保存: {filename}", "path": filepath})
    return f"Screenshot saved: {filename}"


# ── 悬停 ────────────────────────────────────────────────────────────────────
def handle_hover(page, target: str, value: str, dom_indexer, **_) -> ActionResult:
    selector, method = dom_indexer.resolve_target(target)
    logger.debug(f"[ActionHandler] Resolved hover target: '{target}' → '{selector}' (via {method})")

    def _role_hover():
        page.get_by_role("button", name=target).or_(
            page.get_by_role("link", name=target)
        ).or_(
            page.get_by_role("menuitem", name=target)
        ).or_(
            page.get_by_text(target, exact=False)
        ).first.hover(timeout=10000)

    if method in ('index', 'text', 'selector'):
        try:
            el = page.locator(selector).first
            el.scroll_into_view_if_needed(timeout=5000)
            el.hover(timeout=5000)
        except Exception:
            _role_hover()
    else:
        _role_hover()

    time.sleep(0.3)
    return f"Hovered {target}"


# ── Done ────────────────────────────────────────────────────────────────────
def handle_done(page, target: str, value: str, **_) -> ActionResult:
    return "Done"


# ══════════════════════════════════════════════════════════════════════════════
# Action Registry — ExecutorAgent 通过此注册表查表调用
# ══════════════════════════════════════════════════════════════════════════════
ACTION_REGISTRY: Dict[str, Callable] = {
    'goto': handle_goto,
    'click': handle_click,
    'fill': handle_fill,
    'select': handle_select,
    'wait': handle_wait,
    'key': handle_key,
    'assert': handle_assert,
    'db_query': handle_db_query,
    'snapshot_db': handle_snapshot_db,
    'backup_db': handle_backup_db,
    'extract': handle_extract,
    'set_var': handle_set_var,
    'visual_check': handle_visual_check,
    'mock': handle_mock,
    'api_call': handle_api_call,
    'scroll': handle_scroll,
    'screenshot': handle_screenshot,
    'hover': handle_hover,
    'done': handle_done,
}







