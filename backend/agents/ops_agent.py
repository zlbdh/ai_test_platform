"""
Ops Agent - operations diagnostics (superseded by the enhanced RCA Agent)
Note: use RCAAgent in agents/rca_agent.py for enhanced functionality
Retained for backward compatibility
"""
from typing import Dict, Any, List, Optional
from core.config import Config
from core.llm_manager import get_llm_for_role
from skills.ops_tools import OPS_TOOLS


class OpsAgent:
    """Operations diagnostics agent (deprecated; use RCAAgent)"""

    def __init__(self):
        """Initialize Ops Agent"""
        import warnings
        warnings.warn(
            "OpsAgent is deprecated; use agents.rca_agent.RCAAgent for enhanced functionality",
            DeprecationWarning,
            stacklevel=2
        )
        self.llm = get_llm_for_role("executor")

        self.tools = OPS_TOOLS

    def diagnose_error(self, error_message: str, log_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Diagnose errors

        Args:
            error_message: Error message
            log_path: Log file path (optional)

        Returns:
            Diagnostic result
        """
        results = {
            "agent": "ops_agent",
            "error_message": error_message,
            "diagnosis": None,
            "related_logs": [],
            "root_cause": None,
            "suggested_fixes": [],
            "status": "success"
        }

        try:
            # Use the diagnostic tool
            diagnosis = OPS_TOOLS[2].invoke({
                "error_message": error_message,
                "log_path": log_path
            })  # diagnose_error

            results["diagnosis"] = diagnosis
            results["root_cause"] = diagnosis.get("possible_causes", [])
            results["suggested_fixes"] = diagnosis.get("suggested_fixes", [])

            # Include related logs in the results when available
            if diagnosis.get("related_logs"):
                results["related_logs"] = diagnosis["related_logs"]

        except Exception as e:
            results["status"] = "error"
            results["error"] = str(e)

        return results

    def analyze_logs(self, log_path: str, time_range_minutes: int = 10) -> Dict[str, Any]:
        """
        Analyze logs

        Args:
            log_path: Log file path
            time_range_minutes: Time range in minutes

        Returns:
            Log analysis results
        """
        results = {
            "agent": "ops_agent",
            "log_path": log_path,
            "errors_found": [],
            "warnings_found": [],
            "summary": {}
        }

        try:
            # Search for errors
            errors = OPS_TOOLS[1].invoke({
                "log_path": log_path,
                "time_range_minutes": time_range_minutes
            })  # search_errors_in_log

            results["errors_found"] = errors

            # Analyze performance metrics
            performance = OPS_TOOLS[4].invoke({
                "log_path": log_path,
                "metric_type": "response_time"
            })  # analyze_performance_metrics

            results["performance"] = performance

            # Generate a summary
            results["summary"] = {
                "total_errors": len(errors),
                "error_types": self._categorize_errors(errors),
                "performance_status": "normal" if not performance.get("error") else "degraded"
            }

        except Exception as e:
            results["error"] = str(e)

        return results

    def check_service_health(self, service_urls: List[str]) -> Dict[str, Any]:
        """
        Check service health

        Args:
            service_urls: List of service URLs

        Returns:
            Health check results
        """
        results = {
            "agent": "ops_agent",
            "services": [],
            "overall_health": "healthy"
        }

        unhealthy_count = 0

        for url in service_urls:
            health = OPS_TOOLS[3].invoke({"service_url": url})  # check_service_health
            results["services"].append(health)

            if not health.get("is_healthy", False):
                unhealthy_count += 1

        if unhealthy_count > 0:
            results["overall_health"] = "unhealthy"

        return results

    def _categorize_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, int]:
        """Classify errors"""
        categories = {
            "null_pointer": 0,
            "timeout": 0,
            "connection": 0,
            "permission": 0,
            "other": 0
        }

        for error in errors:
            log_line = error.get("log_line", "").lower()

            if "null" in log_line or "pointer" in log_line:
                categories["null_pointer"] += 1
            elif "timeout" in log_line:
                categories["timeout"] += 1
            elif "connection" in log_line or "refused" in log_line:
                categories["connection"] += 1
            elif "permission" in log_line or "unauthorized" in log_line:
                categories["permission"] += 1
            else:
                categories["other"] += 1

        return categories

    def correlate_errors(self, ui_error: Optional[str], api_error: Optional[str],
                         log_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Correlate multiple errors to identify the root cause

        Args:
            ui_error: UI error message
            api_error: API error message
            log_path: Log file path

        Returns:
            Correlation analysis results
        """
        results = {
            "agent": "ops_agent",
            "ui_error": ui_error,
            "api_error": api_error,
            "correlation": None,
            "root_cause": None,
            "confidence": "medium"
        }

        # Analyze the relationship between the two errors
        if ui_error and api_error:
            # Increase confidence if both errors indicate the same problem
            if "timeout" in ui_error.lower() and "timeout" in api_error.lower():
                results["root_cause"] = "Network or service timeout"
                results["confidence"] = "high"
            elif "500" in api_error or "internal" in api_error.lower():
                results["root_cause"] = "A backend service error prevents the frontend from responding"
                results["confidence"] = "high"
            else:
                results["root_cause"] = "Further log analysis is needed"

        # Perform deeper analysis if logs are provided
        if log_path:
            log_analysis = self.analyze_logs(log_path)
            results["log_analysis"] = log_analysis

        return results
