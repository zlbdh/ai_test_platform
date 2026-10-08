"""
Requirement Parser

Automatically extract from PRD/requirement documents:
- Business rules
- Acceptance criteria
- Test cases
Support 95%+ AI test automation
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import re
import json


class RuleType(Enum):
    FUNCTIONAL = "functional"      # Functional requirements
    VALIDATION = "validation"      # Validation rules
    BUSINESS = "business"          # Business logic
    UI = "ui"                      # UI requirements
    PERFORMANCE = "performance"    # Performance requirements
    SECURITY = "security"          # Security requirements


class Priority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class BusinessRule:
    """Business rule"""
    rule_id: str
    rule_type: RuleType
    description: str
    conditions: List[str]
    expected_behavior: str
    priority: Priority
    source_text: str
    metadata: Dict[str, Any] = None


@dataclass
class TestCase:
    """Test case"""
    case_id: str
    title: str
    description: str
    preconditions: List[str]
    steps: List[str]
    expected_results: List[str]
    test_type: str
    priority: Priority
    related_rules: List[str]
    tags: List[str] = None


@dataclass
class ParsedRequirement:
    """Parsed requirements"""
    title: str
    summary: str
    rules: List[BusinessRule]
    test_cases: List[TestCase]
    raw_sections: Dict[str, str]
    confidence: float


class RequirementParser:
    """Requirement document parser"""
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.rule_patterns = self._init_patterns()
    
    def _init_patterns(self) -> Dict:
        """Initialize rule-recognition patterns"""
        return {
            "must": r"(必须|应该|需要|要求|must|shall|should|require)",
            "condition": r"(当|如果|若|在.*情况下|when|if|given)",
            "validation": r"(验证|校验|检查|确保|validate|verify|check|ensure)",
            "error": r"(错误|失败|异常|拒绝|error|fail|exception|reject)",
            "success": r"(成功|通过|完成|success|pass|complete)",
            "boundary": r"(最大|最小|范围|限制|max|min|range|limit)",
            "ui": r"(显示|页面|按钮|输入框|表单|display|page|button|input|form)",
            "perf": r"(响应时间|性能|并发|吞吐|response time|performance|concurrent)"
        }
    
    def parse_text(self, content: str, title: str = "Untitled") -> ParsedRequirement:
        """
        Parse requirement document text
        
        Args:
            content: Requirement document contents
            title: Document title
        
        Returns:
            ParsedRequirement: Parsing result
        """
        # Split into sections
        sections = self._split_sections(content)
        
        # Extract rules
        rules = self._extract_rules(content, sections)
        
        # Generate test cases
        test_cases = self._generate_test_cases(rules)
        
        # Calculate confidence
        confidence = self._calculate_confidence(rules, content)
        
        return ParsedRequirement(
            title=title,
            summary=self._generate_summary(content),
            rules=rules,
            test_cases=test_cases,
            raw_sections=sections,
            confidence=confidence
        )
    
    def _split_sections(self, content: str) -> Dict[str, str]:
        """Split document sections"""
        sections = {}
        
        # Match Markdown headings
        pattern = r'^(#{1,3})\s+(.+)$'
        lines = content.split('\n')
        
        current_section = "intro"
        current_content = []
        
        for line in lines:
            match = re.match(pattern, line)
            if match:
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                current_section = match.group(2).strip()
                current_content = []
            else:
                current_content.append(line)
        
        if current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def _extract_rules(
        self, 
        content: str, 
        sections: Dict[str, str]
    ) -> List[BusinessRule]:
        """Extract business rules"""
        rules = []
        rule_counter = 0
        
        # Split into sentences
        sentences = re.split(r'[。.!！?？\n]', content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            
            rule_type = self._classify_rule(sentence)
            if rule_type:
                rule_counter += 1
                
                # Extract conditions and expected behavior
                conditions, behavior = self._parse_condition_behavior(sentence)
                
                rules.append(BusinessRule(
                    rule_id=f"BR-{rule_counter:03d}",
                    rule_type=rule_type,
                    description=sentence,
                    conditions=conditions,
                    expected_behavior=behavior,
                    priority=self._determine_priority(sentence),
                    source_text=sentence
                ))
        
        return rules
    
    def _classify_rule(self, text: str) -> Optional[RuleType]:
        """Classify the rule type"""
        text_lower = text.lower()
        
        # Check each pattern category
        if re.search(self.rule_patterns["perf"], text_lower):
            return RuleType.PERFORMANCE
        elif re.search(self.rule_patterns["validation"], text_lower):
            return RuleType.VALIDATION
        elif re.search(self.rule_patterns["ui"], text_lower):
            return RuleType.UI
        elif re.search(self.rule_patterns["must"], text_lower):
            if re.search(self.rule_patterns["condition"], text_lower):
                return RuleType.BUSINESS
            return RuleType.FUNCTIONAL
        elif re.search(self.rule_patterns["condition"], text_lower):
            return RuleType.BUSINESS
        
        return None
    
    def _parse_condition_behavior(self, text: str) -> tuple:
        """Parse conditions and expected behavior"""
        conditions = []
        behavior = text
        
        # Find condition keywords
        cond_patterns = [
            r"当(.+?)时[,，](.+)",
            r"如果(.+?)[,，]则(.+)",
            r"若(.+?)[,，](.+)",
            r"在(.+?)情况下[,，](.+)",
            r"(?i)\b(?:when|if|given)\s+(.+?)[,;]\s*(?:then\s+)?(.+)"
        ]
        
        for pattern in cond_patterns:
            match = re.search(pattern, text)
            if match:
                conditions.append(match.group(1).strip())
                behavior = match.group(2).strip()
                break
        
        return conditions, behavior
    
    def _determine_priority(self, text: str) -> Priority:
        """Determine rule priority"""
        critical_keywords = ["必须", "关键", "核心", "must", "critical", "essential"]
        high_keywords = ["重要", "需要", "should", "important", "required"]
        low_keywords = ["可选", "建议", "optional", "nice to have"]
        
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in critical_keywords):
            return Priority.CRITICAL
        elif any(kw in text_lower for kw in high_keywords):
            return Priority.HIGH
        elif any(kw in text_lower for kw in low_keywords):
            return Priority.LOW
        
        return Priority.MEDIUM
    
    def _generate_test_cases(self, rules: List[BusinessRule]) -> List[TestCase]:
        """Generate test cases from rules"""
        test_cases = []
        case_counter = 0
        
        for rule in rules:
            case_counter += 1
            
            # Positive test case
            test_cases.append(self._create_positive_case(rule, case_counter))
            
            # Generate boundary/negative cases when conditions exist
            if rule.conditions:
                case_counter += 1
                test_cases.append(self._create_negative_case(rule, case_counter))
        
        return test_cases
    
    def _create_positive_case(self, rule: BusinessRule, counter: int) -> TestCase:
        """Create a positive test case"""
        return TestCase(
            case_id=f"TC-{counter:03d}",
            title=f"Verify: {rule.description[:50]}...",
            description=f"Verify the positive scenario for rule {rule.rule_id}",
            preconditions=rule.conditions if rule.conditions else ["The system is operating normally"],
            steps=[
                "Prepare test data",
                "Perform the relevant actions",
                "Observe the system response"
            ],
            expected_results=[rule.expected_behavior],
            test_type=self._map_rule_to_test_type(rule.rule_type),
            priority=rule.priority,
            related_rules=[rule.rule_id],
            tags=[rule.rule_type.value]
        )
    
    def _create_negative_case(self, rule: BusinessRule, counter: int) -> TestCase:
        """Create a negative test case"""
        return TestCase(
            case_id=f"TC-{counter:03d}",
            title=f"Boundary test: {rule.description[:40]}...",
            description=f"Verify boundary/exception scenarios for rule {rule.rule_id}",
            preconditions=["The system is operating normally"],
            steps=[
                "Prepare invalid/boundary test data",
                "Perform the relevant actions",
                "Observe error handling"
            ],
            expected_results=["The system handles exceptions correctly"],
            test_type=self._map_rule_to_test_type(rule.rule_type),
            priority=rule.priority,
            related_rules=[rule.rule_id],
            tags=[rule.rule_type.value, "negative", "boundary"]
        )
    
    def _map_rule_to_test_type(self, rule_type: RuleType) -> str:
        """Map rule types to test types"""
        mapping = {
            RuleType.FUNCTIONAL: "ui_e2e",
            RuleType.VALIDATION: "api_rest",
            RuleType.BUSINESS: "ui_e2e",
            RuleType.UI: "visual_regression",
            RuleType.PERFORMANCE: "performance",
            RuleType.SECURITY: "security"
        }
        return mapping.get(rule_type, "ui_e2e")
    
    def _generate_summary(self, content: str) -> str:
        """Generate a document summary"""
        lines = content.split('\n')
        summary_lines = []
        
        for line in lines[:20]:
            line = line.strip()
            if line and not line.startswith('#'):
                summary_lines.append(line)
                if len(summary_lines) >= 3:
                    break
        
        return ' '.join(summary_lines)[:200]
    
    def _calculate_confidence(
        self, 
        rules: List[BusinessRule], 
        content: str
    ) -> float:
        """Calculate parsing confidence"""
        if not content:
            return 0.0
        
        # Base score
        score = 0.3
        
        # Bonus for rule count
        if len(rules) > 0:
            score += min(0.3, len(rules) * 0.03)
        
        # Bonus for document structure
        if '##' in content or '###' in content:
            score += 0.2
        
        # Bonus for keyword density
        keywords_found = sum(
            1 for p in self.rule_patterns.values()
            if re.search(p, content.lower())
        )
        score += min(0.2, keywords_found * 0.03)
        
        return min(1.0, score)
    
    def to_json(self, result: ParsedRequirement) -> str:
        """Convert to JSON"""
        data = {
            "title": result.title,
            "summary": result.summary,
            "confidence": result.confidence,
            "rules": [
                {
                    **asdict(r),
                    "rule_type": r.rule_type.value,
                    "priority": r.priority.value
                }
                for r in result.rules
            ],
            "test_cases": [
                {
                    **asdict(tc),
                    "priority": tc.priority.value
                }
                for tc in result.test_cases
            ]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)


# Singleton
_parser: Optional[RequirementParser] = None

def get_requirement_parser() -> RequirementParser:
    """Get the requirement parser singleton"""
    global _parser
    if _parser is None:
        _parser = RequirementParser()
    return _parser
