"""
DocumentParser 单元测试
覆盖: parse_markdown, parse_sql, parse_openapi, parse_text
"""
import pytest
import json
from core.parsers import DocumentParser


class TestParseMarkdown:
    def test_basic(self):
        md = "# Title\nSome content\n## Section\nMore content"
        result = DocumentParser.parse_markdown(md, source_name="test.md")
        assert len(result) > 0
        assert all("content" in r for r in result)
        assert all("metadata" in r for r in result)

    def test_source_metadata(self):
        md = "# Hello\nWorld"
        result = DocumentParser.parse_markdown(md, source_name="doc.md")
        assert result[0]["metadata"]["source"] == "doc.md"
        assert result[0]["metadata"]["type"] == "markdown"

    def test_empty_content(self):
        result = DocumentParser.parse_markdown("", source_name="empty.md")
        # 空内容可能返回空列表或一个空项
        assert isinstance(result, list)

    def test_enriched_content(self):
        md = "# Main\nBody text"
        result = DocumentParser.parse_markdown(md, source_name="test.md")
        if result:
            assert "test.md" in result[0]["content"]


class TestParseSQL:
    def test_create_table(self):
        sql = "CREATE TABLE users (id INT, name VARCHAR(100));"
        result = DocumentParser.parse_sql(sql, source_name="schema.sql")
        assert len(result) == 1
        assert result[0]["metadata"]["table_name"] == "users"
        assert result[0]["metadata"]["type"] == "sql_schema"

    def test_multiple_tables(self):
        sql = """
        CREATE TABLE users (id INT, name VARCHAR(100));
        CREATE TABLE orders (id INT, user_id INT);
        """
        result = DocumentParser.parse_sql(sql, source_name="schema.sql")
        assert len(result) == 2
        tables = {r["metadata"]["table_name"] for r in result}
        assert "users" in tables
        assert "orders" in tables

    def test_ignores_non_create(self):
        sql = "SELECT * FROM users; INSERT INTO users VALUES (1, 'test');"
        result = DocumentParser.parse_sql(sql, source_name="data.sql")
        assert len(result) == 0

    def test_empty_sql(self):
        result = DocumentParser.parse_sql("", source_name="empty.sql")
        assert result == []

    def test_enriched_content(self):
        sql = "CREATE TABLE products (id INT);"
        result = DocumentParser.parse_sql(sql, source_name="db.sql")
        assert "products" in result[0]["content"]
        assert "db.sql" in result[0]["content"]


class TestParseOpenAPI:
    def test_basic_paths(self):
        spec = {
            "paths": {
                "/api/users": {
                    "get": {"summary": "List users", "description": "Get all users"},
                    "post": {"summary": "Create user", "description": "Create a new user"},
                }
            }
        }
        result = DocumentParser.parse_openapi(json.dumps(spec), source_name="api.json")
        assert len(result) == 2
        methods = {r["metadata"]["method"] for r in result}
        assert "GET" in methods
        assert "POST" in methods

    def test_metadata(self):
        spec = {"paths": {"/api/health": {"get": {"summary": "Health check"}}}}
        result = DocumentParser.parse_openapi(json.dumps(spec), source_name="swagger.json")
        assert result[0]["metadata"]["path"] == "/api/health"
        assert result[0]["metadata"]["type"] == "api_spec"

    def test_invalid_json(self):
        result = DocumentParser.parse_openapi("not valid json", source_name="broken.json")
        assert len(result) == 1
        assert result[0]["metadata"]["type"] == "text_error"

    def test_empty_paths(self):
        spec = {"paths": {}}
        result = DocumentParser.parse_openapi(json.dumps(spec), source_name="empty.json")
        assert result == []


class TestParseText:
    def test_basic(self):
        result = DocumentParser.parse_text("Hello world", source_name="readme.txt")
        assert len(result) == 1
        assert result[0]["content"] == "Hello world"
        assert result[0]["metadata"]["source"] == "readme.txt"
        assert result[0]["metadata"]["type"] == "text"

    def test_empty(self):
        result = DocumentParser.parse_text("", source_name="empty.txt")
        assert len(result) == 1
        assert result[0]["content"] == ""
