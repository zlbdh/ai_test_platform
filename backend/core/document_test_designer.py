"""
面向需求文档 / 开发文档的测试设计器

职责：
- 将 RequirementParser 的基础结果转成可执行测试
- 按文档类型补充更专业的测试策略
- 返回生成摘要，帮助前端解释“为什么这样生成”
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


PRIORITY_RANK = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


class DocumentTestDesigner:
    def design(
        self,
        content: str,
        title: str,
        analysis: Any,
        parsed_result: Optional[Any] = None,
        document_role: str = "primary",
    ) -> Dict[str, Any]:
        tests: List[Dict[str, Any]] = []

        tests.extend(self._build_parser_based_tests(parsed_result, analysis))

        doc_type = getattr(analysis, "document_type", "general_text")
        if doc_type == "api_spec":
            tests.extend(self._build_api_spec_tests(analysis))
        elif doc_type == "database_schema":
            tests.extend(self._build_database_schema_tests(analysis))
        elif doc_type == "development_design":
            tests.extend(self._build_development_design_tests(analysis))
        else:
            tests.extend(self._build_requirement_gap_tests(analysis))

        tests = self._dedupe_tests(tests)
        tests = self._annotate_tests(
            tests,
            title=title,
            document_type=getattr(analysis, "document_type", "general_text"),
            document_label=getattr(analysis, "document_label", "文档"),
            document_role=document_role,
        )

        summary = self._build_generation_summary(title, analysis, tests, document_role=document_role)
        return {
            "tests": tests,
            "generation_summary": summary,
        }

    def design_bundle(
        self,
        primary_content: str,
        primary_title: str,
        primary_analysis: Any,
        primary_parsed_result: Optional[Any],
        references: List[Dict[str, Any]],
        bundle_analysis: Any,
    ) -> Dict[str, Any]:
        primary_design = self.design(
            primary_content,
            primary_title,
            primary_analysis,
            primary_parsed_result,
            document_role="primary",
        )

        all_tests = list(primary_design["tests"])
        document_sources = list(primary_design["generation_summary"].get("document_sources", []))
        analyses = [primary_analysis]
        focus_areas = list(primary_design["generation_summary"].get("focus_areas", []))

        for reference in references:
            analysis = reference["analysis"]
            reference_design = self.design(
                reference["content"],
                reference["title"],
                analysis,
                reference.get("parsed_result"),
                document_role="reference",
            )
            all_tests.extend(reference_design["tests"])
            document_sources.extend(reference_design["generation_summary"].get("document_sources", []))
            analyses.append(analysis)
            focus_areas.extend(reference_design["generation_summary"].get("focus_areas", []))

        bundle_tests = self._annotate_tests(
            self._build_bundle_alignment_tests(bundle_analysis),
            title="多文档交叉检测",
            document_type="document_bundle",
            document_label="交叉检测",
            document_role="bundle",
        )
        all_tests.extend(bundle_tests)
        if bundle_tests:
            document_sources.append({
                "title": "多文档交叉检测",
                "document_type": "document_bundle",
                "document_label": "交叉检测",
                "document_role": "bundle",
                "generated_count": len(bundle_tests),
            })

        combined_tests = self._dedupe_tests(all_tests)
        summary = self._build_bundle_generation_summary(
            primary_title=primary_title,
            primary_analysis=primary_analysis,
            tests=combined_tests,
            analyses=analyses,
            document_sources=document_sources,
            bundle_analysis=bundle_analysis,
            focus_areas=focus_areas,
        )
        return {
            "tests": combined_tests,
            "generation_summary": summary,
        }

    def _build_parser_based_tests(self, parsed_result: Optional[Any], analysis: Any) -> List[Dict[str, Any]]:
        if parsed_result is None or not getattr(parsed_result, "test_cases", None):
            return []

        document_label = getattr(analysis, "document_label", "文档")
        generated = []
        for tc in parsed_result.test_cases:
            rule_refs = []
            for rule_id in getattr(tc, "related_rules", []) or []:
                rule_refs.append(rule_id)

            instruction_parts = [
                getattr(tc, "description", ""),
                f"来源: {document_label}",
                f"步骤: {'; '.join(getattr(tc, 'steps', []) or [])}",
                f"期望: {'; '.join(getattr(tc, 'expected_results', []) or [])}",
            ]
            if rule_refs:
                instruction_parts.append(f"追溯规则: {', '.join(rule_refs)}")

            generated.append({
                "id": getattr(tc, "case_id", "TC-UNKNOWN"),
                "name": getattr(tc, "title", "未命名测试"),
                "type": getattr(tc, "test_type", "ui_e2e"),
                "priority": getattr(getattr(tc, "priority", None), "value", "medium"),
                "instruction": "\n".join([part for part in instruction_parts if part]),
                "tags": self._merge_tags(
                    getattr(tc, "tags", []) or [],
                    [f"doc:{getattr(analysis, 'document_type', 'general_text')}", "generated:parser"],
                ),
                "basis": rule_refs,
                "source": "parser",
            })

        return generated

    def _build_api_spec_tests(self, analysis: Any) -> List[Dict[str, Any]]:
        endpoints = list(getattr(analysis, "extracted", {}).get("api_endpoints", []))
        api_parameters = list(getattr(analysis, "extracted", {}).get("api_parameters", []))
        response_statuses = list(getattr(analysis, "extracted", {}).get("response_statuses", []))
        schema_entities = list(getattr(analysis, "extracted", {}).get("schema_entities", []))
        error_codes = list(getattr(analysis, "extracted", {}).get("error_codes", []))
        tests: List[Dict[str, Any]] = []

        for idx, endpoint in enumerate(endpoints, 1):
            endpoint_parameters = self._filter_prefixed_items(endpoint, api_parameters)
            endpoint_statuses = self._filter_prefixed_items(endpoint, response_statuses)

            tests.append({
                "id": f"API-HAPPY-{idx:03d}",
                "name": f"接口主流程: {endpoint}",
                "type": "api_rest",
                "priority": "high",
                "instruction": (
                    f"验证接口 {endpoint} 的主流程返回。\n"
                    f"步骤: 准备合法请求参数; 调用接口 {endpoint}; 校验响应码、核心字段和结构。\n"
                    f"期望: 返回成功状态，响应结构与接口定义一致。"
                ),
                "tags": ["api", "contract", "generated:api_spec", f"doc:{analysis.document_type}"],
                "basis": [endpoint],
                "source": "api_spec",
            })

            tests.append({
                "id": f"API-CONTRACT-{idx:03d}",
                "name": f"接口契约校验: {endpoint}",
                "type": "contract",
                "priority": "high",
                "instruction": (
                    f"对接口 {endpoint} 做契约校验。\n"
                    f"步骤: 读取接口文档; 发送请求; 对比响应字段、数据类型、必填项和状态码。\n"
                    f"期望: 请求/响应符合 OpenAPI/Swagger 定义。"
                ),
                "tags": ["api", "contract", "schema", "generated:api_spec", f"doc:{analysis.document_type}"],
                "basis": [endpoint],
                "source": "api_spec",
            })

            if endpoint_parameters:
                tests.append({
                    "id": f"API-PARAM-{idx:03d}",
                    "name": f"接口参数校验: {endpoint}",
                    "type": "api_rest",
                    "priority": "high",
                    "instruction": (
                        f"围绕接口 {endpoint} 的参数定义做校验。\n"
                        f"步骤: 覆盖参数 {', '.join(endpoint_parameters[:4])}; 分别验证必填、边界值、非法类型和缺失场景。\n"
                        "期望: 参数校验行为与接口定义一致，错误提示清晰。"
                    ),
                    "tags": ["api", "parameter", "data_validation", "generated:api_spec", f"doc:{analysis.document_type}"],
                    "basis": [endpoint, *endpoint_parameters[:4]],
                    "source": "api_spec",
                })

            if endpoint_statuses:
                tests.append({
                    "id": f"API-STATUS-{idx:03d}",
                    "name": f"响应状态覆盖: {endpoint}",
                    "type": "contract",
                    "priority": "medium",
                    "instruction": (
                        f"验证接口 {endpoint} 的响应状态覆盖。\n"
                        f"步骤: 分别触发文档定义的状态 {', '.join(endpoint_statuses[:4])}; 检查状态码、错误信息和响应体结构。\n"
                        "期望: 每类状态均能稳定复现，且语义与文档一致。"
                    ),
                    "tags": ["api", "status_code", "contract", "generated:api_spec", f"doc:{analysis.document_type}"],
                    "basis": [endpoint, *endpoint_statuses[:4]],
                    "source": "api_spec",
                })

            if error_codes:
                tests.append({
                    "id": f"API-NEG-{idx:03d}",
                    "name": f"接口异常处理: {endpoint}",
                    "type": "api_rest",
                    "priority": "medium",
                    "instruction": (
                        f"验证接口 {endpoint} 的异常响应处理。\n"
                        f"步骤: 构造非法参数或缺失参数; 调用接口 {endpoint}; 校验错误码和错误信息。\n"
                        f"期望: 返回文档中定义的错误码，如 {', '.join(error_codes[:3])}。"
                    ),
                    "tags": ["api", "negative", "error_handling", "generated:api_spec", f"doc:{analysis.document_type}"],
                    "basis": [endpoint, *error_codes[:3]],
                    "source": "api_spec",
                })

        for idx, schema_name in enumerate(schema_entities[:6], 1):
            tests.append({
                "id": f"API-SCHEMA-{idx:03d}",
                "name": f"模型结构校验: {schema_name}",
                "type": "contract",
                "priority": "medium",
                "instruction": (
                    f"验证接口文档中的模型 {schema_name} 是否能正确映射到请求/响应结构。\n"
                    "步骤: 读取模型字段定义; 抽样验证字段名、类型、必填约束和嵌套结构。\n"
                    "期望: 模型结构可稳定支撑接口契约校验。"
                ),
                "tags": ["api", "schema", "contract", "generated:api_spec", f"doc:{analysis.document_type}"],
                "basis": [schema_name],
                "source": "api_spec",
            })

        return tests

    def _build_database_schema_tests(self, analysis: Any) -> List[Dict[str, Any]]:
        tables = list(getattr(analysis, "extracted", {}).get("database_objects", []))
        constraints = list(getattr(analysis, "extracted", {}).get("data_constraints", []))
        columns = list(getattr(analysis, "extracted", {}).get("database_columns", []))
        indexes = list(getattr(analysis, "extracted", {}).get("database_indexes", []))
        relations = list(getattr(analysis, "extracted", {}).get("database_relations", []))
        tests: List[Dict[str, Any]] = []

        for idx, table in enumerate(tables[:10], 1):
            table_constraints = [item for item in constraints if item.startswith(f"{table}.")]
            table_columns = [item for item in columns if item.startswith(f"{table}.")]
            table_indexes = [item for item in indexes if item.startswith(f"{table}.")]
            table_relations = [item for item in relations if item.startswith(f"{table}.")]

            tests.append({
                "id": f"DB-SCHEMA-{idx:03d}",
                "name": f"表结构校验: {table}",
                "type": "data_validation",
                "priority": "high",
                "instruction": (
                    f"验证表 {table} 的结构定义是否满足设计。\n"
                    f"步骤: 查询表结构; 校验字段 {', '.join(table_columns[:4]) or '定义字段'}、主键、索引和默认值定义; 记录缺失约束。\n"
                    f"期望: 表结构与数据库设计一致。"
                ),
                "tags": ["database", "schema", "generated:db_schema", f"doc:{analysis.document_type}"],
                "basis": [table, *table_columns[:4]],
                "source": "database_schema",
            })

            if table_constraints:
                tests.append({
                    "id": f"DB-CONSTRAINT-{idx:03d}",
                    "name": f"数据约束校验: {table}",
                    "type": "data_validation",
                    "priority": "medium",
                    "instruction": (
                        f"围绕表 {table} 做约束验证。\n"
                        f"步骤: 准备边界数据; 插入/更新数据; 验证约束 {', '.join(table_constraints[:4])}。\n"
                        f"期望: 数据库按设计拒绝非法数据，并保留有效数据。"
                    ),
                    "tags": ["database", "constraint", "negative", "generated:db_schema", f"doc:{analysis.document_type}"],
                    "basis": [table, *table_constraints[:4]],
                    "source": "database_schema",
                })

            if table_relations:
                tests.append({
                    "id": f"DB-REL-{idx:03d}",
                    "name": f"外键完整性校验: {table}",
                    "type": "data_validation",
                    "priority": "high",
                    "instruction": (
                        f"验证表 {table} 的关联完整性。\n"
                        f"步骤: 围绕关系 {', '.join(table_relations[:3])} 构造插入、删除和更新场景; 检查外键限制与级联行为。\n"
                        "期望: 关联数据保持一致，不会出现脏引用。"
                    ),
                    "tags": ["database", "relation", "integrity", "generated:db_schema", f"doc:{analysis.document_type}"],
                    "basis": [table, *table_relations[:3]],
                    "source": "database_schema",
                })

            if table_indexes:
                tests.append({
                    "id": f"DB-INDEX-{idx:03d}",
                    "name": f"索引策略验证: {table}",
                    "type": "data_validation",
                    "priority": "medium",
                    "instruction": (
                        f"验证表 {table} 的索引配置是否支撑核心查询场景。\n"
                        f"步骤: 检查索引 {', '.join(table_indexes[:3])}; 对典型查询执行 explain 或执行计划分析; 观察是否命中索引。\n"
                        "期望: 核心查询可命中预期索引，避免明显全表扫描。"
                    ),
                    "tags": ["database", "index", "performance", "generated:db_schema", f"doc:{analysis.document_type}"],
                    "basis": [table, *table_indexes[:3]],
                    "source": "database_schema",
                })

        return tests

    def _build_development_design_tests(self, analysis: Any) -> List[Dict[str, Any]]:
        endpoints = list(getattr(analysis, "extracted", {}).get("api_endpoints", []))
        flows = list(getattr(analysis, "extracted", {}).get("flows", []))
        constraints = list(getattr(analysis, "extracted", {}).get("data_constraints", []))
        error_codes = list(getattr(analysis, "extracted", {}).get("error_codes", []))
        tests: List[Dict[str, Any]] = []

        for idx, flow in enumerate(flows[:6], 1):
            tests.append({
                "id": f"DESIGN-FLOW-{idx:03d}",
                "name": f"设计流转验证: {flow[:28]}",
                "type": "business_flow",
                "priority": "high",
                "instruction": (
                    f"根据开发设计验证流程：{flow}。\n"
                    f"步骤: 准备前置条件; 按设计执行模块交互; 检查状态流转、接口调用顺序和结果落库。\n"
                    f"期望: 实现行为与设计说明一致。"
                ),
                "tags": ["integration", "flow", "generated:design", f"doc:{analysis.document_type}"],
                "basis": [flow],
                "source": "development_design",
            })

        for idx, endpoint in enumerate(endpoints[:8], 1):
            tests.append({
                "id": f"DESIGN-API-{idx:03d}",
                "name": f"设计接口联调: {endpoint}",
                "type": "api_rest",
                "priority": "high",
                "instruction": (
                    f"按开发设计验证接口 {endpoint}。\n"
                    f"步骤: 基于设计准备请求; 调用接口; 检查关键字段、状态变化与副作用。\n"
                    f"期望: 接口行为符合设计说明，并能支撑上层业务流程。"
                ),
                "tags": ["api", "integration", "generated:design", f"doc:{analysis.document_type}"],
                "basis": [endpoint],
                "source": "development_design",
            })

        if constraints:
            tests.append({
                "id": "DESIGN-BOUNDARY-001",
                "name": "开发约束边界验证",
                "type": "data_validation",
                "priority": "medium",
                "instruction": (
                    "针对开发文档中的关键约束做边界测试。\n"
                    f"步骤: 准备边界数据; 覆盖约束 {', '.join(constraints[:4])}; 校验系统拒绝非法输入并正确提示。\n"
                    "期望: 系统严格遵守设计约束。"
                ),
                "tags": ["boundary", "constraint", "generated:design", f"doc:{analysis.document_type}"],
                "basis": constraints[:4],
                "source": "development_design",
            })

        if error_codes:
            tests.append({
                "id": "DESIGN-ERROR-001",
                "name": "设计异常码验证",
                "type": "api_rest",
                "priority": "medium",
                "instruction": (
                    "验证开发文档定义的异常码和失败处理逻辑。\n"
                    f"步骤: 人为制造失败场景; 观察返回码/异常码 {', '.join(error_codes[:4])}; 检查补偿、回滚或提示信息。\n"
                    "期望: 失败路径符合设计说明。"
                ),
                "tags": ["negative", "error_handling", "generated:design", f"doc:{analysis.document_type}"],
                "basis": error_codes[:4],
                "source": "development_design",
            })

        return tests

    def _build_requirement_gap_tests(self, analysis: Any) -> List[Dict[str, Any]]:
        rules = list(getattr(analysis, "extracted", {}).get("business_rules", []))
        flows = list(getattr(analysis, "extracted", {}).get("flows", []))
        tests: List[Dict[str, Any]] = []

        for idx, flow in enumerate(flows[:4], 1):
            tests.append({
                "id": f"REQ-FLOW-{idx:03d}",
                "name": f"主流程验证: {flow[:28]}",
                "type": "ui_e2e",
                "priority": "high",
                "instruction": (
                    f"围绕需求流程“{flow}”生成端到端验证。\n"
                    "步骤: 准备账号和数据; 按流程完成操作; 验证页面反馈、接口结果和状态变化。\n"
                    "期望: 用户可顺利完成该流程，关键断言均通过。"
                ),
                "tags": ["ui", "business_flow", "generated:requirement", f"doc:{analysis.document_type}"],
                "basis": [flow],
                "source": "requirement",
            })

        if rules:
            tests.append({
                "id": "REQ-NEG-001",
                "name": "核心业务规则负向验证",
                "type": "business_flow",
                "priority": "medium",
                "instruction": (
                    "针对需求中的核心规则设计负向场景。\n"
                    f"步骤: 选择关键规则 {', '.join(rules[:3])}; 构造违反规则的输入; 检查系统拦截和提示。\n"
                    "期望: 系统拒绝非法操作，并保留清晰的错误反馈。"
                ),
                "tags": ["negative", "rule_validation", "generated:requirement", f"doc:{analysis.document_type}"],
                "basis": rules[:3],
                "source": "requirement",
            })

        return tests

    def _build_generation_summary(
        self,
        title: str,
        analysis: Any,
        tests: List[Dict[str, Any]],
        document_role: str = "primary",
    ) -> Dict[str, Any]:
        doc_type = getattr(analysis, "document_type", "general_text")
        strategy_map = {
            "requirement_prd": ("需求优先", "优先覆盖业务主流程、验收标准与关键负向规则。"),
            "development_design": ("设计驱动", "优先覆盖接口联调、状态流转、边界约束和异常码。"),
            "api_spec": ("接口契约优先", "优先覆盖接口主流程、契约一致性和异常响应。"),
            "database_schema": ("数据结构优先", "优先覆盖表结构、约束和数据一致性。"),
            "general_text": ("通用提炼", "基于文档中可识别的规则和流程生成基础测试建议。"),
        }
        strategy_label, rationale = strategy_map.get(doc_type, strategy_map["general_text"])

        counts_by_type = dict(Counter(test["type"] for test in tests))
        extracted = getattr(analysis, "extracted", {})
        traceability = {
            "business_rules": len(extracted.get("business_rules", [])),
            "flows": len(extracted.get("flows", [])),
            "api_endpoints": len(extracted.get("api_endpoints", [])),
            "api_parameters": len(extracted.get("api_parameters", [])),
            "response_statuses": len(extracted.get("response_statuses", [])),
            "schema_entities": len(extracted.get("schema_entities", [])),
            "database_objects": len(extracted.get("database_objects", [])),
            "database_columns": len(extracted.get("database_columns", [])),
            "database_indexes": len(extracted.get("database_indexes", [])),
            "database_relations": len(extracted.get("database_relations", [])),
            "data_constraints": len(extracted.get("data_constraints", [])),
        }

        focus_areas = list(getattr(analysis, "recommended_test_types", []))[:6]
        if not focus_areas:
            focus_areas = ["ui_e2e"]

        return {
            "title": title,
            "document_type": doc_type,
            "strategy_label": strategy_label,
            "rationale": rationale,
            "generated_count": len(tests),
            "counts_by_type": counts_by_type,
            "counts_by_origin": {document_role: len(tests)},
            "focus_areas": focus_areas,
            "traceability": traceability,
            "document_sources": [
                {
                    "title": title,
                    "document_type": doc_type,
                    "document_label": getattr(analysis, "document_label", "文档"),
                    "document_role": document_role,
                    "generated_count": len(tests),
                }
            ],
            "bundle_findings_count": 0,
        }

    def _build_bundle_generation_summary(
        self,
        primary_title: str,
        primary_analysis: Any,
        tests: List[Dict[str, Any]],
        analyses: List[Any],
        document_sources: List[Dict[str, Any]],
        bundle_analysis: Any,
        focus_areas: List[str],
    ) -> Dict[str, Any]:
        counts_by_type = dict(Counter(test["type"] for test in tests))
        counts_by_origin = dict(Counter(str(test.get("document_role", "primary")) for test in tests))
        traceability = self._build_combined_traceability(analyses)

        combined_focus_areas = self._unique_values(focus_areas)
        if getattr(bundle_analysis, "findings", []):
            combined_focus_areas.extend(["contract", "data_validation"])
        combined_focus_areas = self._unique_values(combined_focus_areas)[:8] or ["ui_e2e"]

        primary_strategy_map = {
            "requirement_prd": "需求驱动",
            "development_design": "设计驱动",
            "api_spec": "接口契约驱动",
            "database_schema": "数据结构驱动",
            "general_text": "文档驱动",
        }
        primary_type = getattr(primary_analysis, "document_type", "general_text")
        primary_strategy = primary_strategy_map.get(primary_type, primary_strategy_map["general_text"])

        rationale = (
            f"以主文档的{primary_strategy}策略为主，吸收参考文档中的接口、数据或设计细节，"
            "并根据交叉检测结果补充一致性验证。"
        )

        return {
            "title": primary_title,
            "document_type": primary_type,
            "strategy_label": "多文档联合设计",
            "rationale": rationale,
            "generated_count": len(tests),
            "counts_by_type": counts_by_type,
            "counts_by_origin": counts_by_origin,
            "focus_areas": combined_focus_areas,
            "traceability": traceability,
            "document_sources": self._normalize_document_sources(document_sources),
            "bundle_findings_count": len(getattr(bundle_analysis, "findings", [])),
        }

    def _dedupe_tests(self, tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        seen = set()

        for test in tests:
            name = str(test.get("name", "")).strip().lower()
            test_type = str(test.get("type", "")).strip().lower()
            key = f"{name}|{test_type}"
            if not name or key in seen:
                continue
            seen.add(key)
            unique.append(test)

        unique.sort(
            key=lambda item: (
                -PRIORITY_RANK.get(str(item.get("priority", "medium")).lower(), 0),
                str(item.get("name", "")),
            )
        )
        return unique

    def _annotate_tests(
        self,
        tests: List[Dict[str, Any]],
        title: str,
        document_type: str,
        document_label: str,
        document_role: str,
    ) -> List[Dict[str, Any]]:
        annotated: List[Dict[str, Any]] = []
        for test in tests:
            item = dict(test)
            item["document_title"] = title
            item["document_type"] = document_type
            item["document_label"] = document_label
            item["document_role"] = document_role
            item["tags"] = self._merge_tags(
                list(item.get("tags", [])),
                [f"role:{document_role}", f"doc:{document_type}"],
            )
            annotated.append(item)
        return annotated

    def _build_bundle_alignment_tests(self, bundle_analysis: Any) -> List[Dict[str, Any]]:
        tests: List[Dict[str, Any]] = []
        findings = list(getattr(bundle_analysis, "findings", []))
        for idx, finding in enumerate(findings[:4], 1):
            category = str(getattr(finding, "category", "consistency"))
            severity = str(getattr(finding, "severity", "warning"))
            test_type = "contract"
            if category == "coverage":
                test_type = "business_flow"
            if "约束" in str(getattr(finding, "message", "")) or "字段" in str(getattr(finding, "message", "")):
                test_type = "data_validation"

            tests.append({
                "id": f"BUNDLE-{idx:03d}",
                "name": f"跨文档{category}验证 {idx}",
                "type": test_type,
                "priority": "high" if severity in {"error", "warning"} else "medium",
                "instruction": (
                    "基于主文档与参考文档的交叉检测结果执行联合验证。\n"
                    f"问题: {getattr(finding, 'message', '')}\n"
                    "步骤: 对照主文档、参考文档和系统实现; 触发相关业务/API/数据场景; 检查行为、响应和数据是否同时满足多份文档。\n"
                    f"期望: {getattr(finding, 'suggestion', '')}"
                ),
                "tags": ["bundle", "cross_document", "generated:bundle", f"bundle:{category}"],
                "basis": [getattr(finding, "message", "")],
                "source": "bundle_analysis",
            })
        return tests

    def _build_combined_traceability(self, analyses: List[Any]) -> Dict[str, int]:
        traceability_keys = [
            "business_rules",
            "flows",
            "api_endpoints",
            "api_parameters",
            "response_statuses",
            "schema_entities",
            "database_objects",
            "database_columns",
            "database_indexes",
            "database_relations",
            "data_constraints",
        ]
        combined = {key: 0 for key in traceability_keys}
        for analysis in analyses:
            extracted = getattr(analysis, "extracted", {})
            for key in traceability_keys:
                combined[key] += len(extracted.get(key, []))
        return combined

    def _normalize_document_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen = set()
        for source in sources:
            title = str(source.get("title", "")).strip()
            role = str(source.get("document_role", "primary")).strip()
            key = f"{title}|{role}"
            if not title or key in seen:
                continue
            seen.add(key)
            normalized.append(source)
        return normalized

    def _merge_tags(self, left: List[str], right: List[str]) -> List[str]:
        merged = []
        seen = set()
        for tag in [*(left or []), *(right or [])]:
            if not tag or tag in seen:
                continue
            seen.add(tag)
            merged.append(tag)
        return merged

    def _filter_prefixed_items(self, prefix: str, items: List[str]) -> List[str]:
        return [item for item in items if item.startswith(f"{prefix} -> ")]

    def _unique_values(self, values: List[str]) -> List[str]:
        merged = []
        seen = set()
        for value in values:
            item = str(value).strip()
            if not item or item in seen:
                continue
            seen.add(item)
            merged.append(item)
        return merged


_document_test_designer: Optional[DocumentTestDesigner] = None


def get_document_test_designer() -> DocumentTestDesigner:
    global _document_test_designer
    if _document_test_designer is None:
        _document_test_designer = DocumentTestDesigner()
    return _document_test_designer
