from core.session_manager import session_manager, SessionManager

class SharedBrowserState:
    """
    过渡期兼容类：代理到 DEFAULT_SESSION_ID
    即将废弃，请在各处代码显式使用 session_manager.get_session(session_id)
    """
    
    @classmethod
    def _default(cls):
        return session_manager.get_session(SessionManager.DEFAULT_SESSION_ID)

    @classmethod
    def set_status(cls, status, task=""):
        cls._default().set_status(status, task)

    @classmethod
    def append_log(cls, log_entry: dict):
        cls._default().append_log(log_entry)

    @classmethod
    def get_logs(cls):
        return cls._default().get_logs()

    @classmethod
    def clear_logs(cls):
        cls._default().clear_logs()

    @classmethod
    def get_status(cls):
        return cls._default().get_status()

    @classmethod
    def set_signal(cls, signal, reason=None):
        cls._default().set_signal(signal, reason)

    @classmethod
    def set_intervention_screenshot(cls, screenshot):
        cls._default().set_intervention_screenshot(screenshot)

    @classmethod
    def get_intervention_screenshot(cls):
        return cls._default().get_intervention_screenshot()

    @classmethod
    def get_signal(cls):
        return cls._default().get_signal()

    @classmethod
    def get_pause_reason(cls):
        return cls._default().get_pause_reason()

    @classmethod
    def set_page_state(cls, state: dict):
        cls._default().set_page_state(state)

    @classmethod
    def get_page_state(cls) -> dict:
        return cls._default().get_page_state()

    @classmethod
    def set_context(cls, key, value):
        cls._default().set_context(key, value)

    @classmethod
    def get_context(cls, key=None):
        return cls._default().get_context(key)

    @classmethod
    def clear_context(cls):
        cls._default().clear_context()

    @classmethod
    def set_page(cls, p, context_id=None):
        cls._default().set_page(p, context_id)

    @classmethod
    def clear(cls, context_id=None):
        cls._default().clear(context_id)

    @classmethod
    def get_page(cls):
        return cls._default().get_page()

    @classmethod
    def set_frame(cls, frame_bytes: bytes):
        cls._default().set_frame(frame_bytes)

    @classmethod
    def get_frame(cls) -> bytes:
        return cls._default().get_frame()

    # 兼容直接属性访问 (部分测试代码可能使用了直接访问如 agent_status)
    @property
    def agent_status(self):
        return self._default().agent_status
        
    @property
    def current_task(self):
        return self._default().current_task

    @property
    def execution_signal(self):
        return self._default().execution_signal
        
    @property
    def page(self):
        return self._default().page
