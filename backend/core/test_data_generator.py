# -*- coding: utf-8 -*-
"""
TestDataGenerator — AI 驱动的测试数据管理模块
功能：
1. AI 智能数据生成（边界值、异常值、格式化数据）
2. 数据参数化支持（CSV/JSON 数据集）
3. 预置数据模板（用户/地址/支付/搜索词等）
"""
import json
import random
import string
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ── 预置数据模板 ──

_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "user": {
        "label": "用户信息",
        "description": "生成用户注册/登录测试数据",
        "fields": ["username", "email", "password", "phone", "age"],
        "generator": "_gen_user",
    },
    "address": {
        "label": "地址信息",
        "description": "生成中国地址测试数据",
        "fields": ["province", "city", "district", "street", "zipcode"],
        "generator": "_gen_address",
    },
    "payment": {
        "label": "支付信息",
        "description": "生成支付/订单测试数据",
        "fields": ["order_id", "amount", "currency", "card_number", "expiry"],
        "generator": "_gen_payment",
    },
    "search": {
        "label": "搜索词",
        "description": "生成搜索测试数据（含特殊字符、SQL注入等）",
        "fields": ["keyword", "type"],
        "generator": "_gen_search",
    },
    "boundary": {
        "label": "边界值",
        "description": "生成边界值测试数据（空值、超长、特殊字符）",
        "fields": ["value", "type", "description"],
        "generator": "_gen_boundary",
    },
    "sample_platform_work_order": {
        "label": "示例项目工单",
        "description": "生成示例项目工单调度测试数据，带 TEST_SAMPLE 可回收前缀",
        "fields": ["title", "businessType", "urgencyLevel", "customerName", "customerPhone", "address", "source", "cleanupTag"],
        "generator": "_gen_sample_platform_work_order",
    },
    "sample_platform_property_parking": {
        "label": "示例项目停车合同",
        "description": "生成智慧物业停车合同测试数据，便于续费/终止/导出回归",
        "fields": ["communityName", "licensePlate", "parkingSpaceNo", "contractStatus", "contactName", "contactPhone", "amount", "cleanupTag"],
        "generator": "_gen_sample_platform_property_parking",
    },
    "sample_platform_elder_profile": {
        "label": "示例项目老人档案",
        "description": "生成养老管理老人档案测试数据，默认带脱敏验证字段",
        "fields": ["elderName", "communityName", "careLevel", "contactPhone", "emergencyContact", "specialNeeds", "cleanupTag"],
        "generator": "_gen_sample_platform_elder_profile",
    },
    "sample_platform_announcement": {
        "label": "示例项目公告",
        "description": "生成智慧物业公告/报事测试数据，适合发布与回收验证",
        "fields": ["communityName", "title", "category", "content", "publishStatus", "cleanupTag"],
        "generator": "_gen_sample_platform_announcement",
    },
}

# ── 数据生成器 ──

_FIRST_NAMES = ["张", "李", "王", "赵", "刘", "陈", "杨", "黄", "周", "吴"]
_LAST_NAMES = ["伟", "强", "芳", "敏", "静", "杰", "磊", "洋", "勇", "艳"]
_PROVINCES = ["北京", "上海", "广东", "浙江", "江苏", "四川", "湖北", "山东"]
_CITIES = {"北京": ["朝阳区", "海淀区"], "上海": ["浦东新区", "徐汇区"],
           "广东": ["广州", "深圳"], "浙江": ["杭州", "宁波"]}
_SAMPLE_COMMUNITIES = ["幸福里", "示例项目花园", "康养嘉苑", "春和景明"]
_SAMPLE_BUSINESS_TYPES = ["家政服务", "物业服务", "养老服务"]
_SAMPLE_CARE_LEVELS = ["自理", "半失能", "失能", "特护"]
_SAMPLE_ANNOUNCEMENT_CATEGORIES = ["物业公告", "停水停电", "活动通知", "维修通知"]


def _prefixed_token(prefix: str, index: int) -> str:
    return f"TEST_SAMPLE_{prefix}_{datetime.now().strftime('%m%d')}_{index:03d}"


def _rand_str(n: int, charset: str = string.ascii_lowercase) -> str:
    return ''.join(random.choices(charset, k=n))


def _validate_count(count: int) -> Optional[str]:
    if not isinstance(count, int):
        return "count must be an integer"
    if count < 0:
        return "count must be >= 0"
    if count > 1000:
        return "count must be <= 1000"
    return None


def _gen_user(count: int, include_edge: bool = True) -> List[Dict]:
    """生成用户测试数据"""
    data = []
    for i in range(count):
        name = random.choice(_FIRST_NAMES) + random.choice(_LAST_NAMES) + str(i)
        data.append({
            "username": name,
            "email": f"{_rand_str(6)}@example.com",
            "password": _rand_str(8, string.ascii_letters + string.digits + "!@#$"),
            "phone": f"100{_rand_str(8, string.digits)}",
            "age": random.randint(18, 80),
        })

    if include_edge and count > 0:
        data.extend([
            {"username": "", "email": "", "password": "", "phone": "", "age": 0,
             "_edge": "空值"},
            {"username": "a" * 256, "email": "x" * 200 + "@test.com",
             "password": "a", "phone": "000", "age": -1,
             "_edge": "超长/无效值"},
            {"username": "<script>alert(1)</script>", "email": "test@",
             "password": "12345678", "phone": "00000000000", "age": 999,
             "_edge": "XSS/格式异常"},
        ])

    return data


def _gen_address(count: int, include_edge: bool = True) -> List[Dict]:
    """生成地址测试数据"""
    data = []
    for _ in range(count):
        province = random.choice(_PROVINCES)
        cities = _CITIES.get(province, [province + "市"])
        data.append({
            "province": province,
            "city": random.choice(cities),
            "district": f"{random.choice(['东', '西', '南', '北'])}城区",
            "street": f"{_rand_str(2, '大学中山人民建设')}路{random.randint(1,999)}号",
            "zipcode": _rand_str(6, string.digits),
        })

    if include_edge and count > 0:
        data.append({"province": "", "city": "", "district": "", "street": "", "zipcode": "",
                      "_edge": "空地址"})

    return data


def _gen_payment(count: int, include_edge: bool = True) -> List[Dict]:
    """生成支付测试数据"""
    data = []
    for _ in range(count):
        data.append({
            "order_id": str(uuid.uuid4())[:12].upper(),
            "amount": round(random.uniform(0.01, 99999.99), 2),
            "currency": random.choice(["CNY", "USD", "EUR", "JPY"]),
            "card_number": f"{''.join(random.choices(string.digits, k=16))}",
            "expiry": f"{random.randint(1,12):02d}/{random.randint(25,30)}",
        })

    if include_edge and count > 0:
        data.extend([
            {"order_id": "", "amount": 0, "currency": "", "card_number": "", "expiry": "",
             "_edge": "空值"},
            {"order_id": "X" * 100, "amount": -1, "currency": "INVALID",
             "card_number": "0000000000000000", "expiry": "13/99",
             "_edge": "无效值"},
            {"order_id": "A1", "amount": 0.001, "currency": "CNY",
             "card_number": "1234", "expiry": "00/00",
             "_edge": "边界值"},
        ])

    return data


def _gen_search(count: int, include_edge: bool = True) -> List[Dict]:
    """生成搜索关键词测试数据"""
    normal = ["AI测试", "python教程", "自动化测试工具", "Playwright", "selenium",
              "机器学习", "GPT", "测试用例管理", "DevOps", "云原生"]
    data = [{"keyword": random.choice(normal), "type": "normal"} for _ in range(count)]

    if include_edge and count > 0:
        data.extend([
            {"keyword": "", "type": "empty"},
            {"keyword": " " * 10, "type": "whitespace"},
            {"keyword": "a" * 500, "type": "overflow"},
            {"keyword": "<img onerror=alert(1) src=x>", "type": "xss"},
            {"keyword": "' OR 1=1 --", "type": "sql_injection"},
            {"keyword": "../../etc/passwd", "type": "path_traversal"},
            {"keyword": "测试%00空字节", "type": "null_byte"},
            {"keyword": "🤖💥🔥👾", "type": "emoji"},
            {"keyword": "   前后空格   ", "type": "trim_test"},
        ])

    return data


def _gen_boundary(count: int, **_) -> List[Dict]:
    """生成通用边界值数据，根据 count 参数截取合理数量"""
    all_boundaries = [
        {"value": "", "type": "empty_string", "description": "空字符串"},
        {"value": None, "type": "null", "description": "null 值"},
        {"value": 0, "type": "zero", "description": "零"},
        {"value": -1, "type": "negative", "description": "负数"},
        {"value": 2147483647, "type": "int_max", "description": "INT 最大值"},
        {"value": -2147483648, "type": "int_min", "description": "INT 最小值"},
        {"value": 0.1 + 0.2, "type": "float_precision", "description": "浮点精度问题"},
        {"value": "a" * 1000, "type": "long_string", "description": "超长字符串 (1000)"},
        {"value": "a" * 10000, "type": "very_long", "description": "极长字符串 (10000)"},
        {"value": " ", "type": "single_space", "description": "单个空格"},
        {"value": "\t\n\r", "type": "whitespace_chars", "description": "制表+换行符"},
        {"value": "<script>alert('xss')</script>", "type": "xss", "description": "XSS 攻击"},
        {"value": "'; DROP TABLE users; --", "type": "sql_injection", "description": "SQL 注入"},
        {"value": "../../etc/passwd", "type": "path_traversal", "description": "路径遍历"},
        {"value": "🤖💥🔥", "type": "emoji", "description": "Emoji 字符"},
        {"value": "中文テスト한국어", "type": "multibyte", "description": "多语言字符"},
        {"value": True, "type": "boolean_true", "description": "布尔 True"},
        {"value": False, "type": "boolean_false", "description": "布尔 False"},
        {"value": [], "type": "empty_array", "description": "空数组"},
        {"value": {}, "type": "empty_object", "description": "空对象"},
    ]
    # 根据 count 参数随机采样，避免固定返回全量 20 条
    return random.sample(all_boundaries, min(count, len(all_boundaries)))


def _gen_sample_platform_work_order(count: int, include_edge: bool = True) -> List[Dict]:
    data = []
    for i in range(count):
        token = _prefixed_token("WO", i)
        data.append({
            "title": f"{token}_工单回归",
            "businessType": random.choice(_SAMPLE_BUSINESS_TYPES),
            "urgencyLevel": random.choice(["普通", "紧急", "非常紧急"]),
            "customerName": f"测试客户{i + 1}",
            "customerPhone": f"139{_rand_str(8, string.digits)}",
            "address": f"{random.choice(_SAMPLE_COMMUNITIES)}{random.randint(1, 20)}栋{random.randint(101, 2402)}室",
            "source": random.choice(["自有", "平台"]),
            "cleanupTag": token,
        })

    if include_edge and count > 0:
        data.extend([
            {
                "title": "",
                "businessType": "",
                "urgencyLevel": "",
                "customerName": "",
                "customerPhone": "",
                "address": "",
                "source": "",
                "cleanupTag": "TEST_SAMPLE_WO_EDGE_EMPTY",
                "_edge": "空值工单",
            },
            {
                "title": "X" * 128,
                "businessType": "未知业务",
                "urgencyLevel": "极限",
                "customerName": "<script>alert(1)</script>",
                "customerPhone": "123",
                "address": "a" * 256,
                "source": "平台",
                "cleanupTag": "TEST_SAMPLE_WO_EDGE_INVALID",
                "_edge": "超长/异常值",
            },
        ])
    return data


def _gen_sample_platform_property_parking(count: int, include_edge: bool = True) -> List[Dict]:
    data = []
    province_code = random.choice(["京", "沪", "粤", "浙", "苏"])
    for i in range(count):
        token = _prefixed_token("PK", i)
        data.append({
            "communityName": random.choice(_SAMPLE_COMMUNITIES),
            "licensePlate": f"{province_code}{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{_rand_str(5, string.ascii_uppercase + string.digits)}",
            "parkingSpaceNo": f"A{random.randint(1, 9)}-{random.randint(1, 999):03d}",
            "contractStatus": random.choice(["生效中", "待签约", "已到期"]),
            "contactName": f"车主{i + 1}",
            "contactPhone": f"138{_rand_str(8, string.digits)}",
            "amount": round(random.uniform(100.0, 2000.0), 2),
            "cleanupTag": token,
        })
    if include_edge and count > 0:
        data.append({
            "communityName": "",
            "licensePlate": "无牌",
            "parkingSpaceNo": "",
            "contractStatus": "未知",
            "contactName": "",
            "contactPhone": "000",
            "amount": -1,
            "cleanupTag": "TEST_SAMPLE_PK_EDGE_INVALID",
            "_edge": "异常合同",
        })
    return data


def _gen_sample_platform_elder_profile(count: int, include_edge: bool = True) -> List[Dict]:
    data = []
    for i in range(count):
        token = _prefixed_token("ELDER", i)
        elder_name = random.choice(_FIRST_NAMES) + random.choice(_LAST_NAMES)
        data.append({
            "elderName": elder_name,
            "communityName": random.choice(_SAMPLE_COMMUNITIES),
            "careLevel": random.choice(_SAMPLE_CARE_LEVELS),
            "contactPhone": f"137{_rand_str(8, string.digits)}",
            "emergencyContact": f"家属{i + 1}",
            "specialNeeds": random.choice(["无", "低盐饮食", "助行器", "定时服药"]),
            "cleanupTag": token,
        })
    if include_edge and count > 0:
        data.extend([
            {
                "elderName": "",
                "communityName": "",
                "careLevel": "",
                "contactPhone": "",
                "emergencyContact": "",
                "specialNeeds": "",
                "cleanupTag": "TEST_SAMPLE_ELDER_EDGE_EMPTY",
                "_edge": "空档案",
            },
            {
                "elderName": "敏感老人",
                "communityName": random.choice(_SAMPLE_COMMUNITIES),
                "careLevel": "特护",
                "contactPhone": "110",
                "emergencyContact": "<script>",
                "specialNeeds": "a" * 128,
                "cleanupTag": "TEST_SAMPLE_ELDER_EDGE_INVALID",
                "_edge": "隐私/格式异常",
            },
        ])
    return data


def _gen_sample_platform_announcement(count: int, include_edge: bool = True) -> List[Dict]:
    data = []
    for i in range(count):
        token = _prefixed_token("NOTICE", i)
        data.append({
            "communityName": random.choice(_SAMPLE_COMMUNITIES),
            "title": f"{token}_公告发布验证",
            "category": random.choice(_SAMPLE_ANNOUNCEMENT_CATEGORIES),
            "content": f"{token} 用于验证公告新增、编辑、发布与回收。",
            "publishStatus": random.choice(["草稿", "已发布", "已下线"]),
            "cleanupTag": token,
        })
    if include_edge and count > 0:
        data.append({
            "communityName": "",
            "title": "",
            "category": "",
            "content": "",
            "publishStatus": "未知",
            "cleanupTag": "TEST_SAMPLE_NOTICE_EDGE_EMPTY",
            "_edge": "空公告",
        })
    return data


_GENERATORS = {
    "_gen_user": _gen_user,
    "_gen_address": _gen_address,
    "_gen_payment": _gen_payment,
    "_gen_search": _gen_search,
    "_gen_boundary": _gen_boundary,
    "_gen_sample_platform_work_order": _gen_sample_platform_work_order,
    "_gen_sample_platform_property_parking": _gen_sample_platform_property_parking,
    "_gen_sample_platform_elder_profile": _gen_sample_platform_elder_profile,
    "_gen_sample_platform_announcement": _gen_sample_platform_announcement,
}


class TestDataGenerator:
    """测试数据生成器"""

    @staticmethod
    def list_templates() -> List[Dict]:
        """列出所有可用的数据模板"""
        return [
            {"id": k, "label": v["label"], "description": v["description"], "fields": v["fields"]}
            for k, v in _TEMPLATES.items()
        ]

    @staticmethod
    def generate(template_id: str, count: int = 5, include_edge: bool = True) -> Dict:
        """按模板生成测试数据"""
        count_error = _validate_count(count)
        if count_error:
            return {"error": count_error}

        tpl = _TEMPLATES.get(template_id)
        if not tpl:
            return {"error": f"Unknown template: {template_id}"}

        gen_fn = _GENERATORS.get(tpl["generator"])
        if not gen_fn:
            return {"error": f"Generator not found: {tpl['generator']}"}

        try:
            data = gen_fn(count, include_edge=include_edge)
        except TypeError:
            data = gen_fn(count)

        return {
            "template": template_id,
            "label": tpl["label"],
            "count": len(data),
            "fields": tpl["fields"],
            "data": data,
        }

    @staticmethod
    def generate_custom(fields: List[Dict], count: int = 5) -> Dict:
        """
        自定义字段生成。
        fields: [{"name": "username", "type": "string", "min": 3, "max": 20}, ...]
        """
        count_error = _validate_count(count)
        if count_error:
            return {"error": count_error}

        data = []
        for _ in range(count):
            row = {}
            for f in fields:
                fname = f.get("name", "field")
                ftype = f.get("type", "string")
                fmin = f.get("min", 1)
                fmax = f.get("max", 100)

                if fmin > fmax:
                    return {"error": f"Invalid range for field '{fname}': min cannot be greater than max"}

                if ftype == "string":
                    row[fname] = _rand_str(random.randint(fmin, fmax))
                elif ftype == "integer":
                    row[fname] = random.randint(fmin, fmax)
                elif ftype == "float":
                    row[fname] = round(random.uniform(fmin, fmax), 2)
                elif ftype == "email":
                    row[fname] = f"{_rand_str(6)}@test.com"
                elif ftype == "phone":
                    row[fname] = f"1{random.choice(['3','5','8'])}{_rand_str(9, string.digits)}"
                elif ftype == "date":
                    d = datetime.now() - timedelta(days=random.randint(0, 365))
                    row[fname] = d.strftime("%Y-%m-%d")
                elif ftype == "boolean":
                    row[fname] = random.choice([True, False])
                elif ftype == "uuid":
                    row[fname] = str(uuid.uuid4())
                else:
                    row[fname] = _rand_str(10)

            data.append(row)

        return {"count": len(data), "fields": [f["name"] for f in fields], "data": data}
