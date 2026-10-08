# -*- coding: utf-8 -*-
"""
Cookie manager — persist browser authentication state
Supports cookie export/import, authentication profiles, and skipping sign-in
Inspired by browser-use cookie management
"""
import json
import inspect
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Cookie storage directory
COOKIE_DIR = Path(__file__).parent.parent / "data" / "cookies"
PRESETS_FILE = COOKIE_DIR / "_presets.json"


class CookieManager:
    """Cookie persistence manager"""

    def __init__(self):
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Export/import
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
        Export cookies from a Playwright page and persist them.

        Args:
            page: Playwright Page object
            name: Export filename without an extension
            domain: Optional domain filter for exported cookies

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
        Import cookies from a JSON file into the browser context.

        Args:
            context: Playwright BrowserContext
            name: Cookie filename without an extension

        Returns:
            {"count": N, "name": "..."}
        """
        cookies = self.load_cookie_payload(name)
        await self._resolve_maybe_async(context.add_cookies(cookies))
        logger.info(f"[CookieManager] Imported {len(cookies)} cookies from {name}")
        return {"count": len(cookies), "name": name}

    # ------------------------------------------------------------------
    # Preset management
    # ------------------------------------------------------------------
    def list_saved(self) -> List[Dict[str, Any]]:
        """List all saved cookie files"""
        result = []
        for f in sorted(COOKIE_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue  # Skip internal files
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
        """Delete a saved cookie file"""
        filepath = COOKIE_DIR / f"{name}.json"
        if filepath.exists():
            filepath.unlink()
            logger.info(f"[CookieManager] Deleted cookie file: {name}")
            return True
        return False

    # ------------------------------------------------------------------
    # Authentication profile presets
    # ------------------------------------------------------------------
    def list_presets(self) -> List[Dict[str, str]]:
        """List authentication profile presets"""
        if not PRESETS_FILE.exists():
            return []
        try:
            data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
            return [{"name": k, "cookie_file": v} for k, v in data.items()]
        except Exception:
            return []

    def save_preset(self, preset_name: str, cookie_name: str) -> bool:
        """
        Register a saved cookie file as an authentication profile preset.

        Args:
            preset_name: Preset name, such as "admin_login")
            cookie_name: Cookie filename, such as "baidu_admin")
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
        """Delete an authentication profile preset"""
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
        Inject preset authentication cookies into the browser context to skip sign-in.

        Args:
            context: Playwright BrowserContext
            preset_name: Preset name

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


# Module-level singleton
cookie_manager = CookieManager()
