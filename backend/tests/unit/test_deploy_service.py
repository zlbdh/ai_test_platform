import asyncio
from pathlib import Path
from unittest.mock import patch

from services.deploy_models import ProjectConfig, RepoConfig
from services.deploy_service import DeployService


class _FakeProc:
    def __init__(self, pid: int, returncode: int):
        self.pid = pid
        self.returncode = returncode

    def poll(self):
        return self.returncode


class _RunningProc:
    def __init__(self, pid: int):
        self.pid = pid

    def poll(self):
        return None


def _make_service(project_dir: Path) -> tuple[DeployService, RepoConfig]:
    service = DeployService.__new__(DeployService)
    repo = RepoConfig(
        id="repo1",
        label="后端",
        repo_url="https://example.com/backend.git",
        local_dir="unused",
        tech_stack="Java 17 + Spring Cloud",
        install_cmd="mvn clean install -DskipTests",
        start_cmd="mvn spring-boot:run",
        port=8080,
    )
    project = ProjectConfig(key="proj1", name="测试项目", repos=[repo])

    service.projects = {project.key: project}
    service.processes = {}
    service.docker_repos = {}
    service.history = []
    service.memory = {}
    service._deploy_event_bus = {}
    service._repo_path = lambda _repo: project_dir
    service._save_history = lambda: None
    service._save_projects = lambda: None
    service._load_env_file = lambda _target: {}
    service._update_memory = lambda *_args, **_kwargs: None
    service._check_port = lambda _port: False
    service._wait_for_port_stability = lambda *_args, **_kwargs: True
    service._verify_repo_http_readiness = lambda *_args, **_kwargs: True
    return service, repo


def test_start_repo_switches_to_compose_when_spring_boot_run_has_no_main_class(tmp_path: Path):
    project_dir = tmp_path / "backend"
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "docker-compose-dev.yml").write_text("services: {}\n", encoding="utf-8")

    service, repo = _make_service(project_dir)
    popen_calls = []

    def fake_popen(cmd, **kwargs):
        popen_calls.append(cmd)
        if len(popen_calls) == 1:
            return _FakeProc(pid=101, returncode=1)
        return _FakeProc(pid=202, returncode=0)

    with patch("services.deploy_service.subprocess.Popen", side_effect=fake_popen), \
         patch("services.deploy_service.time.sleep", return_value=None), \
         patch.object(service, "_parse_start_error", return_value=("Unable to find a suitable main class", False)), \
         patch.object(service, "_derive_compose_start_cmd", return_value="cd docker && docker compose -f docker-compose-dev.yml up -d"), \
         patch.object(service, "_start_microservices", return_value=[{"name": "sample-gateway", "pid": 303, "status": "running"}]):
        record = asyncio.run(service.start_repo("proj1", repo.id))

    assert record.status == "success"
    assert "Docker" in record.message
    assert repo.start_cmd == "cd docker && docker compose -f docker-compose-dev.yml up -d"
    assert popen_calls[0] == "mvn spring-boot:run"
    assert popen_calls[1] == "cd docker && docker compose -f docker-compose-dev.yml up -d"


def test_start_repo_switches_to_compose_when_spring_boot_run_exits_late(tmp_path: Path):
    project_dir = tmp_path / "backend"
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "docker-compose-dev.yml").write_text("services: {}\n", encoding="utf-8")

    service, repo = _make_service(project_dir)
    popen_calls = []

    class _LateExitProc:
        def __init__(self, pid: int, first_running: bool, returncode: int):
            self.pid = pid
            self.returncode = returncode
            self._first_running = first_running
            self._calls = 0

        def poll(self):
            self._calls += 1
            if self._first_running and self._calls <= 3:
                return None
            return self.returncode

    def fake_popen(cmd, **kwargs):
        popen_calls.append(cmd)
        if len(popen_calls) == 1:
            return _LateExitProc(pid=101, first_running=True, returncode=1)
        return _FakeProc(pid=202, returncode=0)

    with patch("services.deploy_service.subprocess.Popen", side_effect=fake_popen), \
         patch("services.deploy_service.time.sleep", return_value=None), \
         patch.object(service, "_parse_start_error", return_value=("Unable to find a suitable main class", False)), \
         patch.object(service, "_derive_compose_start_cmd", return_value="cd docker && docker compose -f docker-compose-dev.yml up -d"), \
         patch.object(service, "_start_microservices", return_value=[{"name": "sample-gateway", "pid": 303, "status": "running"}]):
        record = asyncio.run(service.start_repo("proj1", repo.id))

    assert record.status == "success"
    assert repo.start_cmd == "cd docker && docker compose -f docker-compose-dev.yml up -d"
    assert popen_calls[0] == "mvn spring-boot:run"
    assert popen_calls[1] == "cd docker && docker compose -f docker-compose-dev.yml up -d"


def test_derive_compose_start_cmd_rejects_missing_build_contexts(tmp_path: Path):
    project_dir = tmp_path / "backend"
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "docker-compose.yml").write_text(
        "services:\n  gateway:\n    build:\n      context: ./gateway\n",
        encoding="utf-8",
    )

    service, _ = _make_service(project_dir)
    record = service._add_record("proj1", "repo1", "后端", "start")

    cmd = service._derive_compose_start_cmd(project_dir, record)

    assert cmd == ""
    assert any("构建上下文缺失" in log for log in record.logs)


def test_start_repo_switches_gateway_only_command_to_local_microservices(tmp_path: Path):
    project_dir = tmp_path / "backend"
    gateway_target = project_dir / "sample-gateway" / "target"
    auth_target = project_dir / "sample-auth" / "target"
    gateway_target.mkdir(parents=True)
    auth_target.mkdir(parents=True)
    (gateway_target / "sample-gateway.jar").write_text("", encoding="utf-8")
    (auth_target / "sample-auth.jar").write_text("", encoding="utf-8")

    service, repo = _make_service(project_dir)
    repo.tech_stack = "Java 17 + Spring Cloud + Nacos"
    repo.start_cmd = "java -jar sample-gateway/target/sample-gateway.jar"

    def fake_local_start(_repo, _project_dir, record, reason=""):
        record.logs.append(reason)
        record.status = "success"
        record.message = "启动成功 (Fallback + 2/2 微服务)"
        return record

    with patch.object(service, "_start_microservices_without_docker", side_effect=fake_local_start) as fallback, \
         patch("services.deploy_service.subprocess.Popen") as popen:
        record = asyncio.run(service.start_repo("proj1", repo.id))

    assert record.status == "success"
    assert "2/2 微服务" in record.message
    assert fallback.call_count == 1
    assert popen.call_count == 0


def test_start_repo_switches_gateway_only_spring_boot_run_to_compose(tmp_path: Path):
    project_dir = tmp_path / "backend"
    docker_dir = project_dir / "docker"
    gateway_target = project_dir / "sample-gateway" / "target"
    auth_target = project_dir / "sample-auth" / "target"
    docker_dir.mkdir(parents=True)
    gateway_target.mkdir(parents=True)
    auth_target.mkdir(parents=True)
    (docker_dir / "docker-compose-dev.yml").write_text("services: {}\n", encoding="utf-8")
    (gateway_target / "sample-gateway.jar").write_text("", encoding="utf-8")
    (auth_target / "sample-auth.jar").write_text("", encoding="utf-8")

    service, repo = _make_service(project_dir)
    repo.tech_stack = "Java 17 + Spring Cloud + Nacos"
    repo.start_cmd = "mvn spring-boot:run -pl sample-gateway -Dspring-boot.run.arguments='--server.port=8080'"

    popen_calls = []

    def fake_popen(cmd, **kwargs):
        popen_calls.append(cmd)
        return _FakeProc(pid=202, returncode=0)

    with patch("services.deploy_service.subprocess.Popen", side_effect=fake_popen), \
         patch("services.deploy_service.time.sleep", return_value=None), \
         patch.object(service, "_derive_compose_start_cmd", return_value="cd docker && docker compose -f docker-compose-dev.yml up -d"), \
         patch.object(service, "_start_microservices", return_value=[
             {"name": "sample-gateway", "pid": 303, "status": "running"},
             {"name": "sample-auth", "pid": 304, "status": "running"},
         ]):
        record = asyncio.run(service.start_repo("proj1", repo.id))

    assert record.status == "success"
    assert "Docker + 2/2 微服务" in record.message
    assert repo.start_cmd == "cd docker && docker compose -f docker-compose-dev.yml up -d"
    assert popen_calls == ["cd docker && docker compose -f docker-compose-dev.yml up -d"]


def test_normalize_start_command_adds_strict_port_for_vite(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    repo.label = "前端"
    repo.tech_stack = "Vue 3 + Vite"
    record = service._add_record("proj1", repo.id, repo.label, "start")

    normalized = service._normalize_start_command(repo, "npm run dev -- --host 0.0.0.0", 81, record)

    assert "--port 81" in normalized
    assert "--strictPort" in normalized
    assert any("Vite 启动命令已强制绑定目标端口" in log for log in record.logs)


def test_normalize_start_command_rewrites_privileged_vite_port(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    repo.label = "前端"
    repo.tech_stack = "Vue 3 + Vite"
    record = service._add_record("proj1", repo.id, repo.label, "start")

    normalized = service._normalize_start_command(
        repo,
        "npm run dev -- --host 0.0.0.0 -- --port 80 --strictPort",
        81,
        record,
    )

    assert "--port 81" in normalized
    assert "--port 80" not in normalized
    assert normalized.count("--strictPort") == 1


def test_normalize_start_command_flattens_npm_forwarded_args(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    repo.label = "前端"
    repo.tech_stack = "Vue 3 + Vite"
    record = service._add_record("proj1", repo.id, repo.label, "start")

    normalized = service._normalize_start_command(
        repo,
        "npm run dev -- --host 0.0.0.0 -- --port 80 --strictPort",
        81,
        record,
    )

    assert normalized == "npm run dev -- --host 0.0.0.0 --port 81 --strictPort"


def test_apply_ai_config_rewrites_privileged_frontend_port(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    repo.label = "前端"
    repo.tech_stack = "Vue 3 + Vite"
    repo.start_cmd = "npm run dev -- --host 0.0.0.0 -- --port 80"
    repo.port = 80

    result = service.apply_ai_config(
        "proj1",
        repo.id,
        {
            "tech_stack": "Vue 3 + Vite",
            "start_cmd": "npm run dev -- --host 0.0.0.0 -- --port 80",
            "port": 80,
            "deploy_context": {},
        },
    )

    assert repo.port == 81
    assert result["port"] == 81
    assert "--port 81" in repo.start_cmd
    assert " -- --port" not in repo.start_cmd
    assert "--strictPort" in repo.start_cmd


def test_load_env_file_falls_back_to_root_env_when_docker_env_missing(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    root_env = tmp_path / ".env"
    root_env.write_text("SPRING_PROFILES_ACTIVE=test\nNACOS_GROUP=TEST\n", encoding="utf-8")

    service._load_env_file = DeployService._load_env_file.__get__(service, DeployService)

    env_vars = service._load_env_file(tmp_path)

    assert env_vars["SPRING_PROFILES_ACTIVE"] == "test"
    assert env_vars["NACOS_GROUP"] == "TEST"


def test_write_env_file_merges_existing_values_instead_of_overwriting(tmp_path: Path):
    project_dir = tmp_path / "backend"
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True)
    env_file = docker_dir / ".env"
    env_file.write_text(
        "SPRING_PROFILES_ACTIVE=test\n"
        "NACOS_NAMESPACE=214afc94-6bb6-4704-bfbb-6ae44d646fc9\n"
        "NACOS_GROUP=TEST\n",
        encoding="utf-8",
    )

    service, repo = _make_service(project_dir)
    repo.deploy_context = {
        "env_vars": "NACOS_GROUP=UAT\nJAVA_VERSION=17",
        "server_address": "10.0.0.8",
        "db_connection": "mysql://demo",
    }
    record = service._add_record("proj1", repo.id, repo.label, "full_deploy")

    service._write_env_file(project_dir, repo, record)

    written = env_file.read_text(encoding="utf-8")
    assert "SPRING_PROFILES_ACTIVE=test" in written
    assert "NACOS_NAMESPACE=214afc94-6bb6-4704-bfbb-6ae44d646fc9" in written
    assert "NACOS_GROUP=UAT" in written
    assert "JAVA_VERSION=17" in written
    assert "DEPLOY_SERVER=10.0.0.8" in written
    assert "DATABASE_URL=mysql://demo" in written
    assert any("增量更新环境配置" in log for log in record.logs)


def test_start_repo_rewrites_privileged_frontend_port_before_launch(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    repo.label = "前端"
    repo.tech_stack = "Vue 3 + Vite"
    repo.start_cmd = "npm run dev -- --host 0.0.0.0 -- --port 80 --strictPort"
    repo.port = 80
    service._find_free_port = lambda *_args, **_kwargs: 82
    service._check_port = lambda port: port == 82

    with patch.object(service, "_kill_project_frontend_processes", return_value=0), \
         patch("services.deploy_service.subprocess.Popen", return_value=_RunningProc(321)) as popen, \
         patch("services.deploy_service.time.sleep", return_value=None):
        record = asyncio.run(service.start_repo("proj1", repo.id))

    launched_cmd = popen.call_args.args[0]
    assert record.status == "success"
    assert repo.port == 82
    assert "--port 82" in launched_cmd
    assert "--port 80" not in launched_cmd
    assert any("前端低位端口 80" in log for log in record.logs)


def test_parse_start_error_detects_vite_port_conflict(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    record = service._add_record("proj1", repo.id, repo.label, "start")
    log_file = tmp_path / "vite.log"
    log_file.write_text("Port 81 is in use, trying another one...\n", encoding="utf-8")

    err_detail, is_port_error = service._parse_start_error(log_file, record)

    assert is_port_error is True
    assert "Port 81 is in use" in err_detail


def test_start_repo_cleans_stale_frontend_processes_before_launch(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    repo.label = "前端"
    repo.tech_stack = "Vue 3 + Vite"
    repo.start_cmd = "npx vite --host 0.0.0.0 --port 81"
    repo.port = 81
    service._check_port = lambda _port: True

    with patch.object(service, "_kill_project_frontend_processes", return_value=2) as cleanup, \
         patch("services.deploy_service.subprocess.Popen", return_value=_RunningProc(321)), \
         patch("services.deploy_service.time.sleep", return_value=None):
        record = asyncio.run(service.start_repo("proj1", repo.id))

    assert record.status == "success"
    assert cleanup.call_count == 1


def test_stop_repo_cleans_stale_frontend_processes_when_no_tracked_process(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    repo.label = "前端"
    repo.tech_stack = "Vue 3 + Vite"

    with patch.object(service, "_kill_project_frontend_processes", return_value=3) as cleanup:
        record = asyncio.run(service.stop_repo("proj1", repo.id))

    assert record.status == "success"
    assert record.message == "已清理 3 个残留前端进程"
    assert cleanup.call_count == 1


def test_normalize_compose_command_binds_to_project_compose_file(tmp_path: Path):
    project_dir = tmp_path / "backend"
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "docker-compose-dev.yml").write_text("services: {}\n", encoding="utf-8")

    service, repo = _make_service(project_dir)
    record = service._add_record("proj1", repo.id, repo.label, "start")

    normalized = service._normalize_compose_command(project_dir, "docker compose up -d", record)

    assert normalized == "cd docker && docker compose -f docker-compose-dev.yml up -d"
    assert any("通用 Docker Compose 命令已绑定到项目内 Compose 文件" in log for log in record.logs)


def test_build_java_system_properties_promotes_nacos_env_vars(tmp_path: Path):
    service, _ = _make_service(tmp_path)

    props = service._build_java_system_properties({
        "SPRING_PROFILES_ACTIVE": "test",
        "NACOS_SERVER_ADDR": "192.168.31.92:8848",
        "NACOS_NAMESPACE": "214afc94-6bb6-4704-bfbb-6ae44d646fc9",
        "NACOS_GROUP": "TEST",
        "NACOS_USERNAME": "nacos",
        "NACOS_PASSWORD": "example-org#6789",
    })

    assert "-Dspring.profiles.active=test" in props
    assert "-Dspring.cloud.nacos.discovery.server-addr=192.168.31.92:8848" in props
    assert "-Dspring.cloud.nacos.config.server-addr=192.168.31.92:8848" in props
    assert "-Dspring.cloud.nacos.discovery.group=TEST" in props
    assert "-Dspring.cloud.nacos.config.password=example-org#6789" in props


def test_ai_analyze_repo_returns_effective_env_state_and_saved_context(tmp_path: Path):
    project_dir = tmp_path / "backend"
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / ".env").write_text(
        "SPRING_PROFILES_ACTIVE=test\n"
        "NACOS_SERVER_ADDR=192.168.31.92:8848\n"
        "NACOS_NAMESPACE=214afc94-6bb6-4704-bfbb-6ae44d646fc9\n"
        "NACOS_GROUP=TEST\n",
        encoding="utf-8",
    )

    service, repo = _make_service(project_dir)
    repo.deploy_context = {
        "server_address": "10.0.0.8",
        "db_connection": "",
        "env_vars": "NACOS_GROUP=TEST\nJAVA_VERSION=17",
        "user_notes": "保持测试环境",
    }
    service.memory = {
        repo.id: {
            "effective_env": {"summary": "SPRING_PROFILES_ACTIVE=test | NACOS_GROUP=TEST"},
            "deploy_count": 2,
            "last_success": "2026-03-13T16:10:44",
        }
    }

    captured = {}

    async def fake_analyze_project(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "tech_stack": "Java + Spring Cloud",
            "install_cmd": "mvn clean install -DskipTests",
            "start_cmd": "cd docker && docker compose -f docker-compose-dev.yml up -d",
            "build_cmd": "",
            "port": 8080,
            "env_vars": {"SPRING_PROFILES_ACTIVE": "dev"},
            "notes": "已识别",
            "confidence": 0.88,
            "source": "ai",
        }

    with patch("services.ai_deploy_analyzer.analyze_project", side_effect=fake_analyze_project):
        result = asyncio.run(service.ai_analyze_repo("proj1", repo.id))

    assert "SPRING_PROFILES_ACTIVE=test" in captured["current_env_text"]
    assert "上次生效环境" in captured["memory_hint"]
    assert result["effective_env_vars"]["SPRING_PROFILES_ACTIVE"] == "test"
    assert result["effective_env_source"] == "docker/.env"
    assert result["saved_context"]["env_vars"] == "NACOS_GROUP=TEST\nJAVA_VERSION=17"
    assert result["saved_env_text"] == "NACOS_GROUP=TEST\nJAVA_VERSION=17"
    assert result["env_apply_behavior"].startswith("不填写补充信息时")


def test_ai_analyze_repo_prefers_stable_docker_start_command(tmp_path: Path):
    project_dir = tmp_path / "backend"
    docker_dir = project_dir / "docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "docker-compose-dev.yml").write_text("services: {}\n", encoding="utf-8")
    (docker_dir / ".env").write_text("SPRING_PROFILES_ACTIVE=test\n", encoding="utf-8")

    service, repo = _make_service(project_dir)
    repo.start_cmd = "cd docker && docker compose -f docker-compose-dev.yml up -d"
    service.memory = {
        repo.id: {
            "start_config": {
                "docker_cmd": "cd docker && docker compose -f docker-compose-dev.yml up -d",
                "success_count": 16,
                "total_count": 16,
            },
            "deploy_count": 5,
        }
    }

    async def fake_analyze_project(*_args, **_kwargs):
        return {
            "tech_stack": "Java + Spring Cloud",
            "install_cmd": "mvn clean install -DskipTests",
            "start_cmd": "java -jar sample-gateway.jar",
            "build_cmd": "",
            "port": 8080,
            "env_vars": {"SPRING_PROFILES_ACTIVE": "test"},
            "notes": "AI 识别为多模块启动",
            "confidence": 0.9,
            "source": "ai",
        }

    with patch("services.ai_deploy_analyzer.analyze_project", side_effect=fake_analyze_project):
        result = asyncio.run(service.ai_analyze_repo("proj1", repo.id))

    assert result["start_cmd"] == "cd docker && docker compose -f docker-compose-dev.yml up -d"
    assert result["stability_guard_applied"] is True
    assert "沿用当前验证通过的 Docker 启动命令" in result["notes"]


def test_extract_gateway_port_from_log_text_prefers_gateway_registration():
    log_text = "\n".join([
        "17:20:03 INFO SentinelHealthIndicator - Find sentinel dashboard server list: [Endpoint{protocol=HTTP, host='61.241.172.73, port=8858}]",
        "17:20:05 INFO naming - [REGISTER-SERVICE] namespace registering service sample-gateway with instance Instance{instanceId='null', ip='192.168.31.9', port=9602, weight=1.0}",
    ])

    port = DeployService._extract_gateway_port_from_log_text(log_text)

    assert port == 9602


def test_finalize_microservice_start_switches_to_discovered_gateway_port(tmp_path: Path):
    project_dir = tmp_path / "backend"
    log_dir = project_dir / "docker" / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "sample-gateway.log").write_text(
        "17:14:57 INFO naming - [REGISTER-SERVICE] namespace registering service sample-gateway with instance Instance{instanceId='null', ip='192.168.31.9', port=9602, weight=1.0}\n",
        encoding="utf-8",
    )

    service, repo = _make_service(project_dir)
    record = service._add_record("proj1", repo.id, repo.label, "start")
    saved_ports = []
    memory_updates = []

    def fake_wait_for_port_stability(port, **_kwargs):
        return port == 9602

    service._wait_for_port_stability = fake_wait_for_port_stability
    service._verify_repo_http_readiness = lambda *_args, **_kwargs: True
    service._pid_alive = lambda _pid: True
    service._save_projects = lambda: saved_ports.append(repo.port)
    service._update_memory = lambda repo_id, key, value, _record=None: memory_updates.append((repo_id, key, value))

    result = service._finalize_microservice_start(
        repo,
        record,
        project_dir=project_dir,
        current_cmd="cd docker && docker compose -f docker-compose-dev.yml up -d",
        service_pids=[
            {"name": "sample-gateway", "pid": 101, "status": "running"},
            {"name": "sample-auth", "pid": 102, "status": "running"},
        ],
        current_port=8080,
        docker_pid=100,
    )

    assert result.status == "success"
    assert repo.port == 9602
    assert saved_ports[-1] == 9602
    assert any(item[1] == "start_config" and item[2]["port"] == 9602 for item in memory_updates)
    assert any("改用网关真实运行端口 9602" in log for log in record.logs)


def test_finalize_microservice_start_tracks_only_critical_services(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    record = service._add_record("proj1", repo.id, repo.label, "start")
    captured = {}

    def fake_wait(*_args, **kwargs):
        captured["process_ids"] = kwargs.get("process_ids")
        return True

    service._wait_for_port_stability = fake_wait
    service._pid_alive = lambda _pid: True

    result = service._finalize_microservice_start(
        repo,
        record,
        project_dir=tmp_path,
        current_cmd="cd docker && docker compose -f docker-compose-dev.yml up -d",
        service_pids=[
            {"name": "sample-gateway", "pid": 101, "status": "running"},
            {"name": "sample-auth", "pid": 102, "status": "running"},
            {"name": "sample-modules-system", "pid": 103, "status": "running"},
            {"name": "sample-modules-ai", "pid": 104, "status": "running"},
        ],
        current_port=8080,
    )

    assert result.status == "success"
    assert captured["process_ids"] == [101, 102, 103]


def test_finalize_microservice_start_allows_optional_service_exit(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    record = service._add_record("proj1", repo.id, repo.label, "start")

    service._wait_for_port_stability = lambda *_args, **_kwargs: True
    service._pid_alive = lambda pid: pid != 104

    result = service._finalize_microservice_start(
        repo,
        record,
        project_dir=tmp_path,
        current_cmd="cd docker && docker compose -f docker-compose-dev.yml up -d",
        service_pids=[
            {"name": "sample-gateway", "pid": 101, "status": "running"},
            {"name": "sample-auth", "pid": 102, "status": "running"},
            {"name": "sample-modules-system", "pid": 103, "status": "running"},
            {"name": "sample-modules-ai", "pid": 104, "status": "running"},
        ],
        current_port=8080,
    )

    assert result.status == "success"
    assert any("非关键微服务已退出" in log for log in result.logs)


def test_finalize_microservice_start_fails_when_critical_service_missing(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    record = service._add_record("proj1", repo.id, repo.label, "start")
    wait_called = {"value": False}

    def fake_wait(*_args, **_kwargs):
        wait_called["value"] = True
        return True

    service._wait_for_port_stability = fake_wait

    result = service._finalize_microservice_start(
        repo,
        record,
        project_dir=tmp_path,
        current_cmd="cd docker && docker compose -f docker-compose-dev.yml up -d",
        service_pids=[
            {"name": "sample-gateway", "pid": 101, "status": "running"},
            {"name": "sample-auth", "pid": None, "status": "failed"},
            {"name": "sample-modules-ai", "pid": 104, "status": "running"},
        ],
        current_port=8080,
    )

    assert result.status == "failed"
    assert "关键微服务未启动" in result.message
    assert wait_called["value"] is False


def test_add_project_preserves_deploy_context_and_legacy_token(tmp_path: Path):
    service, existing_repo = _make_service(tmp_path)
    existing_repo.local_dir = "backend"
    service._legacy_token = "legacy-token"

    project = service.add_project(
        "新项目",
        [{
            "label": "后端",
            "repo_url": "https://example.com/backend.git",
            "deploy_context": {"env_vars": "SPRING_PROFILES_ACTIVE=test"},
        }],
    )

    assert project.git_token == "legacy-token"
    assert service._legacy_token == ""
    assert project.repos[0].local_dir == "backend_1"
    assert project.repos[0].deploy_context == {"env_vars": "SPRING_PROFILES_ACTIVE=test"}


def test_update_project_preserves_repo_deploy_context(tmp_path: Path):
    service, repo = _make_service(tmp_path)

    updated = service.update_project(
        "proj1",
        repos=[{
            "id": repo.id,
            "label": repo.label,
            "repo_url": repo.repo_url,
            "local_dir": "backend-service",
            "deploy_context": {"db_connection": "mysql://demo", "env_vars": "A=1"},
        }],
    )

    assert updated.repos[0].local_dir == "backend-service"
    assert updated.repos[0].deploy_context == {"db_connection": "mysql://demo", "env_vars": "A=1"}


def test_get_logs_returns_empty_when_lines_is_non_positive(tmp_path: Path):
    service, repo = _make_service(tmp_path)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / f"{repo.id}_output.log").write_text("a\nb\nc\n", encoding="utf-8")

    with patch("services.deploy_service.DEPLOY_DIR", log_dir):
        assert service.get_logs(repo.id, 0) == []
        assert service.get_logs(repo.id, -5) == []
