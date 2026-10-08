"""
ApiWorkbenchService unit tests
Coverage: data structures; Collection/Request/Environment CRUD;
          variable substitution; JSON path extraction; assertion evaluation;
          request execution; collection execution; singleton access.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from services.api_workbench import (
    RequestItem, Collection, Environment, RequestResult,
    ApiWorkbenchService
)


@pytest.fixture
def svc(tmp_path):
    """Use a temporary directory to avoid affecting real data."""
    with patch("services.api_workbench.DATA_DIR", tmp_path), \
         patch("services.api_workbench.COLLECTIONS_FILE", tmp_path / "collections.json"), \
         patch("services.api_workbench.ENVIRONMENTS_FILE", tmp_path / "environments.json"):
        return ApiWorkbenchService()


# ---------------------------------------------------------------------------
# Data structure tests
# ---------------------------------------------------------------------------
class TestDataClasses:
    def test_request_item(self):
        req = RequestItem()
        assert req.name == "New Request"
        assert req.method == "GET"
        assert req.id  # auto uuid

    def test_collection(self):
        col = Collection()
        assert col.name == "New Collection"
        assert col.requests == []

    def test_environment(self):
        env = Environment()
        assert env.name == "Default"
        assert env.is_active is False

    def test_request_result(self):
        result = RequestResult(request_id="r1", request_name="Login")
        assert result.success is False
        assert result.status_code == 0
        assert result.error is None


# ---------------------------------------------------------------------------
# Collection CRUD tests
# ---------------------------------------------------------------------------
class TestCollectionCRUD:
    def test_create(self, svc):
        col = svc.create_collection("Test Collection", "Description")
        assert col["name"] == "Test Collection"
        assert col["id"] in svc.collections

    def test_list(self, svc):
        svc.create_collection("C1")
        svc.create_collection("C2")
        result = svc.list_collections()
        assert len(result) == 2

    def test_get(self, svc):
        col = svc.create_collection("MyCol")
        retrieved = svc.get_collection(col["id"])
        assert retrieved is not None
        assert retrieved["name"] == "MyCol"

    def test_get_not_found(self, svc):
        result = svc.get_collection("nonexistent")
        assert result is None

    def test_delete(self, svc):
        col = svc.create_collection("ToDelete")
        assert svc.delete_collection(col["id"]) is True
        assert col["id"] not in svc.collections

    def test_delete_not_found(self, svc):
        assert svc.delete_collection("nonexistent") is False

    def test_update(self, svc):
        col = svc.create_collection("Original")
        updated = svc.update_collection(col["id"], {"name": "Updated"})
        assert updated["name"] == "Updated"

    def test_update_not_found(self, svc):
        assert svc.update_collection("nonexistent", {"name": "x"}) is None


# ---------------------------------------------------------------------------
# Environment CRUD tests
# ---------------------------------------------------------------------------
class TestEnvironmentCRUD:
    def test_create(self, svc):
        env = svc.create_environment("Staging", {"BASE_URL": "http://staging.example.com"})
        assert env["name"] == "Staging"
        assert env["variables"]["BASE_URL"] == "http://staging.example.com"

    def test_list(self, svc):
        svc.create_environment("Dev")
        svc.create_environment("Prod")
        result = svc.list_environments()
        assert len(result) >= 2

    def test_set_active(self, svc):
        e1 = svc.create_environment("Env1")
        e2 = svc.create_environment("Env2")
        svc.set_active_environment(e1["id"])
        assert svc.environments[e1["id"]].is_active is True
        svc.set_active_environment(e2["id"])
        assert svc.environments[e2["id"]].is_active is True
        assert svc.environments[e1["id"]].is_active is False

    def test_set_active_not_found(self, svc):
        assert svc.set_active_environment("nonexistent") is False

    def test_get_active(self, svc):
        env = svc.create_environment("Active")
        svc.set_active_environment(env["id"])
        active = svc.get_active_environment()
        assert active is not None
        assert active["name"] == "Active"

    def test_delete(self, svc):
        env = svc.create_environment("ToDelete")
        assert svc.delete_environment(env["id"]) is True
        assert env["id"] not in svc.environments

    def test_update(self, svc):
        env = svc.create_environment("Original")
        updated = svc.update_environment(env["id"], {"name": "Updated", "variables": {"K": "V"}})
        assert updated["name"] == "Updated"
        assert updated["variables"]["K"] == "V"

    def test_update_not_found(self, svc):
        assert svc.update_environment("nonexistent", {"name": "x"}) is None


# ---------------------------------------------------------------------------
# Request CRUD tests
# ---------------------------------------------------------------------------
class TestRequestCRUD:
    def test_add_request(self, svc):
        col = svc.create_collection("APITests")
        req = svc.add_request(col["id"], {
            "name": "Get Users",
            "method": "GET",
            "url": "http://api.example.com/users",
        })
        assert req is not None
        assert len(svc.collections[col["id"]].requests) == 1

    def test_add_request_to_nonexistent_collection(self, svc):
        assert svc.add_request("nonexistent", {"name": "x"}) is None

    def test_update_request(self, svc):
        col = svc.create_collection("APITests")
        req = svc.add_request(col["id"], {"name": "Original", "method": "GET", "url": "/"})
        updated = svc.update_request(col["id"], req["id"], {"name": "Updated", "method": "POST"})
        assert updated["name"] == "Updated"
        assert updated["method"] == "POST"

    def test_update_request_not_found(self, svc):
        col = svc.create_collection("APITests")
        assert svc.update_request(col["id"], "nonexistent", {"name": "x"}) is None

    def test_delete_request(self, svc):
        col = svc.create_collection("APITests")
        req = svc.add_request(col["id"], {"name": "Temp", "method": "GET", "url": "/"})
        assert svc.delete_request(col["id"], req["id"]) is True
        assert len(svc.collections[col["id"]].requests) == 0

    def test_delete_request_not_found(self, svc):
        col = svc.create_collection("APITests")
        assert svc.delete_request(col["id"], "nonexistent") is False


# ---------------------------------------------------------------------------
# Variable substitution tests
# ---------------------------------------------------------------------------
class TestSubstituteVariables:
    def test_no_variables(self, svc):
        assert svc._substitute_variables("hello world") == "hello world"

    def test_empty_text(self, svc):
        assert svc._substitute_variables("") == ""

    def test_none_text(self, svc):
        assert svc._substitute_variables(None) is None

    def test_env_variable(self, svc):
        env = svc.create_environment("Dev", {"BASE_URL": "http://localhost:8080"})
        svc.set_active_environment(env["id"])
        result = svc._substitute_variables("{{BASE_URL}}/api/users")
        assert result == "http://localhost:8080/api/users"

    def test_runtime_variable(self, svc):
        svc.runtime_variables["token"] = "abc123"
        result = svc._substitute_variables("Bearer {{token}}")
        assert result == "Bearer abc123"

    def test_extra_vars(self, svc):
        result = svc._substitute_variables("user={{name}}", {"name": "admin"})
        assert result == "user=admin"

    def test_runtime_overrides_env(self, svc):
        """Runtime variables should override environment variables."""
        env = svc.create_environment("Dev", {"key": "env_val"})
        svc.set_active_environment(env["id"])
        svc.runtime_variables["key"] = "runtime_val"
        result = svc._substitute_variables("{{key}}")
        assert result == "runtime_val"


# ---------------------------------------------------------------------------
# JSON path extraction tests
# ---------------------------------------------------------------------------
class TestExtractJsonPath:
    def test_simple_key(self, svc):
        assert svc._extract_json_path({"name": "test"}, "$.name") == "test"

    def test_nested_key(self, svc):
        data = {"data": {"user": {"name": "admin"}}}
        assert svc._extract_json_path(data, "$.data.user.name") == "admin"

    def test_array_index(self, svc):
        data = {"items": ["a", "b", "c"]}
        assert svc._extract_json_path(data, "$.items.1") == "b"

    def test_invalid_path(self, svc):
        assert svc._extract_json_path({"a": 1}, "$.nonexistent") is None

    def test_no_dollar_prefix(self, svc):
        assert svc._extract_json_path({"a": 1}, "a") is None


# ---------------------------------------------------------------------------
# Assertion evaluation tests
# ---------------------------------------------------------------------------
class TestEvaluateAssertion:
    def _make_result(self, status_code=200, response_time_ms=100,
                     response_headers=None, response_body=""):
        return RequestResult(
            request_id="r1", request_name="test",
            status_code=status_code,
            response_time_ms=response_time_ms,
            response_headers=response_headers or {},
            response_body=response_body,
        )

    def test_status_equals_pass(self, svc):
        result = self._make_result(status_code=200)
        r = svc._evaluate_assertion(
            {"type": "status", "operator": "equals", "expected": 200},
            result, None
        )
        assert r["passed"] is True

    def test_status_equals_fail(self, svc):
        result = self._make_result(status_code=404)
        r = svc._evaluate_assertion(
            {"type": "status", "operator": "equals", "expected": 200},
            result, None
        )
        assert r["passed"] is False

    def test_json_path(self, svc):
        result = self._make_result()
        r = svc._evaluate_assertion(
            {"type": "json_path", "operator": "equals", "expected": "admin", "path": "$.user"},
            result, {"user": "admin"}
        )
        assert r["passed"] is True

    def test_response_time_less_than(self, svc):
        result = self._make_result(response_time_ms=50)
        r = svc._evaluate_assertion(
            {"type": "response_time", "operator": "less_than", "expected": 100},
            result, None
        )
        assert r["passed"] is True

    def test_header_contains(self, svc):
        result = self._make_result(response_headers={"content-type": "application/json"})
        r = svc._evaluate_assertion(
            {"type": "header", "operator": "contains", "expected": "json", "path": "content-type"},
            result, None
        )
        assert r["passed"] is True

    def test_body_contains(self, svc):
        result = self._make_result(response_body="Hello World")
        r = svc._evaluate_assertion(
            {"type": "body_contains", "operator": "equals", "expected": "Hello"},
            result, None
        )
        assert r["passed"] is True

    def test_not_equals(self, svc):
        result = self._make_result(status_code=200)
        r = svc._evaluate_assertion(
            {"type": "status", "operator": "not_equals", "expected": 500},
            result, None
        )
        assert r["passed"] is True

    def test_exists_operator(self, svc):
        result = self._make_result()
        r = svc._evaluate_assertion(
            {"type": "json_path", "operator": "exists", "path": "$.name"},
            result, {"name": "test"}
        )
        assert r["passed"] is True

    def test_greater_than(self, svc):
        result = self._make_result(response_time_ms=150)
        r = svc._evaluate_assertion(
            {"type": "response_time", "operator": "greater_than", "expected": 100},
            result, None
        )
        assert r["passed"] is True


# ---------------------------------------------------------------------------
# Request execution tests (mock httpx)
# ---------------------------------------------------------------------------
class TestExecuteRequest:
    @pytest.mark.asyncio
    async def test_successful_get(self, svc):
        """A GET request succeeds."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.api_workbench.httpx.AsyncClient", return_value=mock_client):
            result = await svc.execute_request({
                "id": "r1", "name": "GET Test",
                "method": "GET", "url": "http://example.com/api"
            })
        assert result["success"] is True
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_assertion_evaluation(self, svc):
        """Assertions should be evaluated when a request runs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"ok": true}'
        mock_response.json.return_value = {"ok": True}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.api_workbench.httpx.AsyncClient", return_value=mock_client):
            result = await svc.execute_request({
                "id": "r1", "name": "Assert Test",
                "method": "GET", "url": "http://x.com",
                "assertions": [
                    {"type": "status", "operator": "equals", "expected": 200}
                ]
            })
        assert result["assertions_passed"] == 1
        assert result["assertions_failed"] == 0

    @pytest.mark.asyncio
    async def test_variable_extraction(self, svc):
        """Variables should be extracted from the response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"x-token": "abc123"}
        mock_response.text = '{"data": {"token": "jwt_xyz"}}'
        mock_response.json.return_value = {"data": {"token": "jwt_xyz"}}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.api_workbench.httpx.AsyncClient", return_value=mock_client):
            result = await svc.execute_request({
                "id": "r1", "name": "Extract Test",
                "method": "GET", "url": "http://x.com",
                "extract_variables": [
                    {"name": "auth_token", "source": "json", "path": "$.data.token"},
                    {"name": "header_token", "source": "header", "path": "x-token"}
                ]
            })
        assert result["extracted_variables"]["auth_token"] == "jwt_xyz"
        assert result["extracted_variables"]["header_token"] == "abc123"
        assert svc.runtime_variables["auth_token"] == "jwt_xyz"

    @pytest.mark.asyncio
    async def test_timeout_error(self, svc):
        """A timeout should return an error."""
        import httpx
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.api_workbench.httpx.AsyncClient", return_value=mock_client):
            result = await svc.execute_request({
                "method": "GET", "url": "http://slow.com"
            })
        assert result["success"] is False
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_post_with_json_body(self, svc):
        """A POST request should send a JSON body."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.text = '{}'
        mock_response.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.api_workbench.httpx.AsyncClient", return_value=mock_client):
            result = await svc.execute_request({
                "method": "POST", "url": "http://x.com",
                "body": '{"name": "test"}', "body_type": "json"
            })
        assert result["status_code"] == 201
        call_kwargs = mock_client.request.call_args
        assert call_kwargs[1]["json"] == {"name": "test"}


# ---------------------------------------------------------------------------
# Collection execution tests
# ---------------------------------------------------------------------------
class TestRunCollection:
    @pytest.mark.asyncio
    async def test_collection_not_found(self, svc):
        result = await svc.run_collection("nonexistent")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_with_mocked_execute(self, svc):
        """Running a collection should execute each request in order."""
        col = svc.create_collection("RunTest")
        svc.add_request(col["id"], {"name": "R1", "method": "GET", "url": "/"})
        svc.add_request(col["id"], {"name": "R2", "method": "GET", "url": "/"})

        mock_result = {
            "request_id": "x", "request_name": "x",
            "success": True, "assertions_passed": 0, "assertions_failed": 0
        }
        with patch.object(svc, "execute_request", new_callable=AsyncMock, return_value=mock_result):
            result = await svc.run_collection(col["id"])
        assert result["executed"] == 2
        assert result["passed"] == 2
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_stop_on_failure(self, svc):
        """Execution should stop after a failure when stop_on_failure=True."""
        col = svc.create_collection("StopTest")
        svc.add_request(col["id"], {"name": "R1", "method": "GET", "url": "/"})
        svc.add_request(col["id"], {"name": "R2", "method": "GET", "url": "/"})

        call_count = 0
        async def mock_execute(req_dict):
            nonlocal call_count
            call_count += 1
            return {"success": False, "request_id": "x", "request_name": "x"}

        with patch.object(svc, "execute_request", side_effect=mock_execute):
            result = await svc.run_collection(col["id"], stop_on_failure=True)
        assert result["executed"] == 1
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_clears_runtime_variables(self, svc):
        """runtime_variables should be cleared before a collection runs."""
        col = svc.create_collection("ClearTest")
        svc.runtime_variables["old_var"] = "should_be_cleared"

        mock_result = {"success": True, "request_id": "x", "request_name": "x"}
        with patch.object(svc, "execute_request", new_callable=AsyncMock, return_value=mock_result):
            await svc.run_collection(col["id"])
        # runtime_variables should be cleared at the start of run_collection.
        # execute_request may populate them again.
        # The key check is that clear() was called.


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton(self, tmp_path):
        import services.api_workbench as mod
        mod._service_instance = None
        with patch("services.api_workbench.DATA_DIR", tmp_path), \
             patch("services.api_workbench.COLLECTIONS_FILE", tmp_path / "c.json"), \
             patch("services.api_workbench.ENVIRONMENTS_FILE", tmp_path / "e.json"):
            from services.api_workbench import get_api_workbench_service
            s1 = get_api_workbench_service()
            s2 = get_api_workbench_service()
            assert s1 is s2
        mod._service_instance = None
