#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Test Platform CLI — Command-line test runner

Usage:
    python -m aitest run --url https://example.com --goal "Search for AI testing"
    python -m aitest run --url https://example.com --goal "Login test" --output junit
    python -m aitest status
    python -m aitest report --format html
    python -m aitest health

Environment variables:
    AITEST_API_URL  — Platform API URL (default: http://localhost:8020)
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
    """Call the platform API"""
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        print(f"❌ API error [{e.code}]: {body_text}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ Cannot connect to the platform: {e.reason}", file=sys.stderr)
        print(f"   Ensure the platform is running at {API_URL}", file=sys.stderr)
        sys.exit(1)


def cmd_health(args):
    """health — Check platform health"""
    resp = _api("GET", "/api/health")
    status = resp.get("status", "unknown")
    print(f"🏥 Platform status: {'✅ Healthy' if status == 'ok' else '❌ Unhealthy'}")
    print(f"   API: {API_URL}")
    if "version" in resp:
        print(f"   Version: {resp['version']}")
    return 0 if status == "ok" else 1


def cmd_run(args):
    """run — Run tests"""
    print(f"🚀 Starting test...")
    print(f"   Target: {args.url}")
    print(f"   Instructions: {args.goal}")
    print(f"   Mode: {args.mode}")
    print()

    # Start the test
    payload = {
        "url": args.url,
        "requirement": args.goal,
        "mode": args.mode,
    }
    resp = _api("POST", "/api/test", payload)
    task_id = resp.get("task_id", "")
    print(f"📋 Task ID: {task_id}")

    if not args.wait:
        print("ℹ️  Use --wait to wait for test completion")
        return 0

    # Wait for completion
    print("⏳ Waiting for execution to finish...")
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
            # Progress indicator
            dots = "." * (elapsed // 3 % 4)
            print(f"\r   Running{dots}  ({elapsed}s)", end="", flush=True)
        except SystemExit:
            continue

    print()  # Newline

    if final_status in ("success", "completed"):
        print(f"✅ Test passed! (duration: {elapsed}s)")
        exit_code = 0
    elif final_status in ("failed", "error"):
        print(f"❌ Test failed! (duration: {elapsed}s)")
        exit_code = 1
    else:
        print(f"⏰ Timed out after {max_wait}s; the test is still running")
        exit_code = 2

    # Output the report
    if args.output == "junit":
        _output_junit(task_id)
    elif args.output == "json":
        detail = _api("GET", f"/api/history/{task_id}")
        print(json.dumps(detail, indent=2, ensure_ascii=False))

    return exit_code


def _output_junit(task_id: str):
    """Output a JUnit XML report"""
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
    print(f"📄 JUnit XML report saved: {outfile}")


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


def cmd_status(args):
    """status — View recent execution status"""
    resp = _api("GET", "/api/history?limit=5")
    items = resp.get("items", [])
    if not items:
        print("📭 No execution records yet")
        return 0

    print(f"📊 Latest {len(items)} execution records:\n")
    print(f"{'ID':<12} {'Status':<10} {'Requirement':<40} {'Time'}")
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
    """report — Generate a report"""
    resp = _api("POST", "/api/report/generate")
    if resp.get("status") == "success" or resp.get("report_url"):
        url = resp.get("report_url", "")
        print(f"✅ Report generated")
        if url:
            print(f"   View: {API_URL}{url}")
    else:
        print(f"❌ Report generation failed: {resp.get('message', 'unknown')}")
    return 0


def cmd_analytics(args):
    """analytics — View the analytics summary"""
    resp = _api("GET", "/api/analytics/summary")
    print("📊 Platform analytics summary\n")
    print(f"  Total executions:   {resp.get('total', 0)}")
    print(f"  Passed:       {resp.get('passed', 0)}")
    print(f"  Failed:       {resp.get('failed', 0)}")
    print(f"  Healed:       {resp.get('healed', 0)}")
    print(f"  Pass rate:     {resp.get('overallPassRate', 0)}%")
    print(f"  Average duration:   {resp.get('avgDurationMs', 0)}ms")
    print(f"  Executions today:   {resp.get('today', 0)}")
    print(f"  Executions this week:   {resp.get('thisWeek', 0)}")
    return 0


def main():
    global API_URL
    parser = argparse.ArgumentParser(
        prog="aitest",
        description="AI Test Platform CLI — Command-line test runner",
    )
    parser.add_argument("--api-url", default=API_URL, help=f"Platform API URL (default: {API_URL})")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # run
    run_parser = subparsers.add_parser("run", help="Run tests")
    run_parser.add_argument("--url", required=True, help="Test target URL")
    run_parser.add_argument("--goal", required=True, help="Natural-language test instructions")
    run_parser.add_argument("--mode", default="smart", choices=["smart", "fast", "deep"], help="Test mode")
    run_parser.add_argument("--wait", action="store_true", help="Wait for test completion")
    run_parser.add_argument("--timeout", type=int, default=120, help="Maximum wait time in seconds")
    run_parser.add_argument("--output", default="text", choices=["text", "json", "junit"], help="Output format")

    # status
    subparsers.add_parser("status", help="View recent execution status")

    # report
    subparsers.add_parser("report", help="Generate a report")

    # analytics
    subparsers.add_parser("analytics", help="View the analytics summary")

    # health
    subparsers.add_parser("health", help="Check platform health")

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
