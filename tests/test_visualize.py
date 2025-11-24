"""Unit tests for visualization module and CLI command."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import yaml

from kubeman.cli import cmd_visualize
from kubeman.register import TemplateRegistry
from kubeman.visualize import (
    ResourceAnalyzer,
    ResourceNode,
    ResourceRelationship,
    DOTGenerator,
    generate_visualization,
)


class TestResourceNode:
    """Test cases for ResourceNode class."""

    def test_node_id_generation(self):
        """Test node ID generation."""
        node = ResourceNode("Deployment", "my-app", "default", "template1")
        node_id = node.node_id()
        assert "deployment" in node_id
        assert "my_app" in node_id
        assert "default" in node_id

    def test_node_id_no_namespace(self):
        """Test node ID generation without namespace."""
        node = ResourceNode("ClusterRole", "my-role", None, "template1")
        node_id = node.node_id()
        assert "clusterrole" in node_id
        assert "my_role" in node_id

    def test_display_name(self):
        """Test display name generation."""
        node = ResourceNode("Deployment", "my-app", "default", "template1")
        display = node.display_name()
        assert "Deployment" in display
        assert "my-app" in display
        assert "template1" in display

    def test_display_name_no_template(self):
        """Test display name without template."""
        node = ResourceNode("Service", "my-service", "default", None)
        display = node.display_name()
        assert "Service" in display
        assert "my-service" in display

    def test_equality(self):
        """Test resource node equality."""
        node1 = ResourceNode("Deployment", "app", "ns", "t1")
        node2 = ResourceNode("Deployment", "app", "ns", "t2")
        node3 = ResourceNode("Service", "app", "ns", "t1")

        assert node1 == node2  # Same kind, name, namespace
        assert node1 != node3  # Different kind


class TestResourceRelationship:
    """Test cases for ResourceRelationship class."""

    def test_relationship_without_address(self):
        """Test relationship without address."""
        source = ResourceNode("Deployment", "app", "default")
        target = ResourceNode("Service", "app", "default")
        rel = ResourceRelationship(source, target, "uses")

        assert rel.source == source
        assert rel.target == target
        assert rel.relationship_type == "uses"
        assert rel.label == "uses"
        assert rel.address is None

    def test_relationship_with_address(self):
        """Test relationship with address."""
        source = ResourceNode("Deployment", "app", "default")
        target = ResourceNode("Service", "db", "default")
        rel = ResourceRelationship(source, target, "connects-to", address="db:5432")

        assert rel.label == "connects-to\ndb:5432"
        assert rel.address == "db:5432"

    def test_relationship_with_custom_label_and_address(self):
        """Test relationship with custom label and address."""
        source = ResourceNode("Deployment", "app", "default")
        target = ResourceNode("Service", "db", "default")
        rel = ResourceRelationship(
            source, target, "connects-to", label="connects-to-via-config", address="db:5432"
        )

        assert rel.label == "connects-to-via-config\ndb:5432"
        assert rel.address == "db:5432"


class TestResourceAnalyzer:
    """Test cases for ResourceAnalyzer class."""

    def test_analyze_empty_directory(self, tmp_path):
        """Test analyzing empty manifests directory."""
        analyzer = ResourceAnalyzer(tmp_path)
        namespace_to_resources, relationships = analyzer.analyze()

        assert namespace_to_resources == {}
        assert relationships == []

    def test_analyze_simple_deployment(self, tmp_path):
        """Test analyzing a simple deployment."""
        manifest_dir = tmp_path / "test-template"
        manifest_dir.mkdir()

        deployment_file = manifest_dir / "app-deployment.yaml"
        deployment_file.write_text(
            """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: default
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: app
        image: nginx
"""
        )

        analyzer = ResourceAnalyzer(manifest_dir)
        namespace_to_resources, relationships = analyzer.analyze()

        assert "default" in namespace_to_resources
        assert len(namespace_to_resources["default"]) == 1
        assert namespace_to_resources["default"][0].kind == "Deployment"
        assert namespace_to_resources["default"][0].name == "app"

    def test_analyze_deployment_with_configmap(self, tmp_path):
        """Test analyzing deployment with ConfigMap reference."""
        manifest_dir = tmp_path / "test-template"
        manifest_dir.mkdir()

        # Create ConfigMap
        cm_file = manifest_dir / "config-configmap.yaml"
        cm_file.write_text(
            """apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: default
data:
  KEY: value
"""
        )

        # Create Deployment that uses ConfigMap
        deployment_file = manifest_dir / "app-deployment.yaml"
        deployment_file.write_text(
            """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: default
spec:
  template:
    spec:
      containers:
      - name: app
        image: nginx
        env:
        - name: KEY
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: KEY
"""
        )

        analyzer = ResourceAnalyzer(manifest_dir)
        namespace_to_resources, relationships = analyzer.analyze()

        # Check resources
        assert len(namespace_to_resources["default"]) == 2

        # Check relationships
        uses_configmap_rels = [r for r in relationships if r.relationship_type == "uses-configmap"]
        assert len(uses_configmap_rels) == 1
        assert uses_configmap_rels[0].source.name == "app"
        assert uses_configmap_rels[0].target.name == "app-config"

    def test_analyze_service_selector_relationship(self, tmp_path):
        """Test analyzing service selector relationship."""
        manifest_dir = tmp_path / "test-template"
        manifest_dir.mkdir()

        # Create Deployment
        deployment_file = manifest_dir / "app-deployment.yaml"
        deployment_file.write_text(
            """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: default
spec:
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: app
        image: nginx
"""
        )

        # Create Service with matching selector
        service_file = manifest_dir / "app-service.yaml"
        service_file.write_text(
            """apiVersion: v1
kind: Service
metadata:
  name: app
  namespace: default
spec:
  selector:
    app: myapp
  ports:
  - port: 80
"""
        )

        analyzer = ResourceAnalyzer(manifest_dir)
        namespace_to_resources, relationships = analyzer.analyze()

        # Check relationships
        selects_rels = [r for r in relationships if r.relationship_type == "selects"]
        assert len(selects_rels) == 1
        assert selects_rels[0].source.name == "app"
        assert selects_rels[0].source.kind == "Service"
        assert selects_rels[0].target.name == "app"
        assert selects_rels[0].target.kind == "Deployment"

    def test_analyze_network_connections(self, tmp_path):
        """Test analyzing network connections from ConfigMap data."""
        manifest_dir = tmp_path / "test-template"
        manifest_dir.mkdir()

        # Create ConfigMap with database URL
        cm_file = manifest_dir / "config-configmap.yaml"
        cm_file.write_text(
            """apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: default
data:
  DATABASE_URL: "postgresql://user:pass@postgres:5432/db"
"""
        )

        # Create Service
        service_file = manifest_dir / "postgres-service.yaml"
        service_file.write_text(
            """apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: default
spec:
  ports:
  - port: 5432
"""
        )

        # Create Deployment that uses ConfigMap
        deployment_file = manifest_dir / "app-deployment.yaml"
        deployment_file.write_text(
            """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: default
spec:
  template:
    spec:
      containers:
      - name: app
        image: nginx
        env:
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: DATABASE_URL
"""
        )

        analyzer = ResourceAnalyzer(manifest_dir)
        namespace_to_resources, relationships = analyzer.analyze()

        # Check for network connection relationship
        connects_rels = [r for r in relationships if "connects-to" in r.relationship_type]
        assert len(connects_rels) > 0

        # Find the connection to postgres service
        postgres_conn = [
            r for r in connects_rels if r.target.name == "postgres" and r.target.kind == "Service"
        ]
        assert len(postgres_conn) > 0
        assert postgres_conn[0].address is not None
        assert "postgres" in postgres_conn[0].address
        assert "5432" in postgres_conn[0].address

    def test_filter_by_template_names(self, tmp_path):
        """Test filtering resources by template names."""
        # Create two template directories
        template1_dir = tmp_path / "template1"
        template1_dir.mkdir()

        template2_dir = tmp_path / "template2"
        template2_dir.mkdir()

        # Create resources in template1
        (template1_dir / "app-deployment.yaml").write_text(
            """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app1
  namespace: default
spec:
  template:
    spec:
      containers:
      - name: app
        image: nginx
"""
        )

        # Create resources in template2
        (template2_dir / "app-deployment.yaml").write_text(
            """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app2
  namespace: default
spec:
  template:
    spec:
      containers:
      - name: app
        image: nginx
"""
        )

        analyzer = ResourceAnalyzer(tmp_path, template_names=["template1"])
        namespace_to_resources, relationships = analyzer.analyze()

        # Should only have resources from template1
        resources = namespace_to_resources.get("default", [])
        assert len(resources) == 1
        assert resources[0].name == "app1"

    def test_skip_crds(self, tmp_path):
        """Test that CRDs are skipped by default."""
        manifest_dir = tmp_path / "test-template"
        manifest_dir.mkdir()

        crd_file = manifest_dir / "crd.yaml"
        crd_file.write_text(
            """apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: kafkas.kafka.strimzi.io
"""
        )

        analyzer = ResourceAnalyzer(manifest_dir, show_crds=False)
        namespace_to_resources, relationships = analyzer.analyze()

        # CRD should be skipped
        all_resources = []
        for resources in namespace_to_resources.values():
            all_resources.extend(resources)
        crds = [r for r in all_resources if r.kind == "CustomResourceDefinition"]
        assert len(crds) == 0

    def test_include_crds_when_requested(self, tmp_path):
        """Test that CRDs are included when show_crds is True."""
        manifest_dir = tmp_path / "test-template"
        manifest_dir.mkdir()

        crd_file = manifest_dir / "crd.yaml"
        crd_file.write_text(
            """apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: kafkas.kafka.strimzi.io
"""
        )

        analyzer = ResourceAnalyzer(manifest_dir, show_crds=True)
        namespace_to_resources, relationships = analyzer.analyze()

        # CRD should be included
        all_resources = []
        for resources in namespace_to_resources.values():
            all_resources.extend(resources)
        crds = [r for r in all_resources if r.kind == "CustomResourceDefinition"]
        assert len(crds) == 1


class TestDOTGenerator:
    """Test cases for DOTGenerator class."""

    def test_generate_empty_graph(self):
        """Test generating DOT for empty graph."""
        generator = DOTGenerator({}, [])
        dot = generator.generate()

        assert "digraph G" in dot
        assert 'rankdir="TB"' in dot

    def test_generate_simple_graph(self):
        """Test generating DOT for simple graph."""
        namespace_to_resources = {
            "default": [
                ResourceNode("Deployment", "app", "default", "template1"),
                ResourceNode("Service", "app", "default", "template1"),
            ]
        }
        relationships = [
            ResourceRelationship(
                namespace_to_resources["default"][0],
                namespace_to_resources["default"][1],
                "uses",
            )
        ]

        generator = DOTGenerator(namespace_to_resources, relationships)
        dot = generator.generate()

        assert "cluster_default" in dot
        assert "deployment_app_default" in dot
        assert "service_app_default" in dot
        assert "deployment_app_default -> service_app_default" in dot

    def test_generate_with_addresses(self):
        """Test generating DOT with connection addresses."""
        namespace_to_resources = {
            "default": [
                ResourceNode("Deployment", "app", "default", "template1"),
                ResourceNode("Service", "db", "default", "template1"),
            ]
        }
        relationships = [
            ResourceRelationship(
                namespace_to_resources["default"][0],
                namespace_to_resources["default"][1],
                "connects-to",
                address="db:5432",
            )
        ]

        generator = DOTGenerator(namespace_to_resources, relationships)
        dot = generator.generate()

        assert "connects-to" in dot
        assert "db:5432" in dot
        assert "\\n" in dot  # Newline should be escaped

    def test_generate_cluster_scoped_resources(self):
        """Test generating DOT with cluster-scoped resources."""
        namespace_to_resources = {
            "cluster-scoped": [
                ResourceNode("ClusterRole", "admin", None, "template1"),
            ],
            "default": [
                ResourceNode("Deployment", "app", "default", "template1"),
            ],
        }
        relationships = []

        generator = DOTGenerator(namespace_to_resources, relationships)
        dot = generator.generate()

        assert "cluster_cluster_scoped" in dot
        assert "cluster_default" in dot
        assert "clusterrole_admin" in dot


class TestGenerateVisualization:
    """Test cases for generate_visualization function."""

    def test_generate_from_empty_directory(self, tmp_path):
        """Test generating visualization from empty directory."""
        dot = generate_visualization(tmp_path)
        assert "digraph G" in dot

    def test_generate_with_template_filter(self, tmp_path):
        """Test generating visualization with template filter."""
        manifest_dir = tmp_path / "template1"
        manifest_dir.mkdir()

        (manifest_dir / "app-deployment.yaml").write_text(
            """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: default
spec:
  template:
    spec:
      containers:
      - name: app
        image: nginx
"""
        )

        dot = generate_visualization(tmp_path, template_names=["template1"])
        assert "digraph G" in dot
        assert "deployment_app_default" in dot


class TestCmdVisualize:
    """Test cases for cmd_visualize function."""

    def setup_method(self):
        """Clear registry before each test."""
        TemplateRegistry.clear()

    @patch("kubeman.cli.generate_visualization")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    @patch("kubeman.cli.TemplateRegistry")
    def test_successful_visualize(
        self, mock_registry, mock_load, mock_render, mock_gen_viz, capsys, tmp_path
    ):
        """Test successful visualize command."""
        mock_render.return_value = ["template1", "template2"]
        mock_gen_viz.return_value = "digraph G { }"
        test_file = tmp_path / "kubeman.py"
        test_output = tmp_path / "output.dot"
        args = Mock(file=str(test_file), output=str(test_output), output_dir=None, show_crds=False)

        cmd_visualize(args)

        mock_registry.set_skip_builds.assert_called_once_with(True)
        mock_registry.set_skip_loads.assert_called_once_with(True)
        mock_load.assert_called_once_with(str(test_file))
        mock_render.assert_called_once_with(manifests_dir=None)
        mock_gen_viz.assert_called_once()

        output = capsys.readouterr()
        assert "Templates rendered successfully" in output.out
        assert "Visualization written to" in output.out

    @patch("kubeman.cli.generate_visualization")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    @patch("kubeman.cli.TemplateRegistry")
    def test_visualize_with_show_crds(
        self, mock_registry, mock_load, mock_render, mock_gen_viz, capsys, tmp_path
    ):
        """Test visualize command with --show-crds flag."""
        mock_render.return_value = ["template1"]
        mock_gen_viz.return_value = "digraph G { }"
        test_file = tmp_path / "kubeman.py"
        test_output = tmp_path / "output.dot"
        args = Mock(file=str(test_file), output=str(test_output), output_dir=None, show_crds=True)

        cmd_visualize(args)

        # Check that show_crds was passed to generate_visualization
        call_args = mock_gen_viz.call_args
        assert call_args[1]["show_crds"] is True

        output = capsys.readouterr()
        assert "Including CustomResourceDefinitions" in output.out

    @patch("kubeman.cli.generate_visualization")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    @patch("kubeman.cli.TemplateRegistry")
    def test_visualize_stdout(self, mock_registry, mock_load, mock_render, mock_gen_viz, capsys):
        """Test visualize command writing to stdout."""
        mock_render.return_value = ["template1"]
        mock_gen_viz.return_value = "digraph G { test }"
        args = Mock(file="/test/kubeman.py", output=None, output_dir=None, show_crds=False)

        cmd_visualize(args)

        output = capsys.readouterr()
        assert "digraph G" in output.out
        assert "=" * 60 in output.out  # Separator line

    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_visualize_file_not_found(self, mock_load, mock_render, capsys):
        """Test visualize command with file not found."""
        mock_load.side_effect = FileNotFoundError("File not found")
        args = Mock(file="/test/kubeman.py")

        with pytest.raises(SystemExit) as exc_info:
            cmd_visualize(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr()
        assert "Error: File not found" in output.err

    @patch("kubeman.cli.generate_visualization")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    def test_visualize_manifests_dir_not_found(self, mock_load, mock_render, mock_gen_viz, capsys):
        """Test visualize command when manifests directory doesn't exist."""
        mock_render.return_value = ["template1"]
        args = Mock(
            file="/test/kubeman.py", output="/test/output.dot", output_dir=None, show_crds=False
        )

        with patch("kubeman.cli.Template.manifests_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_dir.return_value = mock_path

            with pytest.raises(SystemExit) as exc_info:
                cmd_visualize(args)

            assert exc_info.value.code == 1
            output = capsys.readouterr()
            assert "Manifests directory not found" in output.err

    @patch("kubeman.cli.generate_visualization")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    @patch("kubeman.cli.TemplateRegistry")
    def test_visualize_default_file(
        self, mock_registry, mock_load, mock_render, mock_gen_viz, tmp_path
    ):
        """Test visualize command with default file path."""
        mock_render.return_value = ["template1"]
        mock_gen_viz.return_value = "digraph G { }"
        test_output = tmp_path / "output.dot"
        args = Mock(file=None, output=str(test_output), output_dir=None, show_crds=False)

        cmd_visualize(args)

        mock_load.assert_called_once_with("./kubeman.py")

    @patch("kubeman.cli.generate_visualization")
    @patch("kubeman.cli.render_templates")
    @patch("kubeman.cli.load_templates_file")
    @patch("kubeman.cli.TemplateRegistry")
    def test_visualize_with_output_dir(
        self, mock_registry, mock_load, mock_render, mock_gen_viz, tmp_path
    ):
        """Test visualize command with custom output directory."""
        mock_render.return_value = ["template1"]
        mock_gen_viz.return_value = "digraph G { }"
        test_file = tmp_path / "kubeman.py"
        test_output = tmp_path / "output.dot"
        custom_dir = tmp_path / "custom" / "manifests"
        args = Mock(
            file=str(test_file),
            output=str(test_output),
            output_dir=str(custom_dir),
            show_crds=False,
        )

        cmd_visualize(args)

        mock_render.assert_called_once_with(manifests_dir=Path(str(custom_dir)))
