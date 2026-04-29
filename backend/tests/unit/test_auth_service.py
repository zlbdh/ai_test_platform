"""
AuthenticationService 单元测试
覆盖: 枚举/数据类, 创建用户, 认证(密码/API Key/Token), 权限检查,
      项目管理, 审计日志, 登出, 单例
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from services.auth_service import (
    UserRole, Permission, ROLE_PERMISSIONS,
    User, Project, Session, AuditLog,
    AuthenticationService
)


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
class TestUserRole:
    def test_values(self):
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.DEVELOPER.value == "developer"
        assert UserRole.TESTER.value == "tester"
        assert UserRole.VIEWER.value == "viewer"


class TestPermission:
    def test_values(self):
        assert Permission.CREATE_TEST.value == "create_test"
        assert Permission.ADMIN.value == "admin"


class TestRolePermissions:
    def test_admin_has_all(self):
        assert set(Permission) == set(ROLE_PERMISSIONS[UserRole.ADMIN])

    def test_viewer_limited(self):
        assert ROLE_PERMISSIONS[UserRole.VIEWER] == [Permission.VIEW_RESULTS]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def auth(tmp_path):
    return AuthenticationService(storage_path=str(tmp_path / "auth"))


# ---------------------------------------------------------------------------
# 用户管理
# ---------------------------------------------------------------------------
class TestUserManagement:
    def test_default_admin_created(self, auth):
        """初始化时应自动创建默认管理员"""
        admin = [u for u in auth.users.values() if u.role == UserRole.ADMIN]
        assert len(admin) >= 1
        assert admin[0].username == "admin"

    def test_create_user(self, auth):
        user = auth.create_user("alice", "alice@test.com", "pass123")
        assert user.username == "alice"
        assert user.role == UserRole.TESTER  # 默认角色
        assert user.api_key is not None
        assert user.api_key.startswith("atp_")
        assert user.is_active is True

    def test_create_user_with_role(self, auth):
        user = auth.create_user("dev", "dev@test.com", "pass", role=UserRole.DEVELOPER)
        assert user.role == UserRole.DEVELOPER


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------
class TestAuthentication:
    def test_login_success(self, auth):
        auth.create_user("bob", "bob@test.com", "secret")
        session = auth.authenticate("bob", "secret")
        assert session is not None
        assert session.token is not None

    def test_login_wrong_password(self, auth):
        auth.create_user("bob", "bob@test.com", "secret")
        session = auth.authenticate("bob", "wrong")
        assert session is None

    def test_login_nonexistent_user(self, auth):
        session = auth.authenticate("nobody", "pass")
        assert session is None

    def test_login_inactive_user(self, auth):
        user = auth.create_user("inactive", "x@x.com", "pass")
        user.is_active = False
        session = auth.authenticate("inactive", "pass")
        assert session is None

    def test_api_key_auth(self, auth):
        user = auth.create_user("api_user", "api@test.com", "pass")
        found = auth.authenticate_api_key(user.api_key)
        assert found is not None
        assert found.username == "api_user"

    def test_api_key_not_found(self, auth):
        assert auth.authenticate_api_key("nonexistent_key") is None

    def test_validate_token(self, auth):
        auth.create_user("user", "u@t.com", "pass")
        session = auth.authenticate("user", "pass")
        user = auth.validate_token(session.token)
        assert user is not None
        assert user.username == "user"

    def test_validate_token_persists_across_service_restart(self, tmp_path):
        storage = tmp_path / "auth_session_persist"
        auth = AuthenticationService(storage_path=str(storage))
        auth.create_user("persist_user", "persist@test.com", "pass")
        session = auth.authenticate("persist_user", "pass")

        reloaded = AuthenticationService(storage_path=str(storage))
        user = reloaded.validate_token(session.token)

        assert user is not None
        assert user.username == "persist_user"

    def test_validate_expired_token(self, auth):
        auth.create_user("user", "u@t.com", "pass")
        session = auth.authenticate("user", "pass")
        session.expires_at = (datetime.now() - timedelta(hours=1)).isoformat()
        assert auth.validate_token(session.token) is None

    def test_expired_token_removed_after_restart(self, tmp_path):
        storage = tmp_path / "auth_session_expired"
        auth = AuthenticationService(storage_path=str(storage))
        auth.create_user("expired_user", "expired@test.com", "pass")
        session = auth.authenticate("expired_user", "pass")
        session.expires_at = (datetime.now() - timedelta(hours=1)).isoformat()
        auth._persist_session(session)

        reloaded = AuthenticationService(storage_path=str(storage))

        assert reloaded.validate_token(session.token) is None
        assert session.token not in reloaded.sessions

    def test_validate_invalid_token(self, auth):
        assert auth.validate_token("invalid") is None


# ---------------------------------------------------------------------------
# 权限
# ---------------------------------------------------------------------------
class TestPermissions:
    def test_admin_has_all_permissions(self, auth):
        admin = [u for u in auth.users.values() if u.role == UserRole.ADMIN][0]
        assert auth.check_permission(admin, Permission.MANAGE_USERS) is True

    def test_viewer_no_create(self, auth):
        user = auth.create_user("v", "v@t.com", "p", role=UserRole.VIEWER)
        assert auth.check_permission(user, Permission.CREATE_TEST) is False

    def test_viewer_can_view(self, auth):
        user = auth.create_user("v", "v@t.com", "p", role=UserRole.VIEWER)
        assert auth.check_permission(user, Permission.VIEW_RESULTS) is True


# ---------------------------------------------------------------------------
# 项目管理
# ---------------------------------------------------------------------------
class TestProjectManagement:
    def test_create_project(self, auth):
        admin = [u for u in auth.users.values() if u.role == UserRole.ADMIN][0]
        project = auth.create_project("TestProj", "desc", admin.user_id)
        assert project.name == "TestProj"
        assert admin.user_id in project.member_ids
        assert project.project_id in admin.project_ids

    def test_add_member(self, auth):
        admin = [u for u in auth.users.values() if u.role == UserRole.ADMIN][0]
        user = auth.create_user("member", "m@t.com", "p")
        project = auth.create_project("P", "d", admin.user_id)
        result = auth.add_project_member(project.project_id, user.user_id, admin.user_id)
        assert result is True
        assert user.user_id in project.member_ids

    def test_add_member_invalid(self, auth):
        assert auth.add_project_member("none", "none", "none") is False

    def test_check_access_admin(self, auth):
        admin = [u for u in auth.users.values() if u.role == UserRole.ADMIN][0]
        assert auth.check_project_access(admin, "any_project") is True

    def test_check_access_member(self, auth):
        admin = [u for u in auth.users.values() if u.role == UserRole.ADMIN][0]
        user = auth.create_user("user", "u@t.com", "p")
        project = auth.create_project("P", "d", admin.user_id)
        auth.add_project_member(project.project_id, user.user_id, admin.user_id)
        assert auth.check_project_access(user, project.project_id) is True

    def test_check_access_denied(self, auth):
        user = auth.create_user("user", "u@t.com", "p")
        assert auth.check_project_access(user, "not_my_proj") is False


# ---------------------------------------------------------------------------
# 审计日志
# ---------------------------------------------------------------------------
class TestAuditLogs:
    def test_logs_created(self, auth):
        """创建用户时应产生审计日志"""
        auth.create_user("x", "x@t.com", "p")
        logs = auth.get_audit_logs()
        actions = [l.action for l in logs]
        assert "create_user" in actions

    def test_filter_by_action(self, auth):
        auth.create_user("a", "a@t.com", "p")
        auth.create_user("b", "b@t.com", "p")
        logs = auth.get_audit_logs(action="create_user")
        assert all(l.action == "create_user" for l in logs)

    def test_limit(self, auth):
        for i in range(5):
            auth.create_user(f"u{i}", f"u{i}@t.com", "p")
        logs = auth.get_audit_logs(limit=2)
        assert len(logs) <= 2

    def test_logs_persist_across_service_restart(self, tmp_path):
        storage = tmp_path / "auth_persist"
        auth = AuthenticationService(storage_path=str(storage))
        created = auth.create_user("persisted", "persisted@test.com", "p")

        reloaded = AuthenticationService(storage_path=str(storage))
        logs = reloaded.get_audit_logs(action="create_user", limit=20)

        assert any(
            log.resource_id == created.user_id and log.details.get("username") == "persisted"
            for log in logs
        )

    def test_filter_by_user_id_reads_from_persistent_storage(self, tmp_path):
        storage = tmp_path / "auth_filter"
        auth = AuthenticationService(storage_path=str(storage))
        auth.create_user("bob", "bob@test.com", "secret")
        session = auth.authenticate("bob", "secret")

        reloaded = AuthenticationService(storage_path=str(storage))
        logs = reloaded.get_audit_logs(user_id=session.user_id, action="login", limit=10)

        assert len(logs) == 1
        assert logs[0].resource_type == "session"

    def test_filter_by_action_prefix(self, auth):
        auth.record_audit_event("deploy_repo_clone", "deploy_repo", "repo1", {"project_key": "proj1"}, user_id="ops")
        auth.record_audit_event("deploy_repo_start", "deploy_repo", "repo1", {"project_key": "proj1"}, user_id="ops")
        auth.record_audit_event("create_user", "user", "user1", {"username": "demo"}, user_id="system")

        logs = auth.get_audit_logs(action_prefix="deploy_", limit=10)

        assert len(logs) == 2
        assert all(log.action.startswith("deploy_") for log in logs)

    def test_filter_by_resource_type(self, auth):
        auth.record_audit_event("deploy_repo_clone", "deploy_repo", "repo1", {"project_key": "proj1"}, user_id="ops")
        auth.record_audit_event("deploy_job_cancel", "deploy_job", "job1", {"project_key": "proj1"}, user_id="ops")

        logs = auth.get_audit_logs(resource_type="deploy_job", limit=10)

        assert len(logs) == 1
        assert logs[0].action == "deploy_job_cancel"


# ---------------------------------------------------------------------------
# 登出
# ---------------------------------------------------------------------------
class TestLogout:
    def test_logout(self, auth):
        auth.create_user("user", "u@t.com", "pass")
        session = auth.authenticate("user", "pass")
        auth.logout(session.token)
        assert auth.validate_token(session.token) is None

    def test_logout_invalid_token(self, auth):
        auth.logout("bogus")  # 不应崩溃


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton(self):
        import services.auth_service as mod
        mod._auth_service = None
        s1 = mod.get_auth_service()
        s2 = mod.get_auth_service()
        assert s1 is s2
        mod._auth_service = None
