"""
Test Knowledge Base - 测试知识库

学习历史测试模式，持续优化测试决策：
- 记录成功/失败模式
- 学习最佳测试策略
- 推荐历史类似案例
- 持久化知识
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import hashlib
from pathlib import Path


@dataclass
class TestPattern:
    """测试模式"""

    __test__ = False

    pattern_id: str
    requirement_hash: str
    requirement_keywords: List[str]
    test_types: List[str]
    success_count: int = 0
    failure_count: int = 0
    avg_duration_ms: float = 0
    last_used: str = ""
    metadata: Dict[str, Any] = None

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0


@dataclass
class TestCase:
    """测试用例记录"""

    __test__ = False

    case_id: str
    requirement: str
    target_url: Optional[str]
    test_types: List[str]
    result: str  # success, failure, skipped
    duration_ms: int
    error_message: Optional[str]
    timestamp: str
    healing_applied: bool = False
    ai_confidence: float = 0


class TestKnowledgeBase:
    """测试知识库"""

    __test__ = False

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or "data/test_knowledge")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.patterns: Dict[str, TestPattern] = {}
        self.cases: List[TestCase] = []
        self.keyword_index: Dict[str, List[str]] = {}  # keyword -> requirement_hashes

        self._load()

    def _load(self):
        """加载持久化数据"""
        patterns_file = self.storage_path / "patterns.json"
        cases_file = self.storage_path / "cases.json"

        if patterns_file.exists():
            try:
                with open(patterns_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for p in data:
                        pattern = TestPattern(**p)
                        self.patterns[pattern.requirement_hash] = pattern
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to load patterns: {e}")

        if cases_file.exists():
            try:
                with open(cases_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cases = [TestCase(**c) for c in data[-1000:]]
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to load cases: {e}")

        self._rebuild_index()

    def _save(self):
        """持久化数据"""
        patterns_file = self.storage_path / "patterns.json"
        cases_file = self.storage_path / "cases.json"

        with open(patterns_file, "w", encoding="utf-8") as f:
            json.dump([asdict(p) for p in self.patterns.values()], f, ensure_ascii=False, indent=2)

        with open(cases_file, "w", encoding="utf-8") as f:
            json.dump([asdict(c) for c in self.cases[-1000:]], f, ensure_ascii=False, indent=2)

    def _rebuild_index(self):
        """重建关键词索引"""
        self.keyword_index.clear()
        for pattern_key, pattern in self.patterns.items():
            self._add_to_index(pattern_key, pattern.requirement_keywords)

    @staticmethod
    def _unique_preserve_order(items: List[str]) -> List[str]:
        """去重并保持原顺序"""
        return list(dict.fromkeys(items))

    def _add_to_index(self, pattern_key: str, keywords: List[str]):
        """向关键词索引注册模式键"""
        for kw in self._unique_preserve_order(keywords):
            bucket = self.keyword_index.setdefault(kw, [])
            if pattern_key not in bucket:
                bucket.append(pattern_key)

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        import re

        words = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text.lower())
        stopwords = {"的", "是", "在", "和", "了", "a", "the", "is", "and", "to", "test"}
        return [w for w in words if w not in stopwords and len(w) > 1]

    def _hash_requirement(self, requirement: str) -> str:
        """生成需求哈希"""
        keywords = sorted(self._extract_keywords(requirement))
        return hashlib.md5("_".join(keywords).encode()).hexdigest()[:16]

    def record_test(
        self,
        requirement: str,
        target_url: Optional[str],
        test_types: List[str],
        result: str,
        duration_ms: int,
        error_message: Optional[str] = None,
        healing_applied: bool = False,
        ai_confidence: float = 0,
    ) -> TestCase:
        """记录测试执行"""
        case_id = f"tc_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.cases)}"

        case = TestCase(
            case_id=case_id,
            requirement=requirement,
            target_url=target_url,
            test_types=list(test_types),
            result=result,
            duration_ms=duration_ms,
            error_message=error_message,
            timestamp=datetime.now().isoformat(),
            healing_applied=healing_applied,
            ai_confidence=ai_confidence,
        )

        self.cases.append(case)
        self._update_pattern(requirement, test_types, result, duration_ms)

        if len(self.cases) % 10 == 0:
            self._save()

        return case

    def _update_pattern(
        self,
        requirement: str,
        test_types: List[str],
        result: str,
        duration_ms: int,
    ):
        """更新或创建模式"""
        req_hash = self._hash_requirement(requirement)
        keywords = self._unique_preserve_order(self._extract_keywords(requirement))
        normalized_test_types = self._unique_preserve_order(list(test_types))

        if req_hash in self.patterns:
            pattern = self.patterns[req_hash]
            pattern.test_types = self._unique_preserve_order(
                pattern.test_types + normalized_test_types
            )
            if result == "success":
                pattern.success_count += 1
            else:
                pattern.failure_count += 1

            total = pattern.success_count + pattern.failure_count
            pattern.avg_duration_ms = (
                (pattern.avg_duration_ms * (total - 1) + duration_ms) / total
            )
            pattern.last_used = datetime.now().isoformat()
            self._add_to_index(req_hash, pattern.requirement_keywords)
        else:
            pattern = TestPattern(
                pattern_id=f"pat_{req_hash}",
                requirement_hash=req_hash,
                requirement_keywords=keywords,
                test_types=normalized_test_types,
                success_count=1 if result == "success" else 0,
                failure_count=0 if result == "success" else 1,
                avg_duration_ms=duration_ms,
                last_used=datetime.now().isoformat(),
                metadata={},
            )
            self.patterns[req_hash] = pattern
            self._add_to_index(req_hash, keywords)

    def find_similar_patterns(
        self,
        requirement: str,
        limit: int = 5,
    ) -> List[TestPattern]:
        """查找相似模式"""
        keywords = self._extract_keywords(requirement)

        scores: Dict[str, float] = {}
        for kw in self._unique_preserve_order(keywords):
            for pattern_key in self.keyword_index.get(kw, []):
                scores[pattern_key] = scores.get(pattern_key, 0) + 1

        results = []
        for pattern_key, _score in sorted(scores.items(), key=lambda x: -x[1]):
            pattern = self.patterns.get(pattern_key)
            if pattern:
                results.append(pattern)
                if len(results) >= limit:
                    break

        return results

    def recommend_test_types(self, requirement: str) -> Dict[str, float]:
        """根据历史推荐测试类型"""
        similar = self.find_similar_patterns(requirement, limit=10)

        if not similar:
            return {}

        type_scores: Dict[str, float] = {}
        for pattern in similar:
            weight = pattern.success_rate
            for test_type in pattern.test_types:
                type_scores[test_type] = type_scores.get(test_type, 0) + weight

        max_score = max(type_scores.values()) if type_scores else 1
        return {k: v / max_score for k, v in type_scores.items()}

    def get_statistics(self) -> Dict[str, Any]:
        """获取知识库统计"""
        total_cases = len(self.cases)
        success_cases = sum(1 for c in self.cases if c.result == "success")

        return {
            "total_patterns": len(self.patterns),
            "total_cases": total_cases,
            "success_rate": success_cases / total_cases if total_cases > 0 else 0,
            "avg_duration_ms": sum(c.duration_ms for c in self.cases) / total_cases if total_cases else 0,
            "healing_rate": sum(1 for c in self.cases if c.healing_applied) / total_cases if total_cases else 0,
        }

    def export_report(self) -> Dict[str, Any]:
        """导出知识库报告"""
        stats = self.get_statistics()

        top_patterns = sorted(
            self.patterns.values(),
            key=lambda p: (p.success_rate, p.success_count),
            reverse=True,
        )[:10]

        return {
            "statistics": stats,
            "top_patterns": [asdict(p) for p in top_patterns],
            "recent_failures": [asdict(c) for c in self.cases[-100:] if c.result != "success"][-10:],
        }


_knowledge_base: Optional[TestKnowledgeBase] = None


def get_knowledge_base() -> TestKnowledgeBase:
    """获取知识库单例"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = TestKnowledgeBase()
    return _knowledge_base
