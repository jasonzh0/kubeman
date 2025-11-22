"""Unit tests for GitManager."""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from kubeman.git import GitManager


class TestGitManager:
    """Test cases for GitManager class."""

    def test_singleton_pattern(self):
        """Test that GitManager follows singleton pattern."""
        # Clear any existing instance
        GitManager._instance = None
        GitManager._commit_hash = None
        GitManager._branch_name = None

        instance1 = GitManager()
        instance2 = GitManager()

        assert instance1 is instance2
        assert id(instance1) == id(instance2)

    def test_read_from_env_success(self, monkeypatch):
        """Test reading environment variable successfully."""
        GitManager._instance = None
        git_manager = GitManager()

        monkeypatch.setenv("TEST_VAR", "test_value")
        with patch("builtins.print"):
            result = git_manager.read_from_env("TEST_VAR")
            assert result == "test_value"

    def test_read_from_env_missing(self, monkeypatch):
        """Test reading missing environment variable exits."""
        GitManager._instance = None
        git_manager = GitManager()

        monkeypatch.delenv("TEST_VAR", raising=False)
        with patch("sys.exit") as mock_exit:
            with patch("builtins.print"):
                git_manager.read_from_env("TEST_VAR")
                mock_exit.assert_called_once_with(1)

    def test_fetch_commit_hash(self, monkeypatch):
        """Test fetching commit hash from environment."""
        GitManager._instance = None
        GitManager._commit_hash = None
        git_manager = GitManager()

        monkeypatch.setenv("STABLE_GIT_COMMIT", "abc123")
        with patch("builtins.print"):
            result = git_manager.fetch_commit_hash()
            assert result == "abc123"
            # Test caching
            assert git_manager._commit_hash == "abc123"

    def test_fetch_branch_name(self, monkeypatch):
        """Test fetching branch name from environment."""
        GitManager._instance = None
        GitManager._branch_name = None
        git_manager = GitManager()

        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")
        with patch("builtins.print"):
            result = git_manager.fetch_branch_name()
            assert result == "main"
            # Test caching
            assert git_manager._branch_name == "main"

    def test_fetch_manifest_dir(self, monkeypatch):
        """Test fetching manifest directory from environment."""
        GitManager._instance = None
        git_manager = GitManager()

        monkeypatch.setenv("RENDERED_MANIFEST_DIR", "/path/to/manifests")
        with patch("builtins.print"):
            result = git_manager.fetch_manifest_dir()
            assert result == "/path/to/manifests"

    def test_push_manifests_with_repo_url(self, monkeypatch, tmp_path):
        """Test pushing manifests with provided repo URL."""
        GitManager._instance = None
        GitManager._commit_hash = None
        GitManager._branch_name = None
        git_manager = GitManager()

        # Set up environment variables
        monkeypatch.setenv("STABLE_GIT_COMMIT", "abc123")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")
        monkeypatch.setenv("RENDERED_MANIFEST_DIR", str(tmp_path / "manifests"))

        # Create manifests directory
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()
        (manifests_dir / "test.yaml").write_text("test content")

        with patch("subprocess.run") as mock_run:
            # Mock all git commands in sequence
            # 1. git clone
            # 2. git ls-remote (with stdout capture)
            # 3. git fetch
            # 4. git checkout
            # 5. git add
            # 6. git commit
            # 7. git push
            mock_run.side_effect = [
                Mock(returncode=0),  # clone
                Mock(stdout="refs/heads/main", stderr="", returncode=0),  # ls-remote
                Mock(returncode=0),  # fetch
                Mock(returncode=0),  # checkout
                Mock(returncode=0),  # add
                Mock(returncode=0),  # commit
                Mock(returncode=0),  # push
            ]

            with patch("builtins.print"):
                git_manager.push_manifests(repo_url="https://github.com/test/repo.git")

            # Verify git commands were called
            assert mock_run.call_count == 7

    def test_push_manifests_with_env_repo_url(self, monkeypatch, tmp_path):
        """Test pushing manifests with repo URL from environment."""
        GitManager._instance = None
        GitManager._commit_hash = None
        GitManager._branch_name = None
        git_manager = GitManager()

        # Set up environment variables
        monkeypatch.setenv("STABLE_GIT_COMMIT", "abc123")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")
        monkeypatch.setenv("RENDERED_MANIFEST_DIR", str(tmp_path / "manifests"))
        monkeypatch.setenv("MANIFEST_REPO_URL", "https://github.com/test/repo.git")

        # Create manifests directory
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0),  # clone
                Mock(stdout="refs/heads/main", stderr="", returncode=0),  # ls-remote
                Mock(returncode=0),  # fetch
                Mock(returncode=0),  # checkout
                Mock(returncode=0),  # add
                Mock(returncode=0),  # commit
                Mock(returncode=0),  # push
            ]

            with patch("builtins.print"):
                git_manager.push_manifests()

            assert mock_run.call_count == 7

    def test_push_manifests_no_repo_url(self):
        """Test pushing manifests without repo URL raises error."""
        GitManager._instance = None
        git_manager = GitManager()

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="repo_url must be provided"):
                git_manager.push_manifests()

    def test_push_manifests_new_branch(self, monkeypatch, tmp_path):
        """Test pushing manifests to a new branch."""
        GitManager._instance = None
        GitManager._commit_hash = None
        GitManager._branch_name = None
        git_manager = GitManager()

        # Set up environment variables
        monkeypatch.setenv("STABLE_GIT_COMMIT", "abc123")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "new-branch")
        monkeypatch.setenv("RENDERED_MANIFEST_DIR", str(tmp_path / "manifests"))

        # Create manifests directory
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            # Mock all git commands in sequence for new branch
            # 1. git clone
            # 2. git ls-remote (no branch exists)
            # 3. git fetch origin main
            # 4. git checkout origin/main -b new-branch
            # 5. git add
            # 6. git commit
            # 7. git push
            mock_run.side_effect = [
                Mock(returncode=0),  # clone
                Mock(stdout="", stderr="", returncode=0),  # ls-remote (no branch)
                Mock(returncode=0),  # fetch main
                Mock(returncode=0),  # checkout new branch
                Mock(returncode=0),  # add
                Mock(returncode=0),  # commit
                Mock(returncode=0),  # push
            ]

            with patch("builtins.print"):
                git_manager.push_manifests(repo_url="https://github.com/test/repo.git")

            # Verify branch creation logic was called
            calls = [str(call) for call in mock_run.call_args_list]
            assert any("origin/main" in str(call) for call in calls)
            assert mock_run.call_count == 7
