"""Unit tests for CLI module."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import subprocess

from kubeman.cli import (
    load_template_file,
    render_templates,
    apply_manifests,
    cmd_render,
    cmd_apply,
    main,
)
from kubeman.register import TemplateRegistry
from kubeman.template import Template


class TestLoadTemplateFile:
    """Test cases for load_template_file function."""

    def test_file_not_found(self):
        """Test loading a non-existent file."""
        with pytest.raises(FileNotFoundError, match="Template file not found"):
            load_template_file("/nonexistent/file.py")

    def test_file_not_python(self):
        """Test loading a file that's not a Python file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Template file must be a Python file"):
                load_template_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_successful_import(self, tmp_path):
        """Test successfully importing a template file."""
        template_file = tmp_path / "test_templates.py"
        template_file.write_text(
            """
from kubeman import KubernetesResource, TemplateRegistry

@TemplateRegistry.register
class TestResource(KubernetesResource):
    @property
    def name(self):
        return "test"

    @property
    def namespace(self):
        return "default"
"""
        )

        TemplateRegistry.clear()
        load_template_file(str(template_file))

        templates = TemplateRegistry.get_registered_templates()
        assert len(templates) == 1
        assert templates[0].__name__ == "TestResource"

    def test_import_error(self, tmp_path):
        """Test importing a file with syntax errors."""
        template_file = tmp_path / "bad_templates.py"
        template_file.write_text("invalid python syntax {")

        with pytest.raises(ImportError, match="Error importing template file"):
            load_template_file(str(template_file))


class TestRenderTemplates:
    """Test cases for render_templates function."""

    def setup_method(self):
        """Clear registry before each test."""
        TemplateRegistry.clear()

    def test_no_templates_registered(self):
        """Test rendering when no templates are registered."""
        with pytest.raises(ValueError, match="No templates registered"):
            render_templates()

    def test_successful_render(self, capsys):
        """Test successfully rendering templates."""
        from kubeman import KubernetesResource

        class TestTemplate(KubernetesResource):
            @property
            def name(self):
                return "test"

            @property
            def namespace(self):
                return "default"

            def render(self):
                pass  # Mock render

        TemplateRegistry.register(TestTemplate)

        render_templates()

        output = capsys.readouterr()
        assert "Found 1 registered template(s)" in output.out
        assert "Rendering template: TestTemplate" in output.out
        assert "Successfully rendered TestTemplate" in output.out

    def test_render_failure(self):
        """Test rendering failure."""
        from kubeman import KubernetesResource

        class FailingTemplate(KubernetesResource):
            @property
            def name(self):
                return "test"

            @property
            def namespace(self):
                return "default"

            def render(self):
                raise Exception("Render failed")

        TemplateRegistry.register(FailingTemplate)

        with pytest.raises(RuntimeError, match="Failed to render template FailingTemplate"):
            render_templates()


class TestApplyManifests:
    """Test cases for apply_manifests function."""

    @patch("kubeman.cli.subprocess.run")
    def test_kubectl_not_found(self, mock_run):
        """Test when kubectl is not found."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(FileNotFoundError, match="kubectl not found"):
            apply_manifests()

    @patch("kubeman.cli.subprocess.run")
    def test_manifests_directory_not_found(self, mock_run):
        """Test when manifests directory doesn't exist."""
        # Mock kubectl version check to succeed
        mock_run.return_value = MagicMock(returncode=0)

        with patch("kubeman.cli.os.path.exists", return_value=False):
            with pytest.raises(RuntimeError, match="Manifests directory not found"):
                apply_manifests()

    @patch("kubeman.cli.subprocess.run")
    @patch("kubeman.cli.os.path.exists")
    def test_successful_apply(self, mock_exists, mock_run, capsys):
        """Test successfully applying manifests."""
        # Mock kubectl version check
        mock_run.return_value = MagicMock(returncode=0)
        mock_exists.return_value = True

        with patch("kubeman.cli.Template.manifests_dir", return_value="/test/manifests"):
            apply_manifests()

        # Check kubectl version was called
        assert mock_run.call_count >= 2
        # Check kubectl apply was called - find the call with "apply" in the command
        apply_calls = [
            c
            for c in mock_run.call_args_list
            if len(c[0]) > 0
            and isinstance(c[0][0], list)
            and len(c[0][0]) > 1
            and c[0][0][1] == "apply"
        ]
        assert len(apply_calls) > 0

        output = capsys.readouterr()
        assert "Applying manifests" in output.out
        assert "Successfully applied manifests" in output.out

    @patch("kubeman.cli.subprocess.run")
    @patch("kubeman.cli.os.path.exists")
    def test_apply_with_namespace(self, mock_exists, mock_run, capsys):
        """Test applying manifests with namespace."""
        mock_run.return_value = MagicMock(returncode=0)
        mock_exists.return_value = True

        with patch("kubeman.cli.Template.manifests_dir", return_value="/test/manifests"):
            apply_manifests(namespace="test-ns")

        # Check that namespace was added to command
        # Find the apply call (second call after version check)
        apply_calls = [
            c
            for c in mock_run.call_args_list
            if len(c[0]) > 0
            and isinstance(c[0][0], list)
            and len(c[0][0]) > 1
            and c[0][0][1] == "apply"
        ]
        assert len(apply_calls) > 0
        cmd = apply_calls[0][0][0]  # Get the command list
        assert "--namespace" in cmd
        assert "test-ns" in cmd

        output = capsys.readouterr()
        assert "Using namespace: test-ns" in output.out

    @patch("kubeman.cli.subprocess.run")
    @patch("kubeman.cli.os.path.exists")
    def test_apply_failure(self, mock_exists, mock_run):
        """Test kubectl apply failure."""
        # Mock kubectl version check to succeed
        mock_run.side_effect = [
            MagicMock(returncode=0),  # version check
            subprocess.CalledProcessError(1, "kubectl", stderr="Error applying"),
        ]
        mock_exists.return_value = True

        with patch("kubeman.cli.Template.manifests_dir", return_value="/test/manifests"):
            with pytest.raises(RuntimeError, match="kubectl apply failed"):
                apply_manifests()


class TestCmdRender:
    """Test cases for cmd_render function."""

    def setup_method(self):
        """Clear registry before each test."""
        TemplateRegistry.clear()

    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_template_file")
    def test_successful_render(self, mock_load, mock_render, capsys):
        """Test successful render command."""
        args = Mock(file="/test/templates.py")

        cmd_render(args)

        mock_load.assert_called_once_with("/test/templates.py")
        mock_render.assert_called_once()

        output = capsys.readouterr()
        assert "All templates rendered successfully" in output.out

    @patch("kubeman.cli.load_template_file")
    def test_file_not_found_error(self, mock_load, capsys):
        """Test render command with file not found."""
        mock_load.side_effect = FileNotFoundError("File not found")
        args = Mock(file="/test/templates.py")

        with pytest.raises(SystemExit) as exc_info:
            cmd_render(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: File not found" in output.err

    @patch("kubeman.cli.load_template_file")
    @patch("kubeman.cli.render_templates")
    def test_render_error(self, mock_render, mock_load, capsys):
        """Test render command with render error."""
        mock_load.return_value = None
        mock_render.side_effect = RuntimeError("Render failed")
        args = Mock(file="/test/templates.py")

        with pytest.raises(SystemExit) as exc_info:
            cmd_render(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: Render failed" in output.err


class TestCmdApply:
    """Test cases for cmd_apply function."""

    def setup_method(self):
        """Clear registry before each test."""
        TemplateRegistry.clear()

    @patch("kubeman.cli.apply_manifests")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_template_file")
    def test_successful_apply(self, mock_load, mock_render, mock_apply, capsys):
        """Test successful apply command."""
        args = Mock(file="/test/templates.py", namespace=None)

        cmd_apply(args)

        mock_load.assert_called_once_with("/test/templates.py")
        mock_render.assert_called_once()
        mock_apply.assert_called_once_with(namespace=None)

        output = capsys.readouterr()
        assert "Templates rendered successfully" in output.out

    @patch("kubeman.cli.apply_manifests")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_template_file")
    def test_apply_with_namespace(self, mock_load, mock_render, mock_apply):
        """Test apply command with namespace."""
        args = Mock(file="/test/templates.py", namespace="test-ns")

        cmd_apply(args)

        mock_apply.assert_called_once_with(namespace="test-ns")

    @patch("kubeman.cli.load_template_file")
    def test_apply_file_not_found(self, mock_load, capsys):
        """Test apply command with file not found."""
        mock_load.side_effect = FileNotFoundError("File not found")
        args = Mock(file="/test/templates.py", namespace=None)

        with pytest.raises(SystemExit) as exc_info:
            cmd_apply(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: File not found" in output.err

    @patch("kubeman.cli.load_template_file")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.apply_manifests")
    def test_apply_error(self, mock_apply, mock_render, mock_load, capsys):
        """Test apply command with apply error."""
        mock_load.return_value = None
        mock_render.return_value = None
        mock_apply.side_effect = RuntimeError("Apply failed")
        args = Mock(file="/test/templates.py", namespace=None)

        with pytest.raises(SystemExit) as exc_info:
            cmd_apply(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: Apply failed" in output.err


class TestMain:
    """Test cases for main function."""

    @patch("kubeman.cli.cmd_render")
    @patch("sys.argv", ["kubeman", "render", "--file", "templates.py"])
    def test_main_render_command(self, mock_cmd_render):
        """Test main function with render command."""
        main()
        mock_cmd_render.assert_called_once()
        args = mock_cmd_render.call_args[0][0]
        assert args.file == "templates.py"

    @patch("kubeman.cli.cmd_apply")
    @patch("sys.argv", ["kubeman", "apply", "--file", "templates.py"])
    def test_main_apply_command(self, mock_cmd_apply):
        """Test main function with apply command."""
        main()
        mock_cmd_apply.assert_called_once()
        args = mock_cmd_apply.call_args[0][0]
        assert args.file == "templates.py"
        assert args.namespace is None

    @patch("kubeman.cli.cmd_apply")
    @patch("sys.argv", ["kubeman", "apply", "--file", "templates.py", "--namespace", "test-ns"])
    def test_main_apply_with_namespace(self, mock_cmd_apply):
        """Test main function with apply command and namespace."""
        main()
        mock_cmd_apply.assert_called_once()
        args = mock_cmd_apply.call_args[0][0]
        assert args.file == "templates.py"
        assert args.namespace == "test-ns"

    @patch("sys.argv", ["kubeman", "--help"])
    def test_main_help(self, capsys):
        """Test main function help output."""
        with pytest.raises(SystemExit):
            main()
        output = capsys.readouterr()
        assert "Kubeman" in output.out or "kubeman" in output.out.lower()
