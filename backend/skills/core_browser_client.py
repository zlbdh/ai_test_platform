# -*- coding: utf-8 -*-
"""
Core Browser Client (Refactored for Native Playwright)
Directly interacts with SharedBrowser singleton to execute browser actions.
Replaces the legacy agent-browser CLI wrapper.
"""
import logging
from typing import Dict, Any, List
from core.browser import SharedBrowser

logger = logging.getLogger(__name__)


def _normalize_session_id(session_id: str = "default") -> str:
    return "default_session" if not session_id or session_id == "default" else session_id


async def _run_on_browser(browser: SharedBrowser, session_id: str, callback, timeout: float = 10.0):
    return await browser.run_browser(callback, session_id=session_id, timeout=timeout)


async def execute_browser_command(action: str, args: List[str] = None, session_id: str = "default") -> Dict[str, Any]:
    """
    Executes browser commands using the SharedBrowser instance.
    Arguments are mapped from agent-browser CLI style to Playwright calls.

    Returns:
        Dict with keys: success (bool), result (Any), error (str)
    """
    args = args or []
    session_id = _normalize_session_id(session_id)
    browser = SharedBrowser()

    try:
        if action == "launch":
            page = await browser.get_page(session_id=session_id)
            if not page:
                return {"success": False, "error": f"No active browser session: {session_id}"}

            url = await _run_on_browser(browser, session_id, lambda page: page.url)
            title = await _run_on_browser(browser, session_id, lambda page: page.title())
            return {"success": True, "result": {"url": url, "title": title}}

        if action == "open" or action == "navigate":
            url = args[0] if args else "about:blank"
            logger.info(f"Navigating to {url}")
            await _run_on_browser(
                browser,
                session_id,
                lambda page: page.goto(url, wait_until="domcontentloaded"),
                timeout=30.0,
            )
            current_url = await _run_on_browser(browser, session_id, lambda page: page.url)
            title = await _run_on_browser(browser, session_id, lambda page: page.title())
            return {"success": True, "result": {"url": current_url, "title": title}}

        elif action == "click":
            selector = args[0] if args else None
            if not selector:
                return {"success": False, "error": "No selector provided"}

            await _run_on_browser(browser, session_id, lambda page: page.click(selector))
            return {"success": True, "result": "clicked"}

        elif action == "fill":
            selector = args[0] if args else None
            text = args[1] if len(args) > 1 else ""
            if not selector:
                return {"success": False, "error": "No selector provided"}

            await _run_on_browser(browser, session_id, lambda page: page.fill(selector, text))
            return {"success": True, "result": "filled"}

        elif action == "screenshot":
            import base64
            import os
            import time
            from core.config import Config

            screenshots_dir = os.path.join(
                Config.WORK_DIR if hasattr(Config, "WORK_DIR") else os.getcwd(),
                "screenshots",
            )
            os.makedirs(screenshots_dir, exist_ok=True)

            timestamp = int(time.time() * 1000)
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(screenshots_dir, filename)

            screenshot_bytes = await _run_on_browser(
                browser,
                session_id,
                lambda page: page.screenshot(path=filepath, full_page=False),
                timeout=30.0,
            )
            b64_str = base64.b64encode(screenshot_bytes).decode("utf-8")

            return {
                "success": True,
                "result": {
                    "path": filepath,
                    "base64": b64_str,
                    "data": b64_str,
                },
            }

        elif action == "snapshot":
            snapshot = await _run_on_browser(
                browser,
                session_id,
                lambda page: page.accessibility.snapshot(),
                timeout=20.0,
            )

            elements = []

            def flatten(node):
                role = node.get("role")
                name = node.get("name")

                if role and role not in ["WebArea", "generic", "presentation"]:
                    el = {
                        "tag": role,
                        "role": role,
                        "text": name,
                        "rect": {"x": 0, "y": 0, "w": 0, "h": 0},
                    }
                    if name:
                        elements.append(el)

                for child in node.get("children", []):
                    flatten(child)

            if snapshot:
                flatten(snapshot)

            if not elements:
                js_elements = await _run_on_browser(
                    browser,
                    session_id,
                    lambda page: page.evaluate(
                        """() => {
                            const els = Array.from(document.querySelectorAll('button, input, a, [role="button"]'));
                            return els.map(e => {
                                const rect = e.getBoundingClientRect();
                                return {
                                    tag: e.tagName.toLowerCase(),
                                    text: e.innerText || e.value || e.getAttribute('aria-label') || "",
                                    role: e.getAttribute('role') || e.tagName.toLowerCase(),
                                    rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height}
                                };
                            });
                        }"""
                    ),
                    timeout=20.0,
                )
                elements.extend(js_elements)

            return {"success": True, "result": {"snapshot": snapshot, "elements": elements, "refs": {}}}

        elif action == "evaluate":
            script = args[0] if args else ""
            res = await _run_on_browser(browser, session_id, lambda page: page.evaluate(script), timeout=20.0)
            return {"success": True, "result": res}

        elif action == "wait":
            selector = args[0] if args else None
            timeout = 5000
            if not selector:
                return {"success": False, "error": "No selector provided"}
            try:
                await _run_on_browser(
                    browser,
                    session_id,
                    lambda page: page.wait_for_selector(selector, timeout=timeout),
                    timeout=(timeout / 1000) + 5,
                )
                return {"success": True, "result": "found"}
            except Exception:
                return {"success": False, "error": "Timeout"}

        elif action == "back":
            await _run_on_browser(browser, session_id, lambda page: page.go_back())
            return {"success": True}

        elif action == "reload":
            await _run_on_browser(browser, session_id, lambda page: page.reload())
            return {"success": True}

        elif action == "innertext" or action == "gettext":
            selector = args[0] if args else "body"
            text = await _run_on_browser(browser, session_id, lambda page: page.inner_text(selector), timeout=20.0)
            return {"success": True, "result": text}

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        logger.error(f"Browser command failed: {action} {args} - {e}")
        return {"success": False, "error": str(e)}


def get_port_for_session(session_id: str) -> int:
    return 0
