"""Unit tests for GitManager."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from kubeman.git import GitManager
from kubeman.config import Config


class TestGitManager:
    """Test cases for GitManager class."""

    def test_fetch_commit_hash(self, monkeypatch):
        """Test fetching commit hash from environment."""
        git_manager = GitManager()

        monkeypatch.setenv("STABLE_GIT_COMMIT", "abc123")
        result = git_manager.fetch_commit_hash()
        assert result == "abc123"

    def test_fetch_branch_name(self, monkeypatch):
        """Test fetching branch name from environment."""
        git_manager = GitManager()

        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")
        result = git_manager.fetch_branch_name()
        assert result == "main"

    def test_fetch_manifest_dir(self, monkeypatch):
        """Test fetching manifest directory from environment."""
        git_manager = GitManager()

        monkeypatch.setenv("RENDERED_MANIFEST_DIR", "/path/to/manifests")
        result = git_manager.fetch_manifest_dir()
        assert result == Path("/path/to/manifests")

    def test_push_manifests_with_repo_url(self, monkeypatch, tmp_path):
        """Test pushing manifests with provided repo URL."""
        git_manager = GitManager()

        # Set up environment variables
        monkeypatch.setenv("STABLE_GIT_COMMIT", "abc123")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")
        monkeypatch.setenv("RENDERED_MANIFEST_DIR", str(tmp_path / "manifests"))

        # Create manifests directory
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()
        (manifests_dir / "test.yaml").write_text("test content")

        mock_executor = MagicMock()
        # Mock all git commands in sequence
        # 1. git clone
        # 2. git ls-remote (with stdout capture)
        # 3. git fetch
        # 4. git checkout
        # 5. git add
        # 6. git commit
        # 7. git push
        mock_executor.run_silent.return_value = Mock(
            stdout="refs/heads/main", stderr="", returncode=0
        )
        mock_executor.run.return_value = Mock(returncode=0)

        git_manager.executor = mock_executor

        git_manager.push_manifests(repo_url="https://github.com/test/repo.git")

        # Verify git commands were called
        assert mock_executor.run.call_count >= 6  # clone, fetch, checkout, add, commit, push
        assert mock_executor.run_silent.call_count == 1  # ls-remote

    def test_push_manifests_with_env_repo_url(self, monkeypatch, tmp_path):
        """Test pushing manifests with repo URL from environment."""
        git_manager = GitManager()

        # Set up environment variables
        monkeypatch.setenv("STABLE_GIT_COMMIT", "abc123")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")
        monkeypatch.setenv("RENDERED_MANIFEST_DIR", str(tmp_path / "manifests"))
        monkeypatch.setenv("MANIFEST_REPO_URL", "https://github.com/test/repo.git")

        # Create manifests directory
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()

        mock_executor = MagicMock()
        mock_executor.run_silent.return_value = Mock(
            stdout="refs/heads/main", stderr="", returncode=0
        )
        mock_executor.run.return_value = Mock(returncode=0)

        git_manager.executor = mock_executor

        git_manager.push_manifests()

        assert mock_executor.run.call_count >= 6

    def test_push_manifests_no_repo_url(self, monkeypatch):
        """Test pushing manifests without repo URL raises error."""
        git_manager = GitManager()

        monkeypatch.delenv("MANIFEST_REPO_URL", raising=False)
        with pytest.raises(ValueError, match="repo_url must be provided"):
            git_manager.push_manifests()

    def test_push_manifests_new_branch(self, monkeypatch, tmp_path):
        """Test pushing manifests to a new branch."""
        git_manager = GitManager()

        # Set up environment variables
        monkeypatch.setenv("STABLE_GIT_COMMIT", "abc123")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "new-branch")
        monkeypatch.setenv("RENDERED_MANIFEST_DIR", str(tmp_path / "manifests"))

        # Create manifests directory
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()

        mock_executor = MagicMock()
        # Mock all git commands in sequence for new branch
        # 1. git clone
        # 2. git ls-remote (no branch exists)
        # 3. git fetch origin main
        # 4. git checkout origin/main -b new-branch
        # 5. git add
        # 6. git commit
        # 7. git push
        mock_executor.run_silent.return_value = Mock(stdout="", stderr="", returncode=0)
        mock_executor.run.return_value = Mock(returncode=0)

        git_manager.executor = mock_executor

        git_manager.push_manifests(repo_url="https://github.com/test/repo.git")

        # Verify branch creation logic was called
        calls = [str(call) for call in mock_executor.run.call_args_list]
        assert any("origin/main" in str(call) for call in calls)
        assert mock_executor.run.call_count >= 6
