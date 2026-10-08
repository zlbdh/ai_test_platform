"""
ContractTestingService unit tests.
Covers enums and data classes, create_contract, verify_contract, _verify_interaction,
Pact export/import, get_statistics, and the singleton.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from services.contract_testing import (
    ContractStatus, ContractInteraction, Contract,
    VerificationResult, ContractTestingService
)


# ---------------------------------------------------------------------------
# Enums and data classes.
# ---------------------------------------------------------------------------
class TestContractStatus:
    def test_values(self):
        assert ContractStatus.PENDING.value == "pending"
        assert ContractStatus.VERIFIED.value == "verified"
        assert ContractStatus.FAILED.value == "failed"


class TestContractInteraction:
    def test_creation(self):
        ci = ContractInteraction(
            description="get user",
            request={"method": "GET", "path": "/user"},
            response={"status": 200}
        )
        assert ci.description == "get user"


class TestVerificationResult:
    def test_creation(self):
        vr = VerificationResult(
            contract_id="abc", passed=True,
            total_interactions=3, passed_interactions=3,
            failed_interactions=0, failures=[],
            verification_time_ms=120
        )
        assert vr.passed is True


# ---------------------------------------------------------------------------
# ContractTestingService
# ---------------------------------------------------------------------------
@pytest.fixture
def svc():
    return ContractTestingService()


SAMPLE_INTERACTIONS = [
    {
        "description": "get user list",
        "request": {"method": "GET", "path": "/api/users"},
        "response": {"status": 200, "body": {"count": 5}}
    },
    {
        "description": "create user",
        "request": {"method": "POST", "path": "/api/users", "body": {"name": "Alice"}},
        "response": {"status": 201}
    }
]


class TestCreateContract:
    def test_basic(self, svc):
        c = svc.create_contract("frontend", "backend", SAMPLE_INTERACTIONS)
        assert c.consumer == "frontend"
        assert c.provider == "backend"
        assert len(c.interactions) == 2
        assert c.status == ContractStatus.PENDING
        assert c.contract_id in svc.contracts

    def test_version(self, svc):
        c = svc.create_contract("a", "b", [], version="2.0.0")
        assert c.version == "2.0.0"


class TestGenerateId:
    def test_length(self, svc):
        cid = svc._generate_id("a", "b")
        assert len(cid) == 12


# ---------------------------------------------------------------------------
# verify_contract tests.
# ---------------------------------------------------------------------------
def _make_aiohttp_ctx(mock_resp):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestVerifyContract:
    @pytest.mark.asyncio
    async def test_contract_not_found(self, svc):
        result = await svc.verify_contract("nonexistent", "http://example.com")
        assert result.passed is False
        assert result.failures[0]["error"] == "Contract not found"

    @pytest.mark.asyncio
    async def test_all_pass(self, svc):
        """All interactions pass verification."""
        c = svc.create_contract("fe", "be", [
            {"description": "get", "request": {"method": "GET", "path": "/"},
             "response": {"status": 200}}
        ])

        with patch.object(svc, "_verify_interaction", new_callable=AsyncMock,
                          return_value={"passed": True}):
            result = await svc.verify_contract(c.contract_id, "http://be")

        assert result.passed is True
        assert result.passed_interactions == 1
        assert c.status == ContractStatus.VERIFIED
        assert len(svc.verification_history) == 1

    @pytest.mark.asyncio
    async def test_partial_fail(self, svc):
        """Some interactions fail verification."""
        c = svc.create_contract("fe", "be", SAMPLE_INTERACTIONS)

        returns = [
            {"passed": True},
            {"passed": False, "error": "Status code mismatch", "expected": 201, "actual": 500}
        ]
        with patch.object(svc, "_verify_interaction", new_callable=AsyncMock,
                          side_effect=returns):
            result = await svc.verify_contract(c.contract_id, "http://be")

        assert result.passed is False
        assert result.passed_interactions == 1
        assert result.failed_interactions == 1
        assert c.status == ContractStatus.FAILED


# ---------------------------------------------------------------------------
# _verify_interaction tests.
# ---------------------------------------------------------------------------
class TestVerifyInteraction:
    @pytest.mark.asyncio
    async def test_status_match(self, svc):
        interaction = ContractInteraction(
            description="ok", request={"method": "GET", "path": "/"},
            response={"status": 200}
        )
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content_type = "text/html"
        mock_resp.text = AsyncMock(return_value="ok")

        mock_session = MagicMock()
        mock_session.request.return_value = _make_aiohttp_ctx(mock_resp)

        result = await svc._verify_interaction(mock_session, "http://be", interaction)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_status_mismatch(self, svc):
        interaction = ContractInteraction(
            description="fail", request={"method": "GET", "path": "/"},
            response={"status": 200}
        )
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_resp.content_type = "text/html"
        mock_resp.text = AsyncMock(return_value="")

        mock_session = MagicMock()
        mock_session.request.return_value = _make_aiohttp_ctx(mock_resp)

        result = await svc._verify_interaction(mock_session, "http://be", interaction)
        assert result["passed"] is False
        assert result["error"] == "Status code mismatch"

    @pytest.mark.asyncio
    async def test_body_mismatch(self, svc):
        interaction = ContractInteraction(
            description="body check",
            request={"method": "GET", "path": "/"},
            response={"status": 200, "body": {"name": "Alice"}}
        )
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content_type = "application/json"
        mock_resp.json = AsyncMock(return_value={"name": "Bob"})

        mock_session = MagicMock()
        mock_session.request.return_value = _make_aiohttp_ctx(mock_resp)

        result = await svc._verify_interaction(mock_session, "http://be", interaction)
        assert result["passed"] is False
        assert "Body mismatch" in result["error"]

    @pytest.mark.asyncio
    async def test_body_match(self, svc):
        interaction = ContractInteraction(
            description="body ok",
            request={"method": "GET", "path": "/"},
            response={"status": 200, "body": {"name": "Alice"}}
        )
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content_type = "application/json"
        mock_resp.json = AsyncMock(return_value={"name": "Alice"})

        mock_session = MagicMock()
        mock_session.request.return_value = _make_aiohttp_ctx(mock_resp)

        result = await svc._verify_interaction(mock_session, "http://be", interaction)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_exception_returns_failed(self, svc):
        interaction = ContractInteraction(
            description="error", request={"method": "GET", "path": "/"},
            response={"status": 200}
        )
        mock_session = MagicMock()
        mock_session.request.side_effect = Exception("connection refused")

        result = await svc._verify_interaction(mock_session, "http://be", interaction)
        assert result["passed"] is False
        assert "connection refused" in result["error"]


# ---------------------------------------------------------------------------
# Pact import/export.
# ---------------------------------------------------------------------------
class TestPact:
    def test_export_pact(self, svc):
        c = svc.create_contract("fe", "be", SAMPLE_INTERACTIONS)
        pact = svc.export_pact(c.contract_id)
        assert pact["consumer"]["name"] == "fe"
        assert pact["provider"]["name"] == "be"
        assert len(pact["interactions"]) == 2
        assert pact["metadata"]["pactSpecification"]["version"] == "2.0.0"

    def test_export_not_found(self, svc):
        assert svc.export_pact("none") == {}

    def test_import_pact(self, svc):
        pact_data = {
            "consumer": {"name": "mobile"},
            "provider": {"name": "api"},
            "interactions": [
                {"description": "hello", "request": {"path": "/"}, "response": {"status": 200}}
            ]
        }
        c = svc.import_pact(pact_data)
        assert c.consumer == "mobile"
        assert c.provider == "api"
        assert len(c.interactions) == 1

    def test_roundtrip(self, svc):
        """Exporting and reimporting should produce an equivalent contract."""
        c1 = svc.create_contract("fe", "be", SAMPLE_INTERACTIONS)
        pact = svc.export_pact(c1.contract_id)
        c2 = svc.import_pact(pact)
        assert c2.consumer == c1.consumer
        assert c2.provider == c1.provider
        assert len(c2.interactions) == len(c1.interactions)


# ---------------------------------------------------------------------------
# Statistics.
# ---------------------------------------------------------------------------
class TestStatistics:
    def test_empty(self, svc):
        stats = svc.get_statistics()
        assert stats["total_contracts"] == 0
        assert stats["verification_runs"] == 0

    def test_with_contracts(self, svc):
        c1 = svc.create_contract("a", "b", [])
        c2 = svc.create_contract("c", "d", [])
        c1.status = ContractStatus.VERIFIED
        c2.status = ContractStatus.FAILED
        stats = svc.get_statistics()
        assert stats["total_contracts"] == 2
        assert stats["verified"] == 1
        assert stats["failed"] == 1
        assert stats["pending"] == 0


# ---------------------------------------------------------------------------
# Singleton.
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton(self):
        import services.contract_testing as mod
        mod._contract_service = None
        s1 = mod.get_contract_service()
        s2 = mod.get_contract_service()
        assert s1 is s2
        mod._contract_service = None
