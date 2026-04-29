#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Test Platform CLI — 命令行测试运行工具

用法:
    python -m aitest run --url https://example.com --goal "搜索AI测试"
    python -m aitest run --url https://example.com --goal "登录测试" --output junit
    python -m aitest status
    python -m aitest report --format html
    python -m aitest health

环境变量:
    AITEST_API_URL  — 平台 API 地址（默认 http://localhost:8020）
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

API_URL = os.environ.get("AITEST_API_URL", "http://localhost:8020")


def _api(method: str, path: str, body: dict = None) -> dict:
    """调用平台 API"""
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        print(f"❌ API 错误 [{e.code}]: {body_text}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ 无法连接平台: {e.reason}", file=sys.stderr)
        print(f"   请确认平台运行在 {API_URL}", file=sys.stderr)
        sys.exit(1)


def cmd_health(args):
    """health — 检查平台健康状态"""
    resp = _api("GET", "/api/health")
    status = resp.get("status", "unknown")
    print(f"🏥 平台状态: {'✅ 正常' if status == 'ok' else '❌ 异常'}")
    print(f"   API: {API_URL}")
    if "version" in resp:
        print(f"   版本: {resp['version']}")
    return 0 if status == "ok" else 1


def cmd_run(args):
    """run — 执行测试"""
    print(f"🚀 启动测试...")
    print(f"   目标: {args.url}")
    print(f"   指令: {args.goal}")
    print(f"   模式: {args.mode}")
    print()

    # 发起测试
    payload = {
        "url": args.url,
        "requirement": args.goal,
        "mode": args.mode,
    }
    resp = _api("POST", "/api/test", payload)
    task_id = resp.get("task_id", "")
    print(f"📋 任务 ID: {task_id}")

    if not args.wait:
        print("ℹ️  使用 --wait 参数等待测试完成")
        return 0

    # 等待完成
    print("⏳ 等待执行完成...")
    max_wait = args.timeout
    elapsed = 0
    final_status = "unknown"

    while elapsed < max_wait:
        time.sleep(3)
        elapsed += 3
        try:
            detail = _api("GET", f"/api/history/{task_id}")
            status = detail.get("status", "running")
            if status in ("success", "completed", "failed", "error"):
                final_status = status
                break
            # 进度指示
            dots = "." * (elapsed // 3 % 4)
            print(f"\r   执行中{dots}  ({elapsed}s)", end="", flush=True)
        except SystemExit:
            continue

    print()  # 换行

    if final_status in ("success", "completed"):
        print(f"✅ 测试通过! (耗时 {elapsed}s)")
        exit_code = 0
    elif final_status in ("failed", "error"):
        print(f"❌ 测试失败! (耗时 {elapsed}s)")
        exit_code = 1
    else:
        print(f"⏰ 超时 ({max_wait}s)，测试仍在执行中")
        exit_code = 2

    # 输出报告
    if args.output == "junit":
        _output_junit(task_id)
    elif args.output == "json":
        detail = _api("GET", f"/api/history/{task_id}")
        print(json.dumps(detail, indent=2, ensure_ascii=False))

    return exit_code


def _output_junit(task_id: str):
    """输出 JUnit XML 格式报告"""
    detail = _api("GET", f"/api/history/{task_id}")
    logs = detail.get("logs", [])

    test_name = detail.get("requirement", task_id)
    status = detail.get("status", "unknown")
    duration = (detail.get("duration_ms") or 0) / 1000

    steps = [l for l in logs if l.get("type") in ("action", "result", "error")]
    failures = [l for l in logs if l.get("type") == "error"]

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuites tests="{len(steps)}" failures="{len(failures)}" time="{duration:.2f}">',
        f'  <testsuite name="AITest" tests="{len(steps)}" failures="{len(failures)}" time="{duration:.2f}">',
    ]

    for i, step in enumerate(steps):
        step_name = _xml_escape(step.get("content", f"Step {i+1}"))
        step_status = step.get("status", "")
        xml_lines.append(f'    <testcase name="{step_name}" classname="{_xml_escape(test_name)}" time="0">')

        if step.get("type") == "error" or step_status in ("error", "fail", "failed"):
            msg = _xml_escape(step.get("content", "Unknown error"))
            xml_lines.append(f'      <failure message="{msg}">{msg}</failure>')

        xml_lines.append('    </testcase>')

    xml_lines.append('  </testsuite>')
    xml_lines.append('</testsuites>')

    xml_content = "\n".join(xml_lines)

    outfile = f"test-results-{task_id[:8]}.xml"
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"📄 JUnit XML 报告已保存: {outfile}")


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


def cmd_status(args):
    """status — 查看最近执行状态"""
    resp = _api("GET", "/api/history?limit=5")
    items = resp.get("items", [])
    if not items:
        print("📭 暂无执行记录")
        return 0

    print(f"📊 最近 {len(items)} 条执行记录:\n")
    print(f"{'ID':<12} {'状态':<10} {'需求':<40} {'时间'}")
    print("─" * 80)
    for item in items:
        tid = (item.get("task_id") or item.get("id", ""))[:10]
        status = item.get("status", "?")
        status_icon = "✅" if status in ("success", "completed") else "❌" if status in ("failed", "error") else "⏳"
        req = (item.get("requirement") or item.get("goal") or "")[:38]
        ts = (item.get("created_at") or item.get("timestamp") or "")[:19]
        print(f"{tid:<12} {status_icon} {status:<7} {req:<40} {ts}")

    return 0


def cmd_report(args):
    """report — 生成报告"""
    resp = _api("POST", "/api/report/generate")
    if resp.get("status") == "success" or resp.get("report_url"):
        url = resp.get("report_url", "")
        print(f"✅ 报告已生成")
        if url:
            print(f"   查看: {API_URL}{url}")
    else:
        print(f"❌ 报告生成失败: {resp.get('message', 'unknown')}")
    return 0


def cmd_analytics(args):
    """analytics — 查看分析摘要"""
    resp = _api("GET", "/api/analytics/summary")
    print("📊 平台分析摘要\n")
    print(f"  总执行数:   {resp.get('total', 0)}")
    print(f"  通过:       {resp.get('passed', 0)}")
    print(f"  失败:       {resp.get('failed', 0)}")
    print(f"  自愈:       {resp.get('healed', 0)}")
    print(f"  通过率:     {resp.get('overallPassRate', 0)}%")
    print(f"  平均耗时:   {resp.get('avgDurationMs', 0)}ms")
    print(f"  今日执行:   {resp.get('today', 0)}")
    print(f"  本周执行:   {resp.get('thisWeek', 0)}")
    return 0


def main():
    global API_URL
    parser = argparse.ArgumentParser(
        prog="aitest",
        description="AI Test Platform CLI — 命令行测试运行工具",
    )
    parser.add_argument("--api-url", default=API_URL, help=f"平台 API 地址 (默认: {API_URL})")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # run
    run_parser = subparsers.add_parser("run", help="执行测试")
    run_parser.add_argument("--url", required=True, help="测试目标 URL")
    run_parser.add_argument("--goal", required=True, help="自然语言测试指令")
    run_parser.add_argument("--mode", default="smart", choices=["smart", "fast", "deep"], help="测试模式")
    run_parser.add_argument("--wait", action="store_true", help="等待测试完成")
    run_parser.add_argument("--timeout", type=int, default=120, help="最大等待时间（秒）")
    run_parser.add_argument("--output", default="text", choices=["text", "json", "junit"], help="输出格式")

    # status
    subparsers.add_parser("status", help="查看最近执行状态")

    # report
    subparsers.add_parser("report", help="生成报告")

    # analytics
    subparsers.add_parser("analytics", help="查看分析摘要")

    # health
    subparsers.add_parser("health", help="检查平台健康状态")

    args = parser.parse_args()
    if args.api_url:
        API_URL = args.api_url

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "run": cmd_run,
        "status": cmd_status,
        "report": cmd_report,
        "analytics": cmd_analytics,
        "health": cmd_health,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
