"""Unit tests for DockerManager."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from kubeman.docker import DockerManager


class TestDockerManager:
    """Test cases for DockerManager class."""

    def test_init_with_registry(self, monkeypatch):
        """Test initialization with registry parameter."""
        monkeypatch.delenv("DOCKER_REGISTRY", raising=False)
        manager = DockerManager(registry="us-central1-docker.pkg.dev/test-project/my-repo")
        assert manager.registry == "us-central1-docker.pkg.dev/test-project/my-repo"

    def test_init_with_env_registry(self, monkeypatch):
        """Test initialization with registry from environment."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/env-project/my-repo")
        manager = DockerManager()
        assert manager.registry == "us-central1-docker.pkg.dev/env-project/my-repo"

    def test_init_no_registry(self, monkeypatch):
        """Test that initialization without registry is allowed (only required for pushing)."""
        monkeypatch.delenv("DOCKER_REGISTRY", raising=False)
        manager = DockerManager()
        assert manager.registry == ""

    def test_init_registry_parameter_overrides_env(self, monkeypatch):
        """Test that registry parameter overrides environment variable."""
        monkeypatch.setenv("DOCKER_REGISTRY", "env-registry.com")
        manager = DockerManager(registry="custom.registry.com")
        assert manager.registry == "custom.registry.com"

    def test_build_image(self, monkeypatch):
        """Test building a Docker image."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/test-project/my-repo")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_image("component", "/path/to/context", "v1.0.0")

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 1  # build

    def test_build_image_default_tag(self, monkeypatch):
        """Test building image with default 'latest' tag."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/test-project/my-repo")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_image("component", "/path/to/context")

        assert image_name.endswith(":latest")
        assert mock_executor.run.call_count == 1

    def test_build_image_custom_dockerfile(self, monkeypatch):
        """Test building image with custom Dockerfile name."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/test-project/my-repo")
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

    def test_build_image_no_registry(self, monkeypatch):
        """Test building image without registry uses local image name."""
        monkeypatch.delenv("DOCKER_REGISTRY", raising=False)
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_image("component", "/path/to/context", "v1.0.0")

        assert image_name == "component:v1.0.0"
        assert mock_executor.run.call_count == 1

    def test_push_image(self, monkeypatch):
        """Test pushing a Docker image."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/test-project/my-repo")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.push_image("component", "v1.0.0")

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 1  # push

    def test_push_image_default_tag(self, monkeypatch):
        """Test pushing image with default 'latest' tag."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/test-project/my-repo")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.push_image("component")

        assert image_name.endswith(":latest")

    def test_push_image_not_authenticated(self, monkeypatch):
        """Test pushing image when push fails raises error."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/test-project/my-repo")
        manager = DockerManager()

        mock_executor = MagicMock()
        import subprocess

        mock_executor.run.side_effect = subprocess.CalledProcessError(
            1, ["docker", "push", "test"], stderr="denied: access denied"
        )
        manager.executor = mock_executor

        with pytest.raises(subprocess.CalledProcessError):
            manager.push_image("component")

    def test_push_image_no_registry(self, monkeypatch):
        """Test that pushing without registry raises error."""
        monkeypatch.delenv("DOCKER_REGISTRY", raising=False)
        manager = DockerManager()

        with pytest.raises(ValueError, match="Docker registry is not configured"):
            manager.push_image("component")

    def test_build_and_push(self, monkeypatch):
        """Test building and pushing an image."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/test-project/my-repo")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_and_push("component", "/path/to/context", "v1.0.0")

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 2  # build + push

    def test_build_and_push_custom_dockerfile(self, monkeypatch):
        """Test building and pushing with custom Dockerfile."""
        monkeypatch.setenv("DOCKER_REGISTRY", "us-central1-docker.pkg.dev/test-project/my-repo")
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
