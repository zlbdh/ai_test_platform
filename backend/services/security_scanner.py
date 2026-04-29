# -*- coding: utf-8 -*-
"""
安全测试服务 - 基于 OWASP ZAP 的漏洞扫描模块
提供 SQL 注入、XSS、CSRF 等常见漏洞检测
"""
import os
import json
import asyncio
import subprocess
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import re

from services.execution_center_service import get_execution_center_service


class ScanType(str, Enum):
    QUICK = "quick"       # 快速扫描 (Spider only)
    STANDARD = "standard"  # 标准扫描 (Spider + Passive)
    FULL = "full"         # 完整扫描 (Spider + Active)


class ScanStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class AlertRisk(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Informational"


@dataclass
class SecurityAlert:
    """安全告警"""
    name: str
    risk: AlertRisk
    confidence: str
    url: str
    description: str
    solution: str
    evidence: str = ""
    cweid: str = ""
    wascid: str = ""


@dataclass
class ScanConfig:
    """扫描配置"""
    target_url: str
    scan_type: ScanType = ScanType.STANDARD
    max_depth: int = 5
    max_children: int = 10
    ajax_spider: bool = False
    auth: Optional[Dict[str, str]] = None
    session_id: str = "default_session"
    execution_group_id: Optional[str] = None
    group_title: Optional[str] = None


@dataclass
class ScanResult:
    """扫描结果"""
    scan_id: str
    status: ScanStatus
    config: ScanConfig
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    alerts: List[SecurityAlert] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    @property
    def high_count(self) -> int:
        return sum(1 for a in self.alerts if a.risk == AlertRisk.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for a in self.alerts if a.risk == AlertRisk.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for a in self.alerts if a.risk == AlertRisk.LOW)


class SecurityScanner:
    """安全扫描器"""

    def __init__(self, results_dir: str = "data/security", zap_api_url: str = None):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.zap_api_url = zap_api_url or os.getenv("ZAP_API_URL", "http://localhost:8080")
        self.zap_api_key = os.getenv("ZAP_API_KEY", "")
        self._status = ScanStatus.IDLE
        self._current_result: Optional[ScanResult] = None

    @property
    def status(self) -> ScanStatus:
        return self._status

    async def scan(self, config: ScanConfig) -> ScanResult:
        """执行安全扫描"""
        import uuid
        
        scan_id = str(uuid.uuid4())[:8]
        self._status = ScanStatus.RUNNING
        
        result = ScanResult(
            scan_id=scan_id,
            status=ScanStatus.RUNNING,
            config=config,
            started_at=datetime.now()
        )
        self._current_result = result
        
        try:
            # 尝试使用 ZAP API
            if await self._check_zap_available():
                result = await self._run_zap_scan(result, config)
            else:
                # 使用简化扫描器
                result = await self._run_simple_scan(result, config)
                
        except Exception as e:
            result.status = ScanStatus.FAILED
            result.errors.append(str(e))
            self._status = ScanStatus.FAILED
            
        finally:
            self._save_result(result)
            
        return result

    async def _check_zap_available(self) -> bool:
        """检查 ZAP API 是否可用"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.zap_api_url}/JSON/core/view/version/"
                if self.zap_api_key:
                    url += f"?apikey={self.zap_api_key}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _run_zap_scan(self, result: ScanResult, config: ScanConfig) -> ScanResult:
        """使用 ZAP API 执行扫描"""
        async with aiohttp.ClientSession() as session:
            # 1. Spider 扫描
            spider_url = f"{self.zap_api_url}/JSON/spider/action/scan/"
            params = {
                "url": config.target_url,
                "maxChildren": config.max_children,
                "recurse": "true",
                "contextName": "",
                "subtreeOnly": "false"
            }
            if self.zap_api_key:
                params["apikey"] = self.zap_api_key
                
            async with session.get(spider_url, params=params) as resp:
                spider_data = await resp.json()
                spider_id = spider_data.get("scan")
            
            # 等待 Spider 完成
            while True:
                status_url = f"{self.zap_api_url}/JSON/spider/view/status/"
                params = {"scanId": spider_id}
                if self.zap_api_key:
                    params["apikey"] = self.zap_api_key
                    
                async with session.get(status_url, params=params) as resp:
                    status_data = await resp.json()
                    if int(status_data.get("status", 0)) >= 100:
                        break
                await asyncio.sleep(2)
            
            # 2. Active Scan (仅 FULL 模式)
            if config.scan_type == ScanType.FULL:
                ascan_url = f"{self.zap_api_url}/JSON/ascan/action/scan/"
                params = {"url": config.target_url, "recurse": "true", "inScopeOnly": "false"}
                if self.zap_api_key:
                    params["apikey"] = self.zap_api_key
                    
                async with session.get(ascan_url, params=params) as resp:
                    ascan_data = await resp.json()
                    ascan_id = ascan_data.get("scan")
                
                # 等待 Active Scan 完成
                while True:
                    status_url = f"{self.zap_api_url}/JSON/ascan/view/status/"
                    params = {"scanId": ascan_id}
                    if self.zap_api_key:
                        params["apikey"] = self.zap_api_key
                        
                    async with session.get(status_url, params=params) as resp:
                        status_data = await resp.json()
                        if int(status_data.get("status", 0)) >= 100:
                            break
                    await asyncio.sleep(5)
            
            # 3. 获取告警
            alerts_url = f"{self.zap_api_url}/JSON/core/view/alerts/"
            params = {"baseurl": config.target_url}
            if self.zap_api_key:
                params["apikey"] = self.zap_api_key
                
            async with session.get(alerts_url, params=params) as resp:
                alerts_data = await resp.json()
                
            for alert in alerts_data.get("alerts", []):
                result.alerts.append(SecurityAlert(
                    name=alert.get("name", ""),
                    risk=AlertRisk(alert.get("risk", "Informational")),
                    confidence=alert.get("confidence", ""),
                    url=alert.get("url", ""),
                    description=alert.get("description", ""),
                    solution=alert.get("solution", ""),
                    evidence=alert.get("evidence", "")[:200],
                    cweid=alert.get("cweid", ""),
                    wascid=alert.get("wascid", "")
                ))
        
        result.finished_at = datetime.now()
        result.status = ScanStatus.COMPLETED
        self._status = ScanStatus.COMPLETED
        
        result.stats = {
            "total_alerts": len(result.alerts),
            "high": result.high_count,
            "medium": result.medium_count,
            "low": result.low_count,
            "info": len(result.alerts) - result.high_count - result.medium_count - result.low_count
        }
        
        return result

    async def _run_simple_scan(self, result: ScanResult, config: ScanConfig) -> ScanResult:
        """简化的安全扫描（不依赖 ZAP）"""
        try:
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 检测常见漏洞
                checks = [
                    self._check_security_headers(session, config.target_url),
                    self._check_ssl(session, config.target_url),
                    self._check_sensitive_files(session, config.target_url),
                ]
                
                alerts_lists = await asyncio.gather(*checks, return_exceptions=True)
                
                for alerts in alerts_lists:
                    if isinstance(alerts, list):
                        result.alerts.extend(alerts)
                        
        except Exception as e:
            result.errors.append(f"Simple scan error: {e}")
        
        result.finished_at = datetime.now()
        result.status = ScanStatus.COMPLETED
        self._status = ScanStatus.COMPLETED
        
        result.stats = {
            "total_alerts": len(result.alerts),
            "high": result.high_count,
            "medium": result.medium_count,
            "low": result.low_count,
            "scan_type": "simple"
        }
        
        return result

    async def _check_security_headers(self, session, url: str) -> List[SecurityAlert]:
        """检查安全响应头"""
        alerts = []
        required_headers = {
            "Content-Security-Policy": ("Medium", "CSP 可防止 XSS 攻击"),
            "X-Frame-Options": ("Medium", "防止点击劫持"),
            "X-Content-Type-Options": ("Low", "防止 MIME 嗅探"),
            "Strict-Transport-Security": ("Medium", "强制 HTTPS"),
            "X-XSS-Protection": ("Low", "XSS 过滤器")
        }
        
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                for header, (risk, desc) in required_headers.items():
                    if header.lower() not in [h.lower() for h in resp.headers.keys()]:
                        alerts.append(SecurityAlert(
                            name=f"缺少安全头: {header}",
                            risk=AlertRisk(risk),
                            confidence="High",
                            url=url,
                            description=f"响应中缺少 {header} 头。{desc}。",
                            solution=f"添加 {header} 响应头"
                        ))
        except Exception:
            pass
            
        return alerts

    async def _check_ssl(self, session, url: str) -> List[SecurityAlert]:
        """检查 SSL/TLS 配置"""
        alerts = []
        
        if url.startswith("http://"):
            alerts.append(SecurityAlert(
                name="未使用 HTTPS",
                risk=AlertRisk.HIGH,
                confidence="High",
                url=url,
                description="网站使用 HTTP 而非 HTTPS，数据传输未加密。",
                solution="启用 SSL/TLS 证书，强制使用 HTTPS"
            ))
            
        return alerts

    async def _check_sensitive_files(self, session, url: str) -> List[SecurityAlert]:
        """检查敏感文件暴露"""
        alerts = []
        sensitive_paths = [
            ("/.git/config", "Git 配置泄露"),
            ("/.env", "环境变量泄露"),
            ("/wp-config.php", "WordPress 配置泄露"),
            ("/backup.sql", "数据库备份泄露"),
            ("/.htpasswd", "密码文件泄露"),
            ("/phpinfo.php", "PHP 信息泄露")
        ]
        
        base_url = url.rstrip("/")
        
        for path, desc in sensitive_paths:
            try:
                async with session.get(f"{base_url}{path}", 
                                      timeout=aiohttp.ClientTimeout(total=5),
                                      allow_redirects=False) as resp:
                    body = await resp.text()
                    if resp.status == 200 and self._looks_like_sensitive_content(path, dict(resp.headers), body):
                        alerts.append(SecurityAlert(
                            name=desc,
                            risk=AlertRisk.HIGH,
                            confidence="High",
                            url=f"{base_url}{path}",
                            description=f"发现敏感文件 {path} 可被公开访问",
                            solution=f"删除或限制访问 {path}"
                        ))
            except Exception:
                pass
                
        return alerts

    def _looks_like_sensitive_content(self, path: str, headers: Dict[str, str], body: str) -> bool:
        """通过内容特征避免将 HTML fallback / JSON 错误页误判为敏感文件暴露。"""
        sample = (body or "").strip()
        lowered = sample.lower()
        content_type = (headers.get("Content-Type") or headers.get("content-type") or "").lower()

        if not sample:
            return False
        if lowered.startswith("{") and ("no static resource" in lowered or '"code"' in lowered):
            return False
        if "<html" in lowered and path != "/phpinfo.php":
            return False
        if "application/json" in content_type and path != "/phpinfo.php":
            return False

        if path == "/.git/config":
            return "[core]" in lowered and "repositoryformatversion" in lowered
        if path == "/.env":
            return bool(re.search(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", sample, re.MULTILINE))
        if path == "/wp-config.php":
            return "<?php" in lowered and ("db_name" in lowered or "db_password" in lowered)
        if path == "/backup.sql":
            return "create table" in lowered or "insert into" in lowered or "mysqldump" in lowered
        if path == "/.htpasswd":
            return bool(re.search(r"^[^:\n]+:\$?[A-Za-z0-9./$-]{10,}$", sample, re.MULTILINE))
        if path == "/phpinfo.php":
            return "<html" in lowered and "php version" in lowered
        return False

    def _save_result(self, result: ScanResult):
        """保存扫描结果"""
        result_file = self.results_dir / f"result_{result.scan_id}.json"
        
        data = {
            "scan_id": result.scan_id,
            "status": result.status.value,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "finished_at": result.finished_at.isoformat() if result.finished_at else None,
            "duration": result.duration,
            "config": asdict(result.config),
            "stats": result.stats,
            "alerts": [asdict(a) for a in result.alerts],
            "errors": result.errors
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            get_execution_center_service().record_security_result(result)
        except Exception as exc:
            result.errors.append(f"execution center sync failed: {exc}")

    def stop_scan(self):
        """停止当前扫描"""
        self._status = ScanStatus.STOPPED
        if self._current_result:
            self._current_result.status = ScanStatus.STOPPED
            self._current_result.finished_at = datetime.now()
            self._save_result(self._current_result)

    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取扫描历史"""
        results = []
        
        for f in sorted(self.results_dir.glob("result_*.json"), reverse=True)[:limit]:
            with open(f, 'r', encoding='utf-8') as file:
                results.append(json.load(file))
                
        return results

    def delete_history(self, scan_id: str) -> bool:
        """删除单条扫描历史"""
        result_file = self.results_dir / f"result_{scan_id}.json"
        if result_file.exists():
            result_file.unlink()
            # 同时清理报告文件
            report_file = self.results_dir / f"report_{scan_id}.html"
            if report_file.exists():
                report_file.unlink()
            return True
        return False

    def clear_history(self) -> int:
        """清空全部扫描历史，返回删除数量"""
        count = 0
        for f in self.results_dir.glob("result_*.json"):
            f.unlink()
            count += 1
        for f in self.results_dir.glob("report_*.html"):
            f.unlink()
        return count

    def generate_report(self, scan_id: str) -> Dict[str, Any]:
        """生成安全报告"""
        result_file = self.results_dir / f"result_{scan_id}.json"
        
        if not result_file.exists():
            return {"status": "error", "message": "Scan result not found"}
        
        with open(result_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 生成 HTML 报告
        html = self._build_security_report(data)
        report_file = self.results_dir / f"report_{scan_id}.html"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return {
            "status": "success",
            "report_path": str(report_file),
            "summary": data.get("stats", {})
        }

    def _build_security_report(self, data: Dict) -> str:
        """构建安全报告 HTML"""
        alerts = data.get("alerts", [])
        stats = data.get("stats", {})
        
        alert_rows = ""
        for alert in alerts:
            risk_class = alert.get("risk", "info").lower()
            alert_rows += f"""
            <tr class="{risk_class}">
                <td><span class="risk-badge">{alert.get('risk', 'Unknown')}</span></td>
                <td>{alert.get('name', 'Unknown')}</td>
                <td class="url">{alert.get('url', '')[:60]}...</td>
                <td>{alert.get('description', '')[:100]}...</td>
            </tr>
            """
        
        return f"""
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>安全扫描报告 - {data.get('scan_id', '')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #ff4757; margin-bottom: 20px; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: #16213e; padding: 20px; border-radius: 10px; text-align: center; }}
        .stat-card h3 {{ font-size: 2em; margin-bottom: 5px; }}
        .stat-card.high h3 {{ color: #ff4757; }}
        .stat-card.medium h3 {{ color: #ffa502; }}
        .stat-card.low h3 {{ color: #2ed573; }}
        .stat-card.info h3 {{ color: #1e90ff; }}
        table {{ width: 100%; border-collapse: collapse; background: #16213e; border-radius: 10px; overflow: hidden; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #0f0f23; color: #00d9ff; }}
        .risk-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }}
        tr.high .risk-badge {{ background: #ff4757; color: white; }}
        tr.medium .risk-badge {{ background: #ffa502; color: black; }}
        tr.low .risk-badge {{ background: #2ed573; color: black; }}
        tr.informational .risk-badge {{ background: #1e90ff; color: white; }}
        .url {{ font-family: monospace; font-size: 0.85em; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 安全扫描报告</h1>
        <p>扫描 ID: {data.get('scan_id', '')} | 时间: {data.get('finished_at', '')}</p>
        
        <div class="stats">
            <div class="stat-card high"><h3>{stats.get('high', 0)}</h3><p>高风险</p></div>
            <div class="stat-card medium"><h3>{stats.get('medium', 0)}</h3><p>中风险</p></div>
            <div class="stat-card low"><h3>{stats.get('low', 0)}</h3><p>低风险</p></div>
            <div class="stat-card info"><h3>{stats.get('info', 0)}</h3><p>信息</p></div>
        </div>
        
        <table>
            <thead><tr><th>风险</th><th>漏洞</th><th>URL</th><th>描述</th></tr></thead>
            <tbody>{alert_rows if alert_rows else '<tr><td colspan="4" style="text-align:center;">未发现漏洞 ✅</td></tr>'}</tbody>
        </table>
    </div>
</body>
</html>
"""


# 全局实例
_scanner: Optional[SecurityScanner] = None


def get_security_scanner() -> SecurityScanner:
    """获取安全扫描器单例"""
    global _scanner
    if _scanner is None:
        from core.config import Config
        results_dir = os.path.join(Config.PROJECT_ROOT, "data", "security")
        _scanner = SecurityScanner(results_dir)
    return _scanner
