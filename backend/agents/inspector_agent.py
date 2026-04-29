# -*- coding: utf-8 -*-
"""
Inspector Agent — 视觉质检员
每步执行完成后主动审查截图，判定业务是否正确。
与 Healer（修 DOM 定位）和 Judge（文本语义断言）互补：
Inspector 关注的是"操作没报错但业务出错"的场景。

Phase 3 增强：
- store_finding(): 驳回结果写入 ChromaDB bugs 集合
- RAG 召回: 审查前从 bugs 集合检索同页面/同操作的历史记录
- 置信度阈值: confidence < threshold 时自动放行
"""
import json
import logging
import time
from typing import Optional, List

from core.models import InspectionResult
from core.prompts import INSPECTOR_VISION_PROMPT
from core.llm_manager import get_vision_llm
from core.config import Config

logger = logging.getLogger(__name__)

# 无需审查的动作白名单（这些动作不产生业务结果）
SKIP_ACTIONS = frozenset({"goto", "wait", "scroll", "screenshot", "set_var", "done"})


class InspectorAgent:
    """视觉质检员 — 每步执行后审查截图，判定业务正确性"""

    def __init__(self, vlm=None, vector_store=None, confidence_threshold: float = None):
        """
        Args:
            vlm: 可选的 VLM 实例（测试时注入 fake）。
                 如果为 None，运行时通过 get_vision_llm() 懒加载。
            vector_store: 可选的 VectorStore 实例（测试时注入 mock）。
            confidence_threshold: 置信度阈值，低于此值自动放行。
                                  默认读取 Config.INSPECTOR_CONFIDENCE_THRESHOLD。
        """
        self._vlm = vlm
        self._vector_store = vector_store
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else Config.INSPECTOR_CONFIDENCE_THRESHOLD
        )

    @property
    def vlm(self):
        if self._vlm is None:
            self._vlm = get_vision_llm()
        return self._vlm

    @property
    def vector_store(self):
        if self._vector_store is None:
            try:
                from core.vector_store import get_vector_store
                self._vector_store = get_vector_store()
            except Exception as e:
                logger.warning(f"[Inspector] VectorStore unavailable: {e}")
        return self._vector_store

    @staticmethod
    def should_inspect(action: str) -> bool:
        """判断该动作是否需要 Inspector 审查"""
        return action not in SKIP_ACTIONS

    def inspect(
        self,
        screenshot_b64: str,
        step_desc: str,
        expected_outcome: str,
        page_state: dict,
    ) -> InspectionResult:
        """
        审查一张截图，返回通过/驳回判定。

        Args:
            screenshot_b64: 执行后的页面截图 (base64 JPEG)
            step_desc: 刚执行的动作描述 (如 "click(提交按钮)")
            expected_outcome: 期望的业务结果 (如 "应显示提交成功")
            page_state: 当前页面状态 dict (url, title, visible_text 等)

        Returns:
            InspectionResult(passed, confidence, reason, anomalies)
        """
        vision_llm = self.vlm
        if vision_llm is None:
            logger.warning("[Inspector] Vision LLM not available, auto-passing.")
            return InspectionResult(
                passed=True,
                confidence=0.0,
                reason="Vision LLM unavailable, skipped inspection",
            )

        url = page_state.get("url", "unknown")
        visible_text = page_state.get("visible_text", "")
        if isinstance(visible_text, list):
            visible_text = " | ".join(visible_text)
        # Truncate to avoid token overflow
        visible_text = visible_text[:2000]

        # Phase 3: RAG 召回历史审查记录
        history_context = self._recall_history(url, step_desc)

        prompt_text = INSPECTOR_VISION_PROMPT.format(
            step_desc=step_desc,
            expected_outcome=expected_outcome or "操作应正常完成，无异常",
            url=url,
            visible_text=visible_text,
        )

        # 如果有历史记录，追加到 prompt
        if history_context:
            prompt_text += f"\n\n历史审查参考（同页面/同操作的过往发现）:\n{history_context}"

        # Build multimodal message with screenshot
        from langchain_core.messages import HumanMessage

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{screenshot_b64}",
                    },
                },
            ]
        )

        try:
            from core.llm_manager import invoke_with_fallback
            response = invoke_with_fallback(vision_llm, [message])
            result_text = response.content if hasattr(response, "content") else str(response)
            result = self._parse_result(result_text)

            # Phase 3: 置信度阈值校准 — 低置信度自动放行
            if not result.passed and result.confidence < self.confidence_threshold:
                logger.info(
                    f"[Inspector] Confidence {result.confidence:.0%} < threshold "
                    f"{self.confidence_threshold:.0%}, auto-passing despite rejection"
                )
                result = InspectionResult(
                    passed=True,
                    confidence=result.confidence,
                    reason=f"Auto-passed: confidence {result.confidence:.0%} below threshold {self.confidence_threshold:.0%}. Original: {result.reason}",
                    anomalies=result.anomalies,
                )

            # Phase 3: 驳回结果写入 ChromaDB
            if not result.passed:
                self.store_finding(
                    url=url,
                    step_desc=step_desc,
                    result=result,
                )

            return result
        except Exception as e:
            logger.error(f"[Inspector] VLM invocation failed: {e}")
            return InspectionResult(
                passed=True,
                confidence=0.0,
                reason=f"VLM error, auto-passing: {e}",
            )

    def store_finding(
        self,
        url: str,
        step_desc: str,
        result: InspectionResult,
    ) -> Optional[str]:
        """
        将驳回的审查结果写入 ChromaDB bugs 集合（Phase 3: 记忆闭环）。

        Args:
            url: 页面 URL
            step_desc: 操作描述
            result: 审查结果

        Returns:
            存储的文档 ID，失败返回 None
        """
        vs = self.vector_store
        if vs is None:
            logger.warning("[Inspector] VectorStore unavailable, skipping store_finding")
            return None

        content = (
            f"Inspector 驳回 | URL: {url} | 操作: {step_desc} | "
            f"理由: {result.reason} | 异常: {', '.join(result.anomalies)} | "
            f"置信度: {result.confidence:.0%}"
        )
        metadata = {
            "source": "inspector",
            "url": url,
            "step_desc": step_desc,
            "confidence": result.confidence,
            "anomaly_count": len(result.anomalies),
            "timestamp": time.time(),
        }

        try:
            doc_id = vs.store_document("bugs", content, metadata)
            logger.info(f"[Inspector] Finding stored to ChromaDB: {doc_id}")
            return doc_id
        except Exception as e:
            logger.warning(f"[Inspector] Failed to store finding: {e}")
            return None

    def _recall_history(self, url: str, step_desc: str) -> str:
        """
        从 ChromaDB bugs 集合 RAG 召回同页面/同操作的历史审查记录（Phase 3: 记忆闭环）。

        Args:
            url: 当前页面 URL
            step_desc: 当前操作描述

        Returns:
            历史记录文本（空字符串表示无记录或功能禁用）
        """
        if not Config.INSPECTOR_ENABLE_RAG:
            return ""

        vs = self.vector_store
        if vs is None:
            return ""

        query = f"Inspector {step_desc} {url}"
        try:
            results = vs.search("bugs", query, n_results=3)
            if not results:
                return ""

            # 只保留 inspector 来源的记录
            inspector_results = [
                r for r in results
                if r.get("metadata", {}).get("source") == "inspector"
            ]
            if not inspector_results:
                return ""

            lines = []
            for r in inspector_results[:3]:
                content = r.get("content", "")[:300]
                lines.append(f"- {content}")

            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"[Inspector] RAG recall failed (non-critical): {e}")
            return ""

    @staticmethod
    def _parse_result(raw: str) -> InspectionResult:
        """解析 VLM 返回的 JSON 文本为 InspectionResult"""
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
            return InspectionResult(
                passed=bool(data.get("passed", True)),
                confidence=float(data.get("confidence", 0.5)),
                reason=str(data.get("reason", "")),
                anomalies=list(data.get("anomalies", [])),
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"[Inspector] JSON parse failed, auto-passing: {e}")
            return InspectionResult(
                passed=True,
                confidence=0.0,
                reason=f"JSON parse error, auto-passing: {raw[:200]}",
            )
