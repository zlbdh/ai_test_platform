# -*- coding: utf-8 -*-
"""
Smart Locator — preventive element locator

Predictive location, compared with conventional healing after a failure:
- ElementFingerprint: Multifeature fingerprint (CSS + text + position + visual hash)
- FingerprintMatcher: Fingerprint matching engine
- LocatorHistory: Selector evolution history
- FlakyDetector: Repeated healing detection and tagging
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
    Multifeature element fingerprint

    Identify elements using multiple features, retaining matches even when one feature changes.
    """
    element_id: str = ""
    # Text features
    text: str = ""
    placeholder: str = ""
    aria_label: str = ""
    # Structural features
    tag: str = ""
    css_selector: str = ""
    xpath: str = ""
    # Position features
    relative_x: float = 0.0       # Normalized viewport-relative coordinates
    relative_y: float = 0.0
    # Visual features
    visual_hash: str = ""         # Hash of the element screenshot
    # Context features
    parent_text: str = ""
    nearby_text: str = ""         # Surrounding text
    # Page identity
    page_url_pattern: str = ""    # URL pattern (ignoring dynamic parameters)
    page_title: str = ""

    # Metadata
    last_success_time: float = 0
    success_count: int = 0
    fail_count: int = 0

    def compute_hash(self) -> str:
        """Calculate the fingerprint hash"""
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
    Fingerprint matching engine

    Find the most likely matching page element using weighted feature matching.
    Weight configuration:
    - Text: 0.35
    - Structure (tag + selector): 0.25
    - Position: 0.15
    - Context: 0.15
    - Visual: 0.10
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
        Find the candidate that best matches the fingerprint.

        Returns:
            (best match, similarity) or None
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
        """Calculate similarity between two fingerprints"""
        scores = {}

        # Text similarity
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

        # Structural similarity
        struct_score = 0.0
        if a.tag == b.tag:
            struct_score += 0.5
        if a.css_selector and b.css_selector and a.css_selector == b.css_selector:
            struct_score += 0.5
        elif a.tag == b.tag:
            struct_score += 0.2  # Partial match for similar tags
        scores["structure"] = min(1.0, struct_score)

        # Position similarity (normalized coordinate distance)
        dx = abs(a.relative_x - b.relative_x)
        dy = abs(a.relative_y - b.relative_y)
        distance = (dx ** 2 + dy ** 2) ** 0.5
        scores["position"] = max(0.0, 1.0 - distance * 5)  # Distance > 0.2 → score 0

        # Context similarity
        ctx_score = 0.0
        if a.parent_text and b.parent_text:
            # Simple substring matching
            if a.parent_text in b.parent_text or b.parent_text in a.parent_text:
                ctx_score = 0.8
            elif any(w in b.parent_text for w in a.parent_text.split()[:3] if len(w) > 1):
                ctx_score = 0.4
        scores["context"] = ctx_score

        # Visual similarity
        if a.visual_hash and b.visual_hash:
            scores["visual"] = 1.0 if a.visual_hash == b.visual_hash else 0.0
        else:
            scores["visual"] = 0.5  # Neutral when visual data is unavailable

        # Weighted sum
        total = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        return total


class LocatorHistory:
    """
    Selector history

    Record successful selector evolution to predict the best selector.
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
        """Record a location attempt"""
        fp_hash = fingerprint.compute_hash()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT INTO locator_records (fingerprint_hash, page_url, element_text, selector_used, success, method, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fp_hash, fingerprint.page_url_pattern, fingerprint.text, selector, int(success), method, time.time()))

            # Update the fingerprint store
            conn.execute("""
                INSERT OR REPLACE INTO fingerprint_store (hash, fingerprint, updated_at)
                VALUES (?, ?, ?)
            """, (fp_hash, json.dumps(fingerprint.to_dict(), ensure_ascii=False), time.time()))

    def get_best_selector(self, fingerprint_hash: str) -> Optional[str]:
        """Get the most successful historical selector"""
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
        """Get statistics"""
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
    Flaky element detector

    Flag elements that repeatedly trigger healing for early optimization or alerts.
    """

    def __init__(self, flaky_threshold: int = 3, window_seconds: float = 3600):
        self._threshold = flaky_threshold
        self._window = window_seconds
        self._db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "locator_history.db",
        )

    def check(self, fingerprint_hash: str) -> Dict[str, Any]:
        """Check whether the element is flaky"""
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
                "recommendation": "Consider semantic location instead of this selector" if is_flaky else "Normal",
            }
        except Exception:
            return {"is_flaky": False, "error": "Check failed"}

    def list_flaky_elements(self) -> List[Dict]:
        """List all flaky elements"""
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


# ── Singleton ──────────────────────────────────────────────────────────────────────

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
