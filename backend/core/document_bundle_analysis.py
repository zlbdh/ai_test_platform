"""
Cross-document analysis

Responsibilities:
- Check consistency and coverage across primary and reference documents
- Identify gaps or conflicts in APIs, status codes, constraints, and related signals
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional


@dataclass
class BundleFinding:
    finding_id: str
    severity: str
    category: str
    message: str
    suggestion: str


@dataclass
class BundleAnalysis:
    coverage_score: float
    consistency_score: float
    involved_document_types: List[str] = field(default_factory=list)
    aligned_signals: Dict[str, int] = field(default_factory=dict)
    uncovered_signals: Dict[str, int] = field(default_factory=dict)
    findings: List[BundleFinding] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)


class DocumentBundleAnalyzer:
    _SIGNAL_KEYS = [
        "api_endpoints",
        "api_parameters",
        "response_statuses",
        "error_codes",
        "database_objects",
        "database_relations",
        "data_constraints",
    ]

    def analyze(self, primary_analysis: object, references: List[Dict[str, object]]) -> BundleAnalysis:
        involved_document_types = self._unique(
            [getattr(primary_analysis, "document_type", "general_text")] +
            [str(item.get("document_type", "general_text")) for item in references]
        )

        aligned_signals: Dict[str, int] = {}
        uncovered_signals: Dict[str, int] = {}
        findings: List[BundleFinding] = []

        primary_extracted = getattr(primary_analysis, "extracted", {})
        reference_extracted = [item.get("extracted", {}) for item in references]

        for signal_key in self._SIGNAL_KEYS:
            primary_values = self._normalize_values(primary_extracted.get(signal_key, []))
            reference_values = self._normalize_values([
                value
                for extracted in reference_extracted
                for value in extracted.get(signal_key, [])
            ])
            aligned_signals[signal_key] = len(primary_values & reference_values)
            uncovered_signals[signal_key] = len(primary_values - reference_values)

        findings.extend(self._build_presence_findings(primary_analysis, references))
        findings.extend(self._build_signal_gap_findings(primary_analysis, references))
        findings.extend(self._build_constraint_conflict_findings(primary_analysis, references))

        coverage_score = self._score_coverage(primary_analysis, references, uncovered_signals)
        consistency_score = self._score_consistency(aligned_signals, findings)

        return BundleAnalysis(
            coverage_score=coverage_score,
            consistency_score=consistency_score,
            involved_document_types=involved_document_types,
            aligned_signals=aligned_signals,
            uncovered_signals=uncovered_signals,
            findings=findings,
            recommended_actions=self._build_recommended_actions(findings, primary_analysis, references),
        )

    def _build_presence_findings(self, primary_analysis: object, references: List[Dict[str, object]]) -> List[BundleFinding]:
        findings: List[BundleFinding] = []
        primary_type = getattr(primary_analysis, "document_type", "general_text")
        reference_types = {str(item.get("document_type", "general_text")) for item in references}
        primary_extracted = getattr(primary_analysis, "extracted", {})

        if primary_type == "requirement_prd" and not reference_types.intersection({"development_design", "api_spec"}):
            findings.append(self._finding(
                "warning",
                "coverage",
                "The requirements document lacks development/API references, limiting cross-document analysis.",
                "Add development designs, OpenAPI specifications, or interface documentation before checking consistency."
            ))

        if primary_extracted.get("data_constraints") and not any(
            item.get("extracted", {}).get("data_constraints") or item.get("extracted", {}).get("database_objects")
            for item in references
        ):
            findings.append(self._finding(
                "warning",
                "coverage",
                "The primary document contains data constraints that are absent from reference field/table definitions.",
                "Add database designs or API field constraints to establish data-validation traceability."
            ))

        if primary_extracted.get("error_codes") and not any(
            item.get("extracted", {}).get("error_codes") or item.get("extracted", {}).get("response_statuses")
            for item in references
        ):
            findings.append(self._finding(
                "info",
                "coverage",
                "The primary document mentions failure/error codes without corresponding reference response definitions.",
                "Add error-code meanings, exception response bodies, and failure-path descriptions."
            ))

        return findings

    def _build_signal_gap_findings(self, primary_analysis: object, references: List[Dict[str, object]]) -> List[BundleFinding]:
        findings: List[BundleFinding] = []
        primary_extracted = getattr(primary_analysis, "extracted", {})

        primary_endpoints = self._normalize_values(primary_extracted.get("api_endpoints", []))
        reference_endpoints = self._normalize_values([
            value
            for item in references
            for value in item.get("extracted", {}).get("api_endpoints", [])
        ])
        if primary_endpoints and reference_endpoints:
            missing_endpoints = sorted(primary_endpoints - reference_endpoints)
            if missing_endpoints:
                findings.append(self._finding(
                    "warning",
                    "consistency",
                    f"Some primary-document APIs lack reference definitions: {', '.join(missing_endpoints[:3])}.",
                    "Check API names and path versions, or add the missing definitions."
                ))

        primary_codes = self._extract_status_like_codes(primary_extracted)
        reference_codes = self._normalize_values([
            code
            for item in references
            for code in self._extract_status_like_codes(item.get("extracted", {}))
        ])
        if primary_codes and reference_codes and not (primary_codes & reference_codes):
            findings.append(self._finding(
                "warning",
                "consistency",
                "The primary and reference documents have no overlapping error codes or response statuses.",
                "Check error-code consistency and standardize success/failure response designs."
            ))

        return findings

    def _build_constraint_conflict_findings(self, primary_analysis: object, references: List[Dict[str, object]]) -> List[BundleFinding]:
        findings: List[BundleFinding] = []
        primary_constraints = self._index_constraints(getattr(primary_analysis, "extracted", {}).get("data_constraints", []))
        reference_constraints: Dict[str, List[tuple[str, str]]] = {}
        for item in references:
            current = self._index_constraints(item.get("extracted", {}).get("data_constraints", []))
            for field_name, values in current.items():
                reference_constraints.setdefault(field_name, []).extend(values)

        for field_name, primary_values in primary_constraints.items():
            reference_values = reference_constraints.get(field_name, [])
            if not reference_values:
                continue

            primary_set = {value for value, _ in primary_values}
            reference_set = {value for value, _ in reference_values}
            if primary_set != reference_set:
                sample_primary = primary_values[0][1]
                sample_reference = reference_values[0][1]
                findings.append(self._finding(
                    "warning",
                    "consistency",
                    f"Field/constraint '{field_name}' differs across documents: {sample_primary} <> {sample_reference}.",
                    "Standardize constraint thresholds, units, and comparison operators to avoid conflicting test assertions."
                ))

        return findings

    def _index_constraints(self, constraints: List[str]) -> Dict[str, List[tuple[str, str]]]:
        indexed: Dict[str, List[tuple[str, str]]] = {}
        for constraint in constraints:
            parsed = self._parse_constraint(constraint)
            if not parsed:
                continue
            field_name, normalized_value = parsed
            indexed.setdefault(field_name, []).append((normalized_value, constraint))
        return indexed

    def _parse_constraint(self, constraint: str) -> Optional[tuple[str, str]]:
        text = constraint.strip()
        patterns = [
            r"(?P<field>[A-Za-z_][A-Za-z0-9_.]*)[^0-9<>=]{0,20}(?P<op>>=|<=|>|<|=)\s*(?P<value>\d+(?:\.\d+)?)",
            r"(?P<field>[\u4e00-\u9fa5A-Za-z_][\u4e00-\u9fa5A-Za-z0-9_.]*)[^0-9]{0,20}(?P<op>不少于|不低于|至少|不小于|不大于|不超过|至多|最多|大于|小于|高于|低于|为)\s*(?P<value>\d+(?:\.\d+)?)",
        ]
        patterns.append(
            r"(?P<field>[A-Za-z_][A-Za-z0-9_.]*)\s+(?i:(?:must\s+be\s+|should\s+be\s+|is\s+)?(?P<op>no less than|not less than|at least|no more than|not greater than|at most|greater than|more than|less than|equals?))\s*(?P<value>\d+(?:\.\d+)?)"
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            field_name = match.group("field").strip().split(".")[-1].lower()
            operator = self._normalize_operator(match.group("op"))
            value = match.group("value").strip()
            return field_name, f"{operator}{value}"
        return None

    def _normalize_operator(self, operator: str) -> str:
        mapping = {
            "不少于": ">=",
            "不低于": ">=",
            "至少": ">=",
            "不小于": ">=",
            "不大于": "<=",
            "不超过": "<=",
            "至多": "<=",
            "最多": "<=",
            "大于": ">",
            "高于": ">",
            "小于": "<",
            "低于": "<",
            "为": "=",
        }
        mapping.update({
            "no less than": ">=", "not less than": ">=", "at least": ">=",
            "no more than": "<=", "not greater than": "<=", "at most": "<=",
            "greater than": ">", "more than": ">", "less than": "<", "equal": "=", "equals": "=",
        })
        return mapping.get(operator.lower(), operator)

    def _extract_status_like_codes(self, extracted: Dict[str, List[str]]) -> set[str]:
        codes = set()
        for code in extracted.get("error_codes", []):
            codes.add(str(code).strip().upper())
        for status_item in extracted.get("response_statuses", []):
            match = re.search(r"(?:->\s*)([1-5]\d{2}|DEFAULT)$", str(status_item).strip(), flags=re.IGNORECASE)
            if match:
                codes.add(match.group(1).upper())
        return codes

    def _score_coverage(
        self,
        primary_analysis: object,
        references: List[Dict[str, object]],
        uncovered_signals: Dict[str, int],
    ) -> float:
        score = 0.45
        reference_types = {str(item.get("document_type", "general_text")) for item in references}
        if reference_types.intersection({"development_design", "api_spec"}):
            score += 0.2
        if reference_types.intersection({"database_schema"}):
            score += 0.15

        covered_categories = sum(1 for count in uncovered_signals.values() if count == 0)
        score += min(covered_categories * 0.03, 0.15)

        primary_type = getattr(primary_analysis, "document_type", "general_text")
        if primary_type == "requirement_prd" and references:
            score += 0.05

        uncovered_categories = sum(1 for count in uncovered_signals.values() if count > 0)
        score -= min(uncovered_categories * 0.03, 0.18)
        return round(max(0.0, min(score, 1.0)), 2)

    def _score_consistency(self, aligned_signals: Dict[str, int], findings: List[BundleFinding]) -> float:
        score = 0.82
        score += min(sum(1 for count in aligned_signals.values() if count > 0) * 0.03, 0.12)
        for finding in findings:
            if finding.severity == "warning":
                score -= 0.08
            elif finding.severity == "info":
                score -= 0.03
            else:
                score -= 0.1
        return round(max(0.0, min(score, 1.0)), 2)

    def _build_recommended_actions(
        self,
        findings: List[BundleFinding],
        primary_analysis: object,
        references: List[Dict[str, object]],
    ) -> List[str]:
        actions = [finding.suggestion for finding in findings]
        primary_type = getattr(primary_analysis, "document_type", "general_text")
        reference_types = {str(item.get("document_type", "general_text")) for item in references}

        if primary_type == "requirement_prd" and "api_spec" in reference_types:
            actions.append("Map requirement scenarios to API paths to trace business workflows to APIs.")
        if "database_schema" in reference_types:
            actions.append("Map key field constraints to database validation and data-consistency tests.")
        if not actions:
            actions.append("No obvious cross-document gaps were found; generate tests from the combined context.")
        return self._unique(actions)

    def _finding(self, severity: str, category: str, message: str, suggestion: str) -> BundleFinding:
        seq = abs(hash((severity, category, message, suggestion))) % 10000
        return BundleFinding(
            finding_id=f"BND-{seq:04d}",
            severity=severity,
            category=category,
            message=message,
            suggestion=suggestion,
        )

    def _normalize_values(self, values: List[str]) -> set[str]:
        return {str(value).strip().lower() for value in values if str(value).strip()}

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


_document_bundle_analyzer: Optional[DocumentBundleAnalyzer] = None


def get_document_bundle_analyzer() -> DocumentBundleAnalyzer:
    global _document_bundle_analyzer
    if _document_bundle_analyzer is None:
        _document_bundle_analyzer = DocumentBundleAnalyzer()
    return _document_bundle_analyzer
