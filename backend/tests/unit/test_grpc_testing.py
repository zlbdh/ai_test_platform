"""
GrpcTestService 单元测试
覆盖: 数据类, _check_grpcurl, _build_command, _get_value_by_path,
      assert_response, call(grpcurl 不可用), 工厂函数
"""
import pytest
from unittest.mock import patch, MagicMock

from services.grpc_testing import (
    GrpcRequest, GrpcResponse, GrpcAssertion,
    GrpcTestService, create_grpc_service
)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------
class TestGrpcRequest:
    def test_creation(self):
        r = GrpcRequest(service="user.UserService", method="GetUser",
                        data={"id": "1"})
        assert r.metadata is None


class TestGrpcResponse:
    def test_creation(self):
        r = GrpcResponse(success=True, data={"name": "A"}, error=None,
                         status_code=0, response_time_ms=10)
        assert r.success is True


class TestGrpcAssertion:
    def test_creation(self):
        a = GrpcAssertion(path="name", operator="eq", expected="Alice")
        assert a.path == "name"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def svc():
    with patch("shutil.which", return_value=None):
        s = GrpcTestService(host="localhost", port=50051)
    return s


@pytest.fixture
def svc_with_grpcurl():
    with patch("shutil.which", return_value="/usr/bin/grpcurl"):
        s = GrpcTestService(host="localhost", port=50051)
    return s


# ---------------------------------------------------------------------------
# _check_grpcurl
# ---------------------------------------------------------------------------
class TestCheckGrpcurl:
    def test_not_available(self, svc):
        assert svc._grpcurl_available is False

    def test_available(self, svc_with_grpcurl):
        assert svc_with_grpcurl._grpcurl_available is True


# ---------------------------------------------------------------------------
# _build_command
# ---------------------------------------------------------------------------
class TestBuildCommand:
    def test_plaintext(self, svc_with_grpcurl):
        cmd = svc_with_grpcurl._build_command("pkg.Svc", "Method", {"key": "val"})
        assert "-plaintext" in cmd
        assert "localhost:50051" in cmd
        assert "pkg.Svc/Method" in cmd

    def test_tls(self):
        with patch("shutil.which", return_value="/usr/bin/grpcurl"):
            svc = GrpcTestService(host="secure.io", port=443, use_tls=True)
        cmd = svc._build_command("Svc", "M", {})
        assert "-plaintext" not in cmd

    def test_with_metadata(self, svc_with_grpcurl):
        cmd = svc_with_grpcurl._build_command("S", "M", {}, metadata={"Authorization": "Bearer x"})
        assert "-H" in cmd
        idx = cmd.index("-H")
        assert "Authorization: Bearer x" in cmd[idx + 1]


# ---------------------------------------------------------------------------
# _get_value_by_path
# ---------------------------------------------------------------------------
class TestGetValueByPath:
    def test_nested(self, svc):
        assert svc._get_value_by_path({"a": {"b": 1}}, "a.b") == 1

    def test_empty_path(self, svc):
        data = {"x": 1}
        assert svc._get_value_by_path(data, "") == data

    def test_missing(self, svc):
        assert svc._get_value_by_path({"a": 1}, "b.c") is None


# ---------------------------------------------------------------------------
# assert_response
# ---------------------------------------------------------------------------
class TestAssertResponse:
    def _response(self, data):
        return GrpcResponse(success=True, data=data, error=None,
                            status_code=0, response_time_ms=5)

    def test_eq(self, svc):
        resp = self._response({"name": "Alice"})
        results = svc.assert_response(resp, [GrpcAssertion("name", "eq", "Alice")])
        assert results[0]["passed"] is True

    def test_ne(self, svc):
        resp = self._response({"name": "Bob"})
        results = svc.assert_response(resp, [GrpcAssertion("name", "ne", "Alice")])
        assert results[0]["passed"] is True

    def test_contains(self, svc):
        resp = self._response({"msg": "hello world"})
        results = svc.assert_response(resp, [GrpcAssertion("msg", "contains", "world")])
        assert results[0]["passed"] is True

    def test_exists(self, svc):
        resp = self._response({"key": "val"})
        results = svc.assert_response(resp, [GrpcAssertion("key", "exists", True)])
        assert results[0]["passed"] is True

    def test_type(self, svc):
        resp = self._response({"count": 5})
        results = svc.assert_response(resp, [GrpcAssertion("count", "type", "int")])
        assert results[0]["passed"] is True


# ---------------------------------------------------------------------------
# call — grpcurl 不可用
# ---------------------------------------------------------------------------
class TestCall:
    @pytest.mark.asyncio
    async def test_grpcurl_unavailable(self, svc):
        req = GrpcRequest(service="S", method="M", data={})
        resp = await svc.call(req)
        assert resp.success is False
        assert "grpcurl" in resp.error


# ---------------------------------------------------------------------------
# list_services / describe — grpcurl 不可用
# ---------------------------------------------------------------------------
class TestListAndDescribe:
    @pytest.mark.asyncio
    async def test_list_no_grpcurl(self, svc):
        result = await svc.list_services()
        assert result == []

    @pytest.mark.asyncio
    async def test_describe_no_grpcurl(self, svc):
        result = await svc.describe_service("Svc")
        assert result == {}


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------
class TestFactory:
    def test_create(self):
        with patch("shutil.which", return_value=None):
            svc = create_grpc_service("localhost", 50051)
        assert isinstance(svc, GrpcTestService)
        assert svc.address == "localhost:50051"
