"""Deployment labels support English and existing saved configurations."""

from pathlib import Path
from unittest.mock import patch

import pytest

from services.deploy_models import RepoConfig
from services.deploy_service import DeployService


@pytest.mark.parametrize("label", ["Frontend", "frontend", "FRONTEND", "前端"])
def test_frontend_label_recognition_preserves_existing_configurations(label):
    repo = RepoConfig(id="test", label=label, repo_url="https://example.com/repo.git", local_dir="unused")
    assert DeployService._is_frontend_repo(repo) is True
    repo.label = "Backend"
    assert DeployService._is_frontend_repo(repo) is False


@pytest.mark.parametrize("stack", ["Java microservices", "Java 微服务"])
def test_microservice_label_recognition_keeps_gateway_and_jar_requirements(stack, tmp_path):
    service = DeployService.__new__(DeployService)
    repo = RepoConfig(id="test", label="Backend", repo_url="https://example.com/repo.git", local_dir="unused", tech_stack=stack)
    jars = [Path("gateway.jar"), Path("auth.jar")]
    with patch.object(service, "_list_local_microservice_jars", return_value=jars), \
         patch.object(service, "_looks_like_gateway_only_start", return_value=True):
        assert service._should_start_local_microservices(repo, tmp_path, "gateway-command") is True
    with patch.object(service, "_list_local_microservice_jars", return_value=jars[:1]), \
         patch.object(service, "_looks_like_gateway_only_start", return_value=True):
        assert service._should_start_local_microservices(repo, tmp_path, "gateway-command") is False
    with patch.object(service, "_list_local_microservice_jars", return_value=jars), \
         patch.object(service, "_looks_like_gateway_only_start", return_value=False):
        assert service._should_start_local_microservices(repo, tmp_path, "all-services-command") is False
