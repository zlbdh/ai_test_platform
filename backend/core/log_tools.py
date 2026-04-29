import os

# 定义服务端日志文件的绝对路径
# 路径逻辑：当前文件 (core/log_tools.py) -> 上二级目录 (root) -> server.log
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server.log")

def read_server_logs(lines: int = 30) -> str:
    """
    读取服务端日志的最后 N 行。
    """
    if lines <= 0:
        return ""

    if not os.path.exists(LOG_PATH):
        return f"Log file not found at: {LOG_PATH}"
    
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors='replace') as f:
            # 对于小型的开发日志，readlines() 足够高效。
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Failed to read logs: {str(e)}"
