# -*- coding: utf-8 -*-
"""
Auth Interceptor — OTP/TOTP/CAPTCHA authentication interceptor

Provides three authentication support capabilities:
1. TOTPGenerator: Generate six-digit verification codes from a TOTP secret
2. OTPInterceptor: Extract SMS/email verification codes from API responses
3. CaptchaWaiter: Pause for human intervention after CAPTCHA detection, with WebSocket notification

Usage:
    from core.auth_interceptor import totp_generator, otp_interceptor, captcha_waiter

    # Automatic TOTP generation
    code = totp_generator.generate("JBSWY3DPEHPK3PXP")

    # OTP interception (extract verification codes from page requests)
    code = otp_interceptor.extract_from_page(page, pattern=r'\d{4,6}')

    # CAPTCHA wait (block until human handling is complete)
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


# ── Automatic TOTP generator ──────────────────────────────────────────────────────────

class TOTPGenerator:
    """
    Generate six-digit verification codes from a TOTP secret.
    Uses the optional pyotp library.
    """

    def generate(self, secret: str, digits: int = 6, interval: int = 30) -> Optional[str]:
        """
        Generate the current TOTP verification code.

        Args:
            secret: Base32-encoded TOTP secret
            digits: Number of code digits (default 6)
            interval: Time window in seconds (default 30)

        Returns:
            Verification code string, or None if pyotp is not installed
        """
        try:
            import pyotp
            totp = pyotp.TOTP(secret, digits=digits, interval=interval)
            code = totp.now()
            logger.info(f"[TOTPGenerator] Generated verification code: {code} ({totp.interval - int(time.time()) % totp.interval}s remaining)")
            return code
        except ImportError:
            logger.warning("[TOTPGenerator] pyotp is not installed; cannot generate TOTP. Run: pip install pyotp")
            return None
        except Exception as e:
            logger.error(f"[TOTPGenerator] Generation failed: {e}")
            return None

    def verify(self, secret: str, code: str) -> bool:
        """Verify a TOTP code"""
        try:
            import pyotp
            return pyotp.TOTP(secret).verify(code)
        except ImportError:
            return False


# ── OTP interceptor ───────────────────────────────────────────────────────────────

class OTPInterceptor:
    """
    Extract verification codes from page network requests or SMS API responses.

    Supported strategies:
    1. Page DOM scanning (hints near SMS verification inputs)
    2. Network interception (listen to responses from code delivery APIs)
    3. Regular-expression extraction (match numeric verification codes in visible text)
    """

    SMS_API_PATTERNS = [
        r'/sms/send', r'/sms/code', r'/verify/code', r'/captcha/sms',
        r'/auth/otp', r'/code/send', r'/message/send',
    ]

    CODE_REGEX = re.compile(r'(?:验证码|code|otp|captcha)[^\d]*(\d{4,8})', re.IGNORECASE)
    PURE_CODE_REGEX = re.compile(r'\b(\d{4,6})\b')

    def extract_from_page(self, page, pattern: Optional[str] = None) -> Optional[str]:
        """Extract a verification code from visible page text."""
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
                logger.info(f"[OTPInterceptor] Extracted a verification code from page text: {code}")
                return code

            logger.debug("[OTPInterceptor] No verification code found on the page")
            return None
        except Exception as e:
            logger.error(f"[OTPInterceptor] Extraction failed: {e}")
            return None

    def setup_network_intercept(self, page, callback=None):
        """Set up a network interceptor to extract codes from verification API responses."""
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
                        logger.info(f"[OTPInterceptor] Intercepted verification code: {code} (from {url})")
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
        logger.debug(f"[CaptchaOCR] Image preprocessing failed; using the original image: {exc}")
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
            "Perform verification-code OCR. Read the code in the image and return only JSON in this format: "
            '{"code":"verification code"}. '
            "Do not explain or add text; if the code is unreadable, return "
            '{"code":""}.'
        )
        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{payload}"}},
        ])
        response = vision_llm.invoke([message])
        content = response.content if hasattr(response, "content") else str(response)
        return _sanitize_captcha_code(content)
    except Exception as exc:
        logger.warning(f"[CaptchaOCR] Vision OCR call failed: {exc}")
        return None


def solve_captcha_from_page(page) -> Optional[str]:
    locator = _find_first_visible_locator(page, CAPTCHA_IMAGE_SELECTORS)
    if locator is None:
        logger.info("[CaptchaOCR] No visible verification-code image found on the page")
        return None

    try:
        raw = locator.screenshot(type="png", timeout=5000)
    except Exception as exc:
        logger.warning(f"[CaptchaOCR] Verification-code screenshot failed: {exc}")
        return None

    for variant in _build_captcha_variants(raw):
        code = _solve_captcha_with_vision(variant)
        if code:
            logger.info(f"[CaptchaOCR] Recognition succeeded: {code}")
            return code

    logger.warning("[CaptchaOCR] Verification-code recognition failed")
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
            logger.warning(f"[CaptchaOCR] Automatic verification-code entry failed: {exc}")
            return None


# ── CAPTCHA waiter ───────────────────────────────────────────────────────────

class CaptchaWaiter:
    """Pause for human intervention after CAPTCHA detection."""

    def wait_for_human(
        self,
        bus,
        session,
        timeout: int = 120,
        poll_interval: float = 2.0,
    ) -> bool:
        """Send a CAPTCHA notification and wait for human handling."""
        bus.publish_log_sync({
            "type": "captcha_intervention",
            "event": "captcha_detected",
            "content": "🔐 Verification code/CAPTCHA detected. Handle it manually, then click Resume.",
            "timeout": timeout,
            "status": "waiting",
        })

        logger.warning(f"[CaptchaWaiter] ⏸️ CAPTCHA detected; waiting for human intervention (timeout {timeout}s)...")

        original_signal = session.get_signal()
        session.set_signal("PAUSED")

        start = time.time()
        while time.time() - start < timeout:
            signal = session.get_signal()
            if signal == "RUNNING":
                elapsed = time.time() - start
                logger.info(f"[CaptchaWaiter] ✅ CAPTCHA handled manually after {elapsed:.1f}s")
                bus.publish_log_sync({
                    "type": "captcha_intervention",
                    "event": "captcha_resolved",
                    "content": f"✅ CAPTCHA handled; resuming after {elapsed:.1f}s",
                    "status": "resolved",
                })
                return True

            if signal == "STOPPED":
                logger.info("[CaptchaWaiter] Execution canceled by the user")
                return False

            time.sleep(poll_interval)

        logger.warning(f"[CaptchaWaiter] ⏰ CAPTCHA wait timed out ({timeout}s); resuming execution")
        session.set_signal(original_signal if original_signal != "PAUSED" else "RUNNING")
        bus.publish_log_sync({
            "type": "captcha_intervention",
            "event": "captcha_timeout",
            "content": f"⏰ CAPTCHA wait timed out ({timeout}s); resuming automatically",
            "status": "timeout",
        })
        return False


# ── Singleton ─────────────────────────────────────────────────────────────────────

totp_generator = TOTPGenerator()
otp_interceptor = OTPInterceptor()
captcha_waiter = CaptchaWaiter()
