# -*- coding: utf-8 -*-
"""
Cookie 管理器 — 浏览器认证态持久化
支持: 导出/导入 Cookie、预置 Auth Profile、跳过登录流程
借鉴 browser-use 的 cookie 管理能力
"""
import json
import inspect
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Cookie 存储目录
COOKIE_DIR = Path(__file__).parent.parent / "data" / "cookies"
PRESETS_FILE = COOKIE_DIR / "_presets.json"


class CookieManager:
    """Cookie 持久化管理器"""

    def __init__(self):
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 导出 / 导入
    # ------------------------------------------------------------------
    async def _resolve_maybe_async(self, value):
        if inspect.isawaitable(value):
            return await value
        return value

    def _cookie_path(self, name: str) -> Path:
        return COOKIE_DIR / f"{name}.json"

    def save_cookie_payload(
        self,
        cookies: List[Dict[str, Any]],
        name: str,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        if domain:
            cookies = [c for c in cookies if domain in c.get("domain", "")]

        filepath = self._cookie_path(name)
        filepath.write_text(json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"[CookieManager] Exported {len(cookies)} cookies → {filepath}")
        return {"count": len(cookies), "file": str(filepath)}

    def load_cookie_payload(self, name: str) -> List[Dict[str, Any]]:
        filepath = self._cookie_path(name)
        if not filepath.exists():
            raise FileNotFoundError(f"Cookie file not found: {filepath}")
        return json.loads(filepath.read_text(encoding="utf-8"))

    async def export_cookies(
        self,
        page,
        name: str,
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从 Playwright page 导出 Cookie 并持久化。

        Args:
            page: Playwright Page 对象
            name: 导出文件名（不含扩展名）
            domain: 可选，仅导出指定域名的 Cookie

        Returns:
            {"count": N, "file": "path"}
        """
        context = page.context
        cookies = await self._resolve_maybe_async(context.cookies())
        return self.save_cookie_payload(cookies, name, domain)

    async def import_cookies(
        self,
        context,
        name: str
    ) -> Dict[str, Any]:
        """
        从 JSON 文件导入 Cookie 到浏览器上下文。

        Args:
            context: Playwright BrowserContext
            name: Cookie 文件名（不含扩展名）

        Returns:
            {"count": N, "name": "..."}
        """
        cookies = self.load_cookie_payload(name)
        await self._resolve_maybe_async(context.add_cookies(cookies))
        logger.info(f"[CookieManager] Imported {len(cookies)} cookies from {name}")
        return {"count": len(cookies), "name": name}

    # ------------------------------------------------------------------
    # 预置管理
    # ------------------------------------------------------------------
    def list_saved(self) -> List[Dict[str, Any]]:
        """列出所有已保存的 Cookie 文件"""
        result = []
        for f in sorted(COOKIE_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue  # 跳过内部文件
            try:
                cookies = json.loads(f.read_text(encoding="utf-8"))
                domains = list({c.get("domain", "?") for c in cookies})
                result.append({
                    "name": f.stem,
                    "count": len(cookies),
                    "domains": domains[:5],
                    "size_bytes": f.stat().st_size,
                })
            except Exception:
                result.append({"name": f.stem, "count": 0, "domains": [], "error": "parse_failed"})
        return result

    def delete_saved(self, name: str) -> bool:
        """删除已保存的 Cookie 文件"""
        filepath = COOKIE_DIR / f"{name}.json"
        if filepath.exists():
            filepath.unlink()
            logger.info(f"[CookieManager] Deleted cookie file: {name}")
            return True
        return False

    # ------------------------------------------------------------------
    # 预置 Auth Profile
    # ------------------------------------------------------------------
    def list_presets(self) -> List[Dict[str, str]]:
        """列出预置 Auth Profile"""
        if not PRESETS_FILE.exists():
            return []
        try:
            data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
            return [{"name": k, "cookie_file": v} for k, v in data.items()]
        except Exception:
            return []

    def save_preset(self, preset_name: str, cookie_name: str) -> bool:
        """
        将已保存的 Cookie 文件注册为预置 Auth Profile。

        Args:
            preset_name: 预置名（如 "admin_login"）
            cookie_name: Cookie 文件名（如 "baidu_admin"）
        """
        cookie_path = self._cookie_path(cookie_name)
        if not cookie_path.exists():
            raise FileNotFoundError(f"Cookie file not found: {cookie_name}")

        presets = {}
        if PRESETS_FILE.exists():
            try:
                presets = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
            except Exception:
                presets = {}

        presets[preset_name] = cookie_name
        PRESETS_FILE.write_text(json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"[CookieManager] Preset '{preset_name}' → '{cookie_name}'")
        return True

    def delete_preset(self, preset_name: str) -> bool:
        """删除预置 Auth Profile"""
        if not PRESETS_FILE.exists():
            return False
        presets = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        if preset_name in presets:
            del presets[preset_name]
            PRESETS_FILE.write_text(json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        return False

    async def inject_preset(self, context, preset_name: str) -> Dict[str, Any]:
        """
        注入预置 Auth Cookie 到浏览器上下文（跳过登录流程）。

        Args:
            context: Playwright BrowserContext
            preset_name: 预置名

        Returns:
            {"count": N, "preset": "..."}
        """
        if not PRESETS_FILE.exists():
            raise ValueError(f"No presets configured")

        presets = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        if preset_name not in presets:
            raise ValueError(f"Preset not found: {preset_name}")

        cookie_name = presets[preset_name]
        result = await self.import_cookies(context, cookie_name)
        result["preset"] = preset_name
        return result


# 模块级单例
cookie_manager = CookieManager()
