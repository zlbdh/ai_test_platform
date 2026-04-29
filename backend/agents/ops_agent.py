"""
Ops Agent - 运维诊断 Agent（已增强为 RCA Agent）
注意：建议使用 agents/rca_agent.py 中的 RCAAgent 以获得更强大的功能
此文件保留以保持向后兼容
"""
from typing import Dict, Any, List, Optional
from core.config import Config
from core.llm_manager import get_llm_for_role
from skills.ops_tools import OPS_TOOLS


class OpsAgent:
    """运维诊断 Agent（已废弃，建议使用 RCAAgent）"""
    
    def __init__(self):
        """初始化 Ops Agent"""
        import warnings
        warnings.warn(
            "OpsAgent 已废弃，建议使用 agents.rca_agent.RCAAgent 以获得更强大的功能",
            DeprecationWarning,
            stacklevel=2
        )
        self.llm = get_llm_for_role("executor")
        
        self.tools = OPS_TOOLS
    
    def diagnose_error(self, error_message: str, log_path: Optional[str] = None) -> Dict[str, Any]:
        """
        诊断错误
        
        Args:
            error_message: 错误消息
            log_path: 日志文件路径（可选）
            
        Returns:
            诊断结果
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
            # 使用诊断工具
            diagnosis = OPS_TOOLS[2].invoke({
                "error_message": error_message,
                "log_path": log_path
            })  # diagnose_error
            
            results["diagnosis"] = diagnosis
            results["root_cause"] = diagnosis.get("possible_causes", [])
            results["suggested_fixes"] = diagnosis.get("suggested_fixes", [])
            
            # 如果有相关日志，添加到结果中
            if diagnosis.get("related_logs"):
                results["related_logs"] = diagnosis["related_logs"]
        
        except Exception as e:
            results["status"] = "error"
            results["error"] = str(e)
        
        return results
    
    def analyze_logs(self, log_path: str, time_range_minutes: int = 10) -> Dict[str, Any]:
        """
        分析日志
        
        Args:
            log_path: 日志文件路径
            time_range_minutes: 时间范围（分钟）
            
        Returns:
            日志分析结果
        """
        results = {
            "agent": "ops_agent",
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
    
    def check_service_health(self, service_urls: List[str]) -> Dict[str, Any]:
        """
        检查服务健康状态
        
        Args:
            service_urls: 服务 URL 列表
            
        Returns:
            健康检查结果
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
        results = {
            "agent": "ops_agent",
            "ui_error": ui_error,
            "api_error": api_error,
            "correlation": None,
            "root_cause": None,
            "confidence": "medium"
        }
        
        # 分析两个错误的关系
        if ui_error and api_error:
            # 如果两个错误都指向同一个问题，提高置信度
            if "timeout" in ui_error.lower() and "timeout" in api_error.lower():
                results["root_cause"] = "网络或服务超时"
                results["confidence"] = "high"
            elif "500" in api_error or "internal" in api_error.lower():
                results["root_cause"] = "后端服务错误导致前端无法响应"
                results["confidence"] = "high"
            else:
                results["root_cause"] = "需要进一步分析日志"
        
        # 如果提供了日志，进行深度分析
        if log_path:
            log_analysis = self.analyze_logs(log_path)
            results["log_analysis"] = log_analysis
        
        return results
