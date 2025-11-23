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
        """Test that initialization without project_id raises error."""
        monkeypatch.delenv("DOCKER_PROJECT_ID", raising=False)
        with pytest.raises(
            ValueError, match="Required environment variable DOCKER_PROJECT_ID is not set"
        ):
            DockerManager()

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
        assert mock_executor.run.call_count == 2  # auth + build

    def test_build_image_default_tag(self, monkeypatch):
        """Test building image with default 'latest' tag."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        image_name = manager.build_image("component", "/path/to/context")

        assert image_name.endswith(":latest")
        assert mock_executor.run.call_count == 2

    def test_push_image(self, monkeypatch):
        """Test pushing a Docker image."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        # Mock auth check (success)
        mock_executor.run.side_effect = [
            Mock(returncode=0, stdout="token"),  # print-access-token
            Mock(returncode=0),  # configure-docker
            Mock(returncode=0),  # push
        ]
        manager.executor = mock_executor

        image_name = manager.push_image("component", "v1.0.0")

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 3  # auth check + configure + push

    def test_push_image_default_tag(self, monkeypatch):
        """Test pushing image with default 'latest' tag."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.side_effect = [
            Mock(returncode=0, stdout="token"),  # print-access-token
            Mock(returncode=0),  # configure-docker
            Mock(returncode=0),  # push
        ]
        manager.executor = mock_executor

        image_name = manager.push_image("component")

        assert image_name.endswith(":latest")

    def test_push_image_not_authenticated(self, monkeypatch):
        """Test pushing image when not authenticated raises error."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        # Mock auth check (failure)
        # First call is _ensure_gcloud_auth (configure-docker)
        # Second call is _ensure_gcloud_login (print-access-token) which fails
        mock_executor.run.side_effect = [
            Mock(returncode=0),  # configure-docker succeeds
            Exception("Not authenticated"),  # print-access-token fails
        ]
        manager.executor = mock_executor

        with patch("builtins.print"):
            with pytest.raises(ValueError, match="Cloud provider authentication required"):
                manager.push_image("component")

    def test_build_and_push(self, monkeypatch):
        """Test building and pushing an image."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.side_effect = [
            Mock(returncode=0),  # configure-docker (build)
            Mock(returncode=0),  # build
            Mock(returncode=0, stdout="token"),  # print-access-token
            Mock(returncode=0),  # configure-docker (push)
            Mock(returncode=0),  # push
        ]
        manager.executor = mock_executor

        image_name = manager.build_and_push("component", "/path/to/context", "v1.0.0")

        assert image_name == f"{manager.registry}/component:v1.0.0"
        assert mock_executor.run.call_count == 5

    def test_ensure_gcloud_auth(self, monkeypatch):
        """Test container registry authentication configuration."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0)
        manager.executor = mock_executor

        manager._ensure_gcloud_auth()

        mock_executor.run.assert_called_once()
        call_args = mock_executor.run.call_args[0][0]
        assert "gcloud" in call_args
        assert "auth" in call_args
        assert "configure-docker" in call_args
        # Registry should be in the command arguments
        call_args_str = " ".join(call_args)
        assert manager.registry in call_args_str

    def test_ensure_gcloud_login_success(self, monkeypatch):
        """Test cloud provider login check when authenticated."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.return_value = Mock(returncode=0, stdout="token")
        manager.executor = mock_executor

        # Should not raise
        manager._ensure_gcloud_login()

    def test_ensure_gcloud_login_failure(self, monkeypatch):
        """Test cloud provider login check when not authenticated."""
        monkeypatch.setenv("DOCKER_PROJECT_ID", "test-project")
        manager = DockerManager()

        mock_executor = MagicMock()
        mock_executor.run.side_effect = Exception("Not authenticated")
        manager.executor = mock_executor

        with patch("builtins.print"):
            with pytest.raises(ValueError, match="Cloud provider authentication required"):
                manager._ensure_gcloud_login()
