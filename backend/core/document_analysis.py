"""
Document detection and structured analysis

Goals:
- Identify document types (requirements, development, API, database, general text)
- Score completeness, testability, and quality
- Extract structured signals useful for test design
- Provide more reliable input for subsequent test-case generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Dict, List, Optional


@dataclass
class AnalysisIssue:
    issue_id: str
    severity: str
    category: str
    message: str
    suggestion: str


@dataclass
class DocumentAnalysis:
    document_type: str
    document_label: str
    quality_score: float
    completeness_score: float
    testability_score: float
    recommended_test_types: List[str] = field(default_factory=list)
    issues: List[AnalysisIssue] = field(default_factory=list)
    extracted: Dict[str, List[str]] = field(default_factory=dict)
    next_actions: List[str] = field(default_factory=list)


class DocumentAnalyzer:
    """Lightweight document analyzer for test design."""

    _DOC_LABELS = {
        "requirement_prd": "Requirements document",
        "development_design": "Development document",
        "api_spec": "API specification",
        "database_schema": "Database design",
        "general_text": "General text",
    }

    _VAGUE_TERMS = [
        "尽快",
        "合理",
        "适当",
        "友好",
        "稳定",
        "必要时",
        "支持更多",
        "优化体验",
        "尽量",
        "提升性能",
        "as soon as possible", "reasonable", "appropriate", "friendly", "stable",
        "if necessary", "support more", "improve experience", "as much as possible", "improve performance",
    ]

    _ACTOR_PATTERN = re.compile(r"(用户|管理员|商家|运营|访客|游客|客服|审计员|开发人员|测试人员|(?i:\b(?:users?|administrators?|merchants?|operators?|visitors?|guests?|support agents?|auditors?|developers?|testers?)\b))")
    _API_PATTERN = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[A-Za-z0-9_\-/{}/.]+)")
    _ERROR_CODE_PATTERN = re.compile(r"\b(?:ERR_[A-Z0-9_]+|[45]\d{2})\b")
    _SQL_TABLE_PATTERN = re.compile(r"CREATE\s+TABLE\s+[`\"\[]?(\w+)[`\"\]]?", re.IGNORECASE)
    _SECTION_HEADER_PATTERN = re.compile(r"^\s{0,3}(?:#+\s+|##?\s+)?(.+)$")
    _NUMBERED_LINE_PATTERN = re.compile(r"^\s*(?:\d+[.)、]|[-*])\s*(.+)$")
    _CONSTRAINT_PATTERN = re.compile(
        r"(不少于|不大于|不超过|不低于|至少|至多|最大|最小|上限|下限|"
        r"长度|范围|必填|非空|唯一|枚举|有效期|超时|响应时间|并发|TPS|QPS|权限|"
        r"大于|小于|高于|低于|早于|晚于|>=|<=|==|>|<|"
        r"(?i:\b(?:at least|at most|no more than|no less than|maximum|minimum|upper limit|lower limit|length|range|required|nonempty|unique|enum|expiration|timeout|response time|concurrent|concurrency|permissions?|greater than|less than|earlier than|later than)\b))"
    )
    _OPENAPI_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}

    def analyze(
        self,
        content: str,
        title: str = "",
        parsed_result: Optional[object] = None,
    ) -> DocumentAnalysis:
        normalized = content or ""
        doc_type = self.detect_document_type(normalized, title)
        extracted = self._extract_signals(normalized, doc_type, parsed_result)
        issues = self._detect_issues(normalized, doc_type, extracted)
        completeness_score = self._score_completeness(normalized, doc_type, extracted)
        testability_score = self._score_testability(normalized, doc_type, extracted, issues)
        quality_score = round((completeness_score * 0.45 + testability_score * 0.55), 2)

        return DocumentAnalysis(
            document_type=doc_type,
            document_label=self._DOC_LABELS.get(doc_type, "General text"),
            quality_score=quality_score,
            completeness_score=completeness_score,
            testability_score=testability_score,
            recommended_test_types=self._recommend_test_types(doc_type, extracted),
            issues=issues,
            extracted=extracted,
            next_actions=self._build_next_actions(doc_type, issues, extracted),
        )

    def detect_document_type(self, content: str, title: str = "") -> str:
        combined = f"{title}\n{content}".lower()

        if any(token in combined for token in ["openapi", "swagger", '"paths"', "api接口", "接口定义", "api specification", "api definition"]):
            return "api_spec"
        if "create table" in combined or "表结构" in combined or "数据库设计" in combined or "database schema" in combined or "database design" in combined:
            return "database_schema"
        if any(token in combined for token in ["技术方案", "设计说明", "模块设计", "架构设计", "时序图", "部署方案", "开发文档", "technical design", "design specification", "module design", "architecture design", "sequence diagram", "deployment plan", "development document"]):
            return "development_design"
        if any(token in combined for token in ["prd", "需求文档", "功能需求", "验收标准", "用户故事", "业务规则", "requirements document", "functional requirements", "acceptance criteria", "user stories", "business rules"]):
            return "requirement_prd"
        return "general_text"

    def _extract_signals(
        self,
        content: str,
        doc_type: str,
        parsed_result: Optional[object],
    ) -> Dict[str, List[str]]:
        openapi_details = self._extract_openapi_details(content) if doc_type == "api_spec" else self._empty_openapi_details()
        database_details = self._extract_database_details(content) if doc_type == "database_schema" else self._empty_database_details()
        actors = self._unique(self._ACTOR_PATTERN.findall(content))
        flows = self._extract_numbered_lines(content)
        api_endpoints = self._unique(self._extract_api_endpoints(content) + openapi_details["api_endpoints"])
        error_codes = self._unique(self._ERROR_CODE_PATTERN.findall(content))
        database_objects = self._unique(self._extract_database_objects(content) + database_details["database_objects"])
        data_constraints = self._unique(self._extract_data_constraints(content) + database_details["data_constraints"])

        business_rules: List[str] = []
        if parsed_result is not None and getattr(parsed_result, "rules", None):
            business_rules = self._unique(
                [
                    getattr(rule, "description", "").strip()
                    for rule in getattr(parsed_result, "rules", [])
                    if getattr(rule, "description", "").strip()
                ]
            )
        if not business_rules:
            business_rules = self._extract_rule_like_lines(content)

        return {
            "actors": actors,
            "flows": flows,
            "business_rules": business_rules,
            "data_constraints": data_constraints,
            "api_endpoints": api_endpoints,
            "api_parameters": openapi_details["api_parameters"],
            "response_statuses": openapi_details["response_statuses"],
            "schema_entities": openapi_details["schema_entities"],
            "error_codes": error_codes,
            "database_objects": database_objects,
            "database_columns": database_details["database_columns"],
            "database_indexes": database_details["database_indexes"],
            "database_relations": database_details["database_relations"],
        }

    def _detect_issues(
        self,
        content: str,
        doc_type: str,
        extracted: Dict[str, List[str]],
    ) -> List[AnalysisIssue]:
        issues: List[AnalysisIssue] = []

        if doc_type == "requirement_prd":
            if not extracted["flows"]:
                issues.append(self._issue(
                    "warning", "completeness",
                    "No clear business workflow or step descriptions were identified.",
                    "Add main workflows, exception paths, and key preconditions."
                ))
            if not extracted["data_constraints"]:
                issues.append(self._issue(
                    "warning", "testability",
                    "Data constraints suitable for direct test assertions are missing.",
                    "Add verifiable length, range, state, timing, and permission conditions."
                ))
            if not self._contains_any(content, ["验收标准", "期望结果", "应当", "必须", "成功", "失败", "acceptance criteria", "expected results", "shall", "must", "success", "failure"]):
                issues.append(self._issue(
                    "error", "testability",
                    "The document lacks explicit acceptance criteria, reducing the reliability of generated tests.",
                    "Add verifiable success/failure criteria and boundary-handling rules."
                ))

        if doc_type == "development_design":
            if not extracted["api_endpoints"] and not extracted["database_objects"]:
                issues.append(self._issue(
                    "warning", "completeness",
                    "No interface definitions or database objects were identified in the development document.",
                    "Add interfaces, field constraints, state transitions, or module interaction descriptions."
                ))
            if not extracted["error_codes"]:
                issues.append(self._issue(
                    "info", "testability",
                    "No error codes or exception scenarios were identified.",
                    "Add failure scenarios, retry strategies, and rollback/compensation logic."
                ))

        if doc_type == "api_spec":
            if not extracted["api_endpoints"]:
                issues.append(self._issue(
                    "error", "completeness",
                    "No testable API paths were identified in the API document.",
                    "Check that the OpenAPI/Swagger structure is complete."
                ))
            if not extracted.get("api_parameters", []):
                issues.append(self._issue(
                    "info", "testability",
                    "No parameter definitions were identified in the API document.",
                    "Add path/query parameters, request-body fields, and required-field constraints."
                ))
            if not extracted.get("response_statuses", []):
                issues.append(self._issue(
                    "warning", "completeness",
                    "The API document lacks explicit response-status definitions.",
                    "Add response statuses for success, validation failure, and system errors."
                ))
            if not extracted["error_codes"]:
                issues.append(self._issue(
                    "info", "testability",
                    "The API document lacks error-code or exception-response definitions.",
                    "Add 4xx/5xx responses and error-code meanings."
                ))

        if doc_type == "database_schema" and not extracted["database_objects"]:
            issues.append(self._issue(
                "warning", "completeness",
                "No table definitions were identified in the database document.",
                "Add CREATE TABLE statements, indexes, constraints, or a data dictionary."
            ))
        if doc_type == "database_schema" and extracted["database_objects"] and not extracted.get("database_columns", []):
            issues.append(self._issue(
                "warning", "completeness",
                "Table names were identified in the database document, but column definitions were not.",
                "Add column names, types, and column-level constraints such as nullability, uniqueness, and defaults."
            ))

        vague_hits = [term for term in self._VAGUE_TERMS if term.lower() in content.lower()]
        if vague_hits:
            issues.append(self._issue(
                "info", "ambiguity",
                f"Vague wording detected: {', '.join(vague_hits[:4])}.",
                "Rewrite vague goals as measurable, verifiable descriptions."
            ))

        if len(content.strip()) < 80:
            issues.append(self._issue(
                "warning", "completeness",
                "The document is short and may not support high-quality test design.",
                "Add business context, inputs/outputs, boundaries, and error handling."
            ))

        return issues

    def _score_completeness(
        self,
        content: str,
        doc_type: str,
        extracted: Dict[str, List[str]],
    ) -> float:
        score = 0.35
        score += min(len(extracted["business_rules"]) * 0.03, 0.18)
        score += min(len(extracted["flows"]) * 0.03, 0.15)
        score += min(len(extracted["data_constraints"]) * 0.03, 0.12)

        if doc_type in {"api_spec", "development_design"}:
            score += min(len(extracted["api_endpoints"]) * 0.04, 0.16)
        if doc_type == "api_spec":
            score += min(len(extracted.get("api_parameters", [])) * 0.02, 0.12)
            score += min(len(extracted.get("response_statuses", [])) * 0.02, 0.1)
            score += min(len(extracted.get("schema_entities", [])) * 0.02, 0.08)
        if doc_type == "database_schema":
            score += min(len(extracted["database_objects"]) * 0.04, 0.16)
            score += min(len(extracted.get("database_columns", [])) * 0.01, 0.1)
            score += min(len(extracted.get("database_indexes", [])) * 0.02, 0.08)
            score += min(len(extracted.get("database_relations", [])) * 0.02, 0.08)
        if self._contains_any(content, ["异常", "失败", "错误", "error", "rollback", "回滚", "exception", "failure"]):
            score += 0.05
        if self._contains_any(content, ["验收标准", "期望结果", "acceptance", "expected"]):
            score += 0.05

        return round(min(score, 1.0), 2)

    def _score_testability(
        self,
        content: str,
        doc_type: str,
        extracted: Dict[str, List[str]],
        issues: List[AnalysisIssue],
    ) -> float:
        score = 0.4
        measurable_count = len(re.findall(r"(不少于|不大于|<=|>=|<|>|响应时间|并发|ms|分钟|秒|长度|次数|\d+|(?i:\b(?:at least|at most|response time|concurrent|concurrency|minutes?|seconds?|length|count)\b))", content))
        score += min(measurable_count * 0.02, 0.16)
        score += min(len(extracted["error_codes"]) * 0.02, 0.08)
        score += min(len(extracted["actors"]) * 0.02, 0.08)

        if doc_type == "api_spec":
            score += min(len(extracted["api_endpoints"]) * 0.03, 0.12)
            score += min(len(extracted.get("api_parameters", [])) * 0.015, 0.1)
            score += min(len(extracted.get("response_statuses", [])) * 0.015, 0.08)
        if doc_type == "database_schema":
            score += min(len(extracted["database_objects"]) * 0.03, 0.12)
            score += min(len(extracted.get("database_columns", [])) * 0.01, 0.08)
            score += min(len(extracted.get("database_relations", [])) * 0.02, 0.08)

        penalty = 0.0
        for issue in issues:
            if issue.severity == "error":
                penalty += 0.08
            elif issue.severity == "warning":
                penalty += 0.04
            else:
                penalty += 0.01
        score -= min(penalty, 0.24)

        return round(max(0.0, min(score, 1.0)), 2)

    def _recommend_test_types(self, doc_type: str, extracted: Dict[str, List[str]]) -> List[str]:
        recommended: List[str] = []

        if doc_type in {"requirement_prd", "general_text"}:
            recommended.extend(["ui_e2e", "business_flow"])
        if doc_type in {"development_design", "api_spec"} or extracted["api_endpoints"]:
            recommended.extend(["api_rest", "contract"])
        if (
            extracted["data_constraints"]
            or extracted["database_objects"]
            or extracted.get("api_parameters", [])
            or extracted.get("database_columns", [])
        ):
            recommended.extend(["data_validation"])
        if self._contains_security_signals(extracted["business_rules"] + extracted["flows"] + extracted["data_constraints"]):
            recommended.append("security")
        if self._contains_any(" ".join(extracted["business_rules"] + extracted["flows"] + extracted["data_constraints"]), ["性能", "响应时间", "并发", "吞吐", "performance", "response time", "concurrent", "concurrency", "throughput"]):
            recommended.append("performance")

        return self._unique(recommended)

    def _build_next_actions(
        self,
        doc_type: str,
        issues: List[AnalysisIssue],
        extracted: Dict[str, List[str]],
    ) -> List[str]:
        actions: List[str] = []

        if any(issue.severity == "error" for issue in issues):
            actions.append("Resolve critical document gaps before generating formal test cases.")
        if extracted["api_endpoints"]:
            actions.append("Prioritize API/contract tests and add exception-response assertions.")
        if extracted.get("api_parameters", []):
            actions.append("Add validation scenarios for required parameters, boundary values, and invalid combinations.")
        if extracted.get("response_statuses", []):
            actions.append("Cover response statuses for success, business validation failures, and system errors.")
        if extracted["database_objects"]:
            actions.append("Add data consistency, constraint validation, and rollback scenarios.")
        if extracted.get("database_relations", []):
            actions.append("Add foreign-key integrity, cascading update/delete, and relationship-query scenarios.")
        if extracted["flows"]:
            actions.append("Separate scenarios into main workflows, exception paths, and boundary paths.")
        if doc_type == "requirement_prd":
            actions.append("Link requirement sections to test cases for traceability.")
        if doc_type == "development_design":
            actions.append("Map technical constraints to API, data, and fault-tolerance test cases.")

        if not actions:
            actions.append("Document information is limited; add workflows, constraints, and error handling before generation.")

        return self._unique(actions)

    def _extract_numbered_lines(self, content: str) -> List[str]:
        results: List[str] = []
        for line in content.splitlines():
            match = self._NUMBERED_LINE_PATTERN.match(line)
            if match:
                candidate = match.group(1).strip()
                if len(candidate) >= 6:
                    results.append(candidate)
        return self._unique(results[:12])

    def _extract_api_endpoints(self, content: str) -> List[str]:
        endpoints = [f"{method.upper()} {path}" for method, path in self._API_PATTERN.findall(content)]
        return self._unique(endpoints[:20])

    def _extract_openapi_paths(self, content: str) -> List[str]:
        matches = re.findall(r'"(/[^"]+)"\s*:\s*\{', content)
        return self._unique(matches[:20])

    def _extract_openapi_operations(self, content: str) -> List[str]:
        payload = self._safe_load_json(content)
        if payload:
            paths = payload.get("paths", {})
            results: List[str] = []
            for path, methods in paths.items():
                if not isinstance(methods, dict):
                    continue
                for method in methods.keys():
                    if method.lower() in self._OPENAPI_METHODS:
                        results.append(f"{method.upper()} {path}")
            if results:
                return self._unique(results[:20])

        return self._extract_openapi_paths(content)

    def _empty_openapi_details(self) -> Dict[str, List[str]]:
        return {
            "api_endpoints": [],
            "api_parameters": [],
            "response_statuses": [],
            "schema_entities": [],
        }

    def _extract_openapi_details(self, content: str) -> Dict[str, List[str]]:
        payload = self._safe_load_json(content)
        if not payload:
            return self._empty_openapi_details()

        paths = payload.get("paths", {})
        schemas = payload.get("components", {}).get("schemas", {})
        details = self._empty_openapi_details()

        for schema_name in schemas.keys():
            details["schema_entities"].append(str(schema_name))

        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            shared_parameters = methods.get("parameters", [])
            if not isinstance(shared_parameters, list):
                shared_parameters = []

            for method, operation in methods.items():
                if method.lower() not in self._OPENAPI_METHODS or not isinstance(operation, dict):
                    continue

                endpoint = f"{method.upper()} {path}"
                details["api_endpoints"].append(endpoint)

                parameters = [*shared_parameters]
                operation_parameters = operation.get("parameters", [])
                if isinstance(operation_parameters, list):
                    parameters.extend(operation_parameters)

                for parameter in parameters:
                    label = self._format_openapi_parameter(endpoint, parameter)
                    if label:
                        details["api_parameters"].append(label)

                request_body = operation.get("requestBody")
                if isinstance(request_body, dict):
                    content_map = request_body.get("content", {})
                    if isinstance(content_map, dict):
                        for schema_wrapper in content_map.values():
                            if not isinstance(schema_wrapper, dict):
                                continue
                            schema = schema_wrapper.get("schema")
                            for field in self._extract_openapi_schema_fields(schema, schemas):
                                details["api_parameters"].append(f"{endpoint} -> body:{field}")
                            details["schema_entities"].extend(
                                self._extract_openapi_schema_entities(
                                    schema,
                                    schemas,
                                    fallback=f"{endpoint} request body",
                                )
                            )

                responses = operation.get("responses", {})
                if isinstance(responses, dict):
                    for status_code in responses.keys():
                        status_text = str(status_code).strip()
                        if re.fullmatch(r"(?:[1-5]\d{2}|default)", status_text):
                            details["response_statuses"].append(f"{endpoint} -> {status_text}")

        return {key: self._unique(values[:40]) for key, values in details.items()}

    def _format_openapi_parameter(self, endpoint: str, parameter: object) -> Optional[str]:
        if not isinstance(parameter, dict):
            return None

        name = str(parameter.get("name", "")).strip()
        location = str(parameter.get("in", "")).strip()
        if not name or not location:
            return None

        label = f"{endpoint} -> {location}:{name}"
        if parameter.get("required"):
            label += " (required)"
        return label

    def _extract_openapi_request_body_fields(
        self,
        request_body: Dict[str, object],
        schemas: Dict[str, object],
    ) -> List[str]:
        content_map = request_body.get("content", {})
        if not isinstance(content_map, dict):
            return []

        fields: List[str] = []
        for schema_wrapper in content_map.values():
            if not isinstance(schema_wrapper, dict):
                continue
            schema = schema_wrapper.get("schema")
            fields.extend(self._extract_openapi_schema_fields(schema, schemas))
        return self._unique(fields[:20])

    def _extract_openapi_schema_entities(
        self,
        schema: object,
        schemas: Dict[str, object],
        fallback: str,
        depth: int = 0,
    ) -> List[str]:
        if depth > 2 or not isinstance(schema, dict):
            return [fallback]

        ref = schema.get("$ref")
        if isinstance(ref, str):
            ref_name = ref.split("/")[-1]
            return [ref_name]

        if schema.get("type") == "array":
            return self._extract_openapi_schema_entities(schema.get("items"), schemas, fallback, depth + 1)

        title = schema.get("title")
        if isinstance(title, str) and title.strip():
            return [title.strip()]

        if isinstance(schema.get("properties"), dict):
            return [fallback]

        return []

    def _extract_openapi_schema_fields(
        self,
        schema: object,
        schemas: Dict[str, object],
        depth: int = 0,
    ) -> List[str]:
        if depth > 2 or not isinstance(schema, dict):
            return []

        ref = schema.get("$ref")
        if isinstance(ref, str):
            ref_name = ref.split("/")[-1]
            target = schemas.get(ref_name)
            if isinstance(target, dict):
                return self._extract_openapi_schema_fields(target, schemas, depth + 1)
            return []

        if schema.get("type") == "array":
            return self._extract_openapi_schema_fields(schema.get("items"), schemas, depth + 1)

        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])
        if not isinstance(properties, dict):
            return []

        required_names = {str(item) for item in required_fields} if isinstance(required_fields, list) else set()
        results: List[str] = []
        for field_name in properties.keys():
            field_label = str(field_name)
            if field_label in required_names:
                field_label += " (required)"
            results.append(field_label)
        return results

    def _empty_database_details(self) -> Dict[str, List[str]]:
        return {
            "database_objects": [],
            "database_columns": [],
            "database_indexes": [],
            "database_relations": [],
            "data_constraints": [],
        }

    def _extract_database_details(self, content: str) -> Dict[str, List[str]]:
        details = self._empty_database_details()
        table_blocks = re.findall(
            r"CREATE\s+TABLE\s+[`\"\[]?(\w+)[`\"\]]?\s*\((.*?)\)\s*;",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )

        for table_name, table_body in table_blocks:
            details["database_objects"].append(table_name)
            for raw_line in table_body.splitlines():
                line = raw_line.strip().rstrip(",")
                if not line:
                    continue

                upper_line = line.upper()
                if upper_line.startswith("PRIMARY KEY"):
                    details["data_constraints"].append(f"{table_name}.PRIMARY KEY")
                    continue

                if "FOREIGN KEY" in upper_line:
                    relation = self._extract_table_level_relation(table_name, line)
                    if relation:
                        details["database_relations"].append(relation)
                    continue

                if upper_line.startswith(("UNIQUE KEY", "UNIQUE INDEX", "KEY ", "INDEX ")):
                    index_name = self._extract_inline_index_name(line)
                    if index_name:
                        details["database_indexes"].append(f"{table_name}.{index_name}")
                    continue

                column_match = re.match(r'[`\"\[]?(\w+)[`\"\]]?\s+([A-Za-z]+(?:\([^)]+\))?)', line)
                if not column_match:
                    continue

                column_name = column_match.group(1)
                details["database_columns"].append(f"{table_name}.{column_name}")

                constraint_tokens: List[str] = []
                if "NOT NULL" in upper_line:
                    constraint_tokens.append("NOT NULL")
                if re.search(r"\bUNIQUE\b", upper_line):
                    constraint_tokens.append("UNIQUE")

                default_match = re.search(r"\bDEFAULT\b\s+([^,]+)", line, flags=re.IGNORECASE)
                if default_match:
                    constraint_tokens.append(f"DEFAULT {default_match.group(1).strip()}")

                check_match = re.search(r"\bCHECK\s*\((.+?)\)", line, flags=re.IGNORECASE)
                if check_match:
                    constraint_tokens.append(f"CHECK({check_match.group(1).strip()})")

                inline_relation = self._extract_inline_relation(table_name, column_name, line)
                if inline_relation:
                    details["database_relations"].append(inline_relation)

                if constraint_tokens:
                    details["data_constraints"].append(f"{table_name}.{column_name} {'; '.join(constraint_tokens)}")

        index_matches = re.findall(
            r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+[`\"\[]?(\w+)[`\"\]]?\s+ON\s+[`\"\[]?(\w+)[`\"\]]?",
            content,
            flags=re.IGNORECASE,
        )
        for index_name, table_name in index_matches:
            details["database_indexes"].append(f"{table_name}.{index_name}")

        return {key: self._unique(values[:40]) for key, values in details.items()}

    def _extract_inline_index_name(self, line: str) -> Optional[str]:
        match = re.match(r"(?:UNIQUE\s+KEY|UNIQUE\s+INDEX|KEY|INDEX)\s+[`\"\[]?(\w+)[`\"\]]?", line, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_table_level_relation(self, table_name: str, line: str) -> Optional[str]:
        match = re.search(
            r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+[`\"\[]?(\w+)[`\"\]]?\s*\(([^)]+)\)",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        source_column = match.group(1).strip().strip("`\"[]")
        target_table = match.group(2).strip()
        target_column = match.group(3).strip().strip("`\"[]")
        return f"{table_name}.{source_column} -> {target_table}.{target_column}"

    def _extract_inline_relation(self, table_name: str, column_name: str, line: str) -> Optional[str]:
        match = re.search(
            r"REFERENCES\s+[`\"\[]?(\w+)[`\"\]]?\s*\(([^)]+)\)",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        target_table = match.group(1).strip()
        target_column = match.group(2).strip().strip("`\"[]")
        return f"{table_name}.{column_name} -> {target_table}.{target_column}"

    def _safe_load_json(self, content: str) -> Optional[dict]:
        try:
            payload = json.loads(content)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _extract_database_objects(self, content: str) -> List[str]:
        tables = self._SQL_TABLE_PATTERN.findall(content)
        if tables:
            return self._unique(tables[:20])

        text_tables = re.findall(r"(?:表|table)[:：]?\s*([A-Za-z_][A-Za-z0-9_]*)", content, flags=re.IGNORECASE)
        return self._unique(text_tables[:20])

    def _extract_data_constraints(self, content: str) -> List[str]:
        candidates: List[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if self._CONSTRAINT_PATTERN.search(stripped):
                candidates.append(stripped.lstrip("-*1234567890.、) "))
        return self._unique(candidates[:20])

    def _extract_rule_like_lines(self, content: str) -> List[str]:
        results: List[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if re.search(r"(必须|应该|需要|要求|当|如果|若|校验|验证|禁止|支持|应当|shall|must|should|(?i:\b(?:shall|must|should|require|requires|when|if|validate|verify|prohibit|support)\b))", stripped):
                results.append(stripped.lstrip("-*1234567890.、) "))
        return self._unique(results[:20])

    def _issue(self, severity: str, category: str, message: str, suggestion: str) -> AnalysisIssue:
        seq = abs(hash((severity, category, message, suggestion))) % 10000
        return AnalysisIssue(
            issue_id=f"ISS-{seq:04d}",
            severity=severity,
            category=category,
            message=message,
            suggestion=suggestion,
        )

    def _contains_any(self, content: str, tokens: List[str]) -> bool:
        lowered = content.lower()
        return any(token.lower() in lowered for token in tokens)

    def _contains_security_signals(self, items: List[str]) -> bool:
        joined = " ".join(items).lower()
        return any(token in joined for token in ["安全", "权限", "认证", "鉴权", "密码", "token", "csrf", "xss", "sql", "security", "permission", "authentication", "authorization", "password"])

    def _unique(self, values: List[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            item = value.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result


_document_analyzer: Optional[DocumentAnalyzer] = None


def get_document_analyzer() -> DocumentAnalyzer:
    global _document_analyzer
    if _document_analyzer is None:
        _document_analyzer = DocumentAnalyzer()
    return _document_analyzer
