"""
API Documentation Generator - API 文档自动生成器

自动生成 OpenAPI/Swagger 格式的 API 文档：
- 从 FastAPI 提取路由信息
- 生成 Markdown 文档
- 支持导出多种格式
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ApiEndpoint:
    """API 端点"""
    path: str
    method: str
    summary: str
    description: str
    tags: List[str]
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[str, Dict[str, Any]]


class ApiDocGenerator:
    """API 文档生成器"""
    
    def __init__(self, app=None):
        self.app = app
        self.endpoints: List[ApiEndpoint] = []
    
    def extract_from_fastapi(self, app=None) -> List[ApiEndpoint]:
        """从 FastAPI 应用提取端点信息"""
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
        """从路径提取标签"""
        parts = [part for part in path.strip('/').split('/') if part]
        if len(parts) >= 2 and parts[0] == "api":
            return [parts[1]]  # e.g., /api/auth/login -> auth
        if parts:
            return [parts[0]]
        return ["default"]
    
    def _extract_parameters(self, route) -> List[Dict[str, Any]]:
        """提取参数"""
        params = []
        path = route.path
        
        # 路径参数
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
        """提取请求体"""
        # 简化实现，实际可从 Pydantic 模型提取
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
        """生成 OpenAPI 3.0 规范"""
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
        """生成 Markdown 文档"""
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
        
        # 按标签分组
        by_tag: Dict[str, List[ApiEndpoint]] = {}
        for ep in self.endpoints:
            tag = ep.tags[0] if ep.tags else "default"
            if tag not in by_tag:
                by_tag[tag] = []
            by_tag[tag].append(ep)
        
        # 目录
        lines.append("## Table of Contents")
        lines.append("")
        for tag in sorted(by_tag.keys()):
            lines.append(f"- [{tag.upper()}](#{tag})")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 各分组
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
        """生成方法徽章"""
        colors = {
            "GET": "🟢",
            "POST": "🟡",
            "PUT": "🔵",
            "DELETE": "🔴",
            "PATCH": "🟣"
        }
        return f"{colors.get(method, '⚪')} {method}"
    
    def export_json(self) -> str:
        """导出为 JSON"""
        openapi = self.generate_openapi()
        return json.dumps(openapi, ensure_ascii=False, indent=2)
    
    def save_to_file(self, path: str, format: str = "markdown"):
        """保存到文件"""
        if format == "markdown":
            content = self.generate_markdown()
        elif format == "json":
            content = self.export_json()
        else:
            content = self.export_json()
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)


def generate_api_docs(app, output_path: str = None, format: str = "markdown") -> str:
    """生成 API 文档"""
    generator = ApiDocGenerator()
    generator.extract_from_fastapi(app)
    
    if format == "markdown":
        content = generator.generate_markdown("AI Test Platform API")
    else:
        content = generator.export_json()
    
    if output_path:
        generator.save_to_file(output_path, format)
    
    return content
