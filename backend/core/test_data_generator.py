# -*- coding: utf-8 -*-
"""
TestDataGenerator — AI-driven test data management
Features:
1. AI-assisted data generation (boundaries, invalid values, formatted data)
2. Parameterized data support (CSV/JSON datasets)
3. Built-in templates (users/addresses/payments/search terms, etc.)
"""
import json
import random
import string
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ── Built-in data templates ──

_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "user": {
        "label": "User information",
        "description": "Generate registration/sign-in test data",
        "fields": ["username", "email", "password", "phone", "age"],
        "generator": "_gen_user",
    },
    "address": {
        "label": "Address information",
        "description": "Generate synthetic US address test data",
        "fields": ["province", "city", "district", "street", "zipcode"],
        "generator": "_gen_address",
    },
    "payment": {
        "label": "Payment information",
        "description": "Generate payment/order test data",
        "fields": ["order_id", "amount", "currency", "card_number", "expiry"],
        "generator": "_gen_payment",
    },
    "search": {
        "label": "Search terms",
        "description": "Generate search test data, including special characters and SQL injection",
        "fields": ["keyword", "type"],
        "generator": "_gen_search",
    },
    "boundary": {
        "label": "Boundary values",
        "description": "Generate boundary test data: empty, oversized, and special-character values",
        "fields": ["value", "type", "description"],
        "generator": "_gen_boundary",
    },
    "sample_platform_work_order": {
        "label": "Sample project work orders",
        "description": "Generate work-order dispatch data with a TEST_SAMPLE prefix for cleanup",
        "fields": ["title", "businessType", "urgencyLevel", "customerName", "customerPhone", "address", "source", "cleanupTag"],
        "generator": "_gen_sample_platform_work_order",
    },
    "sample_platform_property_parking": {
        "label": "Sample project parking contracts",
        "description": "Generate property parking-contract data for renewal, termination, and export regression tests",
        "fields": ["communityName", "licensePlate", "parkingSpaceNo", "contractStatus", "contactName", "contactPhone", "amount", "cleanupTag"],
        "generator": "_gen_sample_platform_property_parking",
    },
    "sample_platform_elder_profile": {
        "label": "Sample project senior profiles",
        "description": "Generate senior-care profiles with fields for data-masking verification",
        "fields": ["elderName", "communityName", "careLevel", "contactPhone", "emergencyContact", "specialNeeds", "cleanupTag"],
        "generator": "_gen_sample_platform_elder_profile",
    },
    "sample_platform_announcement": {
        "label": "Sample project announcements",
        "description": "Generate property announcement/issue-report data for publishing and cleanup checks",
        "fields": ["communityName", "title", "category", "content", "publishStatus", "cleanupTag"],
        "generator": "_gen_sample_platform_announcement",
    },
}

# ── Data generators ──

_FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Cameron", "Jamie", "Robin"]
_LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Moore", "Taylor"]
_PROVINCES = ["California", "New York", "Texas", "Washington", "Illinois", "Colorado", "Oregon", "Massachusetts"]
_CITIES = {"California": ["San Diego", "Sacramento"], "New York": ["Buffalo", "Albany"],
           "Texas": ["Austin", "Dallas"], "Washington": ["Seattle", "Spokane"], "Illinois": ["Chicago"], "Colorado": ["Denver"], "Oregon": ["Portland"], "Massachusetts": ["Boston"]}
_SAMPLE_COMMUNITIES = ["Maple Grove", "Sample Gardens", "Willow Court", "Oak Meadows"]
# Sample-platform enum payloads intentionally retain the target API values.
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
    """Generate user test data"""
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
             "_edge": "Empty values"},
            {"username": "a" * 256, "email": "x" * 200 + "@test.com",
             "password": "a", "phone": "000", "age": -1,
             "_edge": "Oversized/invalid values"},
            {"username": "<script>alert(1)</script>", "email": "test@",
             "password": "12345678", "phone": "00000000000", "age": 999,
             "_edge": "XSS/invalid format"},
        ])

    return data


def _gen_address(count: int, include_edge: bool = True) -> List[Dict]:
    """Generate address test data"""
    data = []
    for _ in range(count):
        province = random.choice(_PROVINCES)
        cities = _CITIES.get(province, [province])
        data.append({
            "province": province,
            "city": random.choice(cities),
            "district": f"{random.choice(['East', 'West', 'South', 'North'])} District",
            "street": f"{random.randint(1,999)} {random.choice(['Oak', 'Maple', 'Pine', 'Cedar'])} Street",
            "zipcode": _rand_str(5, string.digits),
        })

    if include_edge and count > 0:
        data.append({"province": "", "city": "", "district": "", "street": "", "zipcode": "",
                      "_edge": "Empty address"})

    return data


def _gen_payment(count: int, include_edge: bool = True) -> List[Dict]:
    """Generate payment test data"""
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
             "_edge": "Empty values"},
            {"order_id": "X" * 100, "amount": -1, "currency": "INVALID",
             "card_number": "0000000000000000", "expiry": "13/99",
             "_edge": "Invalid values"},
            {"order_id": "A1", "amount": 0.001, "currency": "CNY",
             "card_number": "1234", "expiry": "00/00",
             "_edge": "Boundary values"},
        ])

    return data


def _gen_search(count: int, include_edge: bool = True) -> List[Dict]:
    """Generate search-keyword test data"""
    normal = ["AI testing", "Python tutorials", "test automation tools", "Playwright", "selenium",
              "machine learning", "GPT", "test case management", "DevOps", "cloud native"]
    data = [{"keyword": random.choice(normal), "type": "normal"} for _ in range(count)]

    if include_edge and count > 0:
        data.extend([
            {"keyword": "", "type": "empty"},
            {"keyword": " " * 10, "type": "whitespace"},
            {"keyword": "a" * 500, "type": "overflow"},
            {"keyword": "<img onerror=alert(1) src=x>", "type": "xss"},
            {"keyword": "' OR 1=1 --", "type": "sql_injection"},
            {"keyword": "../../etc/passwd", "type": "path_traversal"},
            {"keyword": "test%00null byte", "type": "null_byte"},
            {"keyword": "🤖💥🔥👾", "type": "emoji"},
            {"keyword": "   surrounding spaces   ", "type": "trim_test"},
        ])

    return data


def _gen_boundary(count: int, **_) -> List[Dict]:
    """Generate a count-limited sample of general boundary values"""
    all_boundaries = [
        {"value": "", "type": "empty_string", "description": "Empty string"},
        {"value": None, "type": "null", "description": "Null value"},
        {"value": 0, "type": "zero", "description": "Zero"},
        {"value": -1, "type": "negative", "description": "Negative number"},
        {"value": 2147483647, "type": "int_max", "description": "Maximum INT"},
        {"value": -2147483648, "type": "int_min", "description": "Minimum INT"},
        {"value": 0.1 + 0.2, "type": "float_precision", "description": "Floating-point precision"},
        {"value": "a" * 1000, "type": "long_string", "description": "Long string (1000)"},
        {"value": "a" * 10000, "type": "very_long", "description": "Very long string (10000)"},
        {"value": " ", "type": "single_space", "description": "Single space"},
        {"value": "\t\n\r", "type": "whitespace_chars", "description": "Tabs and newlines"},
        {"value": "<script>alert('xss')</script>", "type": "xss", "description": "XSS attack"},
        {"value": "'; DROP TABLE users; --", "type": "sql_injection", "description": "SQL injection"},
        {"value": "../../etc/passwd", "type": "path_traversal", "description": "Path traversal"},
        {"value": "🤖💥🔥", "type": "emoji", "description": "Emoji characters"},
        {"value": "中文テスト한국어", "type": "multibyte", "description": "Multilingual characters"},
        {"value": True, "type": "boolean_true", "description": "Boolean True"},
        {"value": False, "type": "boolean_false", "description": "Boolean False"},
        {"value": [], "type": "empty_array", "description": "Empty array"},
        {"value": {}, "type": "empty_object", "description": "Empty object"},
    ]
    # Randomly sample by count rather than always returning all 20 values
    return random.sample(all_boundaries, min(count, len(all_boundaries)))


def _gen_sample_platform_work_order(count: int, include_edge: bool = True) -> List[Dict]:
    data = []
    for i in range(count):
        token = _prefixed_token("WO", i)
        data.append({
            "title": f"{token}_WorkOrderRegression",
            "businessType": random.choice(_SAMPLE_BUSINESS_TYPES),
            "urgencyLevel": random.choice(["普通", "紧急", "非常紧急"]),
            "customerName": f"Test Customer {i + 1}",
            "customerPhone": f"139{_rand_str(8, string.digits)}",
            "address": f"{random.choice(_SAMPLE_COMMUNITIES)}, Building {random.randint(1, 20)}, Unit {random.randint(101, 2402)}",
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
                "_edge": "Empty work order",
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
                "_edge": "Oversized/invalid values",
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
            "contactName": f"Vehicle Owner {i + 1}",
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
            "_edge": "Invalid contract",
        })
    return data


def _gen_sample_platform_elder_profile(count: int, include_edge: bool = True) -> List[Dict]:
    data = []
    for i in range(count):
        token = _prefixed_token("ELDER", i)
        elder_name = random.choice(_FIRST_NAMES) + " " + random.choice(_LAST_NAMES)
        data.append({
            "elderName": elder_name,
            "communityName": random.choice(_SAMPLE_COMMUNITIES),
            "careLevel": random.choice(_SAMPLE_CARE_LEVELS),
            "contactPhone": f"137{_rand_str(8, string.digits)}",
            "emergencyContact": f"Family Member {i + 1}",
            "specialNeeds": random.choice(["None", "Low-sodium diet", "Walker", "Scheduled medication"]),
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
                "_edge": "Empty profile",
            },
            {
                "elderName": "Sensitive Test Profile",
                "communityName": random.choice(_SAMPLE_COMMUNITIES),
                "careLevel": "特护",
                "contactPhone": "110",
                "emergencyContact": "<script>",
                "specialNeeds": "a" * 128,
                "cleanupTag": "TEST_SAMPLE_ELDER_EDGE_INVALID",
                "_edge": "Privacy/invalid format",
            },
        ])
    return data


def _gen_sample_platform_announcement(count: int, include_edge: bool = True) -> List[Dict]:
    data = []
    for i in range(count):
        token = _prefixed_token("NOTICE", i)
        data.append({
            "communityName": random.choice(_SAMPLE_COMMUNITIES),
            "title": f"{token}_AnnouncementPublication",
            "category": random.choice(_SAMPLE_ANNOUNCEMENT_CATEGORIES),
            "content": f"{token} verifies announcement creation, editing, publication, and cleanup.",
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
            "_edge": "Empty announcement",
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
    """Test data generator"""

    @staticmethod
    def list_templates() -> List[Dict]:
        """List available data templates"""
        return [
            {"id": k, "label": v["label"], "description": v["description"], "fields": v["fields"]}
            for k, v in _TEMPLATES.items()
        ]

    @staticmethod
    def generate(template_id: str, count: int = 5, include_edge: bool = True) -> Dict:
        """Generate test data from a template"""
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
        Generate custom fields.
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
