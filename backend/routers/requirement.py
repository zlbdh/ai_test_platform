# -*- coding: utf-8 -*-
"""
需求解析路由 - 需求文档解析、测试用例生成
"""
import os
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from core.models import RequirementParseRequest, FileParseRequest
from core.document_analysis import get_document_analyzer
from core.document_bundle_analysis import get_document_bundle_analyzer
from core.document_file_parser import extract_text_from_bytes, extract_text_from_path
from core.document_test_designer import get_document_test_designer
from core.project_playbooks import get_requirement_playbook, list_playbooks
from core.requirement_parser import get_requirement_parser

router = APIRouter(prefix="/api/requirement", tags=["Requirement Parsing"])


@router.get("/playbooks")
async def list_requirement_playbooks():
    """列出可用的项目级需求回归包。"""
    return {"playbooks": list_playbooks()}


@router.get("/playbooks/{playbook_id}")
async def get_requirement_playbook_detail(playbook_id: str):
    """获取项目级需求回归包详情。"""
    playbook = get_requirement_playbook(playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return playbook


def _build_analysis_payload(analysis) -> dict:
    return {
        "document_type": analysis.document_type,
        "document_label": analysis.document_label,
        "quality_score": analysis.quality_score,
        "completeness_score": analysis.completeness_score,
        "testability_score": analysis.testability_score,
        "recommended_test_types": analysis.recommended_test_types,
        "issues": [
            {
                "issue_id": issue.issue_id,
                "severity": issue.severity,
                "category": issue.category,
                "message": issue.message,
                "suggestion": issue.suggestion,
            }
            for issue in analysis.issues
        ],
        "extracted": analysis.extracted,
        "next_actions": analysis.next_actions,
    }


def _build_bundle_payload(bundle_analysis) -> dict:
    return {
        "coverage_score": bundle_analysis.coverage_score,
        "consistency_score": bundle_analysis.consistency_score,
        "involved_document_types": bundle_analysis.involved_document_types,
        "aligned_signals": bundle_analysis.aligned_signals,
        "uncovered_signals": bundle_analysis.uncovered_signals,
        "findings": [
            {
                "finding_id": finding.finding_id,
                "severity": finding.severity,
                "category": finding.category,
                "message": finding.message,
                "suggestion": finding.suggestion,
            }
            for finding in bundle_analysis.findings
        ],
        "recommended_actions": bundle_analysis.recommended_actions,
    }


def _resolve_title(preferred_title: str, fallback_name: str) -> str:
    title = (preferred_title or "").strip()
    if title:
        return title
    return os.path.splitext(os.path.basename(fallback_name))[0] or "Untitled Requirement"


def _build_reference_analyses(references) -> list[dict]:
    analyzer = get_document_analyzer()
    parser = get_requirement_parser()
    payloads = []
    for index, reference in enumerate(references or [], 1):
        content = getattr(reference, "content", "").strip()
        if not content:
            continue
        title = _resolve_title(getattr(reference, "title", ""), f"reference_{index}")
        analysis = analyzer.analyze(content, title)
        parsed_result = None
        if analysis.document_type in {"requirement_prd", "development_design", "general_text"}:
            parsed_result = parser.parse_text(content, title)
        payloads.append({
            "title": title,
            "content": content,
            "analysis": analysis,
            "parsed_result": parsed_result,
            "document_type": analysis.document_type,
            "document_label": analysis.document_label,
            "extracted": analysis.extracted,
        })
    return payloads


def _build_parse_response(content: str, title: str, references=None) -> dict:
    parser = get_requirement_parser()
    analyzer = get_document_analyzer()
    bundle_analyzer = get_document_bundle_analyzer()
    result = parser.parse_text(content, title)
    analysis = analyzer.analyze(content, title, result)
    reference_analyses = _build_reference_analyses(references)

    response = {
        "status": "success",
        "title": result.title,
        "summary": result.summary,
        "confidence": result.confidence,
        "rules_count": len(result.rules),
        "test_cases_count": len(result.test_cases),
        "rules": [
            {
                "rule_id": r.rule_id,
                "type": r.rule_type.value,
                "description": r.description,
                "priority": r.priority.value
            }
            for r in result.rules
        ],
        "test_cases": [
            {
                "case_id": tc.case_id,
                "title": tc.title,
                "test_type": tc.test_type,
                "priority": tc.priority.value,
                "steps": tc.steps,
                "expected_results": tc.expected_results
            }
            for tc in result.test_cases
        ],
        "analysis": _build_analysis_payload(analysis),
    }

    if reference_analyses:
        bundle_analysis = bundle_analyzer.analyze(analysis, reference_analyses)
        response["references_analysis"] = [
            {
                "title": item["title"],
                "document_type": item["document_type"],
                "document_label": item["document_label"],
                "analysis": _build_analysis_payload(item["analysis"]),
            }
            for item in reference_analyses
        ]
        response["bundle_analysis"] = _build_bundle_payload(bundle_analysis)

    return response


@router.post("/analyze")
async def analyze_requirement(req: RequirementParseRequest):
    """检测并解析需求/开发文档，返回结构化分析结果。"""
    return _build_parse_response(req.content, req.title, req.references)


@router.post("/parse")
async def parse_requirement(req: RequirementParseRequest):
    """解析需求文档，提取业务规则和生成测试用例"""
    return _build_parse_response(req.content, req.title, req.references)


@router.post("/parse-file")
async def parse_requirement_file(req: FileParseRequest):
    """解析需求文档文件"""
    # 安全校验: 防止路径遍历攻击
    safe_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    abs_path = os.path.abspath(req.file_path)
    if not abs_path.startswith(safe_base):
        raise HTTPException(status_code=403, detail="Access denied: path outside project directory")
    if '..' in req.file_path:
        raise HTTPException(status_code=403, detail="Access denied: path traversal not allowed")

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    content = extract_text_from_path(abs_path)
    title = _resolve_title("", abs_path)
    response = _build_parse_response(content, title)
    response["file"] = req.file_path
    response["extracted_text"] = content
    return response


@router.post("/parse-upload")
async def parse_requirement_upload(
    file: UploadFile = File(...),
    title: str = Form(""),
):
    """上传并解析需求 / 开发文档文件。"""
    filename = file.filename or "uploaded_document"
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        content = extract_text_from_bytes(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resolved_title = _resolve_title(title, filename)
    response = _build_parse_response(content, resolved_title)
    response["uploaded_filename"] = filename
    response["extracted_text"] = content
    return response


@router.post("/generate-tests")
async def generate_tests_from_requirement(req: RequirementParseRequest):
    """从需求直接生成可执行的测试用例"""
    parser = get_requirement_parser()
    analyzer = get_document_analyzer()
    bundle_analyzer = get_document_bundle_analyzer()
    designer = get_document_test_designer()
    result = parser.parse_text(req.content, req.title)
    analysis = analyzer.analyze(req.content, req.title, result)
    reference_analyses = _build_reference_analyses(req.references)
    bundle_analysis = None

    if reference_analyses:
        bundle_analysis = bundle_analyzer.analyze(analysis, reference_analyses)
        designed = designer.design_bundle(
            req.content,
            req.title,
            analysis,
            result,
            reference_analyses,
            bundle_analysis,
        )
    else:
        designed = designer.design(req.content, req.title, analysis, result)

    executable_tests = designed.get("tests", [])

    response = {
        "status": "success",
        "total_tests": len(executable_tests),
        "confidence": result.confidence,
        "tests": executable_tests,
        "analysis": _build_analysis_payload(analysis),
        "generation_summary": designed.get("generation_summary", {}),
    }

    if reference_analyses:
        response["references_analysis"] = [
            {
                "title": item["title"],
                "document_type": item["document_type"],
                "document_label": item["document_label"],
                "analysis": _build_analysis_payload(item["analysis"]),
            }
            for item in reference_analyses
        ]
        response["bundle_analysis"] = _build_bundle_payload(bundle_analysis)

    return response
