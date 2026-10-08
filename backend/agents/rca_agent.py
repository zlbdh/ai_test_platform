"""
RCA Agent - root cause analysis agent (enhanced Ops Agent)
Handles log analysis, error diagnosis, code tracing, and correlation across errors
"""
from typing import Dict, Any, List, Optional
from core.config import Config
from core.llm_manager import get_llm_for_role
from skills.ops_tools import OPS_TOOLS
from skills.knowledge_tools import search_similar_bugs
from skills.ops_tools import git_blame, correlate_logs_with_code, diagnose_error_with_history


class RCAAgent:
    """Root cause analysis agent (enhanced)"""

    def __init__(self):
        """Initialize RCA Agent"""
        self.llm = get_llm_for_role("executor")

        self.tools = OPS_TOOLS

    def diagnose_error(self, error_message: str, log_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Diagnose errors (enhanced: uses the vector database and history)

        Args:
            error_message: Error message
            log_path: Log file path (optional)

        Returns:
            Diagnostic result
        """
        # Use the enhanced diagnostic tool
        diagnosis = diagnose_error_with_history.invoke({
            "error_message": error_message,
            "log_path": log_path
        })

        return {
            "agent": "rca_agent",
            **diagnosis
        }

    def analyze_logs(self, log_path: str, time_range_minutes: int = 10) -> Dict[str, Any]:
        """
        Analyze logs

        Args:
            log_path: Log file path
            time_range_minutes: Time range in minutes

        Returns:
            Log analysis results
        """
        from skills.ops_tools import analyze_logs

        results = {
            "agent": "rca_agent",
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

    def trace_code_changes(self, error_message: str, file_path: Optional[str] = None,
                          line_number: Optional[int] = None) -> Dict[str, Any]:
        """
        Trace code changes (Git blame)

        Args:
            error_message: Error message
            file_path: File path (optional; extracted from the error message)
            line_number: Line number (optional; extracted from the error message)

        Returns:
            Code tracing results
        """
        # Extract the file path and line number from the error message
        import re
        if not file_path:
            file_match = re.search(r'([\w/]+\.(java|py|js|ts|go))', error_message)
            if file_match:
                file_path = file_match.group(1)

        if not line_number:
            line_match = re.search(r'line (\d+)', error_message, re.IGNORECASE)
            if line_match:
                line_number = int(line_match.group(1))

        if not file_path:
            return {
                "status": "error",
                "error": "Cannot extract a file path from the error message"
            }

        # Use Git blame
        blame_result = git_blame.invoke({
            "file_path": file_path,
            "line_number": line_number
        })

        return {
            "agent": "rca_agent",
            "error_message": error_message,
            "file_path": file_path,
            "line_number": line_number,
            **blame_result
        }

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
        # Use the correlation tool
        correlation = correlate_logs_with_code.invoke({
            "error_message": f"UI: {ui_error or 'N/A'}, API: {api_error or 'N/A'}",
            "log_path": log_path
        })

        # Enhanced analysis
        root_cause = None
        confidence = "medium"

        if ui_error and api_error:
            # Increase confidence if both errors indicate the same problem
            if "timeout" in ui_error.lower() and "timeout" in api_error.lower():
                root_cause = "Network or service timeout"
                confidence = "high"
            elif "500" in api_error or "internal" in api_error.lower():
                root_cause = "A backend service error prevents the frontend from responding"
                confidence = "high"
                # Try to trace the code
                code_trace = self.trace_code_changes(api_error)
                correlation["code_trace"] = code_trace
            else:
                root_cause = "Further log analysis is needed"

        # Perform deeper analysis if logs are provided
        if log_path:
            log_analysis = self.analyze_logs(log_path)
            correlation["log_analysis"] = log_analysis

        return {
            "agent": "rca_agent",
            "ui_error": ui_error,
            "api_error": api_error,
            "root_cause": root_cause,
            "confidence": confidence,
            **correlation
        }

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

    def generate_root_cause_report(self, errors: List[Dict[str, Any]],
                                   log_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a root cause analysis report

        Args:
            errors: Error list
            log_path: Log file path

        Returns:
            Root cause analysis report
        """
        report = {
            "agent": "rca_agent",
            "total_errors": len(errors),
            "diagnoses": [],
            "code_traces": [],
            "correlations": [],
            "root_cause": None,
            "recommendations": []
        }

        # Diagnose each error
        for error in errors:
            error_msg = str(error.get("error", ""))
            diagnosis = self.diagnose_error(error_msg, log_path)
            report["diagnoses"].append(diagnosis)

            # Trace the code
            code_trace = self.trace_code_changes(error_msg)
            if code_trace.get("status") == "success":
                report["code_traces"].append(code_trace)

        # Correlate errors if multiple errors exist
        if len(errors) >= 2:
            ui_error = str(errors[0].get("error", "")) if errors[0].get("step") == "ui_test" else None
            api_error = str(errors[1].get("error", "")) if errors[1].get("step") == "api_test" else None

            if ui_error or api_error:
                correlation = self.correlate_errors(ui_error, api_error, log_path)
                report["correlations"].append(correlation)
                report["root_cause"] = correlation.get("root_cause")

        # Generate recommendations
        if report["root_cause"]:
            report["recommendations"].append(f"Root cause: {report['root_cause']}")
            report["recommendations"].append("Review the related code and logs")

        return report
