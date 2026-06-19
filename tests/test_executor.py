"""Unit tests for CommandExecutor."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from kubeman.executor import CommandExecutor, get_executor, _redact_cmd


def _ok():
    return MagicMock(returncode=0, stdout="", stderr="")


class TestCommandExecutorRun:
    @patch("kubeman.executor.subprocess.run")
    def test_success_passes_args_and_default_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = CommandExecutor().run(["echo", "hi"])
        assert result.returncode == 0
        kwargs = mock_run.call_args.kwargs
        assert mock_run.call_args.args[0] == ["echo", "hi"]
        assert kwargs["check"] is True
        assert kwargs["timeout"] == 300

    @patch("kubeman.executor.subprocess.run")
    def test_timeout_override(self, mock_run):
        mock_run.return_value = _ok()
        CommandExecutor().run(["x"], timeout=5)
        assert mock_run.call_args.kwargs["timeout"] == 5

    @patch("kubeman.executor.subprocess.run")
    def test_timeout_none_disables(self, mock_run):
        mock_run.return_value = _ok()
        CommandExecutor().run(["x"], timeout=None)
        assert mock_run.call_args.kwargs["timeout"] is None

    @patch("kubeman.executor.subprocess.run")
    def test_instance_timeout_default(self, mock_run):
        mock_run.return_value = _ok()
        CommandExecutor(timeout=12).run(["x"])
        assert mock_run.call_args.kwargs["timeout"] == 12

    @patch("kubeman.executor.subprocess.run")
    def test_overrides_check_capture_text(self, mock_run):
        mock_run.return_value = _ok()
        CommandExecutor().run(["x"], check=False, capture_output=True, text=False)
        kwargs = mock_run.call_args.kwargs
        assert kwargs["check"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is False

    @patch("kubeman.executor.subprocess.run")
    def test_converts_cwd_to_str(self, mock_run, tmp_path):
        mock_run.return_value = _ok()
        CommandExecutor().run(["x"], cwd=tmp_path)
        assert mock_run.call_args.kwargs["cwd"] == str(tmp_path)

    @patch("kubeman.executor.subprocess.run")
    def test_raises_called_process_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, ["x"], stderr="boom")
        with pytest.raises(subprocess.CalledProcessError):
            CommandExecutor().run(["x"], capture_output=True)

    @patch("kubeman.executor.subprocess.run")
    def test_raises_timeout_expired(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(["x"], 1)
        with pytest.raises(subprocess.TimeoutExpired):
            CommandExecutor().run(["x"])

    @patch("kubeman.executor.subprocess.run")
    def test_raises_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(FileNotFoundError):
            CommandExecutor().run(["nope"])


class TestRunSilent:
    @patch("kubeman.executor.subprocess.run")
    def test_captures_and_disables_check(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        CommandExecutor().run_silent(["x"])
        kwargs = mock_run.call_args.kwargs
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False


class TestGetExecutor:
    def test_returns_command_executor(self):
        assert isinstance(get_executor(), CommandExecutor)

    def test_returns_same_instance(self):
        assert get_executor() is get_executor()


class TestRedactCmd:
    def test_masks_url_credentials(self):
        assert (
            _redact_cmd(["git", "clone", "https://user:tok@github.com/x.git"])
            == "git clone https://***@github.com/x.git"
        )

    def test_leaves_plain_urls_untouched(self):
        assert (
            _redact_cmd(["helm", "repo", "add", "r", "https://charts.example.com"])
            == "helm repo add r https://charts.example.com"
        )
