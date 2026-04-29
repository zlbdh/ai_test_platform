"""
Test Report Generator - 测试报告增强生成器

生成多种格式的测试报告：
- HTML 报告
- JUnit XML
- JSON 报告
- Markdown 报告
- 邮件通知
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import os


class ReportFormat(Enum):
    HTML = "html"
    JUNIT_XML = "junit_xml"
    JSON = "json"
    MARKDOWN = "markdown"


@dataclass
class TestResult:
    """测试结果"""
    __test__ = False
    name: str
    status: str  # passed, failed, skipped
    duration_ms: int
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshots: List[str] = None


@dataclass
class TestSuite:
    """测试套件"""
    __test__ = False
    name: str
    tests: List[TestResult]
    start_time: str
    end_time: str


class EnhancedReportGenerator:
    """增强报告生成器"""
    
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate(
        self,
        suite: TestSuite,
        format: ReportFormat = ReportFormat.HTML
    ) -> str:
        """生成报告"""
        if format == ReportFormat.HTML:
            return self._generate_html(suite)
        elif format == ReportFormat.JUNIT_XML:
            return self._generate_junit_xml(suite)
        elif format == ReportFormat.JSON:
            return self._generate_json(suite)
        elif format == ReportFormat.MARKDOWN:
            return self._generate_markdown(suite)
        else:
            return self._generate_json(suite)
    
    def _calculate_stats(self, suite: TestSuite) -> Dict[str, Any]:
        """计算统计"""
        total = len(suite.tests)
        passed = sum(1 for t in suite.tests if t.status == "passed")
        failed = sum(1 for t in suite.tests if t.status == "failed")
        skipped = sum(1 for t in suite.tests if t.status == "skipped")
        duration = sum(t.duration_ms for t in suite.tests)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "duration_ms": duration,
            "duration_readable": f"{duration / 1000:.2f}s"
        }
    
    def _generate_html(self, suite: TestSuite) -> str:
        """生成 HTML 报告"""
        stats = self._calculate_stats(suite)
        
        html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>测试报告 - {suite.name}</title>
    <style>
        :root {{
            --bg: #0a0a1a;
            --surface: #12122a;
            --surface-hover: #1a1a3a;
            --border: #2a2a4a;
            --text: #e8e8f0;
            --text-2: #a0a0c0;
            --text-3: #6060a0;
            --accent: #6366f1;
            --pass: #22c55e;
            --pass-bg: rgba(34,197,94,0.08);
            --fail: #ef4444;
            --fail-bg: rgba(239,68,68,0.08);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 32px 24px; }}
        h1 {{
            font-size: 1.6rem;
            font-weight: 700;
            background: linear-gradient(135deg, #6366f1, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }}
        .subtitle {{ font-size: 0.8rem; color: var(--text-3); margin-bottom: 24px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin: 20px 0 30px;
        }}
        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 12px;
            text-align: center;
            backdrop-filter: blur(8px);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.2);
        }}
        .stat-card h3 {{ font-size: 1.8rem; font-weight: 800; line-height: 1; }}
        .stat-card p {{ color: var(--text-3); font-size: 0.7rem; margin-top: 6px; text-transform: uppercase; letter-spacing: 1px; }}
        .stat-card.passed h3 {{ color: var(--pass); }}
        .stat-card.failed h3 {{ color: var(--fail); }}
        .stat-card.rate h3 {{ color: #d97706; }}
        .stat-card.duration h3 {{ color: #0ea5e9; font-size: 1.3rem; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: var(--surface);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        th, td {{ padding: 14px 16px; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.85rem; }}
        th {{ background: var(--surface-hover); color: var(--text-2); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: rgba(99,102,241,0.03); }}
        .status-passed {{ color: var(--pass); font-weight: 700; }}
        .status-failed {{ color: var(--fail); font-weight: 700; }}
        .status-skipped {{ color: #d97706; font-weight: 700; }}
        .error {{
            background: var(--fail-bg);
            border: 1px solid rgba(239,68,68,0.2);
            padding: 10px 12px;
            border-radius: 8px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.75rem;
            color: var(--fail);
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 120px;
            overflow-y: auto;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid var(--border);
            font-size: 0.7rem;
            color: var(--text-3);
            display: flex;
            justify-content: space-between;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 测试报告 - {suite.name}</h1>
        <div class="subtitle">执行时间: {suite.start_time} ~ {suite.end_time}</div>
        
        <div class="stats">
            <div class="stat-card passed">
                <h3>{stats['passed']}</h3>
                <p>通过</p>
            </div>
            <div class="stat-card failed">
                <h3>{stats['failed']}</h3>
                <p>失败</p>
            </div>
            <div class="stat-card rate">
                <h3>{stats['pass_rate']}%</h3>
                <p>通过率</p>
            </div>
            <div class="stat-card duration">
                <h3>{stats['duration_readable']}</h3>
                <p>耗时</p>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>测试用例</th>
                    <th>状态</th>
                    <th>耗时</th>
                    <th>错误信息</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for test in suite.tests:
            status_class = f"status-{test.status}"
            error_html = f'<div class="error">{test.error_message}</div>' if test.error_message else "-"
            
            html += f"""
                <tr>
                    <td>{test.name}</td>
                    <td class="{status_class}">{test.status.upper()}</td>
                    <td>{test.duration_ms}ms</td>
                    <td>{error_html}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
        <div class="footer">
            <span>AI Test Platform v2.0</span>
            <span>Enhanced Report Generator</span>
        </div>
    </div>
</body>
</html>
"""
        
        # 保存文件
        filename = f"{suite.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return filepath
    
    def _generate_junit_xml(self, suite: TestSuite) -> str:
        """生成 JUnit XML 报告"""
        stats = self._calculate_stats(suite)
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="{suite.name}" tests="{stats['total']}" failures="{stats['failed']}" skipped="{stats['skipped']}" time="{stats['duration_ms'] / 1000}">
"""
        
        for test in suite.tests:
            xml += f'  <testcase name="{test.name}" time="{test.duration_ms / 1000}"'
            
            if test.status == "passed":
                xml += " />\n"
            elif test.status == "failed":
                xml += f""">
    <failure message="{test.error_message or 'Test failed'}">{test.stack_trace or ''}</failure>
  </testcase>
"""
            elif test.status == "skipped":
                xml += """>
    <skipped />
  </testcase>
"""
        
        xml += "</testsuite>\n"
        
        filename = f"{suite.name.replace(' ', '_')}_junit.xml"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml)
        
        return filepath
    
    def _generate_json(self, suite: TestSuite) -> str:
        """生成 JSON 报告"""
        stats = self._calculate_stats(suite)
        
        data = {
            "suite": suite.name,
            "start_time": suite.start_time,
            "end_time": suite.end_time,
            "statistics": stats,
            "tests": [
                {
                    "name": t.name,
                    "status": t.status,
                    "duration_ms": t.duration_ms,
                    "error": t.error_message
                }
                for t in suite.tests
            ]
        }
        
        filename = f"{suite.name.replace(' ', '_')}.json"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def _generate_markdown(self, suite: TestSuite) -> str:
        """生成 Markdown 报告"""
        stats = self._calculate_stats(suite)
        
        md = f"""# 测试报告 - {suite.name}

**执行时间**: {suite.start_time} ~ {suite.end_time}

## 统计

| 指标 | 值 |
|------|-----|
| 总数 | {stats['total']} |
| 通过 | {stats['passed']} |
| 失败 | {stats['failed']} |
| 跳过 | {stats['skipped']} |
| 通过率 | {stats['pass_rate']}% |
| 耗时 | {stats['duration_readable']} |

## 测试结果

| 用例 | 状态 | 耗时 |
|------|------|------|
"""
        
        for test in suite.tests:
            status_emoji = "✅" if test.status == "passed" else ("❌" if test.status == "failed" else "⏭️")
            md += f"| {test.name} | {status_emoji} {test.status} | {test.duration_ms}ms |\n"
        
        if stats['failed'] > 0:
            md += "\n## 失败详情\n\n"
            for test in suite.tests:
                if test.status == "failed" and test.error_message:
                    md += f"### {test.name}\n\n```\n{test.error_message}\n```\n\n"
        
        filename = f"{suite.name.replace(' ', '_')}.md"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md)
        
        return filepath


def create_report_generator(output_dir: str = "./reports") -> EnhancedReportGenerator:
    """创建报告生成器"""
    return EnhancedReportGenerator(output_dir)
