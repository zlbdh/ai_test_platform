"""
GraphQLTestService unit tests.
Covers data classes, _get_value_by_path, assert_response, execute with mocked httpx,
generate_query_from_schema, and the factory function.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.graphql_testing import (
    GraphQLRequest, GraphQLResponse, GraphQLAssertion,
    GraphQLTestService, create_graphql_service
)


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------
class TestGraphQLRequest:
    def test_creation(self):
        r = GraphQLRequest(query="{ users { id } }")
        assert r.variables is None
        assert r.operation_name is None

    def test_with_variables(self):
        r = GraphQLRequest(query="query($id: ID!){ user(id: $id) { name } }",
                           variables={"id": "1"}, operation_name="GetUser")
        assert r.variables == {"id": "1"}


class TestGraphQLResponse:
    def test_creation(self):
        r = GraphQLResponse(data={"user": {"name": "A"}}, errors=None,
                            extensions=None, status_code=200, response_time_ms=50)
        assert r.status_code == 200


class TestGraphQLAssertion:
    def test_creation(self):
        a = GraphQLAssertion(path="data.user.name", operator="eq", expected="Alice")
        assert a.operator == "eq"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def svc():
    return GraphQLTestService(endpoint="http://localhost:4000/graphql")


# ---------------------------------------------------------------------------
# _get_value_by_path
# ---------------------------------------------------------------------------
class TestGetValueByPath:
    def test_nested_dict(self, svc):
        data = {"a": {"b": {"c": 42}}}
        assert svc._get_value_by_path(data, "a.b.c") == 42

    def test_list_index(self, svc):
        data = {"items": [10, 20, 30]}
        assert svc._get_value_by_path(data, "items.1") == 20

    def test_missing_key(self, svc):
        assert svc._get_value_by_path({"a": 1}, "b") is None


# ---------------------------------------------------------------------------
# assert_response
# ---------------------------------------------------------------------------
class TestAssertResponse:
    def _response(self, data):
        return GraphQLResponse(data=data, errors=None, extensions=None,
                               status_code=200, response_time_ms=10)

    def test_eq_pass(self, svc):
        resp = self._response({"user": {"name": "Alice"}})
        results = svc.assert_response(resp, [
            GraphQLAssertion(path="data.user.name", operator="eq", expected="Alice")
        ])
        assert results[0]["passed"] is True

    def test_eq_fail(self, svc):
        resp = self._response({"user": {"name": "Bob"}})
        results = svc.assert_response(resp, [
            GraphQLAssertion(path="data.user.name", operator="eq", expected="Alice")
        ])
        assert results[0]["passed"] is False

    def test_ne(self, svc):
        resp = self._response({"x": 1})
        results = svc.assert_response(resp, [
            GraphQLAssertion(path="data.x", operator="ne", expected=2)
        ])
        assert results[0]["passed"] is True

    def test_contains_str(self, svc):
        resp = self._response({"msg": "hello world"})
        results = svc.assert_response(resp, [
            GraphQLAssertion(path="data.msg", operator="contains", expected="world")
        ])
        assert results[0]["passed"] is True

    def test_contains_list(self, svc):
        resp = self._response({"tags": ["a", "b"]})
        results = svc.assert_response(resp, [
            GraphQLAssertion(path="data.tags", operator="contains", expected="a")
        ])
        assert results[0]["passed"] is True

    def test_exists(self, svc):
        resp = self._response({"key": "val"})
        results = svc.assert_response(resp, [
            GraphQLAssertion(path="data.key", operator="exists", expected=True)
        ])
        assert results[0]["passed"] is True

    def test_type(self, svc):
        resp = self._response({"count": 5})
        results = svc.assert_response(resp, [
            GraphQLAssertion(path="data.count", operator="type", expected="int")
        ])
        assert results[0]["passed"] is True


# ---------------------------------------------------------------------------
# execute (mock httpx)
# ---------------------------------------------------------------------------
class TestExecute:
    @pytest.mark.asyncio
    async def test_success(self, svc):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"user": {"id": "1"}}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            req = GraphQLRequest(query="{ user { id } }")
            resp = await svc.execute(req)

        assert resp.status_code == 200
        assert resp.data == {"user": {"id": "1"}}

    @pytest.mark.asyncio
    async def test_with_variables(self, svc):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": None, "errors": [{"message": "err"}]}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            req = GraphQLRequest(query="q", variables={"id": 1}, operation_name="Op")
            resp = await svc.execute(req)

        assert resp.errors is not None


# ---------------------------------------------------------------------------
# generate_query_from_schema
# ---------------------------------------------------------------------------
class TestGenerateQuery:
    def test_no_schema(self, svc):
        assert svc.generate_query_from_schema("User") == ""

    def test_with_schema(self, svc):
        svc.schema = {
            "types": [
                {"name": "User", "fields": [
                    {"name": "id"}, {"name": "name"}, {"name": "email"}
                ]}
            ]
        }
        query = svc.generate_query_from_schema("User")
        assert "id" in query
        assert "name" in query

    def test_unknown_type(self, svc):
        svc.schema = {"types": [{"name": "Post", "fields": [{"name": "title"}]}]}
        query = svc.generate_query_from_schema("Unknown")
        assert "id" in query  # fallback


# ---------------------------------------------------------------------------
# Factory.
# ---------------------------------------------------------------------------
class TestFactory:
    def test_create(self):
        svc = create_graphql_service("http://localhost/graphql", {"Auth": "Bearer x"})
        assert isinstance(svc, GraphQLTestService)
        assert svc.headers["Auth"] == "Bearer x"
