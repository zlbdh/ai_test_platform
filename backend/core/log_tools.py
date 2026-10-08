import os

# Define the absolute path to the server log
# Path resolution: current file (core/log_tools.py) → two levels up (root) → server.log
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server.log")

def read_server_logs(lines: int = 30) -> str:
    """
    Read the last N lines of the server log.
    """
    if lines <= 0:
        return ""

    if not os.path.exists(LOG_PATH):
        return f"Log file not found at: {LOG_PATH}"

    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors='replace') as f:
            # readlines() is efficient enough for small development logs.
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Failed to read logs: {str(e)}"
