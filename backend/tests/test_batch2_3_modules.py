"""
Unit Tests for Batch 2 and 3 Modules
Covers accessibility, i18n, compliance, chaos engineering, and mobile emulation.
"""

import pytest
import asyncio


# ============================================================
# Tests for Accessibility Testing Service
# ============================================================
class TestAccessibilityService:
    """Test the accessibility service."""

    def test_import(self):
        from services.accessibility_testing import create_accessibility_service
        service = create_accessibility_service()
        assert service is not None

    def test_service_has_audit_method(self):
        from services.accessibility_testing import create_accessibility_service
        service = create_accessibility_service()
        assert hasattr(service, 'audit')
        assert hasattr(service, 'quick_check')

    def test_service_class_init(self):
        from services.accessibility_testing import AccessibilityTestService
        service = AccessibilityTestService()
        assert service is not None
        assert callable(getattr(service, 'audit', None)) or callable(getattr(service, 'quick_check', None))


# ============================================================
# Tests for i18n Testing Service
# ============================================================
class TestI18nService:
    """Test the internationalization service."""

    def test_import(self):
        from services.i18n_testing import create_i18n_service
        service = create_i18n_service()
        assert service is not None

    def test_service_has_test_method(self):
        from services.i18n_testing import create_i18n_service
        service = create_i18n_service()
        assert hasattr(service, 'test_locale') or hasattr(service, 'test')
        assert hasattr(service, 'quick_check')


# ============================================================
# Tests for Compliance Testing Service
# ============================================================
class TestComplianceService:
    """Test the compliance service."""

    def test_import(self):
        from services.compliance_testing import create_compliance_service
        service = create_compliance_service()
        assert service is not None

    def test_service_has_audit_method(self):
        from services.compliance_testing import create_compliance_service
        service = create_compliance_service()
        assert hasattr(service, 'audit')


# ============================================================
# Tests for Chaos Engineering Service
# ============================================================
class TestChaosEngineering:
    """Test the chaos engineering service."""

    def test_import(self):
        from services.chaos_engineering import create_chaos_service
        service = create_chaos_service()
        assert service is not None

    def test_list_scenarios(self):
        from services.chaos_engineering import create_chaos_service
        service = create_chaos_service()
        scenarios = service.list_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) == 7

    def test_scenario_structure(self):
        from services.chaos_engineering import create_chaos_service
        service = create_chaos_service()
        scenarios = service.list_scenarios()
        for s in scenarios:
            assert "id" in s
            assert "name" in s
            assert "description" in s

    def test_scenario_ids(self):
        from services.chaos_engineering import create_chaos_service
        service = create_chaos_service()
        scenarios = service.list_scenarios()
        ids = {s["id"] for s in scenarios}
        expected = {
            "slow_network", "offline_recovery", "api_timeout",
            "api_500", "cpu_throttle", "large_payload", "memory_pressure"
        }
        assert ids == expected

    def test_chaos_result_dataclass(self):
        from services.chaos_engineering import ChaosResult
        result = ChaosResult(scenario="test", status="passed")
        d = result.to_dict()
        assert d["scenario"] == "test"
        assert d["status"] == "passed"
        assert d["duration_ms"] == 0

    def test_chaos_report_dataclass(self):
        from services.chaos_engineering import ChaosReport
        report = ChaosReport(url="http://test.com")
        d = report.to_dict()
        assert d["url"] == "http://test.com"
        assert d["scenarios_run"] == 0
        assert d["results"] == []


# ============================================================
# Tests for Mobile Emulation Service
# ============================================================
class TestMobileEmulation:
    """Test the mobile emulation service."""

    def test_import(self):
        from services.mobile_emulation import create_mobile_service
        service = create_mobile_service()
        assert service is not None

    def test_list_devices(self):
        from services.mobile_emulation import create_mobile_service
        service = create_mobile_service()
        devices = service.list_devices()
        assert isinstance(devices, list)
        assert len(devices) == 6

    def test_device_structure(self):
        from services.mobile_emulation import create_mobile_service
        service = create_mobile_service()
        devices = service.list_devices()
        for d in devices:
            assert "id" in d
            assert "name" in d
            assert "viewport" in d
            assert "type" in d
            assert d["type"] in ["phone", "tablet"]

    def test_device_ids(self):
        from services.mobile_emulation import create_mobile_service
        service = create_mobile_service()
        devices = service.list_devices()
        ids = {d["id"] for d in devices}
        expected = {
            "iphone_14", "iphone_se", "pixel_7",
            "galaxy_s21", "ipad_pro", "galaxy_tab_s8"
        }
        assert ids == expected

    def test_tablet_detection(self):
        from services.mobile_emulation import create_mobile_service
        service = create_mobile_service()
        devices = service.list_devices()
        tablets = [d for d in devices if d["type"] == "tablet"]
        phones = [d for d in devices if d["type"] == "phone"]
        assert len(tablets) == 2  # iPad Pro, Galaxy Tab S8
        assert len(phones) == 4

    def test_device_presets_config(self):
        from services.mobile_emulation import DEVICE_PRESETS
        for key, preset in DEVICE_PRESETS.items():
            assert "name" in preset
            assert "viewport" in preset
            assert "width" in preset["viewport"]
            assert "height" in preset["viewport"]
            assert "user_agent" in preset
            assert "is_mobile" in preset
            assert preset["is_mobile"] is True

    def test_mobile_report_dataclass(self):
        from services.mobile_emulation import MobileReport
        report = MobileReport(url="http://test.com")
        d = report.to_dict()
        assert d["url"] == "http://test.com"
        assert d["devices_tested"] == 0
        assert d["score"] == 100.0
        assert d["results"] == []


# ============================================================
# Tests for FastAPI Routers (import validation)
# ============================================================
class TestRouterImports:
    """Test router module imports."""

    def test_accessibility_router(self):
        from routers.accessibility import router
        assert router is not None
        assert router.prefix == "/api/accessibility"

    def test_i18n_router(self):
        from routers.i18n import router
        assert router is not None
        assert router.prefix == "/api/i18n"

    def test_compliance_router(self):
        from routers.compliance import router
        assert router is not None
        assert router.prefix == "/api/compliance"

    def test_chaos_router(self):
        from routers.chaos import router
        assert router is not None
        assert router.prefix == "/api/chaos"

    def test_mobile_router(self):
        from routers.mobile import router
        assert router is not None
        assert router.prefix == "/api/mobile"


# ============================================================
# Tests for FastAPI app integration
# ============================================================
class TestAppIntegration:
    """Test application integration."""

    def test_all_routers_in_main(self):
        """Verify that main.py registers every router."""
        import importlib
        main = importlib.import_module("main")
        app = main.app
        routes = [r.path for r in app.routes]
        # Verify that the new router prefixes exist.
        prefixes_to_check = [
            "/api/accessibility/audit",
            "/api/i18n/test",
            "/api/compliance/audit",
            "/api/chaos/run",
            "/api/mobile/test",
        ]
        for prefix in prefixes_to_check:
            assert prefix in routes, f"Route {prefix} not found in app.routes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
