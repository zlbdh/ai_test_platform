# -*- coding: utf-8 -*-
"""
Smart Locator — 预防型智能定位器

对比传统自愈（失败后修复），实现预测型定位：
- ElementFingerprint: 多特征指纹（CSS+文本+位置+视觉hash）
- FingerprintMatcher: 指纹匹配引擎
- LocatorHistory: 选择器演变历史库
- FlakyDetector: 反复自愈检测+标记
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib
import json
import time
import os
import sqlite3
import logging

logger = logging.getLogger(__name__)


@dataclass
class ElementFingerprint:
    """
    元素多特征指纹

    通过多维度特征识别元素，即使单个特征变化也能匹配。
    """
    element_id: str = ""
    # 文本特征
    text: str = ""
    placeholder: str = ""
    aria_label: str = ""
    # 结构特征
    tag: str = ""
    css_selector: str = ""
    xpath: str = ""
    # 位置特征
    relative_x: float = 0.0       # 相对于视口的归一化坐标
    relative_y: float = 0.0
    # 视觉特征
    visual_hash: str = ""         # 元素截图的哈希
    # 上下文特征
    parent_text: str = ""
    nearby_text: str = ""         # 周围的文本内容
    # 页面标识
    page_url_pattern: str = ""    # URL 模式（忽略动态参数）
    page_title: str = ""

    # 元数据
    last_success_time: float = 0
    success_count: int = 0
    fail_count: int = 0

    def compute_hash(self) -> str:
        """计算指纹哈希"""
        key = f"{self.tag}|{self.text}|{self.placeholder}|{self.aria_label}|{self.css_selector}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def to_dict(self) -> Dict:
        return {
            "element_id": self.element_id,
            "text": self.text,
            "tag": self.tag,
            "css_selector": self.css_selector,
            "relative_pos": f"({self.relative_x:.3f}, {self.relative_y:.3f})",
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "hash": self.compute_hash(),
        }


class FingerprintMatcher:
    """
    指纹匹配引擎

    通过加权多特征匹配在页面中找到最可能匹配的元素。
    权重配置：
    - 文本: 0.35
    - 结构（tag + selector）: 0.25
    - 位置: 0.15
    - 上下文: 0.15
    - 视觉: 0.10
    """

    WEIGHTS = {
        "text": 0.35,
        "structure": 0.25,
        "position": 0.15,
        "context": 0.15,
        "visual": 0.10,
    }

    def match(
        self,
        fingerprint: ElementFingerprint,
        candidates: List[ElementFingerprint],
        threshold: float = 0.6,
    ) -> Optional[Tuple[ElementFingerprint, float]]:
        """
        在候选元素中找到最匹配指纹的元素。

        Returns:
            (最佳匹配, 相似度) 或 None
        """
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            score = self._compute_similarity(fingerprint, candidate)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate

        if best_match:
            return (best_match, best_score)
        return None

    def _compute_similarity(self, a: ElementFingerprint, b: ElementFingerprint) -> float:
        """计算两个指纹的相似度"""
        scores = {}

        # 文本相似度
        text_score = 0.0
        text_pairs = [
            (a.text, b.text),
            (a.placeholder, b.placeholder),
            (a.aria_label, b.aria_label),
        ]
        text_matches = sum(1 for x, y in text_pairs if x and y and x == y)
        text_total = sum(1 for x, y in text_pairs if x or y)
        text_score = text_matches / text_total if text_total > 0 else 0.5
        scores["text"] = text_score

        # 结构相似度
        struct_score = 0.0
        if a.tag == b.tag:
            struct_score += 0.5
        if a.css_selector and b.css_selector and a.css_selector == b.css_selector:
            struct_score += 0.5
        elif a.tag == b.tag:
            struct_score += 0.2  # 同类标签部分匹配
        scores["structure"] = min(1.0, struct_score)

        # 位置相似度（归一化坐标距离）
        dx = abs(a.relative_x - b.relative_x)
        dy = abs(a.relative_y - b.relative_y)
        distance = (dx ** 2 + dy ** 2) ** 0.5
        scores["position"] = max(0.0, 1.0 - distance * 5)  # 距离 > 0.2 → 0分

        # 上下文相似度
        ctx_score = 0.0
        if a.parent_text and b.parent_text:
            # 简单字符串包含关系
            if a.parent_text in b.parent_text or b.parent_text in a.parent_text:
                ctx_score = 0.8
            elif any(w in b.parent_text for w in a.parent_text.split()[:3] if len(w) > 1):
                ctx_score = 0.4
        scores["context"] = ctx_score

        # 视觉相似度
        if a.visual_hash and b.visual_hash:
            scores["visual"] = 1.0 if a.visual_hash == b.visual_hash else 0.0
        else:
            scores["visual"] = 0.5  # 无视觉数据时中性

        # 加权求和
        total = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        return total


class LocatorHistory:
    """
    选择器历史库

    记录每次成功定位的选择器演变，用于预测最优选择器。
    """

    def __init__(self):
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "locator_history.db",
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS locator_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint_hash TEXT,
                    page_url TEXT,
                    element_text TEXT,
                    selector_used TEXT,
                    success INTEGER,
                    method TEXT,
                    timestamp REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fingerprint_store (
                    hash TEXT PRIMARY KEY,
                    fingerprint TEXT,
                    updated_at REAL
                )
            """)

    def record(self, fingerprint: ElementFingerprint, selector: str, success: bool, method: str = ""):
        """记录一次定位尝试"""
        fp_hash = fingerprint.compute_hash()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO locator_records (fingerprint_hash, page_url, element_text, selector_used, success, method, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fp_hash, fingerprint.page_url_pattern, fingerprint.text, selector, int(success), method, time.time()))

            # 更新指纹存储
            conn.execute("""
                INSERT OR REPLACE INTO fingerprint_store (hash, fingerprint, updated_at)
                VALUES (?, ?, ?)
            """, (fp_hash, json.dumps(fingerprint.to_dict(), ensure_ascii=False), time.time()))

    def get_best_selector(self, fingerprint_hash: str) -> Optional[str]:
        """获取历史上最成功的选择器"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("""
                SELECT selector_used, COUNT(*) as cnt
                FROM locator_records
                WHERE fingerprint_hash = ? AND success = 1
                GROUP BY selector_used
                ORDER BY cnt DESC
                LIMIT 1
            """, (fingerprint_hash,)).fetchone()
            return row[0] if row else None

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        with sqlite3.connect(self._db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM locator_records").fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM locator_records WHERE success = 1").fetchone()[0]
            unique = conn.execute("SELECT COUNT(DISTINCT fingerprint_hash) FROM locator_records").fetchone()[0]
            return {
                "total_records": total,
                "success_records": success,
                "success_rate": round(success / total, 3) if total > 0 else 0,
                "unique_elements": unique,
            }


class FlakyDetector:
    """
    Flaky 元素检测器

    标记反复触发自愈的元素，提前优化或发出告警。
    """

    def __init__(self, flaky_threshold: int = 3, window_seconds: float = 3600):
        self._threshold = flaky_threshold
        self._window = window_seconds
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "locator_history.db",
        )

    def check(self, fingerprint_hash: str) -> Dict[str, Any]:
        """检查元素是否为 flaky"""
        try:
            cutoff = time.time() - self._window
            with sqlite3.connect(self._db_path) as conn:
                failures = conn.execute("""
                    SELECT COUNT(*) FROM locator_records
                    WHERE fingerprint_hash = ? AND success = 0 AND timestamp > ?
                """, (fingerprint_hash, cutoff)).fetchone()[0]

                total = conn.execute("""
                    SELECT COUNT(*) FROM locator_records
                    WHERE fingerprint_hash = ? AND timestamp > ?
                """, (fingerprint_hash, cutoff)).fetchone()[0]

            is_flaky = failures >= self._threshold
            return {
                "is_flaky": is_flaky,
                "failures_in_window": failures,
                "total_in_window": total,
                "failure_rate": round(failures / total, 3) if total > 0 else 0,
                "recommendation": "建议使用语义定位替代此选择器" if is_flaky else "正常",
            }
        except Exception:
            return {"is_flaky": False, "error": "检查失败"}

    def list_flaky_elements(self) -> List[Dict]:
        """列出所有 flaky 元素"""
        try:
            cutoff = time.time() - self._window
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute("""
                    SELECT fingerprint_hash, element_text, page_url,
                           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
                           COUNT(*) as total
                    FROM locator_records
                    WHERE timestamp > ?
                    GROUP BY fingerprint_hash
                    HAVING failures >= ?
                    ORDER BY failures DESC
                """, (cutoff, self._threshold)).fetchall()

                return [{
                    "fingerprint_hash": r[0],
                    "element_text": r[1],
                    "page_url": r[2],
                    "failures": r[3],
                    "total": r[4],
                    "failure_rate": round(r[3] / r[4], 3) if r[4] > 0 else 0,
                } for r in rows]
        except Exception:
            return []


# ── 单例 ──────────────────────────────────────────────────────────────────────

_matcher: Optional[FingerprintMatcher] = None
_history: Optional[LocatorHistory] = None
_flaky: Optional[FlakyDetector] = None


def get_fingerprint_matcher() -> FingerprintMatcher:
    global _matcher
    if _matcher is None:
        _matcher = FingerprintMatcher()
    return _matcher


def get_locator_history() -> LocatorHistory:
    global _history
    if _history is None:
        _history = LocatorHistory()
    return _history


def get_flaky_detector() -> FlakyDetector:
    global _flaky
    if _flaky is None:
        _flaky = FlakyDetector()
    return _flaky
