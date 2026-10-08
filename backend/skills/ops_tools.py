"""
Operations diagnostic tools
For log analysis, error diagnosis, network monitoring, and related tasks
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
import os
from datetime import datetime
from core.config import Config
from skills.knowledge_tools import search_similar_bugs


@tool
def read_log_file(log_path: str, lines: int = 100, search_keyword: Optional[str] = None) -> List[str]:
    """
    Read a log file

    Args:
        log_path: Log file path
        lines: Number of lines to read from the end
        search_keyword: Optional search keyword

    Returns:
        List of log lines
    """
    try:
        if not os.path.exists(log_path):
            return [f"Log file does not exist: {log_path}"]

        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        # Get the last N lines
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        # Filter by keyword if one is provided
        if search_keyword:
            filtered_lines = [line for line in recent_lines if search_keyword.lower() in line.lower()]
            return filtered_lines

        return recent_lines
    except Exception as e:
        return [f"Failed to read the log: {str(e)}"]


@tool
def search_errors_in_log(log_path: str, time_range_minutes: int = 10) -> List[Dict[str, Any]]:
    """
    Search logs for errors

    Args:
        log_path: Log file path
        time_range_minutes: Time range in minutes

    Returns:
        List of error messages
    """
    try:
        log_lines = read_log_file.invoke({"log_path": log_path, "lines": 1000})

        errors = []
        error_keywords = ["error", "exception", "failed", "failure", "crash", "timeout"]

        for line in log_lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in error_keywords):
                errors.append({
                    "log_line": line.strip(),
                    "timestamp": datetime.now().isoformat(),
                    "severity": "error"
                })

        return errors
    except Exception as e:
        return [{"error": str(e)}]


@tool
def diagnose_error(error_message: str, log_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Diagnose an error (analyze its type and possible causes)

    Args:
        error_message: Error message
        log_path: Optional log file path

    Returns:
        Diagnostic result
    """
    diagnosis = {
        "error_message": error_message,
        "possible_causes": [],
        "suggested_fixes": [],
        "severity": "unknown"
    }

    error_lower = error_message.lower()

    # Diagnose based on the error message type
    if "null pointer" in error_lower or "nullreference" in error_lower:
        diagnosis["possible_causes"].append("Null pointer exception: object not initialized")
        diagnosis["suggested_fixes"].append("Check object initialization logic")
        diagnosis["severity"] = "high"
    elif "timeout" in error_lower:
        diagnosis["possible_causes"].append("Timeout: network latency or slow service response")
        diagnosis["suggested_fixes"].append("Check network connectivity and service performance")
        diagnosis["severity"] = "medium"
    elif "connection refused" in error_lower or "connection reset" in error_lower:
        diagnosis["possible_causes"].append("Connection refused: the service may not be running or the port may be occupied")
        diagnosis["suggested_fixes"].append("Check service status and port usage")
        diagnosis["severity"] = "high"
    elif "404" in error_message or "not found" in error_lower:
        diagnosis["possible_causes"].append("Resource not found: incorrect URL path or missing resource")
        diagnosis["suggested_fixes"].append("Check the URL path and whether the resource exists")
        diagnosis["severity"] = "low"
    elif "500" in error_message or "internal server error" in error_lower:
        diagnosis["possible_causes"].append("Internal server error: code exception or configuration problem")
        diagnosis["suggested_fixes"].append("Review server logs and check the code logic")
        diagnosis["severity"] = "high"
    elif "permission denied" in error_lower or "unauthorized" in error_lower:
        diagnosis["possible_causes"].append("Insufficient permissions: authentication failed or permissions are missing")
        diagnosis["suggested_fixes"].append("Check credentials and permission settings")
        diagnosis["severity"] = "medium"

    # If a log path is provided, try to obtain more information from the logs
    if log_path:
        errors = search_errors_in_log.invoke({"log_path": log_path})
        if errors:
            diagnosis["related_logs"] = errors[:5]  # The five most recent related log entries

    return diagnosis


@tool
def check_service_health(service_url: str) -> Dict[str, Any]:
    """
    Check service health

    Args:
        service_url: Service URL (such as a health check endpoint)

    Returns:
        Health status
    """
    try:
        import requests

        response = requests.get(service_url, timeout=5)

        return {
            "service_url": service_url,
            "status_code": response.status_code,
            "is_healthy": response.status_code == 200,
            "response_time_ms": response.elapsed.total_seconds() * 1000
        }
    except Exception as e:
        return {
            "service_url": service_url,
            "is_healthy": False,
            "error": str(e)
        }


@tool
def analyze_performance_metrics(log_path: str, metric_type: str = "response_time") -> Dict[str, Any]:
    """
    Analyze performance metrics

    Args:
        log_path: Log file path
        metric_type: Metric type (response_time, memory, cpu)

    Returns:
        Performance analysis result
    """
    try:
        log_lines = read_log_file.invoke({"log_path": log_path, "lines": 1000})

        # Basic performance analysis (a production implementation should use specialized tools)
        if metric_type == "response_time":
            response_times = []
            for line in log_lines:
                if "response_time" in line.lower() or "duration" in line.lower():
                    # Try to extract numbers (simplified)
                    import re
                    numbers = re.findall(r'\d+\.?\d*', line)
                    if numbers:
                        response_times.append(float(numbers[0]))

            if response_times:
                return {
                    "metric_type": metric_type,
                    "average": sum(response_times) / len(response_times),
                    "max": max(response_times),
                    "min": min(response_times),
                    "count": len(response_times)
                }

        return {
            "metric_type": metric_type,
            "message": "No relevant performance metrics found"
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def git_blame(file_path: str, line_number: Optional[int] = None) -> Dict[str, Any]:
    """
    View code change history (Git blame)

    Args:
        file_path: File path relative to the Git repository root
        line_number: Optional line number

    Returns:
        Git blame results
    """
    try:
        import git

        repo_path = Config.GIT_REPO_PATH
        repo = git.Repo(repo_path)

        if line_number:
            # Get blame for a specific line
            blame_info = repo.git.blame("-L", f"{line_number},{line_number}", file_path)
        else:
            # Get blame for the entire file
            blame_info = repo.git.blame(file_path)

        # Parse blame information
        lines = blame_info.split('\n')
        blame_data = []

        for line in lines[:20]:  # Limit results to the first 20 lines
            if line.strip():
                # Simplified parsing (a production implementation should use more complete parsing logic)
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    commit_hash = parts[0]
                    author = parts[1] if len(parts) > 1 else "unknown"
                    date = parts[2] if len(parts) > 2 else "unknown"
                    code = parts[3] if len(parts) > 3 else ""

                    blame_data.append({
                        "commit": commit_hash,
                        "author": author,
                        "date": date,
                        "code": code[:100]  # Truncate code
                    })

        return {
            "status": "success",
            "file_path": file_path,
            "line_number": line_number,
            "blame_info": blame_data,
            "total_lines": len(blame_data)
        }
    except ImportError:
        return {
            "status": "error",
            "error": "GitPython is not installed; run: pip install gitpython"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@tool
def correlate_logs_with_code(error_message: str, log_path: Optional[str] = None,
                             file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Correlate logs and code changes

    Args:
        error_message: Error message
        log_path: Log file path
        file_path: Optional path to the related code file

    Returns:
        Correlation analysis results
    """
    try:
        correlation = {
            "error_message": error_message,
            "log_analysis": None,
            "code_analysis": None,
            "correlation": None
        }

        # Analyze logs
        if log_path:
            errors = search_errors_in_log.invoke({"log_path": log_path})
            correlation["log_analysis"] = {
                "errors_found": len(errors),
                "recent_errors": errors[:5]
            }

        # Analyze code if a file path is provided
        if file_path:
            blame_result = git_blame.invoke({"file_path": file_path})
            correlation["code_analysis"] = blame_result

        # Correlation analysis
        # Try to extract the file name and line number from the error message
        import re
        file_match = re.search(r'([\w/]+\.(java|py|js|ts|go))', error_message)
        line_match = re.search(r'line (\d+)', error_message, re.IGNORECASE)

        if file_match or line_match:
            correlation["correlation"] = {
                "extracted_file": file_match.group(1) if file_match else None,
                "extracted_line": int(line_match.group(1)) if line_match else None,
                "confidence": "medium"
            }

        return correlation
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@tool
def diagnose_error_with_history(error_message: str, log_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Diagnose an error (enhanced: retrieve similar historical errors from the vector database)

    Args:
        error_message: Error message
        log_path: Optional log file path

    Returns:
        Diagnostic result including similar historical errors
    """
    # Perform basic diagnosis first
    diagnosis = diagnose_error.invoke({
        "error_message": error_message,
        "log_path": log_path
    })

    # Retrieve similar historical bugs from the vector database
    try:
        similar_bugs = search_similar_bugs.invoke({
            "error_message": error_message,
            "n_results": 3
        })

        if similar_bugs and len(similar_bugs) > 0:
            diagnosis["similar_bugs"] = similar_bugs
            diagnosis["has_historical_reference"] = True

            # Add remediation suggestions if similar historical bugs are found
            if similar_bugs[0].get("metadata"):
                metadata = similar_bugs[0]["metadata"]
                if metadata.get("solution"):
                    diagnosis["suggested_fixes"].append(f"Solution to a similar historical issue: {metadata['solution']}")
    except Exception as e:
        diagnosis["vector_db_error"] = str(e)

    return diagnosis


# Tool list
OPS_TOOLS = [
    read_log_file,
    search_errors_in_log,
    diagnose_error,
    diagnose_error_with_history,  # Added
    check_service_health,
    analyze_performance_metrics,
    git_blame,  # Added
    correlate_logs_with_code,  # Added
]
