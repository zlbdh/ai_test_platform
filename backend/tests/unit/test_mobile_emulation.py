"""
MobileEmulationService 单元测试
覆盖: 数据类, DEVICE_PRESETS, list_devices, test_devices(Playwright ImportError), 工厂
"""
import pytest
from unittest.mock import patch

from services.mobile_emulation import (
    DeviceTestResult, MobileReport, MobileEmulationService,
    DEVICE_PRESETS, create_mobile_service
)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestDeviceTestResult:
    def test_creation(self):
        r = DeviceTestResult(device="iPhone 14", viewport="390x844")
        d = r.to_dict()
        assert d["device"] == "iPhone 14"
        assert d["issues"] == []


class TestMobileReport:
    def test_defaults(self):
        r = MobileReport(url="http://x.com")
        assert r.score == 100.0
        assert r.devices_tested == 0
        assert r.to_dict()["url"] == "http://x.com"


# ---------------------------------------------------------------------------
# DEVICE_PRESETS
# ---------------------------------------------------------------------------
class TestDevicePresets:
    def test_has_expected_devices(self):
        assert "iphone_14" in DEVICE_PRESETS
        assert "pixel_7" in DEVICE_PRESETS
        assert "ipad_pro" in DEVICE_PRESETS

    def test_preset_structure(self):
        for key, preset in DEVICE_PRESETS.items():
            assert "name" in preset
            assert "viewport" in preset
            assert "width" in preset["viewport"]
            assert "height" in preset["viewport"]
            assert "user_agent" in preset
            assert "is_mobile" in preset


# ---------------------------------------------------------------------------
# list_devices
# ---------------------------------------------------------------------------
class TestListDevices:
    def test_returns_all(self):
        svc = MobileEmulationService()
        devices = svc.list_devices()
        assert len(devices) == len(DEVICE_PRESETS)

    def test_device_structure(self):
        svc = MobileEmulationService()
        for d in svc.list_devices():
            assert "id" in d
            assert "name" in d
            assert "viewport" in d
            assert "type" in d
            assert d["type"] in ("phone", "tablet")

    def test_tablet_classification(self):
        svc = MobileEmulationService()
        devices = svc.list_devices()
        ipad = next(d for d in devices if d["id"] == "ipad_pro")
        assert ipad["type"] == "tablet"

    def test_phone_classification(self):
        svc = MobileEmulationService()
        devices = svc.list_devices()
        iphone = next(d for d in devices if d["id"] == "iphone_14")
        assert iphone["type"] == "phone"


# ---------------------------------------------------------------------------
# test_devices (Playwright ImportError 回退)
# ---------------------------------------------------------------------------
class TestDevices:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self):
        svc = MobileEmulationService()
        with patch("builtins.__import__", side_effect=ImportError("no playwright")):
            report = await svc.test_devices("http://x.com")
        assert "Playwright" in report.summary
        assert report.score == -1


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
class TestFactory:
    def test_create(self):
        svc = create_mobile_service()
        assert isinstance(svc, MobileEmulationService)
