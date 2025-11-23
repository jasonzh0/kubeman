"""Unit tests for HelmChart and KubernetesResource abstract classes."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from kubeman.chart import HelmChart
from kubeman.kubernetes import KubernetesResource
from kubeman.git import GitManager


class ConcreteHelmChart(HelmChart):
    """Concrete implementation of HelmChart for testing."""

    @property
    def name(self):
        return "test-chart"

    @property
    def repository(self):
        return {"type": "classic", "remote": "https://charts.example.com"}

    @property
    def namespace(self):
        return "test-namespace"

    @property
    def version(self):
        return "1.2.3"

    def generate_values(self):
        return {"key": "value", "nested": {"item": 123}}


class TestHelmChart:
    """Test cases for HelmChart class."""

    def test_name_property(self):
        """Test that name property is abstract and must be implemented."""
        chart = ConcreteHelmChart()
        assert chart.name == "test-chart"

    def test_repository_property(self):
        """Test that repository property is abstract and must be implemented."""
        chart = ConcreteHelmChart()
        assert chart.repository == {"type": "classic", "remote": "https://charts.example.com"}

    def test_namespace_property(self):
        """Test that namespace property is abstract and must be implemented."""
        chart = ConcreteHelmChart()
        assert chart.namespace == "test-namespace"

    def test_version_property(self):
        """Test that version property is abstract and must be implemented."""
        chart = ConcreteHelmChart()
        assert chart.version == "1.2.3"

    def test_repository_package_default(self):
        """Test that repository_package defaults to name."""
        chart = ConcreteHelmChart()
        assert chart.repository_package == "test-chart"

    def test_generate_values(self):
        """Test that generate_values is abstract and must be implemented."""
        chart = ConcreteHelmChart()
        values = chart.generate_values()
        assert values == {"key": "value", "nested": {"item": 123}}

    def test_to_values_yaml(self):
        """Test converting values to YAML format."""
        chart = ConcreteHelmChart()
        yaml_str = chart.to_values_yaml()
        assert "key: value" in yaml_str
        assert "nested:" in yaml_str
        assert "item: 123" in yaml_str

    def test_manifests_dir(self):
        """Test manifests_dir static method."""
        dir_path = HelmChart.manifests_dir()
        assert dir_path.is_absolute()
        assert "manifests" in str(dir_path)

    def test_argo_ignore_spec_default(self):
        """Test that argo_ignore_spec returns empty list by default."""
        chart = ConcreteHelmChart()
        assert chart.argo_ignore_spec() == []

    def test_application_repo_url_from_env(self, monkeypatch):
        """Test application_repo_url reads from environment."""
        chart = ConcreteHelmChart()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        assert chart.application_repo_url() == "https://github.com/test/repo"

    def test_application_repo_url_default(self, monkeypatch):
        """Test application_repo_url returns empty string if not set."""
        chart = ConcreteHelmChart()
        monkeypatch.delenv("ARGOCD_APP_REPO_URL", raising=False)
        assert chart.application_repo_url() == ""

    def test_application_target_revision(self, monkeypatch):
        """Test application_target_revision uses GitManager."""
        chart = ConcreteHelmChart()
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")
        with patch("builtins.print"):
            with patch.object(GitManager, "fetch_branch_name", return_value="main"):
                assert chart.application_target_revision() == "main"

    def test_managed_namespace_metadata_default(self):
        """Test that managed_namespace_metadata returns empty dict by default."""
        chart = ConcreteHelmChart()
        assert chart.managed_namespace_metadata() == {}

    def test_generate_application(self, monkeypatch):
        """Test generating ArgoCD Application manifest when enabled."""
        chart = ConcreteHelmChart()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")

        class EnabledChart(ConcreteHelmChart):
            def enable_argocd(self):
                return True

        enabled_chart = EnabledChart()
        with patch.object(GitManager, "fetch_branch_name", return_value="main"):
            app = enabled_chart.generate_application()

        assert app is not None
        assert app["apiVersion"] == "argoproj.io/v1alpha1"
        assert app["kind"] == "Application"
        assert app["metadata"]["name"] == "test-chart"
        assert app["metadata"]["namespace"] == "argocd"
        assert app["spec"]["source"]["repoURL"] == "https://github.com/test/repo"
        assert app["spec"]["source"]["targetRevision"] == "main"
        assert app["spec"]["source"]["path"] == "test-chart"
        assert app["spec"]["destination"]["namespace"] == "test-namespace"
        assert app["spec"]["syncPolicy"]["automated"]["prune"] is True
        assert app["spec"]["syncPolicy"]["automated"]["selfHeal"] is True

    def test_enable_argocd_default(self):
        """Test that enable_argocd defaults to False (opt-in)."""
        chart = ConcreteHelmChart()
        assert chart.enable_argocd() is False

    def test_generate_application_no_repo_url(self, monkeypatch):
        """Test that generate_application returns None if no repo URL."""
        chart = ConcreteHelmChart()
        monkeypatch.delenv("ARGOCD_APP_REPO_URL", raising=False)

        app = chart.generate_application()
        assert app is None

    def test_generate_application_disabled(self, monkeypatch):
        """Test that generate_application returns None if ArgoCD is disabled."""
        chart = ConcreteHelmChart()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")

        class DisabledChart(ConcreteHelmChart):
            def enable_argocd(self):
                return False

        disabled_chart = DisabledChart()
        app = disabled_chart.generate_application()
        assert app is None

    def test_generate_application_env_var_alone_not_enough(self, monkeypatch):
        """Test that setting ARGOCD_APP_REPO_URL alone doesn't enable ArgoCD (default off)."""
        chart = ConcreteHelmChart()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        # Don't override enable_argocd() - should default to False

        # Even with env var set, should return None because enable_argocd() defaults to False
        app = chart.generate_application()
        assert app is None

    def test_generate_application_opt_in_via_env(self, monkeypatch):
        """Test that ArgoCD can be enabled via environment variable."""
        chart = ConcreteHelmChart()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")

        class EnabledChart(ConcreteHelmChart):
            def enable_argocd(self):
                return True

        enabled_chart = EnabledChart()
        with patch.object(GitManager, "fetch_branch_name", return_value="main"):
            app = enabled_chart.generate_application()

        assert app is not None
        assert app["apiVersion"] == "argoproj.io/v1alpha1"
        assert app["spec"]["source"]["repoURL"] == "https://github.com/test/repo"

    def test_generate_application_with_managed_namespace_metadata(self, monkeypatch):
        """Test generating application with managed namespace metadata."""

        class ChartWithMetadata(ConcreteHelmChart):
            def enable_argocd(self):
                return True

            def managed_namespace_metadata(self):
                return {"label1": "value1", "label2": "value2"}

        chart = ChartWithMetadata()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")

        with patch.object(GitManager, "fetch_branch_name", return_value="main"):
            app = chart.generate_application()

        assert app is not None
        assert "managedNamespaceMetadata" in app["spec"]["syncPolicy"]
        assert app["spec"]["syncPolicy"]["managedNamespaceMetadata"]["labels"] == {
            "label1": "value1",
            "label2": "value2",
        }

    def test_extra_manifests_default(self):
        """Test that extra_manifests returns empty list by default."""
        chart = ConcreteHelmChart()
        assert chart.extra_manifests() == []

    def test_apps_subdirectory_from_env(self, monkeypatch):
        """Test apps_subdirectory reads from environment."""
        chart = ConcreteHelmChart()
        monkeypatch.setenv("ARGOCD_APPS_SUBDIR", "custom-apps")
        assert chart.apps_subdirectory() == "custom-apps"

    def test_apps_subdirectory_default(self, monkeypatch):
        """Test apps_subdirectory defaults to 'apps'."""
        chart = ConcreteHelmChart()
        monkeypatch.delenv("ARGOCD_APPS_SUBDIR", raising=False)
        assert chart.apps_subdirectory() == "apps"

    def test_full_helm_package_name_classic(self):
        """Test full_helm_package_name for classic repository."""
        chart = ConcreteHelmChart()
        with patch("kubeman.chart.get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            # Mock helm repo list (repo doesn't exist)
            mock_executor.run_silent.return_value = Mock(stdout="", stderr="")
            mock_executor.run.return_value = Mock(returncode=0)
            mock_get_executor.return_value = mock_executor

            package_name = chart.full_helm_package_name()
            assert "repo-test-chart" in package_name
            assert "test-chart" in package_name

    def test_full_helm_package_name_oci(self):
        """Test full_helm_package_name for OCI repository."""

        class OCIChart(ConcreteHelmChart):
            @property
            def repository(self):
                return {"type": "oci", "remote": "oci://registry.example.com"}

        chart = OCIChart()
        package_name = chart.full_helm_package_name()
        assert "registry.example.com" in package_name
        assert "test-chart" in package_name

    def test_full_helm_package_name_unknown_type(self):
        """Test full_helm_package_name raises error for unknown type."""

        class UnknownChart(ConcreteHelmChart):
            @property
            def repository(self):
                return {"type": "unknown", "remote": "https://example.com"}

        chart = UnknownChart()
        with pytest.raises(ValueError, match="Unknown repository type"):
            chart.full_helm_package_name()

    def test_ensure_helm_repo_adds_if_missing(self):
        """Test that ensure_helm_repo adds repo if it doesn't exist."""
        chart = ConcreteHelmChart()
        with patch("kubeman.chart.get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            # Mock helm repo list (repo doesn't exist)
            mock_executor.run_silent.return_value = Mock(stdout="", stderr="")
            mock_executor.run.return_value = Mock(returncode=0)
            mock_get_executor.return_value = mock_executor

            repo_name = chart.ensure_helm_repo()
            assert repo_name == "repo-test-chart"
            assert mock_executor.run.call_count == 2  # repo add + repo update
            assert mock_executor.run_silent.call_count == 1  # repo list

    def test_ensure_helm_repo_skips_if_exists(self):
        """Test that ensure_helm_repo skips adding if repo exists."""
        chart = ConcreteHelmChart()
        with patch("kubeman.chart.get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            # Mock helm repo list (repo exists)
            mock_executor.run_silent.return_value = Mock(
                stdout="repo-test-chart  https://charts.example.com", stderr=""
            )
            mock_executor.run.return_value = Mock(returncode=0)
            mock_get_executor.return_value = mock_executor

            repo_name = chart.ensure_helm_repo()
            assert repo_name == "repo-test-chart"
            # Should call repo list and repo update, but not repo add
            assert mock_executor.run_silent.call_count == 1
            assert mock_executor.run.call_count == 1  # repo update

    def test_render_helm_skips_if_none(self, tmp_path):
        """Test that render_helm skips if repository type is 'none'."""

        class NoRepoChart(ConcreteHelmChart):
            @property
            def repository(self):
                return {"type": "none"}

        chart = NoRepoChart()
        # Should not raise error and should not call helm
        with patch("kubeman.chart.get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_get_executor.return_value = mock_executor

            chart.render_helm()
            # Should not call helm template
            assert mock_executor.run.call_count == 0

    def test_render_extra_with_valid_manifests(self, tmp_path):
        """Test rendering extra manifests."""

        class ChartWithExtras(ConcreteHelmChart):
            def extra_manifests(self):
                return [
                    {
                        "apiVersion": "v1",
                        "kind": "ConfigMap",
                        "metadata": {"name": "test-config"},
                        "data": {"key": "value"},
                    }
                ]

        chart = ChartWithExtras()
        with patch.object(chart, "manifests_dir", return_value=str(tmp_path)):
            chart.render_extra()
            output_file = tmp_path / "test-chart" / "test-config-configmap.yaml"
            assert output_file.exists()

    def test_render_extra_no_metadata(self):
        """Test that render_extra raises error if manifest has no metadata."""

        class ChartWithInvalidExtras(ConcreteHelmChart):
            def extra_manifests(self):
                return [{"kind": "ConfigMap"}]

        chart = ChartWithInvalidExtras()
        with pytest.raises(ValueError, match="no metadata"):
            chart.render_extra()

    def test_render_extra_no_kind(self):
        """Test that render_extra raises error if manifest has no kind."""

        class ChartWithInvalidExtras(ConcreteHelmChart):
            def extra_manifests(self):
                return [{"metadata": {"name": "test"}}]

        chart = ChartWithInvalidExtras()
        with pytest.raises(ValueError, match="no kind"):
            chart.render_extra()

    def test_render_extra_duplicate_file(self, tmp_path):
        """Test that render_extra overwrites existing file."""

        class ChartWithExtras(ConcreteHelmChart):
            def extra_manifests(self):
                return [
                    {
                        "apiVersion": "v1",
                        "kind": "ConfigMap",
                        "metadata": {"name": "test-config"},
                        "data": {"key": "new-value"},
                    }
                ]

        chart = ChartWithExtras()
        output_dir = tmp_path / "test-chart"
        output_dir.mkdir(parents=True)
        existing_file = output_dir / "test-config-configmap.yaml"
        existing_file.write_text("existing")

        with patch.object(chart, "manifests_dir", return_value=str(tmp_path)):
            chart.render_extra()
            # Verify file was overwritten with new content
            assert existing_file.exists()
            content = existing_file.read_text()
            assert "new-value" in content
            assert "existing" not in content


class ConcreteKubernetesResource(KubernetesResource):
    """Concrete implementation of KubernetesResource for testing."""

    @property
    def name(self):
        return "test-resource"

    @property
    def namespace(self):
        return "test-namespace"

    def manifests(self):
        return [
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": "test-config", "namespace": "test-namespace"},
                "data": {"key": "value"},
            },
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "test-deployment", "namespace": "test-namespace"},
                "spec": {
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "test"}},
                    "template": {
                        "metadata": {"labels": {"app": "test"}},
                        "spec": {"containers": [{"name": "test", "image": "nginx:latest"}]},
                    },
                },
            },
        ]


class TestKubernetesResource:
    """Test cases for KubernetesResource class."""

    def test_name_property(self):
        """Test that name property is abstract and must be implemented."""
        resource = ConcreteKubernetesResource()
        assert resource.name == "test-resource"

    def test_namespace_property(self):
        """Test that namespace property is abstract and must be implemented."""
        resource = ConcreteKubernetesResource()
        assert resource.namespace == "test-namespace"

    def test_manifests_method(self):
        """Test that manifests method is abstract and must be implemented."""
        resource = ConcreteKubernetesResource()
        manifests = resource.manifests()
        assert len(manifests) == 2
        assert manifests[0]["kind"] == "ConfigMap"
        assert manifests[1]["kind"] == "Deployment"

    def test_manifests_dir(self):
        """Test manifests_dir static method."""
        dir_path = KubernetesResource.manifests_dir()
        assert dir_path.is_absolute()
        assert "manifests" in str(dir_path)

    def test_argo_ignore_spec_default(self):
        """Test that argo_ignore_spec returns empty list by default."""
        resource = ConcreteKubernetesResource()
        assert resource.argo_ignore_spec() == []

    def test_application_repo_url_from_env(self, monkeypatch):
        """Test application_repo_url reads from environment."""
        resource = ConcreteKubernetesResource()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        assert resource.application_repo_url() == "https://github.com/test/repo"

    def test_application_repo_url_default(self, monkeypatch):
        """Test application_repo_url returns empty string if not set."""
        resource = ConcreteKubernetesResource()
        monkeypatch.delenv("ARGOCD_APP_REPO_URL", raising=False)
        assert resource.application_repo_url() == ""

    def test_application_target_revision(self, monkeypatch):
        """Test application_target_revision uses GitManager."""
        resource = ConcreteKubernetesResource()
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")
        with patch("builtins.print"):
            with patch.object(GitManager, "fetch_branch_name", return_value="main"):
                assert resource.application_target_revision() == "main"

    def test_managed_namespace_metadata_default(self):
        """Test that managed_namespace_metadata returns empty dict by default."""
        resource = ConcreteKubernetesResource()
        assert resource.managed_namespace_metadata() == {}

    def test_generate_application(self, monkeypatch):
        """Test generating ArgoCD Application manifest when enabled."""
        resource = ConcreteKubernetesResource()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")

        class EnabledResource(ConcreteKubernetesResource):
            def enable_argocd(self):
                return True

        enabled_resource = EnabledResource()
        with patch.object(GitManager, "fetch_branch_name", return_value="main"):
            app = enabled_resource.generate_application()

        assert app is not None
        assert app["apiVersion"] == "argoproj.io/v1alpha1"
        assert app["kind"] == "Application"
        assert app["metadata"]["name"] == "test-resource"
        assert app["metadata"]["namespace"] == "argocd"
        assert app["spec"]["source"]["repoURL"] == "https://github.com/test/repo"
        assert app["spec"]["source"]["targetRevision"] == "main"
        assert app["spec"]["source"]["path"] == "test-resource"
        assert app["spec"]["destination"]["namespace"] == "test-namespace"
        assert app["spec"]["syncPolicy"]["automated"]["prune"] is True
        assert app["spec"]["syncPolicy"]["automated"]["selfHeal"] is True

    def test_enable_argocd_default(self):
        """Test that enable_argocd defaults to False (opt-in)."""
        resource = ConcreteKubernetesResource()
        assert resource.enable_argocd() is False

    def test_generate_application_no_repo_url(self, monkeypatch):
        """Test that generate_application returns None if no repo URL."""
        resource = ConcreteKubernetesResource()
        monkeypatch.delenv("ARGOCD_APP_REPO_URL", raising=False)

        app = resource.generate_application()
        assert app is None

    def test_generate_application_disabled(self, monkeypatch):
        """Test that generate_application returns None if ArgoCD is disabled."""
        resource = ConcreteKubernetesResource()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")

        class DisabledResource(ConcreteKubernetesResource):
            def enable_argocd(self):
                return False

        disabled_resource = DisabledResource()
        app = disabled_resource.generate_application()
        assert app is None

    def test_generate_application_env_var_alone_not_enough(self, monkeypatch):
        """Test that setting ARGOCD_APP_REPO_URL alone doesn't enable ArgoCD (default off)."""
        resource = ConcreteKubernetesResource()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        # Don't override enable_argocd() - should default to False

        # Even with env var set, should return None because enable_argocd() defaults to False
        app = resource.generate_application()
        assert app is None

    def test_generate_application_opt_in_via_env(self, monkeypatch):
        """Test that ArgoCD can be enabled via environment variable."""
        resource = ConcreteKubernetesResource()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")

        class EnabledResource(ConcreteKubernetesResource):
            def enable_argocd(self):
                return True

        enabled_resource = EnabledResource()
        with patch.object(GitManager, "fetch_branch_name", return_value="main"):
            app = enabled_resource.generate_application()

        assert app is not None
        assert app["apiVersion"] == "argoproj.io/v1alpha1"
        assert app["spec"]["source"]["repoURL"] == "https://github.com/test/repo"

    def test_generate_application_with_managed_namespace_metadata(self, monkeypatch):
        """Test generating application with managed namespace metadata."""

        class ResourceWithMetadata(ConcreteKubernetesResource):
            def enable_argocd(self):
                return True

            def managed_namespace_metadata(self):
                return {"label1": "value1", "label2": "value2"}

        resource = ResourceWithMetadata()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")

        with patch.object(GitManager, "fetch_branch_name", return_value="main"):
            app = resource.generate_application()

        assert app is not None
        assert "managedNamespaceMetadata" in app["spec"]["syncPolicy"]
        assert app["spec"]["syncPolicy"]["managedNamespaceMetadata"]["labels"] == {
            "label1": "value1",
            "label2": "value2",
        }

    def test_apps_subdirectory_from_env(self, monkeypatch):
        """Test apps_subdirectory reads from environment."""
        resource = ConcreteKubernetesResource()
        monkeypatch.setenv("ARGOCD_APPS_SUBDIR", "custom-apps")
        assert resource.apps_subdirectory() == "custom-apps"

    def test_apps_subdirectory_default(self, monkeypatch):
        """Test apps_subdirectory defaults to 'apps'."""
        resource = ConcreteKubernetesResource()
        monkeypatch.delenv("ARGOCD_APPS_SUBDIR", raising=False)
        assert resource.apps_subdirectory() == "apps"

    def test_render_manifests_with_valid_manifests(self, tmp_path):
        """Test rendering manifests."""
        resource = ConcreteKubernetesResource()
        with patch.object(resource, "manifests_dir", return_value=str(tmp_path)):
            resource.render_manifests()
            # Check that both manifests were created
            config_file = tmp_path / "test-resource" / "test-config-configmap.yaml"
            deployment_file = tmp_path / "test-resource" / "test-deployment-deployment.yaml"
            assert config_file.exists()
            assert deployment_file.exists()

    def test_render_manifests_no_metadata(self):
        """Test that render_manifests raises error if manifest has no metadata."""

        class ResourceWithInvalidManifests(ConcreteKubernetesResource):
            def manifests(self):
                return [{"kind": "ConfigMap"}]

        resource = ResourceWithInvalidManifests()
        with pytest.raises(ValueError, match="no metadata"):
            resource.render_manifests()

    def test_render_manifests_no_kind(self):
        """Test that render_manifests raises error if manifest has no kind."""

        class ResourceWithInvalidManifests(ConcreteKubernetesResource):
            def manifests(self):
                return [{"metadata": {"name": "test"}}]

        resource = ResourceWithInvalidManifests()
        with pytest.raises(ValueError, match="no kind"):
            resource.render_manifests()

    def test_render_manifests_duplicate_file(self, tmp_path):
        """Test that render_manifests overwrites existing file."""

        class ResourceWithManifests(ConcreteKubernetesResource):
            def manifests(self):
                return [
                    {
                        "apiVersion": "v1",
                        "kind": "ConfigMap",
                        "metadata": {"name": "test-config"},
                        "data": {"key": "new-value"},
                    }
                ]

        resource = ResourceWithManifests()
        output_dir = tmp_path / "test-resource"
        output_dir.mkdir(parents=True)
        existing_file = output_dir / "test-config-configmap.yaml"
        existing_file.write_text("existing")

        with patch.object(resource, "manifests_dir", return_value=str(tmp_path)):
            resource.render_manifests()
            # Verify file was overwritten with new content
            assert existing_file.exists()
            content = existing_file.read_text()
            assert "new-value" in content
            assert "existing" not in content

    def test_render_manifests_empty_list(self, tmp_path, capsys):
        """Test that render_manifests handles empty manifest list."""

        class ResourceWithNoManifests(ConcreteKubernetesResource):
            def manifests(self):
                return []

        resource = ResourceWithNoManifests()
        with patch.object(resource, "manifests_dir", return_value=str(tmp_path)):
            resource.render_manifests()
            captured = capsys.readouterr()
            assert "No manifests for test-resource" in captured.out

    def test_render(self, tmp_path, monkeypatch):
        """Test full render process with ArgoCD enabled."""
        resource = ConcreteKubernetesResource()
        monkeypatch.setenv("ARGOCD_APP_REPO_URL", "https://github.com/test/repo")
        monkeypatch.setenv("STABLE_GIT_BRANCH", "main")

        class EnabledResource(ConcreteKubernetesResource):
            def enable_argocd(self):
                return True

        enabled_resource = EnabledResource()
        with patch.object(enabled_resource, "manifests_dir", return_value=str(tmp_path)):
            with patch.object(GitManager, "fetch_branch_name", return_value="main"):
                enabled_resource.render()

        # Check that manifests were created
        config_file = tmp_path / "test-resource" / "test-config-configmap.yaml"
        deployment_file = tmp_path / "test-resource" / "test-deployment-deployment.yaml"
        assert config_file.exists()
        assert deployment_file.exists()

        # Check that Application manifest was created
        app_file = tmp_path / "apps" / "test-resource-application.yaml"
        assert app_file.exists()

    def test_render_without_argocd(self, tmp_path, monkeypatch):
        """Test render process skips ArgoCD when disabled."""
        resource = ConcreteKubernetesResource()
        monkeypatch.delenv("ARGOCD_APP_REPO_URL", raising=False)

        with patch.object(resource, "manifests_dir", return_value=str(tmp_path)):
            resource.render()

        # Check that manifests were created
        config_file = tmp_path / "test-resource" / "test-config-configmap.yaml"
        deployment_file = tmp_path / "test-resource" / "test-deployment-deployment.yaml"
        assert config_file.exists()
        assert deployment_file.exists()

        # Check that Application manifest was NOT created
        app_file = tmp_path / "apps" / "test-resource-application.yaml"
        assert not app_file.exists()
