"""
运维诊断工具
用于日志分析、错误诊断、网络监控等
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
    读取日志文件
    
    Args:
        log_path: 日志文件路径
        lines: 读取的行数（从末尾开始）
        search_keyword: 可选，搜索关键词
        
    Returns:
        日志行列表
    """
    try:
        if not os.path.exists(log_path):
            return [f"日志文件不存在: {log_path}"]
        
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # 获取最后 N 行
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # 如果有关键词，进行过滤
        if search_keyword:
            filtered_lines = [line for line in recent_lines if search_keyword.lower() in line.lower()]
            return filtered_lines
        
        return recent_lines
    except Exception as e:
        return [f"读取日志失败: {str(e)}"]


@tool
def search_errors_in_log(log_path: str, time_range_minutes: int = 10) -> List[Dict[str, Any]]:
    """
    在日志中搜索错误
    
    Args:
        log_path: 日志文件路径
        time_range_minutes: 时间范围（分钟）
        
    Returns:
        错误信息列表
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
    诊断错误（分析错误类型和可能原因）
    
    Args:
        error_message: 错误消息
        log_path: 可选，日志文件路径
        
    Returns:
        诊断结果
    """
    diagnosis = {
        "error_message": error_message,
        "possible_causes": [],
        "suggested_fixes": [],
        "severity": "unknown"
    }
    
    error_lower = error_message.lower()
    
    # 根据错误消息类型进行诊断
    if "null pointer" in error_lower or "nullreference" in error_lower:
        diagnosis["possible_causes"].append("空指针异常：对象未初始化")
        diagnosis["suggested_fixes"].append("检查对象初始化逻辑")
        diagnosis["severity"] = "high"
    elif "timeout" in error_lower:
        diagnosis["possible_causes"].append("超时：网络延迟或服务响应慢")
        diagnosis["suggested_fixes"].append("检查网络连接和服务性能")
        diagnosis["severity"] = "medium"
    elif "connection refused" in error_lower or "connection reset" in error_lower:
        diagnosis["possible_causes"].append("连接被拒绝：服务可能未启动或端口被占用")
        diagnosis["suggested_fixes"].append("检查服务状态和端口占用情况")
        diagnosis["severity"] = "high"
    elif "404" in error_message or "not found" in error_lower:
        diagnosis["possible_causes"].append("资源未找到：URL 路径错误或资源不存在")
        diagnosis["suggested_fixes"].append("检查 URL 路径和资源是否存在")
        diagnosis["severity"] = "low"
    elif "500" in error_message or "internal server error" in error_lower:
        diagnosis["possible_causes"].append("服务器内部错误：代码异常或配置问题")
        diagnosis["suggested_fixes"].append("查看服务器日志，检查代码逻辑")
        diagnosis["severity"] = "high"
    elif "permission denied" in error_lower or "unauthorized" in error_lower:
        diagnosis["possible_causes"].append("权限不足：认证失败或缺少权限")
        diagnosis["suggested_fixes"].append("检查认证信息和权限配置")
        diagnosis["severity"] = "medium"
    
    # 如果提供了日志路径，尝试从日志中获取更多信息
    if log_path:
        errors = search_errors_in_log.invoke({"log_path": log_path})
        if errors:
            diagnosis["related_logs"] = errors[:5]  # 最近 5 条相关日志
    
    return diagnosis


@tool
def check_service_health(service_url: str) -> Dict[str, Any]:
    """
    检查服务健康状态
    
    Args:
        service_url: 服务 URL（如健康检查端点）
        
    Returns:
        健康状态
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
    分析性能指标
    
    Args:
        log_path: 日志文件路径
        metric_type: 指标类型 (response_time, memory, cpu)
        
    Returns:
        性能分析结果
    """
    try:
        log_lines = read_log_file.invoke({"log_path": log_path, "lines": 1000})
        
        # 简单的性能分析（实际应该使用更专业的工具）
        if metric_type == "response_time":
            response_times = []
            for line in log_lines:
                if "response_time" in line.lower() or "duration" in line.lower():
                    # 尝试提取数字（简化处理）
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
            "message": "未找到相关性能指标"
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def git_blame(file_path: str, line_number: Optional[int] = None) -> Dict[str, Any]:
    """
    查看代码修改历史（Git blame）
    
    Args:
        file_path: 文件路径（相对于 Git 仓库根目录）
        line_number: 可选，指定行号
        
    Returns:
        Git blame 结果
    """
    try:
        import git
        
        repo_path = Config.GIT_REPO_PATH
        repo = git.Repo(repo_path)
        
        if line_number:
            # 查看特定行的 blame
            blame_info = repo.git.blame("-L", f"{line_number},{line_number}", file_path)
        else:
            # 查看整个文件的 blame
            blame_info = repo.git.blame(file_path)
        
        # 解析 blame 信息
        lines = blame_info.split('\n')
        blame_data = []
        
        for line in lines[:20]:  # 限制返回前20行
            if line.strip():
                # 简化解析（实际应该使用更完善的解析逻辑）
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
                        "code": code[:100]  # 截断代码
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
            "error": "GitPython 未安装，请运行: pip install gitpython"
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
    关联日志和代码变更
    
    Args:
        error_message: 错误消息
        log_path: 日志文件路径
        file_path: 可选，相关代码文件路径
        
    Returns:
        关联分析结果
    """
    try:
        correlation = {
            "error_message": error_message,
            "log_analysis": None,
            "code_analysis": None,
            "correlation": None
        }
        
        # 分析日志
        if log_path:
            errors = search_errors_in_log.invoke({"log_path": log_path})
            correlation["log_analysis"] = {
                "errors_found": len(errors),
                "recent_errors": errors[:5]
            }
        
        # 分析代码（如果提供了文件路径）
        if file_path:
            blame_result = git_blame.invoke({"file_path": file_path})
            correlation["code_analysis"] = blame_result
        
        # 关联分析
        # 尝试从错误消息中提取文件名和行号
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
    诊断错误（增强版：使用 Vector DB 检索相似历史错误）
    
    Args:
        error_message: 错误消息
        log_path: 可选，日志文件路径
        
    Returns:
        诊断结果（包含相似历史错误）
    """
    # 先进行基础诊断
    diagnosis = diagnose_error.invoke({
        "error_message": error_message,
        "log_path": log_path
    })
    
    # 从 Vector DB 检索相似的历史 Bug
    try:
        similar_bugs = search_similar_bugs.invoke({
            "error_message": error_message,
            "n_results": 3
        })
        
        if similar_bugs and len(similar_bugs) > 0:
            diagnosis["similar_bugs"] = similar_bugs
            diagnosis["has_historical_reference"] = True
            
            # 如果找到相似的历史 Bug，添加解决建议
            if similar_bugs[0].get("metadata"):
                metadata = similar_bugs[0]["metadata"]
                if metadata.get("solution"):
                    diagnosis["suggested_fixes"].append(f"历史类似问题解决方案: {metadata['solution']}")
    except Exception as e:
        diagnosis["vector_db_error"] = str(e)
    
    return diagnosis


# 工具列表
OPS_TOOLS = [
    read_log_file,
    search_errors_in_log,
    diagnose_error,
    diagnose_error_with_history,  # 新增
    check_service_health,
    analyze_performance_metrics,
    git_blame,  # 新增
    correlate_logs_with_code,  # 新增
]
