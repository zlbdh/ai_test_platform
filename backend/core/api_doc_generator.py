"""
API Documentation Generator - automatic API documentation

Generate API documentation in OpenAPI/Swagger format:
- Extract route information from FastAPI
- Generate Markdown documentation
- Export in multiple formats
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ApiEndpoint:
    """API endpoint"""
    path: str
    method: str
    summary: str
    description: str
    tags: List[str]
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[str, Dict[str, Any]]


class ApiDocGenerator:
    """API documentation generator"""

    def __init__(self, app=None):
        self.app = app
        self.endpoints: List[ApiEndpoint] = []

    def extract_from_fastapi(self, app=None) -> List[ApiEndpoint]:
        """Extract endpoint information from a FastAPI application"""
        app = app or self.app
        if app is None:
            self.endpoints = []
            return []

        endpoints = []

        for route in app.routes:
            if not hasattr(route, 'path'):
                continue

            methods = sorted(getattr(route, 'methods', {'GET'}))
            for method in methods:
                if method in {'HEAD', 'OPTIONS'}:
                    continue

                endpoint = route.endpoint if hasattr(route, 'endpoint') else None
                doc = (endpoint.__doc__ or "").strip() if endpoint else ""
                summary = next((line.strip() for line in doc.splitlines() if line.strip()), route.path)

                endpoints.append(ApiEndpoint(
                    path=route.path,
                    method=method,
                    summary=summary,
                    description=doc or "",
                    tags=self._extract_tags(route.path),
                    parameters=self._extract_parameters(route),
                    request_body=self._extract_request_body(route),
                    responses={"200": {"description": "Success"}}
                ))

        self.endpoints = endpoints
        return endpoints

    def _extract_tags(self, path: str) -> List[str]:
        """Extract tags from the path"""
        parts = [part for part in path.strip('/').split('/') if part]
        if len(parts) >= 2 and parts[0] == "api":
            return [parts[1]]  # e.g., /api/auth/login -> auth
        if parts:
            return [parts[0]]
        return ["default"]

    def _extract_parameters(self, route) -> List[Dict[str, Any]]:
        """Extract parameters"""
        params = []
        path = route.path

        # Path parameters
        import re
        path_params = re.findall(r'\{(\w+)\}', path)
        for p in path_params:
            params.append({
                "name": p,
                "in": "path",
                "required": True,
                "type": "string"
            })

        return params

    def _extract_request_body(self, route) -> Optional[Dict[str, Any]]:
        """Extract the request body"""
        # Simplified implementation; production code can extract this from Pydantic models
        if hasattr(route, 'methods') and {'POST', 'PUT', 'PATCH'} & set(route.methods):
            return {
                "content": {
                    "application/json": {
                        "schema": {"type": "object"}
                    }
                }
            }
        return None

    def generate_openapi(self, title: str = "API Documentation", version: str = "1.0.0") -> Dict[str, Any]:
        """Generate an OpenAPI 3.0 specification"""
        paths = {}

        for ep in self.endpoints:
            if ep.path not in paths:
                paths[ep.path] = {}

            paths[ep.path][ep.method.lower()] = {
                "summary": ep.summary,
                "description": ep.description,
                "tags": ep.tags,
                "parameters": ep.parameters,
                "responses": ep.responses
            }

            if ep.request_body:
                paths[ep.path][ep.method.lower()]["requestBody"] = ep.request_body

        return {
            "openapi": "3.0.0",
            "info": {
                "title": title,
                "version": version,
                "description": f"Generated at {datetime.now().isoformat()}"
            },
            "paths": paths
        }

    def generate_markdown(self, title: str = "API Documentation") -> str:
        """Generate Markdown documentation"""
        lines = [
            f"# {title}",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
            f"**Total Endpoints: {len(self.endpoints)}**",
            "",
            "---",
            ""
        ]

        # Group by tag
        by_tag: Dict[str, List[ApiEndpoint]] = {}
        for ep in self.endpoints:
            tag = ep.tags[0] if ep.tags else "default"
            if tag not in by_tag:
                by_tag[tag] = []
            by_tag[tag].append(ep)

        # Table of contents
        lines.append("## Table of Contents")
        lines.append("")
        for tag in sorted(by_tag.keys()):
            lines.append(f"- [{tag.upper()}](#{tag})")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Groups
        for tag in sorted(by_tag.keys()):
            lines.append(f"## {tag.upper()}")
            lines.append("")

            for ep in sorted(by_tag[tag], key=lambda x: x.path):
                method_badge = self._method_badge(ep.method)
                lines.append(f"### {method_badge} `{ep.path}`")
                lines.append("")
                lines.append(f"**{ep.summary}**")
                lines.append("")

                if ep.description and ep.description != ep.summary:
                    lines.append(ep.description)
                    lines.append("")

                if ep.parameters:
                    lines.append("**Parameters:**")
                    lines.append("")
                    lines.append("| Name | In | Required | Type |")
                    lines.append("|------|-----|----------|------|")
                    for p in ep.parameters:
                        lines.append(f"| {p['name']} | {p['in']} | {p.get('required', False)} | {p.get('type', 'string')} |")
                    lines.append("")

                lines.append("---")
                lines.append("")

        return '\n'.join(lines)

    def _method_badge(self, method: str) -> str:
        """Generate a method badge"""
        colors = {
            "GET": "🟢",
            "POST": "🟡",
            "PUT": "🔵",
            "DELETE": "🔴",
            "PATCH": "🟣"
        }
        return f"{colors.get(method, '⚪')} {method}"

    def export_json(self) -> str:
        """Export as JSON"""
        openapi = self.generate_openapi()
        return json.dumps(openapi, ensure_ascii=False, indent=2)

    def save_to_file(self, path: str, format: str = "markdown"):
        """Save to a file"""
        if format == "markdown":
            content = self.generate_markdown()
        elif format == "json":
            content = self.export_json()
        else:
            content = self.export_json()

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)


def generate_api_docs(app, output_path: str = None, format: str = "markdown") -> str:
    """Generate API documentation"""
    generator = ApiDocGenerator()
    generator.extract_from_fastapi(app)

    if format == "markdown":
        content = generator.generate_markdown("AI Test Platform API")
    else:
        content = generator.export_json()

    if output_path:
        generator.save_to_file(output_path, format)

    return content
