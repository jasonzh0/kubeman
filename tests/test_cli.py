"""Unit tests for CLI module."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from kubeman.cli import (
    load_templates_file,
    cmd_render,
    cmd_apply,
    main,
)
from kubeman.cli import render_templates, apply_manifests
from kubeman.register import TemplateRegistry
from kubeman.template import Template


class TestLoadTemplatesFile:
    """Test cases for load_templates_file function."""

    def test_file_not_found(self):
        """Test loading a non-existent file."""
        with pytest.raises(FileNotFoundError, match="Templates file not found"):
            load_templates_file("/nonexistent/file.py")

    def test_file_not_python(self):
        """Test loading a file that's not a Python file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Templates file must be a Python file"):
                load_templates_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_successful_import(self, tmp_path):
        """Test successfully importing a templates file."""
        templates_file = tmp_path / "test_templates.py"
        templates_file.write_text("x = 1")

        # Should not raise an error - just imports the module
        load_templates_file(str(templates_file))

    def test_import_error(self, tmp_path):
        """Test importing a file with syntax errors."""
        templates_file = tmp_path / "bad_templates.py"
        templates_file.write_text("invalid python syntax {")

        with pytest.raises(ImportError, match="Error importing templates file"):
            load_templates_file(str(templates_file))


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

    @patch("kubeman.cli.get_executor")
    def test_kubectl_not_found(self, mock_get_executor):
        """Test when kubectl is not found."""
        mock_executor = MagicMock()
        mock_executor.run.side_effect = FileNotFoundError()
        mock_get_executor.return_value = mock_executor

        with pytest.raises(FileNotFoundError, match="kubectl not found"):
            apply_manifests()

    @patch("kubeman.cli.get_executor")
    def test_manifests_directory_not_found(self, mock_get_executor):
        """Test when manifests directory doesn't exist."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = MagicMock(returncode=0)
        mock_get_executor.return_value = mock_executor

        with patch("kubeman.cli.Template.manifests_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_dir.return_value = mock_path

            with pytest.raises(RuntimeError, match="Manifests directory not found"):
                apply_manifests()

    @patch("kubeman.cli.get_executor")
    def test_successful_apply(self, mock_get_executor, capsys):
        """Test successfully applying manifests."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = MagicMock(returncode=0)
        mock_get_executor.return_value = mock_executor

        with patch("kubeman.cli.Template.manifests_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda x: "/test/manifests"
            # Mock rglob to return some YAML files (use Path objects for sorting)
            from pathlib import Path

            mock_yaml_file = Path("/test/manifests/test.yaml")
            mock_path.rglob.return_value = [mock_yaml_file]
            mock_dir.return_value = mock_path

            apply_manifests()

        # Check kubectl version was called
        assert mock_executor.run.call_count >= 2
        # Check kubectl apply was called - find the call with "apply" in the command
        apply_calls = [
            c
            for c in mock_executor.run.call_args_list
            if len(c[0]) > 0
            and isinstance(c[0][0], list)
            and len(c[0][0]) > 1
            and c[0][0][1] == "apply"
        ]
        assert len(apply_calls) > 0

        output = capsys.readouterr()
        assert "Applying manifests" in output.out
        assert "Successfully applied" in output.out

    @patch("kubeman.cli.get_executor")
    def test_apply_with_namespace(self, mock_get_executor, capsys):
        """Test applying manifests with namespace."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = MagicMock(returncode=0)
        mock_get_executor.return_value = mock_executor

        with patch("kubeman.cli.Template.manifests_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda x: "/test/manifests"
            # Mock rglob to return some YAML files (use Path objects for sorting)
            from pathlib import Path

            mock_yaml_file = Path("/test/manifests/test.yaml")
            mock_path.rglob.return_value = [mock_yaml_file]
            mock_dir.return_value = mock_path

            apply_manifests(namespace="test-ns")

        # Check that namespace was added to command
        # Find the apply call (second call after version check)
        apply_calls = [
            c
            for c in mock_executor.run.call_args_list
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

    @patch("kubeman.cli.get_executor")
    def test_apply_failure(self, mock_get_executor):
        """Test kubectl apply failure."""
        mock_executor = MagicMock()
        # Mock kubectl version check to succeed, then apply to fail
        mock_executor.run.side_effect = [
            MagicMock(returncode=0),  # version check
            Exception("Error applying"),  # apply fails
        ]
        mock_get_executor.return_value = mock_executor

        with patch("kubeman.cli.Template.manifests_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda x: "/test/manifests"
            # Mock rglob to return some YAML files (use Path objects for sorting)
            from pathlib import Path

            mock_yaml_file = Path("/test/manifests/test.yaml")
            mock_path.rglob.return_value = [mock_yaml_file]
            mock_dir.return_value = mock_path

            with pytest.raises(RuntimeError, match="kubectl apply failed"):
                apply_manifests()

    @patch("kubeman.cli.get_executor")
    def test_crd_ordering(self, mock_get_executor, tmp_path, capsys):
        """Test that CRDs are applied before other resources."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = MagicMock(returncode=0)
        mock_get_executor.return_value = mock_executor

        # Create test YAML files
        crd_file = tmp_path / "crd.yaml"
        crd_file.write_text(
            """apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: kafkas.kafka.strimzi.io
"""
        )

        resource_file = tmp_path / "resource.yaml"
        resource_file.write_text(
            """apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: my-cluster
"""
        )

        with patch("kubeman.cli.Template.manifests_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda x: str(tmp_path)
            # rglob is called twice: once for *.yaml, once for *.yml
            # Return files on first call, empty list on second call
            mock_path.rglob.side_effect = [[resource_file, crd_file], []]
            mock_dir.return_value = mock_path

            apply_manifests()

        # Verify CRD was applied first, then resource
        apply_calls = [
            c
            for c in mock_executor.run.call_args_list
            if len(c[0]) > 0
            and isinstance(c[0][0], list)
            and len(c[0][0]) > 1
            and c[0][0][1] == "apply"
        ]
        assert len(apply_calls) == 2

        # First apply should be CRD
        first_apply = apply_calls[0][0][0]
        assert str(crd_file) in first_apply or "crd.yaml" in str(first_apply)

        # Second apply should be resource
        second_apply = apply_calls[1][0][0]
        assert str(resource_file) in second_apply or "resource.yaml" in str(second_apply)

        output = capsys.readouterr()
        assert "CRD file(s) will be applied first" in output.out
        assert "1 CRD file(s)" in output.out
        assert "1 other resource file(s)" in output.out

    @patch("kubeman.cli.get_executor")
    def test_multi_document_yaml_with_crd(self, mock_get_executor, tmp_path):
        """Test handling of multi-document YAML files containing CRDs."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = MagicMock(returncode=0)
        mock_get_executor.return_value = mock_executor

        # Create a multi-document YAML file with CRD
        multi_doc_file = tmp_path / "multi.yaml"
        multi_doc_file.write_text(
            """---
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: kafkas.kafka.strimzi.io
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
"""
        )

        regular_file = tmp_path / "regular.yaml"
        regular_file.write_text(
            """apiVersion: v1
kind: Service
metadata:
  name: test-service
"""
        )

        with patch("kubeman.cli.Template.manifests_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda x: str(tmp_path)
            # rglob is called twice: once for *.yaml, once for *.yml
            # Return files on first call, empty list on second call
            mock_path.rglob.side_effect = [[regular_file, multi_doc_file], []]
            mock_dir.return_value = mock_path

            apply_manifests()

        # Verify multi-doc file with CRD was applied first
        apply_calls = [
            c
            for c in mock_executor.run.call_args_list
            if len(c[0]) > 0
            and isinstance(c[0][0], list)
            and len(c[0][0]) > 1
            and c[0][0][1] == "apply"
        ]
        assert len(apply_calls) == 2

        # First apply should be the multi-doc file (contains CRD)
        first_apply = apply_calls[0][0][0]
        assert str(multi_doc_file) in first_apply or "multi.yaml" in str(first_apply)

        # Second apply should be regular file
        second_apply = apply_calls[1][0][0]
        assert str(regular_file) in second_apply or "regular.yaml" in str(second_apply)

    @patch("kubeman.cli.get_executor")
    def test_no_crds_in_output(self, mock_get_executor, tmp_path, capsys):
        """Test that output doesn't mention CRDs when there are none."""
        mock_executor = MagicMock()
        mock_executor.run.return_value = MagicMock(returncode=0)
        mock_get_executor.return_value = mock_executor

        # Create test YAML files without CRDs
        resource_file = tmp_path / "resource.yaml"
        resource_file.write_text(
            """apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
"""
        )

        with patch("kubeman.cli.Template.manifests_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda x: str(tmp_path)
            mock_path.rglob.return_value = [resource_file]
            mock_dir.return_value = mock_path

            apply_manifests()

        output = capsys.readouterr()
        # Should not mention CRD count when there are no CRDs
        assert "CRD file(s) will be applied first" not in output.out


class TestCmdRender:
    """Test cases for cmd_render function."""

    def setup_method(self):
        """Clear registry before each test."""
        TemplateRegistry.clear()

    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_successful_render(self, mock_load, mock_render, capsys):
        """Test successful render command."""
        args = Mock(file="/test/templates.py")

        cmd_render(args)

        mock_load.assert_called_once_with("/test/templates.py")
        mock_render.assert_called_once()

        output = capsys.readouterr()
        assert "All templates rendered successfully" in output.out

    @patch("kubeman.cli.load_templates_file")
    def test_render_file_not_found(self, mock_load, capsys):
        """Test render command with file not found."""
        mock_load.side_effect = FileNotFoundError("File not found")
        args = Mock(file="/test/templates.py")

        with pytest.raises(SystemExit) as exc_info:
            cmd_render(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: File not found" in output.err

    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_render_error(self, mock_load, mock_render, capsys):
        """Test render command with render error."""
        mock_render.side_effect = RuntimeError("Render failed")
        args = Mock(file="/test/templates.py")

        with pytest.raises(SystemExit) as exc_info:
            cmd_render(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: Render failed" in output.err

    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_render_default_file(self, mock_load, mock_render):
        """Test render command with default file path."""
        args = Mock(file=None)

        cmd_render(args)

        mock_load.assert_called_once_with("./templates.py")


class TestCmdApply:
    """Test cases for cmd_apply function."""

    def setup_method(self):
        """Clear registry before each test."""
        TemplateRegistry.clear()

    @patch("kubeman.cli.apply_manifests")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_successful_apply(self, mock_load, mock_render, mock_apply, capsys):
        """Test successful apply command."""
        args = Mock(file="/test/templates.py", namespace=None)

        cmd_apply(args)

        mock_load.assert_called_once_with("/test/templates.py")
        mock_render.assert_called_once_with(manifests_dir=None)
        mock_apply.assert_called_once_with(namespace=None, manifests_dir=None)

        output = capsys.readouterr()
        assert "Templates rendered successfully" in output.out

    @patch("kubeman.cli.apply_manifests")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_apply_with_namespace(self, mock_load, mock_render, mock_apply):
        """Test apply command with namespace."""
        args = Mock(file="/test/templates.py", namespace="test-ns")

        cmd_apply(args)

        mock_apply.assert_called_once_with(namespace="test-ns", manifests_dir=None)

    @patch("kubeman.cli.load_templates_file")
    def test_apply_file_not_found(self, mock_load, capsys):
        """Test apply command with file not found."""
        mock_load.side_effect = FileNotFoundError("File not found")
        args = Mock(file="/test/templates.py", namespace=None)

        with pytest.raises(SystemExit) as exc_info:
            cmd_apply(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: File not found" in output.err

    @patch("kubeman.cli.apply_manifests")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_apply_error(self, mock_load, mock_render, mock_apply, capsys):
        """Test apply command with apply error."""
        mock_apply.side_effect = RuntimeError("Apply failed")
        args = Mock(file="/test/templates.py", namespace=None)

        with pytest.raises(SystemExit) as exc_info:
            cmd_apply(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: Apply failed" in output.err

    @patch("kubeman.cli.apply_manifests")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_apply_default_file(self, mock_load, mock_render, mock_apply):
        """Test apply command with default file path."""
        args = Mock(file=None, namespace=None)

        cmd_apply(args)

        mock_load.assert_called_once_with("./templates.py")


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

    @patch("kubeman.cli.cmd_render")
    @patch("sys.argv", ["kubeman", "render"])
    def test_main_render_default_file(self, mock_cmd_render):
        """Test main function with render command using default file."""
        main()
        mock_cmd_render.assert_called_once()
        args = mock_cmd_render.call_args[0][0]
        assert args.file is None

    @patch("sys.argv", ["kubeman", "--help"])
    def test_main_help(self, capsys):
        """Test main function help output."""
        with pytest.raises(SystemExit):
            main()
        output = capsys.readouterr()
        assert "Kubeman" in output.out or "kubeman" in output.out.lower()
