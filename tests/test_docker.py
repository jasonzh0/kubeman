"""Unit tests for DockerManager."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from kubeman.docker import DockerManager


class TestDockerManager:
    """Test cases for DockerManager class."""

    def test_init_with_project_id(self, monkeypatch):
        """Test initialization with project_id parameter."""
        monkeypatch.delenv("DOCKER_PROJECT_ID", raising=False)
        manager = DockerManager(project_id="test-project")
        assert manager.project_id == "test-project"

    def test_init_with_env_project_id(self, monkeypatch):
        """Test initialization with project_id from environment."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "env-project")
        manager = DockerManager()
        assert manager.project_id == "env-project"

    def test_init_no_project_id(self, monkeypatch):
        """Test that initialization without project_id is allowed (only required for pushing)."""
        monkeypatch.delenv("DOCKER_PROJECT_ID", raising=False)
        manager = DockerManager()
        assert manager.project_id is None
        assert manager.registry == ""

    def test_init_registry_default(self, monkeypatch):
        """Test default registry construction."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        monkeypatch.setenv("DOCKER_REPOSITORY_NAME", "my-repo")
        monkeypatch.setenv("DOCKER_REGION", "us-west1")
        manager = DockerManager()
        assert manager.registry == "us-west1-docker.pkg.dev/test-project/my-repo"

    def test_init_registry_custom(self, monkeypatch):
        """Test initialization with custom registry."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager(registry="custom.registry.com")
        assert manager.registry == "custom.registry.com"

    def test_init_registry_default_region(self, monkeypatch):
        """Test default region when not set."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        monkeypatch.delenv("DOCKER_REGION", raising=False)
        manager = DockerManager()
        assert "us-central1" in manager.registry

    def test_init_repository_name_default(self, monkeypatch):
        """Test default repository name when not set."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        monkeypatch.delenv("DOCKER_REPOSITORY_NAME", raising=False)
        manager = DockerManager()
        assert "default" in manager.registry

    def test_build_image(self, monkeypatch):
        """Test building a Docker image."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_image("component", "/path/to/context", "v1.0.0")

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 1  # build

    def test_build_image_default_tag(self, monkeypatch):
        """Test building image with default 'latest' tag."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_image("component", "/path/to/context")

        assert image_name.endswith(":latest")
        assert mock_executor.run.call_count == 1

    def test_build_image_custom_dockerfile(self, monkeypatch):
        """Test building image with custom Dockerfile name."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_image(
            "component", "/path/to/context", tag="v1.0.0", dockerfile="Dockerfile.custom"
        )

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 1

        build_call = mock_executor.run.call_args_list[0]
        cmd = build_call[0][0]
        assert "-f" in cmd
        dockerfile_index = cmd.index("-f")
        assert cmd[dockerfile_index + 1] == "/path/to/context/Dockerfile.custom"

    def test_push_image(self, monkeypatch):
        """Test pushing a Docker image."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.push_image("component", "v1.0.0")

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 1  # push

    def test_push_image_default_tag(self, monkeypatch):
        """Test pushing image with default 'latest' tag."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.push_image("component")

        assert image_name.endswith(":latest")

    def test_push_image_not_authenticated(self, monkeypatch):
        """Test pushing image when push fails raises error."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        import subprocess

        mock_executor.run.side_effect = subprocess.CalledProcessError(
            1, ["docker", "push", "test"], stderr="denied: access denied"
        )
        manager.executor = mock_executor

        with pytest.raises(subprocess.CalledProcessError):
            manager.push_image("component")

    def test_push_image_no_project_id(self, monkeypatch):
        """Test that pushing without project_id raises error."""
        monkeypatch.delenv("DOCKER_PROJECT_ID", raising=False)
        manager = DockerManager()

        with pytest.raises(
            ValueError, match="Required environment variable DOCKER_PROJECT_ID is not set"
        ):
            manager.push_image("component")

    def test_build_and_push(self, monkeypatch):
        """Test building and pushing an image."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_and_push("component", "/path/to/context", "v1.0.0")

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 2  # build + push

    def test_build_and_push_custom_dockerfile(self, monkeypatch):
        """Test building and pushing with custom Dockerfile."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_and_push(
            "component", "/path/to/context", "v1.0.0", dockerfile="Dockerfile.custom"
        )

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 2

        build_call = mock_executor.run.call_args_list[0]
        cmd = build_call[0][0]
        assert "-f" in cmd
        dockerfile_index = cmd.index("-f")
        assert cmd[dockerfile_index + 1] == "/path/to/context/Dockerfile.custom"
