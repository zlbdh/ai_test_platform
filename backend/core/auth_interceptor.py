# -*- coding: utf-8 -*-
"""
Auth Interceptor — OTP/TOTP/CAPTCHA 认证拦截器

提供三种认证辅助能力：
1. TOTPGenerator: 基于 TOTP 秘钥自动生成 6 位验证码
2. OTPInterceptor: 拦截 API 响应提取短信/邮件验证码
3. CaptchaWaiter: CAPTCHA 检测后暂停等待人工介入（WebSocket 通知）

使用方式:
    from core.auth_interceptor import totp_generator, otp_interceptor, captcha_waiter

    # TOTP 自动生成
    code = totp_generator.generate("JBSWY3DPEHPK3PXP")

    # OTP 拦截（从页面请求中提取验证码）
    code = otp_interceptor.extract_from_page(page, pattern=r'\d{4,6}')

    # CAPTCHA 等待（阻塞直到人工处理完成）
    captcha_waiter.wait_for_human(bus, timeout=120)
"""

import base64
import json
import logging
import re
import time
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

CAPTCHA_INPUT_SELECTORS = [
    "input[placeholder*='验证码']",
    "input[aria-label*='验证码']",
    "input[name*='captcha' i]",
    "input[name*='code' i]",
    "input[id*='captcha' i]",
    "input[id*='code' i]",
    "input[placeholder*='captcha' i]",
]

CAPTCHA_IMAGE_SELECTORS = [
    "img[alt*='验证码']",
    "img[alt*='captcha' i]",
    "img[src*='captcha' i]",
    "img[src*='code' i]",
    "img[class*='captcha' i]",
    ".captcha img",
    ".code img",
    "canvas",
    "img[src^='data:image']",
]


# ── TOTP 自动生成器 ──────────────────────────────────────────────────────────

class TOTPGenerator:
    """
    基于 TOTP 秘钥自动生成 6 位验证码。
    底层使用 pyotp 库（可选依赖）。
    """

    def generate(self, secret: str, digits: int = 6, interval: int = 30) -> Optional[str]:
        """
        生成当前时刻的 TOTP 验证码。

        Args:
            secret: Base32 编码的 TOTP 秘钥
            digits: 验证码位数（默认 6）
            interval: 时间窗口秒数（默认 30）

        Returns:
            验证码字符串，若 pyotp 未安装则返回 None
        """
        try:
            import pyotp
            totp = pyotp.TOTP(secret, digits=digits, interval=interval)
            code = totp.now()
            logger.info(f"[TOTPGenerator] 生成验证码: {code} (剩余 {totp.interval - int(time.time()) % totp.interval}s)")
            return code
        except ImportError:
            logger.warning("[TOTPGenerator] pyotp 未安装，无法生成 TOTP。请执行: pip install pyotp")
            return None
        except Exception as e:
            logger.error(f"[TOTPGenerator] 生成失败: {e}")
            return None

    def verify(self, secret: str, code: str) -> bool:
        """验证 TOTP 是否正确"""
        try:
            import pyotp
            return pyotp.TOTP(secret).verify(code)
        except ImportError:
            return False


# ── OTP 拦截器 ───────────────────────────────────────────────────────────────

class OTPInterceptor:
    """
    从页面网络请求/SMS API 响应中自动提取验证码。

    支持策略：
    1. 页面 DOM 扫描（短信验证码输入框附近的提示文本）
    2. 网络请求拦截（监听验证码下发 API 的响应）
    3. 正则表达式提取（从可见文本中匹配数字验证码）
    """

    SMS_API_PATTERNS = [
        r'/sms/send', r'/sms/code', r'/verify/code', r'/captcha/sms',
        r'/auth/otp', r'/code/send', r'/message/send',
    ]

    CODE_REGEX = re.compile(r'(?:验证码|code|otp|captcha)[^\d]*(\d{4,8})', re.IGNORECASE)
    PURE_CODE_REGEX = re.compile(r'\b(\d{4,6})\b')

    def extract_from_page(self, page, pattern: Optional[str] = None) -> Optional[str]:
        """从页面可见文本中提取验证码。"""
        try:
            visible_text = page.evaluate("""
            () => {
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT,
                    { acceptNode: (node) => {
                        const p = node.parentElement;
                        if (!p) return NodeFilter.FILTER_REJECT;
                        const s = window.getComputedStyle(p);
                        if (s.display === 'none' || s.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
                        if (!node.textContent.trim()) return NodeFilter.FILTER_REJECT;
                        return NodeFilter.FILTER_ACCEPT;
                    }}
                );
                const texts = [];
                while (walker.nextNode()) {
                    texts.push(walker.currentNode.textContent.trim());
                }
                return texts.join(' ');
            }
            """)

            regex = re.compile(pattern) if pattern else self.CODE_REGEX
            match = regex.search(visible_text)
            if match:
                code = match.group(1)
                logger.info(f"[OTPInterceptor] 从页面文本提取到验证码: {code}")
                return code

            logger.debug("[OTPInterceptor] 页面内未找到验证码")
            return None
        except Exception as e:
            logger.error(f"[OTPInterceptor] 提取失败: {e}")
            return None

    def setup_network_intercept(self, page, callback=None):
        """设置网络拦截器，监听验证码 API 响应自动提取。"""
        captured_codes = []

        def on_response(response):
            url = response.url.lower()
            if any(re.search(p, url) for p in self.SMS_API_PATTERNS):
                try:
                    body = response.text()
                    match = self.PURE_CODE_REGEX.search(body)
                    if match:
                        code = match.group(1)
                        captured_codes.append(code)
                        logger.info(f"[OTPInterceptor] 网络拦截到验证码: {code} (from {url})")
                        if callback:
                            callback(code)
                except Exception:
                    pass

        page.on("response", on_response)
        return captured_codes


def _sanitize_captcha_code(text: str, min_len: int = 3, max_len: int = 8) -> Optional[str]:
    if not text:
        return None

    raw = text.strip()
    if not raw:
        return None

    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            raw = str(payload.get("code", "")).strip()
    except Exception:
        match = re.search(r'"code"\s*:\s*"([^"]+)"', raw, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()

    cleaned = re.sub(r'[^A-Za-z0-9]', '', raw).upper()
    if min_len <= len(cleaned) <= max_len:
        return cleaned

    matches = re.findall(rf'[A-Za-z0-9]{{{min_len},{max_len}}}', raw)
    if matches:
        return max(matches, key=len).upper()
    return None


def _find_first_visible_locator(page, selectors):
    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 5)
            for idx in range(count):
                candidate = locator.nth(idx)
                try:
                    if candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        except Exception:
            continue
    return None


def find_captcha_input(page):
    return _find_first_visible_locator(page, CAPTCHA_INPUT_SELECTORS)


def _image_to_png_bytes(image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _build_captcha_variants(image_bytes: bytes):
    try:
        from PIL import Image, ImageFilter, ImageOps

        image = Image.open(BytesIO(image_bytes)).convert("L")
        enlarged = image.resize((max(image.width * 3, 60), max(image.height * 3, 30)))
        autocontrast = ImageOps.autocontrast(enlarged)
        sharpened = autocontrast.filter(ImageFilter.SHARPEN)
        threshold = sharpened.point(lambda p: 255 if p > 160 else 0, mode="1").convert("L")
        return [
            _image_to_png_bytes(autocontrast),
            _image_to_png_bytes(sharpened),
            _image_to_png_bytes(threshold),
        ]
    except Exception as exc:
        logger.debug(f"[CaptchaOCR] 图像预处理失败，退回原图: {exc}")
        return [image_bytes]


def _solve_captcha_with_vision(image_bytes: bytes) -> Optional[str]:
    try:
        from langchain_core.messages import HumanMessage
        from core.llm_manager import get_vision_llm

        vision_llm = get_vision_llm()
        if not vision_llm:
            return None

        payload = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "你是验证码 OCR。请识别图片中的验证码，只返回 JSON，格式为 "
            '{"code":"验证码"}。'
            "不要解释，不要输出多余文字；如果看不清则返回 "
            '{"code":""}。'
        )
        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{payload}"}},
        ])
        response = vision_llm.invoke([message])
        content = response.content if hasattr(response, "content") else str(response)
        return _sanitize_captcha_code(content)
    except Exception as exc:
        logger.warning(f"[CaptchaOCR] Vision OCR 调用失败: {exc}")
        return None


def solve_captcha_from_page(page) -> Optional[str]:
    locator = _find_first_visible_locator(page, CAPTCHA_IMAGE_SELECTORS)
    if locator is None:
        logger.info("[CaptchaOCR] 页面中未发现可见验证码图片")
        return None

    try:
        raw = locator.screenshot(type="png", timeout=5000)
    except Exception as exc:
        logger.warning(f"[CaptchaOCR] 验证码截图失败: {exc}")
        return None

    for variant in _build_captcha_variants(raw):
        code = _solve_captcha_with_vision(variant)
        if code:
            logger.info(f"[CaptchaOCR] 识别成功: {code}")
            return code

    logger.warning("[CaptchaOCR] 验证码识别失败")
    return None


def fill_captcha_if_present(page) -> Optional[str]:
    locator = find_captcha_input(page)
    if locator is None:
        return None

    try:
        current = (locator.input_value(timeout=1000) or "").strip()
        if current:
            return current
    except Exception:
        pass

    code = solve_captcha_from_page(page)
    if not code:
        return None

    try:
        locator.fill(code, timeout=5000)
        return code
    except Exception:
        try:
            locator.click(timeout=5000)
            page.keyboard.press("Control+a")
            page.keyboard.press("Delete")
            page.keyboard.type(code, delay=30)
            return code
        except Exception as exc:
            logger.warning(f"[CaptchaOCR] 验证码自动填写失败: {exc}")
            return None


# ── CAPTCHA 等待器 ───────────────────────────────────────────────────────────

class CaptchaWaiter:
    """CAPTCHA 检测后暂停等待人工介入。"""

    def wait_for_human(
        self,
        bus,
        session,
        timeout: int = 120,
        poll_interval: float = 2.0,
    ) -> bool:
        """发送 CAPTCHA 通知并等待人工处理。"""
        bus.publish_log_sync({
            "type": "captcha_intervention",
            "event": "captcha_detected",
            "content": "🔐 检测到验证码/CAPTCHA，请手动处理后点击「继续执行」",
            "timeout": timeout,
            "status": "waiting",
        })

        logger.warning(f"[CaptchaWaiter] ⏸️ CAPTCHA 检测到，等待人工介入（超时 {timeout}s）...")

        original_signal = session.get_signal()
        session.set_signal("PAUSED")

        start = time.time()
        while time.time() - start < timeout:
            signal = session.get_signal()
            if signal == "RUNNING":
                elapsed = time.time() - start
                logger.info(f"[CaptchaWaiter] ✅ 人工已处理 CAPTCHA（等待 {elapsed:.1f}s）")
                bus.publish_log_sync({
                    "type": "captcha_intervention",
                    "event": "captcha_resolved",
                    "content": f"✅ CAPTCHA 已处理，继续执行（等待 {elapsed:.1f}s）",
                    "status": "resolved",
                })
                return True

            if signal == "STOPPED":
                logger.info("[CaptchaWaiter] 用户中止执行")
                return False

            time.sleep(poll_interval)

        logger.warning(f"[CaptchaWaiter] ⏰ CAPTCHA 等待超时 ({timeout}s)，恢复执行")
        session.set_signal(original_signal if original_signal != "PAUSED" else "RUNNING")
        bus.publish_log_sync({
            "type": "captcha_intervention",
            "event": "captcha_timeout",
            "content": f"⏰ CAPTCHA 等待超时 ({timeout}s)，自动恢复执行",
            "status": "timeout",
        })
        return False


# ── 单例 ─────────────────────────────────────────────────────────────────────

totp_generator = TOTPGenerator()
otp_interceptor = OTPInterceptor()
captcha_waiter = CaptchaWaiter()
