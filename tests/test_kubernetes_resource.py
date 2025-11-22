"""Tests for KubernetesResource class."""

import pytest
from kubeman import KubernetesResource, TemplateRegistry


class TestKubernetesResource:
    """Test the KubernetesResource helper class."""

    def test_basic_initialization(self):
        """Test basic initialization and properties."""
        resources = KubernetesResource()
        resources.namespace = "test-namespace"

        assert resources.namespace == "test-namespace"
        assert resources.manifests() == []

    def test_add_namespace(self):
        """Test adding a namespace resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_namespace(
            name="test-namespace",
            labels={"app": "test"},
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "Namespace"
        assert manifests[0]["metadata"]["name"] == "test-namespace"
        assert manifests[0]["metadata"]["labels"] == {"app": "test"}

    def test_add_configmap(self):
        """Test adding a configmap resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_configmap(
            name="test-config",
            namespace="test",
            data={"key": "value"},
            labels={"app": "test"},
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "ConfigMap"
        assert manifests[0]["metadata"]["name"] == "test-config"
        assert manifests[0]["data"] == {"key": "value"}

    def test_add_secret(self):
        """Test adding a secret resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_secret(
            name="test-secret",
            namespace="test",
            string_data={"password": "secret123"},
            labels={"app": "test"},
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "Secret"
        assert manifests[0]["metadata"]["name"] == "test-secret"
        assert manifests[0]["stringData"] == {"password": "secret123"}
        assert manifests[0]["type"] == "Opaque"

    def test_add_persistent_volume_claim(self):
        """Test adding a PVC resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_persistent_volume_claim(
            name="test-pvc",
            namespace="test",
            access_modes=["ReadWriteOnce"],
            storage="5Gi",
            labels={"app": "test"},
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "PersistentVolumeClaim"
        assert manifests[0]["metadata"]["name"] == "test-pvc"
        assert manifests[0]["spec"]["accessModes"] == ["ReadWriteOnce"]
        assert manifests[0]["spec"]["resources"]["requests"]["storage"] == "5Gi"

    def test_add_deployment(self):
        """Test adding a deployment resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_deployment(
            name="test-deployment",
            namespace="test",
            replicas=3,
            labels={"app": "test"},
            containers=[
                {
                    "name": "nginx",
                    "image": "nginx:latest",
                    "ports": [{"containerPort": 80}],
                }
            ],
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "Deployment"
        assert manifests[0]["metadata"]["name"] == "test-deployment"
        assert manifests[0]["spec"]["replicas"] == 3
        assert len(manifests[0]["spec"]["template"]["spec"]["containers"]) == 1

    def test_add_service(self):
        """Test adding a service resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_service(
            name="test-service",
            namespace="test",
            service_type="ClusterIP",
            selector={"app": "test"},
            ports=[{"port": 80, "targetPort": 8080}],
            labels={"app": "test"},
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "Service"
        assert manifests[0]["metadata"]["name"] == "test-service"
        assert manifests[0]["spec"]["type"] == "ClusterIP"
        assert manifests[0]["spec"]["selector"] == {"app": "test"}

    def test_add_statefulset(self):
        """Test adding a statefulset resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_statefulset(
            name="test-statefulset",
            namespace="test",
            replicas=3,
            service_name="test-service",
            labels={"app": "test"},
            containers=[
                {
                    "name": "postgres",
                    "image": "postgres:16",
                    "ports": [{"containerPort": 5432}],
                }
            ],
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "StatefulSet"
        assert manifests[0]["metadata"]["name"] == "test-statefulset"
        assert manifests[0]["spec"]["serviceName"] == "test-service"
        assert manifests[0]["spec"]["replicas"] == 3

    def test_add_ingress(self):
        """Test adding an ingress resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_ingress(
            name="test-ingress",
            namespace="test",
            rules=[
                {
                    "host": "example.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": "test-service",
                                        "port": {"number": 80},
                                    }
                                },
                            }
                        ]
                    },
                }
            ],
            ingress_class_name="nginx",
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "Ingress"
        assert manifests[0]["metadata"]["name"] == "test-ingress"
        assert manifests[0]["spec"]["ingressClassName"] == "nginx"

    def test_add_service_account(self):
        """Test adding a service account resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_service_account(
            name="test-sa",
            namespace="test",
            labels={"app": "test"},
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "ServiceAccount"
        assert manifests[0]["metadata"]["name"] == "test-sa"

    def test_add_role(self):
        """Test adding a role resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_role(
            name="test-role",
            namespace="test",
            rules=[
                {
                    "apiGroups": [""],
                    "resources": ["pods"],
                    "verbs": ["get", "list"],
                }
            ],
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "Role"
        assert manifests[0]["metadata"]["name"] == "test-role"

    def test_add_role_binding(self):
        """Test adding a role binding resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_role_binding(
            name="test-role-binding",
            namespace="test",
            role_name="test-role",
            subjects=[
                {
                    "kind": "ServiceAccount",
                    "name": "test-sa",
                    "namespace": "test",
                }
            ],
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "RoleBinding"
        assert manifests[0]["metadata"]["name"] == "test-role-binding"

    def test_add_cluster_role(self):
        """Test adding a cluster role resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_cluster_role(
            name="test-cluster-role",
            rules=[
                {
                    "apiGroups": [""],
                    "resources": ["nodes"],
                    "verbs": ["get", "list"],
                }
            ],
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "ClusterRole"
        assert manifests[0]["metadata"]["name"] == "test-cluster-role"

    def test_add_cluster_role_binding(self):
        """Test adding a cluster role binding resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_cluster_role_binding(
            name="test-cluster-role-binding",
            role_name="test-cluster-role",
            subjects=[
                {
                    "kind": "ServiceAccount",
                    "name": "test-sa",
                    "namespace": "test",
                }
            ],
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "ClusterRoleBinding"
        assert manifests[0]["metadata"]["name"] == "test-cluster-role-binding"

    def test_add_custom_resource(self):
        """Test adding a custom resource."""
        resources = KubernetesResource()
        resources.namespace = "test"

        custom_manifest = {
            "apiVersion": "custom.example.com/v1",
            "kind": "CustomResource",
            "metadata": {"name": "test-custom", "namespace": "test"},
            "spec": {"foo": "bar"},
        }

        resources.add_custom_resource(custom_manifest)

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["kind"] == "CustomResource"
        assert manifests[0]["apiVersion"] == "custom.example.com/v1"

    def test_add_custom_resource_validation(self):
        """Test custom resource validation."""
        resources = KubernetesResource()
        resources.namespace = "test"

        # Missing apiVersion
        with pytest.raises(ValueError, match="apiVersion"):
            resources.add_custom_resource({"kind": "Test", "metadata": {"name": "test"}})

        # Missing kind
        with pytest.raises(ValueError, match="kind"):
            resources.add_custom_resource({"apiVersion": "v1", "metadata": {"name": "test"}})

        # Missing metadata.name
        with pytest.raises(ValueError, match="metadata.name"):
            resources.add_custom_resource({"apiVersion": "v1", "kind": "Test"})

    def test_multiple_resources(self):
        """Test adding multiple resources."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_namespace(name="test", labels={"app": "test"})
        resources.add_configmap(
            name="config",
            namespace="test",
            data={"key": "value"},
        )
        resources.add_secret(
            name="secret",
            namespace="test",
            string_data={"password": "secret"},
        )

        manifests = resources.manifests()
        assert len(manifests) == 3
        assert manifests[0]["kind"] == "Namespace"
        assert manifests[1]["kind"] == "ConfigMap"
        assert manifests[2]["kind"] == "Secret"

    def test_registry_decorator(self):
        """Test using TemplateRegistry decorator with KubernetesResource."""
        TemplateRegistry.clear()

        @TemplateRegistry.register
        class TestChart(KubernetesResource):
            def __init__(self):
                super().__init__()
                self.namespace = "test"

        registered = TemplateRegistry.get_registered_templates()
        assert len(registered) == 1
        assert registered[0] == TestChart

        # Test instantiation
        chart = TestChart()
        assert chart.namespace == "test"

    def test_default_name_from_class_name(self):
        """Test that name is derived from class name if not set."""

        class MyTestChart(KubernetesResource):
            def __init__(self):
                super().__init__()
                self.namespace = "test"

        chart = MyTestChart()
        assert chart.name == "my-test-chart"

    def test_deployment_with_volumes(self):
        """Test deployment with volumes."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_deployment(
            name="test-deployment",
            namespace="test",
            replicas=1,
            labels={"app": "test"},
            containers=[
                {
                    "name": "app",
                    "image": "nginx:latest",
                    "volumeMounts": [{"name": "data", "mountPath": "/data"}],
                }
            ],
            volumes=[{"name": "data", "emptyDir": {}}],
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert "volumes" in manifests[0]["spec"]["template"]["spec"]
        assert manifests[0]["spec"]["template"]["spec"]["volumes"][0]["name"] == "data"

    def test_service_node_port(self):
        """Test service with NodePort."""
        resources = KubernetesResource()
        resources.namespace = "test"

        resources.add_service(
            name="test-service",
            namespace="test",
            service_type="NodePort",
            selector={"app": "test"},
            ports=[{"port": 80, "targetPort": 8080, "nodePort": 30080}],
        )

        manifests = resources.manifests()
        assert len(manifests) == 1
        assert manifests[0]["spec"]["type"] == "NodePort"
        assert manifests[0]["spec"]["ports"][0]["nodePort"] == 30080
