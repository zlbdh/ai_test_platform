# -*- coding: utf-8 -*-
"""
Scenario Generator — 场景生成器

从正常流程推导异常场景：
- 组合参数生成边界用例
- 从正常流程反推错误路径
- 性能/安全场景模板填充
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import logging
import itertools

logger = logging.getLogger(__name__)


# ── 场景模板 ──────────────────────────────────────────────────────────────────

BOUNDARY_TEMPLATES = {
    "string": [
        {"name": "空字符串", "value": ""},
        {"name": "单字符", "value": "a"},
        {"name": "最大长度", "value": "a" * 255},
        {"name": "超长字符串", "value": "a" * 10000},
        {"name": "特殊字符", "value": "<script>alert(1)</script>"},
        {"name": "SQL注入", "value": "' OR 1=1 --"},
        {"name": "Unicode字符", "value": "🎯测试émoji"},
        {"name": "空格填充", "value": "   "},
        {"name": "制表符和换行", "value": "\t\n\r"},
    ],
    "number": [
        {"name": "零", "value": 0},
        {"name": "负数", "value": -1},
        {"name": "极大数", "value": 999999999},
        {"name": "小数", "value": 0.001},
        {"name": "边界最大", "value": 2147483647},
        {"name": "非数字字符串", "value": "abc"},
    ],
    "email": [
        {"name": "无效格式", "value": "not-an-email"},
        {"name": "缺少@", "value": "userexample.com"},
        {"name": "缺少域名", "value": "user@"},
        {"name": "特殊字符", "value": "user+tag@example.com"},
        {"name": "超长邮箱", "value": "a" * 200 + "@example.com"},
    ],
    "url": [
        {"name": "无协议", "value": "example.com"},
        {"name": "无效协议", "value": "ftp://example.com"},
        {"name": "含特殊字符", "value": "https://example.com/<script>"},
        {"name": "本地地址", "value": "http://localhost:8080"},
        {"name": "IP地址", "value": "http://192.168.1.1"},
    ],
}

PERFORMANCE_TEMPLATES = [
    {
        "name": "并发用户负载",
        "description": "模拟 {users} 个并发用户同时执行相同操作",
        "params": {"users": [10, 50, 100, 500]},
    },
    {
        "name": "大数据量测试",
        "description": "提交 {size} 条数据记录观察系统响应",
        "params": {"size": [100, 1000, 10000]},
    },
    {
        "name": "持续压力测试",
        "description": "在 {duration} 分钟内持续发送请求",
        "params": {"duration": [5, 15, 30]},
    },
]

SECURITY_TEMPLATES = [
    {"name": "XSS攻击", "action": "输入 <script>alert('xss')</script> 到所有文本输入框"},
    {"name": "SQL注入", "action": "输入 ' OR '1'='1 到查询和搜索输入框"},
    {"name": "CSRF探测", "action": "检查表单是否包含 CSRF token"},
    {"name": "路径遍历", "action": "在文件上传路径中使用 ../../../etc/passwd"},
    {"name": "认证绕过", "action": "直接访问需要认证的API端点（不带token）"},
    {"name": "权限越权", "action": "用普通用户token访问管理员API"},
    {"name": "敏感信息泄露", "action": "检查API响应中是否包含密码/token等敏感字段"},
]


class ScenarioGenerator:
    """场景生成器"""

    def generate_boundary_scenarios(
        self,
        field_name: str,
        field_type: str = "string",
        custom_values: List[Any] = None,
    ) -> List[Dict]:
        """
        为指定字段生成边界测试场景。

        Args:
            field_name: 字段名称
            field_type: 字段类型（string/number/email/url）
            custom_values: 自定义测试值

        Returns:
            边界测试场景列表
        """
        templates = BOUNDARY_TEMPLATES.get(field_type, BOUNDARY_TEMPLATES["string"])
        scenarios = []

        for t in templates:
            scenarios.append({
                "title": f"{field_name} - {t['name']}",
                "category": "boundary",
                "field": field_name,
                "test_value": t["value"],
                "expected": f"{field_name}字段输入'{t['name']}'时应正确处理",
            })

        if custom_values:
            for i, val in enumerate(custom_values):
                scenarios.append({
                    "title": f"{field_name} - 自定义值 {i+1}",
                    "category": "boundary",
                    "field": field_name,
                    "test_value": val,
                    "expected": f"{field_name}字段输入自定义值时应正确处理",
                })

        return scenarios

    def generate_negative_scenarios(self, positive_flow: List[Dict]) -> List[Dict]:
        """
        从正常流程反推负面场景。

        为每个步骤生成：跳过、错误输入、超时 等变体。
        """
        scenarios = []

        for i, step in enumerate(positive_flow):
            action = step.get("action", step.get("instruction", ""))

            # 跳过此步骤
            scenarios.append({
                "title": f"跳过步骤 {i+1}: {action[:30]}",
                "category": "negative",
                "description": f"跳过 '{action}' 步骤，直接执行后续操作",
                "skip_step": i,
            })

            # 错误输入
            if any(kw in action for kw in ["输入", "填写", "fill", "type"]):
                scenarios.append({
                    "title": f"步骤 {i+1} 错误输入",
                    "category": "negative",
                    "description": f"在 '{action}' 步骤中输入无效数据",
                    "modify_step": i,
                    "modification": "使用无效数据",
                })

            # 重复操作
            scenarios.append({
                "title": f"重复步骤 {i+1}: {action[:30]}",
                "category": "negative",
                "description": f"连续执行两次 '{action}'",
                "repeat_step": i,
            })

        # 反序执行
        if len(positive_flow) > 2:
            scenarios.append({
                "title": "反序执行所有步骤",
                "category": "negative",
                "description": "按逆序执行所有操作步骤",
            })

        return scenarios

    def generate_performance_scenarios(self, target_url: str) -> List[Dict]:
        """生成性能测试场景"""
        return [
            {
                "title": t["name"],
                "category": "performance",
                "description": t["description"].format(**{k: v[0] for k, v in t["params"].items()}),
                "target_url": target_url,
                "variants": [
                    {
                        "params": dict(zip(t["params"].keys(), combo)),
                        "description": t["description"].format(**dict(zip(t["params"].keys(), combo))),
                    }
                    for combo in itertools.product(*t["params"].values())
                ],
            }
            for t in PERFORMANCE_TEMPLATES
        ]

    def generate_security_scenarios(self, target_url: str) -> List[Dict]:
        """生成安全测试场景"""
        return [
            {
                "title": t["name"],
                "category": "security",
                "action": t["action"],
                "target_url": target_url,
                "priority": "high",
            }
            for t in SECURITY_TEMPLATES
        ]

    def generate_combination_scenarios(
        self,
        fields: Dict[str, List[Any]],
        max_combinations: int = 50,
    ) -> List[Dict]:
        """
        组合参数覆盖 — Pairwise 或全组合。

        Args:
            fields: {字段名: [可能的值列表]}
            max_combinations: 最大组合数
        """
        keys = list(fields.keys())
        values = list(fields.values())

        # 全组合
        all_combos = list(itertools.product(*values))
        if len(all_combos) > max_combinations:
            # 降级为 pairwise 近似：取前 N 个
            all_combos = all_combos[:max_combinations]

        scenarios = []
        for i, combo in enumerate(all_combos):
            params = dict(zip(keys, combo))
            scenarios.append({
                "title": f"组合 {i+1}: {json.dumps(params, ensure_ascii=False)[:80]}",
                "category": "combination",
                "parameters": params,
            })

        return scenarios
