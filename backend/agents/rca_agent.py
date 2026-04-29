"""
RCA Agent - 根因分析 Agent（增强版 Ops Agent）
负责日志分析、错误诊断、代码追溯、多错误关联分析
"""
from typing import Dict, Any, List, Optional
from core.config import Config
from core.llm_manager import get_llm_for_role
from skills.ops_tools import OPS_TOOLS
from skills.knowledge_tools import search_similar_bugs
from skills.ops_tools import git_blame, correlate_logs_with_code, diagnose_error_with_history


class RCAAgent:
    """根因分析 Agent（增强版）"""
    
    def __init__(self):
        """初始化 RCA Agent"""
        self.llm = get_llm_for_role("executor")
        
        self.tools = OPS_TOOLS
    
    def diagnose_error(self, error_message: str, log_path: Optional[str] = None) -> Dict[str, Any]:
        """
        诊断错误（增强版：使用 Vector DB 和历史记录）
        
        Args:
            error_message: 错误消息
            log_path: 日志文件路径（可选）
            
        Returns:
            诊断结果
        """
        # 使用增强的诊断工具
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
        分析日志
        
        Args:
            log_path: 日志文件路径
            time_range_minutes: 时间范围（分钟）
            
        Returns:
            日志分析结果
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
            # 搜索错误
            errors = OPS_TOOLS[1].invoke({
                "log_path": log_path,
                "time_range_minutes": time_range_minutes
            })  # search_errors_in_log
            
            results["errors_found"] = errors
            
            # 分析性能指标
            performance = OPS_TOOLS[4].invoke({
                "log_path": log_path,
                "metric_type": "response_time"
            })  # analyze_performance_metrics
            
            results["performance"] = performance
            
            # 生成摘要
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
        追溯代码变更（Git blame）
        
        Args:
            error_message: 错误消息
            file_path: 文件路径（可选，会从错误消息中提取）
            line_number: 行号（可选，会从错误消息中提取）
            
        Returns:
            代码追溯结果
        """
        # 从错误消息中提取文件路径和行号
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
                "error": "无法从错误消息中提取文件路径"
            }
        
        # 使用 Git blame
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
        关联多个错误，找出根因
        
        Args:
            ui_error: UI 错误消息
            api_error: API 错误消息
            log_path: 日志文件路径
            
        Returns:
            关联分析结果
        """
        # 使用关联工具
        correlation = correlate_logs_with_code.invoke({
            "error_message": f"UI: {ui_error or 'N/A'}, API: {api_error or 'N/A'}",
            "log_path": log_path
        })
        
        # 增强分析
        root_cause = None
        confidence = "medium"
        
        if ui_error and api_error:
            # 如果两个错误都指向同一个问题，提高置信度
            if "timeout" in ui_error.lower() and "timeout" in api_error.lower():
                root_cause = "网络或服务超时"
                confidence = "high"
            elif "500" in api_error or "internal" in api_error.lower():
                root_cause = "后端服务错误导致前端无法响应"
                confidence = "high"
                # 尝试追溯代码
                code_trace = self.trace_code_changes(api_error)
                correlation["code_trace"] = code_trace
            else:
                root_cause = "需要进一步分析日志"
        
        # 如果提供了日志，进行深度分析
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
        """分类错误"""
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
        生成根因分析报告
        
        Args:
            errors: 错误列表
            log_path: 日志文件路径
            
        Returns:
            根因分析报告
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
        
        # 诊断每个错误
        for error in errors:
            error_msg = str(error.get("error", ""))
            diagnosis = self.diagnose_error(error_msg, log_path)
            report["diagnoses"].append(diagnosis)
            
            # 追溯代码
            code_trace = self.trace_code_changes(error_msg)
            if code_trace.get("status") == "success":
                report["code_traces"].append(code_trace)
        
        # 如果多个错误，进行关联分析
        if len(errors) >= 2:
            ui_error = str(errors[0].get("error", "")) if errors[0].get("step") == "ui_test" else None
            api_error = str(errors[1].get("error", "")) if errors[1].get("step") == "api_test" else None
            
            if ui_error or api_error:
                correlation = self.correlate_errors(ui_error, api_error, log_path)
                report["correlations"].append(correlation)
                report["root_cause"] = correlation.get("root_cause")
        
        # 生成建议
        if report["root_cause"]:
            report["recommendations"].append(f"根因：{report['root_cause']}")
            report["recommendations"].append("建议检查相关代码和日志")
        
        return report
