"""
Test designer for requirements and development documents

Responsibilities:
- Convert RequirementParser results into executable tests
- Add specialized testing strategies by document type
- Return a generation summary so the frontend can explain the design choices
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
            document_label=getattr(analysis, "document_label", "Document"),
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
            title="Cross-document analysis",
            document_type="document_bundle",
            document_label="Cross-document analysis",
            document_role="bundle",
        )
        all_tests.extend(bundle_tests)
        if bundle_tests:
            document_sources.append({
                "title": "Cross-document analysis",
                "document_type": "document_bundle",
                "document_label": "Cross-document analysis",
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

        document_label = getattr(analysis, "document_label", "Document")
        generated = []
        for tc in parsed_result.test_cases:
            rule_refs = []
            for rule_id in getattr(tc, "related_rules", []) or []:
                rule_refs.append(rule_id)

            instruction_parts = [
                getattr(tc, "description", ""),
                f"Source: {document_label}",
                f"Steps: {'; '.join(getattr(tc, 'steps', []) or [])}",
                f"Expected: {'; '.join(getattr(tc, 'expected_results', []) or [])}",
            ]
            if rule_refs:
                instruction_parts.append(f"Traceability rules: {', '.join(rule_refs)}")

            generated.append({
                "id": getattr(tc, "case_id", "TC-UNKNOWN"),
                "name": getattr(tc, "title", "Untitled test"),
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
                "name": f"API happy path: {endpoint}",
                "type": "api_rest",
                "priority": "high",
                "instruction": (
                    f"Verify the happy-path response from {endpoint}.\n"
                    f"Steps: Prepare valid request parameters; call {endpoint}; validate the status code, key fields, and structure.\n"
                    f"Expected: A success status and a response structure matching the API definition."
                ),
                "tags": ["api", "contract", "generated:api_spec", f"doc:{analysis.document_type}"],
                "basis": [endpoint],
                "source": "api_spec",
            })

            tests.append({
                "id": f"API-CONTRACT-{idx:03d}",
                "name": f"API contract validation: {endpoint}",
                "type": "contract",
                "priority": "high",
                "instruction": (
                    f"Validate the contract for {endpoint}.\n"
                    f"Steps: Read the API specification; send a request; compare response fields, data types, required fields, and status codes.\n"
                    f"Expected: Requests/responses comply with the OpenAPI/Swagger definition."
                ),
                "tags": ["api", "contract", "schema", "generated:api_spec", f"doc:{analysis.document_type}"],
                "basis": [endpoint],
                "source": "api_spec",
            })

            if endpoint_parameters:
                tests.append({
                    "id": f"API-PARAM-{idx:03d}",
                    "name": f"API parameter validation: {endpoint}",
                    "type": "api_rest",
                    "priority": "high",
                    "instruction": (
                        f"Validate the parameter definitions for {endpoint}.\n"
                        f"Steps: Cover parameters {', '.join(endpoint_parameters[:4])}; verify required values, boundaries, invalid types, and missing values.\n"
                        "Expected: Validation follows the API specification and produces clear errors."
                    ),
                    "tags": ["api", "parameter", "data_validation", "generated:api_spec", f"doc:{analysis.document_type}"],
                    "basis": [endpoint, *endpoint_parameters[:4]],
                    "source": "api_spec",
                })

            if endpoint_statuses:
                tests.append({
                    "id": f"API-STATUS-{idx:03d}",
                    "name": f"Response status coverage: {endpoint}",
                    "type": "contract",
                    "priority": "medium",
                    "instruction": (
                        f"Verify response status coverage for {endpoint}.\n"
                        f"Steps: Trigger documented statuses {', '.join(endpoint_statuses[:4])}; check status codes, error messages, and response structure.\n"
                        "Expected: Each status is consistently reproducible and matches the documented meaning."
                    ),
                    "tags": ["api", "status_code", "contract", "generated:api_spec", f"doc:{analysis.document_type}"],
                    "basis": [endpoint, *endpoint_statuses[:4]],
                    "source": "api_spec",
                })

            if error_codes:
                tests.append({
                    "id": f"API-NEG-{idx:03d}",
                    "name": f"API error handling: {endpoint}",
                    "type": "api_rest",
                    "priority": "medium",
                    "instruction": (
                        f"Verify exception responses from {endpoint}.\n"
                        f"Steps: Supply invalid or missing parameters; call {endpoint}; validate error codes and messages.\n"
                        f"Expected: Documented error codes, such as {', '.join(error_codes[:3])}, are returned."
                    ),
                    "tags": ["api", "negative", "error_handling", "generated:api_spec", f"doc:{analysis.document_type}"],
                    "basis": [endpoint, *error_codes[:3]],
                    "source": "api_spec",
                })

        for idx, schema_name in enumerate(schema_entities[:6], 1):
            tests.append({
                "id": f"API-SCHEMA-{idx:03d}",
                "name": f"Model structure validation: {schema_name}",
                "type": "contract",
                "priority": "medium",
                "instruction": (
                    f"Verify that model {schema_name} in the API specification maps correctly to request/response structures.\n"
                    "Steps: Read model field definitions; sample field names, types, required constraints, and nested structures.\n"
                    "Expected: The model consistently supports API contract validation."
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
                "name": f"Table structure validation: {table}",
                "type": "data_validation",
                "priority": "high",
                "instruction": (
                    f"Verify that table {table} matches its design.\n"
                    f"Steps: Query the table structure; check columns {', '.join(table_columns[:4]) or 'defined columns'}, primary keys, indexes, and defaults; record missing constraints.\n"
                    f"Expected: Table structure matches the database design."
                ),
                "tags": ["database", "schema", "generated:db_schema", f"doc:{analysis.document_type}"],
                "basis": [table, *table_columns[:4]],
                "source": "database_schema",
            })

            if table_constraints:
                tests.append({
                    "id": f"DB-CONSTRAINT-{idx:03d}",
                    "name": f"Data constraint validation: {table}",
                    "type": "data_validation",
                    "priority": "medium",
                    "instruction": (
                        f"Validate constraints on table {table}.\n"
                        f"Steps: Prepare boundary data; insert/update records; verify constraints {', '.join(table_constraints[:4])}.\n"
                        f"Expected: The database rejects invalid data and retains valid data as designed."
                    ),
                    "tags": ["database", "constraint", "negative", "generated:db_schema", f"doc:{analysis.document_type}"],
                    "basis": [table, *table_constraints[:4]],
                    "source": "database_schema",
                })

            if table_relations:
                tests.append({
                    "id": f"DB-REL-{idx:03d}",
                    "name": f"Foreign-key integrity validation: {table}",
                    "type": "data_validation",
                    "priority": "high",
                    "instruction": (
                        f"Verify relationship integrity for table {table}.\n"
                        f"Steps: Construct insert, delete, and update scenarios for relationships {', '.join(table_relations[:3])}; check foreign-key restrictions and cascading behavior.\n"
                        "Expected: Related data remains consistent without dangling references."
                    ),
                    "tags": ["database", "relation", "integrity", "generated:db_schema", f"doc:{analysis.document_type}"],
                    "basis": [table, *table_relations[:3]],
                    "source": "database_schema",
                })

            if table_indexes:
                tests.append({
                    "id": f"DB-INDEX-{idx:03d}",
                    "name": f"Index strategy validation: {table}",
                    "type": "data_validation",
                    "priority": "medium",
                    "instruction": (
                        f"Verify that table {table}'s indexes support core query scenarios.\n"
                        f"Steps: Check indexes {', '.join(table_indexes[:3])}; run explain or execution-plan analysis on typical queries; check index usage.\n"
                        "Expected: Core queries use the intended indexes and avoid obvious full-table scans."
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
                "name": f"Design workflow validation: {flow[:28]}",
                "type": "business_flow",
                "priority": "high",
                "instruction": (
                    f"Verify the development-design workflow: {flow}.\n"
                    f"Steps: Prepare prerequisites; perform module interactions as designed; check transitions, API call order, and database persistence.\n"
                    f"Expected: Implementation behavior matches the design description."
                ),
                "tags": ["integration", "flow", "generated:design", f"doc:{analysis.document_type}"],
                "basis": [flow],
                "source": "development_design",
            })

        for idx, endpoint in enumerate(endpoints[:8], 1):
            tests.append({
                "id": f"DESIGN-API-{idx:03d}",
                "name": f"Design API integration: {endpoint}",
                "type": "api_rest",
                "priority": "high",
                "instruction": (
                    f"Verify {endpoint} against the development design.\n"
                    f"Steps: Prepare a request from the design; call the API; check key fields, state changes, and side effects.\n"
                    f"Expected: API behavior follows the design and supports higher-level workflows."
                ),
                "tags": ["api", "integration", "generated:design", f"doc:{analysis.document_type}"],
                "basis": [endpoint],
                "source": "development_design",
            })

        if constraints:
            tests.append({
                "id": "DESIGN-BOUNDARY-001",
                "name": "Development constraint boundary validation",
                "type": "data_validation",
                "priority": "medium",
                "instruction": (
                    "Run boundary tests for key constraints in the development document.\n"
                    f"Steps: Prepare boundary data; cover constraints {', '.join(constraints[:4])}; verify that invalid input is rejected with clear messages.\n"
                    "Expected: The system strictly follows the design constraints."
                ),
                "tags": ["boundary", "constraint", "generated:design", f"doc:{analysis.document_type}"],
                "basis": constraints[:4],
                "source": "development_design",
            })

        if error_codes:
            tests.append({
                "id": "DESIGN-ERROR-001",
                "name": "Design error-code validation",
                "type": "api_rest",
                "priority": "medium",
                "instruction": (
                    "Verify error codes and failure-handling logic defined in the development document.\n"
                    f"Steps: Induce failure scenarios; observe return/error codes {', '.join(error_codes[:4])}; check compensation, rollback, or messages.\n"
                    "Expected: Failure paths follow the design description."
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
                "name": f"Main workflow validation: {flow[:28]}",
                "type": "ui_e2e",
                "priority": "high",
                "instruction": (
                    f"Generate end-to-end verification for requirement workflow '{flow}'.\n"
                    "Steps: Prepare accounts and data; complete the workflow; verify page feedback, API results, and state changes.\n"
                    "Expected: The user completes the workflow and all key assertions pass."
                ),
                "tags": ["ui", "business_flow", "generated:requirement", f"doc:{analysis.document_type}"],
                "basis": [flow],
                "source": "requirement",
            })

        if rules:
            tests.append({
                "id": "REQ-NEG-001",
                "name": "Core business rule negative validation",
                "type": "business_flow",
                "priority": "medium",
                "instruction": (
                    "Design negative scenarios for core requirement rules.\n"
                    f"Steps: Select key rules {', '.join(rules[:3])}; supply inputs that violate them; inspect blocking behavior and messages.\n"
                    "Expected: The system rejects invalid actions and provides clear error feedback."
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
            "requirement_prd": ("Requirements first", "Prioritize main workflows, acceptance criteria, and key negative rules."),
            "development_design": ("Design driven", "Prioritize API integration, state transitions, boundary constraints, and error codes."),
            "api_spec": ("API contracts first", "Prioritize API happy paths, contract consistency, and exception responses."),
            "database_schema": ("Data structures first", "Prioritize table structures, constraints, and data consistency."),
            "general_text": ("General extraction", "Generate basic test recommendations from identifiable document rules and workflows."),
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
                    "document_label": getattr(analysis, "document_label", "Document"),
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
            "requirement_prd": "requirements-driven",
            "development_design": "design-driven",
            "api_spec": "API-contract-driven",
            "database_schema": "data-structure-driven",
            "general_text": "document-driven",
        }
        primary_type = getattr(primary_analysis, "document_type", "general_text")
        primary_strategy = primary_strategy_map.get(primary_type, primary_strategy_map["general_text"])

        rationale = (
            f"Use the primary document's {primary_strategy} strategy, incorporate API, data, or design details from references, "
            "and add consistency checks based on cross-document findings."
        )

        return {
            "title": primary_title,
            "document_type": primary_type,
            "strategy_label": "Combined document design",
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
            if any(token in str(getattr(finding, "message", "")).lower() for token in ("约束", "字段", "constraint", "field")):
                test_type = "data_validation"

            tests.append({
                "id": f"BUNDLE-{idx:03d}",
                "name": f"Cross-document {category} validation {idx}",
                "type": test_type,
                "priority": "high" if severity in {"error", "warning"} else "medium",
                "instruction": (
                    "Run combined verification from primary/reference cross-document findings.\n"
                    f"Issue: {getattr(finding, 'message', '')}\n"
                    "Steps: Compare primary documents, references, and implementation; trigger relevant business/API/data scenarios; verify behavior, responses, and data against every document.\n"
                    f"Expected: {getattr(finding, 'suggestion', '')}"
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
