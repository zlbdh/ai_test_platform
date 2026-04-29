"""
api_doc_generator 单元测试
覆盖: 路由提取、标签/参数/请求体推断、Markdown/JSON/文件导出
"""
import json

from fastapi import FastAPI

from core.api_doc_generator import ApiDocGenerator, ApiEndpoint, generate_api_docs


class TestApiDocGenerator:
    def test_extract_from_none_app_returns_empty(self):
        generator = ApiDocGenerator()
        assert generator.extract_from_fastapi() == []

    def test_extract_from_fastapi_builds_endpoints(self):
        app = FastAPI()

        @app.get("/api/auth/login/{user_id}")
        async def login(user_id: str):
            """
            用户登录

            登录接口说明
            """
            return {"user_id": user_id}

        @app.patch("/profile")
        async def update_profile():
            return {"ok": True}

        generator = ApiDocGenerator(app)
        endpoints = generator.extract_from_fastapi()

        login_endpoint = next(ep for ep in endpoints if ep.path == "/api/auth/login/{user_id}" and ep.method == "GET")
        patch_endpoint = next(ep for ep in endpoints if ep.path == "/profile" and ep.method == "PATCH")

        assert login_endpoint.summary == "用户登录"
        assert login_endpoint.tags == ["auth"]
        assert login_endpoint.parameters == [{
            "name": "user_id",
            "in": "path",
            "required": True,
            "type": "string",
        }]
        assert patch_endpoint.request_body is not None
        assert all(ep.method != "HEAD" for ep in endpoints)
        assert all(ep.method != "OPTIONS" for ep in endpoints)

    def test_extract_tags_for_non_api_path(self):
        generator = ApiDocGenerator()
        assert generator._extract_tags("/health") == ["health"]
        assert generator._extract_tags("/") == ["default"]

    def test_generate_markdown_contains_sections(self):
        generator = ApiDocGenerator()
        generator.endpoints = [
            ApiEndpoint(
                path="/api/users/{id}",
                method="GET",
                summary="查询用户",
                description="查询用户详情",
                tags=["users"],
                parameters=[{"name": "id", "in": "path", "required": True, "type": "string"}],
                request_body=None,
                responses={"200": {"description": "Success"}},
            )
        ]
        markdown = generator.generate_markdown("Users API")

        assert "# Users API" in markdown
        assert "- [USERS](#users)" in markdown
        assert "### 🟢 GET `/api/users/{id}`" in markdown
        assert "| id | path | True | string |" in markdown

    def test_generate_openapi_and_export(self):
        generator = ApiDocGenerator()
        generator.endpoints = [
            type("Endpoint", (), {
                "path": "/api/demo",
                "method": "POST",
                "summary": "Demo",
                "description": "Demo description",
                "tags": ["demo"],
                "parameters": [],
                "request_body": {"content": {"application/json": {"schema": {"type": "object"}}}},
                "responses": {"200": {"description": "Success"}},
            })()
        ]

        openapi = generator.generate_openapi("Demo API", "2.0.0")
        exported = generator.export_json()

        assert openapi["info"]["title"] == "Demo API"
        assert openapi["paths"]["/api/demo"]["post"]["requestBody"] is not None
        assert json.loads(exported)["info"]["title"] == "API Documentation"

    def test_generate_markdown_and_save_files(self, tmp_path):
        generator = ApiDocGenerator()
        generator.endpoints = [
            type("Endpoint", (), {
                "path": "/api/demo/{id}",
                "method": "GET",
                "summary": "查询 Demo",
                "description": "查询 Demo 明细",
                "tags": ["demo"],
                "parameters": [{"name": "id", "in": "path", "required": True, "type": "string"}],
                "request_body": None,
                "responses": {"200": {"description": "Success"}},
            })()
        ]

        markdown = generator.generate_markdown("Demo API")
        md_path = tmp_path / "demo.md"
        json_path = tmp_path / "demo.json"
        fallback_path = tmp_path / "demo.unknown"

        generator.save_to_file(str(md_path), "markdown")
        generator.save_to_file(str(json_path), "json")
        generator.save_to_file(str(fallback_path), "unknown")

        assert "## Table of Contents" in markdown
        assert "### 🟢 GET `/api/demo/{id}`" in markdown
        assert md_path.read_text(encoding="utf-8").startswith("# API Documentation")
        assert json.loads(json_path.read_text(encoding="utf-8"))["openapi"] == "3.0.0"
        assert json.loads(fallback_path.read_text(encoding="utf-8"))["openapi"] == "3.0.0"

    def test_generate_api_docs_helper(self, tmp_path):
        app = FastAPI()

        @app.post("/api/items")
        async def create_item():
            """创建项目"""
            return {"ok": True}

        output_path = tmp_path / "api.md"
        content = generate_api_docs(app, str(output_path), "markdown")

        assert "AI Test Platform API" in content
        assert output_path.exists()

    def test_generate_api_docs_helper_json(self):
        app = FastAPI()

        @app.put("/api/items/{item_id}")
        async def update_item(item_id: str):
            """更新项目"""
            return {"item_id": item_id}

        content = generate_api_docs(app, format="json")
        data = json.loads(content)

        assert data["paths"]["/api/items/{item_id}"]["put"]["summary"] == "更新项目"
