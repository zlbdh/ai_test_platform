# -*- coding: utf-8 -*-
"""
Analytics Router — Dashboard 趋势分析 API
提供：30天趋势、失败Top10热图、Flaky检测、失败原因分类
"""
from fastapi import APIRouter
import json
import logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Any

from core.db_helper import query_all, query_one

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analytics"])


@router.get("/api/analytics/trends")
async def api_analytics_trends(days: int = 30):
    """获取 N 天的每日通过率/执行数/耗时趋势"""
    try:
        rows = query_all(
            "SELECT status, duration_ms, created_at FROM test_runs "
            "WHERE created_at >= date('now', ?) ORDER BY created_at",
            (f"-{days} days",)
        )
    except Exception:
        rows = []

    # 按日期聚合
    daily: Dict[str, Dict] = {}
    for i in range(days):
        d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        daily[d] = {"date": d, "total": 0, "passed": 0, "failed": 0, "healed": 0, "total_ms": 0}

    for r in rows or []:
        d = (r.get("created_at") or "")[:10]
        if d in daily:
            daily[d]["total"] += 1
            s = r.get("status", "")
            if s == "success":
                daily[d]["passed"] += 1
            elif s == "failed":
                daily[d]["failed"] += 1
            elif s == "healed":
                daily[d]["healed"] += 1
            daily[d]["total_ms"] += r.get("duration_ms") or 0

    result = []
    for d in sorted(daily.keys()):
        v = daily[d]
        rate = round(v["passed"] / v["total"] * 100) if v["total"] > 0 else 0
        avg_ms = round(v["total_ms"] / v["total"]) if v["total"] > 0 else 0
        result.append({
            "date": d,
            "label": f"{int(d[5:7])}/{int(d[8:10])}",
            "total": v["total"],
            "passed": v["passed"],
            "failed": v["failed"],
            "healed": v["healed"],
            "successRate": rate,
            "avgDurationMs": avg_ms,
        })

    return {"days": days, "data": result}


@router.get("/api/analytics/failures")
async def api_analytics_failures(limit: int = 10):
    """获取失败 Top N 用例（按需求分组）"""
    try:
        rows = query_all(
            "SELECT requirement, status, error_count, created_at FROM test_runs "
            "WHERE status='failed' ORDER BY created_at DESC LIMIT 200"
        )
    except Exception:
        rows = []

    # 按需求名统计失败次数
    fail_counts: Counter = Counter()
    last_failure: Dict[str, str] = {}
    for r in rows or []:
        name = r.get("requirement") or "Unknown"
        fail_counts[name] += 1
        if name not in last_failure:
            last_failure[name] = r.get("created_at", "")

    top_failures = []
    for name, count in fail_counts.most_common(limit):
        top_failures.append({
            "name": name[:80],
            "failCount": count,
            "lastFailure": last_failure.get(name, ""),
        })

    return {"total_failures": sum(fail_counts.values()), "top": top_failures}


@router.get("/api/analytics/flaky")
async def api_analytics_flaky():
    """检测 Flaky 用例（相同需求的通过率在 20-80% 之间视为 Flaky）"""
    try:
        rows = query_all(
            "SELECT requirement, status FROM test_runs ORDER BY created_at DESC LIMIT 500"
        )
    except Exception:
        rows = []

    # 按需求名统计通过/失败
    req_stats: Dict[str, Dict] = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in rows or []:
        name = r.get("requirement") or "Unknown"
        req_stats[name]["total"] += 1
        if r.get("status") == "success":
            req_stats[name]["passed"] += 1

    flaky_tests = []
    for name, stats in req_stats.items():
        if stats["total"] >= 2:  # 至少 2 次执行
            rate = stats["passed"] / stats["total"] * 100
            if 20 <= rate <= 80:  # 通过率在 20-80% 视为 Flaky
                flaky_tests.append({
                    "name": name[:80],
                    "total": stats["total"],
                    "passed": stats["passed"],
                    "failed": stats["total"] - stats["passed"],
                    "passRate": round(rate),
                    "severity": "high" if 40 <= rate <= 60 else "medium",
                })

    flaky_tests.sort(key=lambda x: abs(x["passRate"] - 50))  # 越接近 50% 越 Flaky
    return {"count": len(flaky_tests), "tests": flaky_tests[:20]}


@router.get("/api/analytics/failure-reasons")
async def api_analytics_failure_reasons():
    """分析失败原因分类"""
    try:
        rows = query_all(
            "SELECT logs_json FROM test_runs WHERE status='failed' "
            "ORDER BY created_at DESC LIMIT 100"
        )
    except Exception:
        rows = []

    reasons: Counter = Counter()
    for r in rows or []:
        logs_str = r.get("logs_json") or "[]"
        try:
            logs = json.loads(logs_str)
        except (json.JSONDecodeError, TypeError):
            logs = []

        classified = False
        for log in logs:
            if log.get("type") != "error":
                continue
            content = (log.get("content") or "").lower()
            if any(k in content for k in ["timeout", "超时", "timed out"]):
                reasons["超时"] += 1
                classified = True
                break
            elif any(k in content for k in ["not found", "locator", "element", "selector", "找不到", "定位"]):
                reasons["元素定位"] += 1
                classified = True
                break
            elif any(k in content for k in ["assert", "断言", "expect", "mismatch"]):
                reasons["断言失败"] += 1
                classified = True
                break
            elif any(k in content for k in ["network", "connection", "网络", "refused", "dns", "fetch"]):
                reasons["网络错误"] += 1
                classified = True
                break
            elif any(k in content for k in ["permission", "auth", "403", "401", "权限"]):
                reasons["权限/认证"] += 1
                classified = True
                break

        if not classified:
            reasons["其他"] += 1

    total = sum(reasons.values())
    result = [
        {"reason": reason, "count": count, "percentage": round(count / total * 100) if total > 0 else 0}
        for reason, count in reasons.most_common()
    ]
    return {"total": total, "reasons": result}


@router.get("/api/analytics/summary")
async def api_analytics_summary():
    """全局分析摘要"""
    try:
        total_row = query_one("SELECT COUNT(*) as c FROM test_runs")
        total = total_row["c"] if total_row else 0

        passed_row = query_one("SELECT COUNT(*) as c FROM test_runs WHERE status='success'")
        passed = passed_row["c"] if passed_row else 0

        failed_row = query_one("SELECT COUNT(*) as c FROM test_runs WHERE status='failed'")
        failed = failed_row["c"] if failed_row else 0

        healed_row = query_one("SELECT COUNT(*) as c FROM test_runs WHERE status='healed'")
        healed = healed_row["c"] if healed_row else 0

        avg_row = query_one("SELECT AVG(duration_ms) as avg_ms FROM test_runs WHERE duration_ms > 0")
        avg_ms = round(avg_row["avg_ms"]) if avg_row and avg_row["avg_ms"] else 0

        today_row = query_one(
            "SELECT COUNT(*) as c FROM test_runs WHERE date(created_at) = date('now')"
        )
        today = today_row["c"] if today_row else 0

        week_row = query_one(
            "SELECT COUNT(*) as c FROM test_runs WHERE created_at >= date('now', '-7 days')"
        )
        this_week = week_row["c"] if week_row else 0

    except Exception:
        return {"total": 0, "passed": 0, "failed": 0, "healed": 0,
                "avgDurationMs": 0, "today": 0, "thisWeek": 0, "overallPassRate": 0}

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "healed": healed,
        "avgDurationMs": avg_ms,
        "today": today,
        "thisWeek": this_week,
        "overallPassRate": round(passed / total * 100) if total > 0 else 0,
    }
