"""
CI/CD Integration Service

Provides:
- Webhook endpoint for Jenkins/GitLab CI triggers
- JUnit XML report generation
- HTML summary report generation
- Trigger history management
"""

import logging
import os
import json
import uuid
import hashlib
import secrets
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)
from xml.etree import ElementTree as ET

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data" / "cicd"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
HISTORY_FILE = DATA_DIR / "trigger_history.json"


@dataclass
class CICDConfig:
    """CI/CD configuration"""
    webhook_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    enabled: bool = True
    default_task_template: str = ""
    notify_on_complete: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TriggerRecord:
    """Record of a CI/CD trigger event"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    triggered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "manual"  # manual, jenkins, gitlab, github
    ref: str = ""  # branch/tag
    commit: str = ""
    task_id: str = ""
    status: str = "pending"  # pending, running, passed, failed
    duration_ms: float = 0
    test_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    report_path: str = ""


@dataclass
class TestCaseResult:
    """Individual test case result for JUnit XML"""
    __test__ = False
    name: str
    classname: str
    time: float
    status: str  # passed, failed, error, skipped
    message: str = ""
    stacktrace: str = ""


class CICDIntegrationService:
    """CI/CD Integration Service"""

    def __init__(self):
        self.config: CICDConfig = CICDConfig()
        self.history: List[TriggerRecord] = []
        self._load_config()
        self._load_history()

    def _load_config(self):
        """Load configuration from disk"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = CICDConfig(**data)
            except Exception as e:
                logger.error(f"Error loading CI/CD config: {e}")
                self.config = CICDConfig()
                self._save_config()
        else:
            self._save_config()

    def _save_config(self):
        """Save configuration to disk"""
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.config), f, indent=2, ensure_ascii=False)

    def _load_history(self):
        """Load trigger history from disk"""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = [TriggerRecord(**item) for item in data]
            except Exception as e:
                logger.error(f"Error loading CI/CD history: {e}")

    def _save_history(self):
        """Save trigger history to disk"""
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in self.history[-100:]], f, indent=2, ensure_ascii=False)

    # ==================== Configuration ====================

    def get_config(self) -> Dict:
        """Get current configuration (mask secret)"""
        return {
            "webhook_url": "/api/ci/webhook",
            "webhook_secret": self.config.webhook_secret[:8] + "..." if self.config.webhook_secret else "",
            "enabled": self.config.enabled,
            "default_task_template": self.config.default_task_template,
            "notify_on_complete": self.config.notify_on_complete
        }

    def update_config(self, data: Dict) -> Dict:
        """Update configuration"""
        if 'enabled' in data:
            self.config.enabled = data['enabled']
        if 'default_task_template' in data:
            self.config.default_task_template = data['default_task_template']
        if 'notify_on_complete' in data:
            self.config.notify_on_complete = data['notify_on_complete']
        if 'regenerate_secret' in data and data['regenerate_secret']:
            self.config.webhook_secret = secrets.token_urlsafe(32)

        self._save_config()
        return self.get_config()

    def get_full_secret(self) -> str:
        """Get full webhook secret (for display once)"""
        return self.config.webhook_secret

    # ==================== Webhook Handling ====================

    def verify_webhook(self, signature: str, payload: str) -> bool:
        """Verify webhook signature"""
        if not self.config.webhook_secret:
            return True

        expected = hashlib.sha256(
            (self.config.webhook_secret + payload).encode()
        ).hexdigest()

        return secrets.compare_digest(signature, expected)

    def trigger_test(self, source: str, ref: str = "", commit: str = "", task_config: Dict = None) -> TriggerRecord:
        """Trigger a test run from CI/CD by invoking Commander for real testing"""
        record = TriggerRecord(
            source=source,
            ref=ref,
            commit=commit,
            status="pending"
        )
        self.history.append(record)
        self._save_history()

        record.status = "running"
        self._save_history()

        # Invoke Commander asynchronously for real testing
        import asyncio
        asyncio.ensure_future(self._run_commander(record, task_config or {}))

        return record

    async def _run_commander(self, record: TriggerRecord, task_config: Dict):
        """Run a Commander task in the background"""
        try:
            from agents.commander import get_commander
            commander = get_commander()

            # Construct test requirements
            user_input = task_config.get("requirement", "")
            if not user_input:
                user_input = f"Regression testing (CI/CD trigger: {record.source}, ref: {record.ref}, commit: {record.commit[:8] if record.commit else 'N/A'})"

            target_url = task_config.get("target_url", "")

            result = await commander.run(
                user_input=user_input,
                target_url=target_url,
                parallel=bool(task_config.get("parallel", True)),
                timeout_seconds=int(task_config.get("timeout_seconds", 900)),
            )

            # Update the trigger record
            record.status = "completed"
            record.task_id = result.get("mission_id", "")
            summary = result.get("summary", {})
            record.test_count = summary.get("total", 0)
            record.passed_count = summary.get("passed", 0)
            record.failed_count = summary.get("failed", 0)
            record.duration_ms = summary.get("duration_ms", 0)
            logger.info(f"[CICD] Commander task completed: {record.task_id}")

        except Exception as e:
            record.status = "failed"
            logger.error(f"[CICD] Commander task failed: {e}")

        self._save_history()

    def update_trigger_status(self, trigger_id: str, status: str, results: Dict = None) -> Optional[TriggerRecord]:
        """Update the status of a trigger"""
        for record in self.history:
            if record.id == trigger_id:
                record.status = status
                if results:
                    record.test_count = results.get('total', 0)
                    record.passed_count = results.get('passed', 0)
                    record.failed_count = results.get('failed', 0)
                    record.duration_ms = results.get('duration_ms', 0)
                self._save_history()
                return record
        return None

    def get_trigger_history(self, limit: int = 20) -> List[Dict]:
        """Get recent trigger history"""
        return [asdict(r) for r in reversed(self.history[-limit:])]

    def get_trigger(self, trigger_id: str) -> Optional[Dict]:
        """Get a specific trigger record"""
        for record in self.history:
            if record.id == trigger_id:
                return asdict(record)
        return None

    # ==================== Report Generation ====================

    def generate_junit_xml(self, trigger_id: str, test_results: List[TestCaseResult]) -> str:
        """Generate JUnit XML report"""
        # Calculate totals
        tests = len(test_results)
        failures = sum(1 for t in test_results if t.status == 'failed')
        errors = sum(1 for t in test_results if t.status == 'error')
        skipped = sum(1 for t in test_results if t.status == 'skipped')
        total_time = sum(t.time for t in test_results)

        # Build XML
        testsuite = ET.Element('testsuite', {
            'name': 'AI Test Platform',
            'tests': str(tests),
            'failures': str(failures),
            'errors': str(errors),
            'skipped': str(skipped),
            'time': f"{total_time:.3f}"
        })

        for tc in test_results:
            testcase = ET.SubElement(testsuite, 'testcase', {
                'name': tc.name,
                'classname': tc.classname,
                'time': f"{tc.time:.3f}"
            })

            if tc.status == 'failed':
                failure = ET.SubElement(testcase, 'failure', {
                    'message': tc.message,
                    'type': 'AssertionError'
                })
                if tc.stacktrace:
                    failure.text = tc.stacktrace
            elif tc.status == 'error':
                error = ET.SubElement(testcase, 'error', {
                    'message': tc.message,
                    'type': 'RuntimeError'
                })
                if tc.stacktrace:
                    error.text = tc.stacktrace
            elif tc.status == 'skipped':
                ET.SubElement(testcase, 'skipped', {'message': tc.message})

        # Save to file
        xml_path = REPORTS_DIR / f"{trigger_id}_junit.xml"
        tree = ET.ElementTree(testsuite)
        tree.write(str(xml_path), encoding='utf-8', xml_declaration=True)

        # Update trigger record
        for record in self.history:
            if record.id == trigger_id:
                record.report_path = str(xml_path)
                self._save_history()
                break

        return str(xml_path)

    def generate_html_summary(self, trigger_id: str, test_results: List[TestCaseResult]) -> str:
        """Generate HTML summary report"""
        tests = len(test_results)
        passed = sum(1 for t in test_results if t.status == 'passed')
        failed = sum(1 for t in test_results if t.status in ['failed', 'error'])
        skipped = sum(1 for t in test_results if t.status == 'skipped')
        total_time = sum(t.time for t in test_results)

        # Get trigger info
        trigger = self.get_trigger(trigger_id)
        trigger_time = trigger.get('triggered_at', '') if trigger else ''

        html = f"""<!DOCTYPE html>
<html lang="en-US">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - {trigger_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 2rem; border-radius: 1rem; margin-bottom: 2rem; }}
        .header h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
        .header .meta {{ font-size: 0.875rem; opacity: 0.8; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .stat {{ background: #1e293b; padding: 1.5rem; border-radius: 0.75rem; text-align: center; }}
        .stat .value {{ font-size: 2rem; font-weight: bold; }}
        .stat .label {{ font-size: 0.75rem; text-transform: uppercase; color: #94a3b8; margin-top: 0.25rem; }}
        .stat.passed .value {{ color: #22c55e; }}
        .stat.failed .value {{ color: #ef4444; }}
        .stat.skipped .value {{ color: #f59e0b; }}
        .results {{ background: #1e293b; border-radius: 0.75rem; overflow: hidden; }}
        .result {{ display: flex; align-items: center; padding: 1rem 1.5rem; border-bottom: 1px solid #334155; }}
        .result:last-child {{ border-bottom: none; }}
        .result .status {{ width: 80px; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }}
        .result .status.passed {{ color: #22c55e; }}
        .result .status.failed {{ color: #ef4444; }}
        .result .status.skipped {{ color: #f59e0b; }}
        .result .name {{ flex: 1; }}
        .result .time {{ color: #94a3b8; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI Test Platform - Test Report</h1>
            <div class="meta">Trigger ID: {trigger_id} | Time: {trigger_time}</div>
        </div>
        <div class="stats">
            <div class="stat"><div class="value">{tests}</div><div class="label">Total</div></div>
            <div class="stat passed"><div class="value">{passed}</div><div class="label">Passed</div></div>
            <div class="stat failed"><div class="value">{failed}</div><div class="label">Failed</div></div>
            <div class="stat skipped"><div class="value">{skipped}</div><div class="label">Skipped</div></div>
            <div class="stat"><div class="value">{total_time:.2f}s</div><div class="label">Duration</div></div>
        </div>
        <div class="results">
"""

        for tc in test_results:
            html += f"""            <div class="result">
                <div class="status {tc.status}">{tc.status}</div>
                <div class="name">{tc.classname}.{tc.name}</div>
                <div class="time">{tc.time:.3f}s</div>
            </div>
"""

        html += """        </div>
    </div>
</body>
</html>
"""

        # Save to file
        html_path = REPORTS_DIR / f"{trigger_id}_summary.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return str(html_path)

    def get_report_path(self, trigger_id: str, report_type: str) -> Optional[str]:
        """Get path to a report file"""
        if report_type == 'junit':
            path = REPORTS_DIR / f"{trigger_id}_junit.xml"
        elif report_type == 'html':
            path = REPORTS_DIR / f"{trigger_id}_summary.html"
        else:
            return None

        return str(path) if path.exists() else None

    # ==================== Mock Test Execution ====================

    def run_mock_tests(self, trigger_id: str) -> Dict:
        """Run mock tests and generate reports (for demo)"""
        import time
        import random

        # Simulate test results
        test_cases = [
            TestCaseResult("test_login_success", "AuthModule", 0.234, "passed"),
            TestCaseResult("test_login_invalid_password", "AuthModule", 0.156, "passed"),
            TestCaseResult("test_dashboard_load", "DashboardModule", 1.234, "passed"),
            TestCaseResult("test_api_response_time", "PerformanceModule", 0.089, "passed"),
            TestCaseResult("test_security_headers", "SecurityModule", 0.167, "passed"),
            TestCaseResult("test_xss_prevention", "SecurityModule", 0.245, "passed"),
            TestCaseResult("test_sql_injection", "SecurityModule", 0.189, "passed"),
            TestCaseResult("test_file_upload", "FileModule", 0.567, random.choice(["passed", "passed", "failed"])),
            TestCaseResult("test_user_creation", "UserModule", 0.345, "passed"),
            TestCaseResult("test_data_export", "ExportModule", 0.789, "passed"),
        ]

        # Add some randomness
        if random.random() < 0.2:
            test_cases.append(TestCaseResult(
                "test_edge_case", "EdgeModule", 0.123, "failed",
                message="Expected value did not match",
                stacktrace="AssertionError: Expected 200, got 500"
            ))

        # Generate reports
        junit_path = self.generate_junit_xml(trigger_id, test_cases)
        html_path = self.generate_html_summary(trigger_id, test_cases)

        # Update trigger status
        passed = sum(1 for t in test_cases if t.status == 'passed')
        failed = sum(1 for t in test_cases if t.status in ['failed', 'error'])
        total_time = sum(t.time for t in test_cases)

        self.update_trigger_status(trigger_id, 
            status="passed" if failed == 0 else "failed",
            results={
                "total": len(test_cases),
                "passed": passed,
                "failed": failed,
                "duration_ms": total_time * 1000
            }
        )

        return {
            "trigger_id": trigger_id,
            "total": len(test_cases),
            "passed": passed,
            "failed": failed,
            "duration_ms": total_time * 1000,
            "junit_path": junit_path,
            "html_path": html_path
        }


# Singleton instance
_service_instance: Optional[CICDIntegrationService] = None


def get_cicd_service() -> CICDIntegrationService:
    """Get or create the singleton service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = CICDIntegrationService()
    return _service_instance
