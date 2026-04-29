import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def get_data_dir():
    # Use path relative to this file's parent (core) -> parent (root) -> data
    # core/history_manager.py -> core/ -> root/ -> data
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    return os.path.join(root_dir, "data")

def get_history_file():
    return os.path.join(get_data_dir(), "history.json")

def ensure_data_dir():
    os.makedirs(get_data_dir(), exist_ok=True)

def load_history() -> List[Dict[str, Any]]:
    """从文件加载执行历史"""
    history_file = get_history_file()
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                logger.error("历史记录文件格式无效: 期望列表")
                return []
        except Exception as e:
            logger.error(f"加载历史记录失败: {e}")
            return []
    return []

def save_history(history: List[Dict[str, Any]]):
    """保存执行历史到文件"""
    ensure_data_dir()
    history_file = get_history_file()
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存历史记录失败: {e}")
