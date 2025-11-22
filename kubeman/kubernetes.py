import os
import yaml
from typing import Any, Optional
from kubeman.template import Template


class KubernetesResource(Template):
    """
    Class for managing raw Kubernetes resources without Helm.

    This class provides two usage patterns:

    1. **Direct instantiation with helper methods**: Create resources using convenience
       methods like add_deployment(), add_service(), etc.

    2. **Subclass and override manifests()**: For custom resource generation logic,
       subclass and implement the manifests() method directly.

    Both patterns support ArgoCD Application generation and manifest management.
    """

    def __init__(self):
        self._manifests: list[dict] = []
        self._name: Optional[str] = None
        self._namespace: Optional[str] = None

    @property
    def name(self) -> str:
        """Return the name of the resource collection"""
        if self._name is None:
            # Use class name in kebab-case as default
            class_name = self.__class__.__name__
            # Convert CamelCase to kebab-case
            name = "".join(["-" + c.lower() if c.isupper() else c for c in class_name]).lstrip("-")
            self._name = name.replace("_", "-")
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the name for the resource collection"""
        self._name = value

    @property
    def namespace(self) -> str:
        """Return the namespace where resources should be deployed"""
        if self._namespace is None:
            raise ValueError("Namespace must be set before calling render()")
        return self._namespace

    @namespace.setter
    def namespace(self, value: str) -> None:
        """Set the namespace for resources"""
        self._namespace = value

    def manifests(self) -> list[dict]:
        """
        Return list of Kubernetes manifest dictionaries to be rendered.

        Override this method in subclasses for custom manifest generation,
        or use the helper methods (add_deployment, add_service, etc.) to build manifests.
        """
        return self._manifests

    def add_namespace(
        self,
        name: str,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a Namespace resource"""
        manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": name},
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        self._manifests.append(manifest)

    def add_configmap(
        self,
        name: str,
        namespace: str,
        data: Optional[dict[str, str]] = None,
        binary_data: Optional[dict[str, str]] = None,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a ConfigMap resource"""
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": name, "namespace": namespace},
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        if data:
            manifest["data"] = data
        if binary_data:
            manifest["binaryData"] = binary_data
        self._manifests.append(manifest)

    def add_secret(
        self,
        name: str,
        namespace: str,
        data: Optional[dict[str, str]] = None,
        string_data: Optional[dict[str, str]] = None,
        secret_type: str = "Opaque",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a Secret resource"""
        manifest = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": name, "namespace": namespace},
            "type": secret_type,
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        if data:
            manifest["data"] = data
        if string_data:
            manifest["stringData"] = string_data
        self._manifests.append(manifest)

    def add_persistent_volume_claim(
        self,
        name: str,
        namespace: str,
        access_modes: list[str],
        storage: str,
        storage_class_name: Optional[str] = None,
        volume_mode: str = "Filesystem",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a PersistentVolumeClaim resource"""
        manifest = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "accessModes": access_modes,
                "resources": {"requests": {"storage": storage}},
                "volumeMode": volume_mode,
            },
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        if storage_class_name:
            manifest["spec"]["storageClassName"] = storage_class_name
        self._manifests.append(manifest)

    def add_deployment(
        self,
        name: str,
        namespace: str,
        replicas: int,
        containers: list[dict[str, Any]],
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
        selector: Optional[dict[str, str]] = None,
        volumes: Optional[list[dict[str, Any]]] = None,
        strategy_type: Optional[str] = None,
        init_containers: Optional[list[dict[str, Any]]] = None,
        service_account_name: Optional[str] = None,
        security_context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a Deployment resource"""
        # Use labels as selector if not provided
        pod_labels = labels or {}
        pod_selector = selector or pod_labels

        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": pod_selector},
                "template": {
                    "metadata": {"labels": pod_labels},
                    "spec": {"containers": containers},
                },
            },
        }

        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        if volumes:
            manifest["spec"]["template"]["spec"]["volumes"] = volumes
        if strategy_type:
            manifest["spec"]["strategy"] = {"type": strategy_type}
        if init_containers:
            manifest["spec"]["template"]["spec"]["initContainers"] = init_containers
        if service_account_name:
            manifest["spec"]["template"]["spec"]["serviceAccountName"] = service_account_name
        if security_context:
            manifest["spec"]["template"]["spec"]["securityContext"] = security_context

        self._manifests.append(manifest)

    def add_service(
        self,
        name: str,
        namespace: str,
        selector: dict[str, str],
        ports: list[dict[str, Any]],
        service_type: str = "ClusterIP",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
        cluster_ip: Optional[str] = None,
        external_traffic_policy: Optional[str] = None,
    ) -> None:
        """Add a Service resource"""
        manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "type": service_type,
                "selector": selector,
                "ports": ports,
            },
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        if cluster_ip:
            manifest["spec"]["clusterIP"] = cluster_ip
        if external_traffic_policy:
            manifest["spec"]["externalTrafficPolicy"] = external_traffic_policy
        self._manifests.append(manifest)

    def add_statefulset(
        self,
        name: str,
        namespace: str,
        replicas: int,
        service_name: str,
        containers: list[dict[str, Any]],
        volume_claim_templates: Optional[list[dict[str, Any]]] = None,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
        selector: Optional[dict[str, str]] = None,
        volumes: Optional[list[dict[str, Any]]] = None,
        init_containers: Optional[list[dict[str, Any]]] = None,
        service_account_name: Optional[str] = None,
        security_context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a StatefulSet resource"""
        pod_labels = labels or {}
        pod_selector = selector or pod_labels

        manifest = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {
                "serviceName": service_name,
                "replicas": replicas,
                "selector": {"matchLabels": pod_selector},
                "template": {
                    "metadata": {"labels": pod_labels},
                    "spec": {"containers": containers},
                },
            },
        }

        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        if volumes:
            manifest["spec"]["template"]["spec"]["volumes"] = volumes
        if volume_claim_templates:
            manifest["spec"]["volumeClaimTemplates"] = volume_claim_templates
        if init_containers:
            manifest["spec"]["template"]["spec"]["initContainers"] = init_containers
        if service_account_name:
            manifest["spec"]["template"]["spec"]["serviceAccountName"] = service_account_name
        if security_context:
            manifest["spec"]["template"]["spec"]["securityContext"] = security_context

        self._manifests.append(manifest)

    def add_ingress(
        self,
        name: str,
        namespace: str,
        rules: list[dict[str, Any]],
        ingress_class_name: Optional[str] = None,
        tls: Optional[list[dict[str, Any]]] = None,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add an Ingress resource"""
        manifest = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {"name": name, "namespace": namespace},
            "spec": {"rules": rules},
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        if ingress_class_name:
            manifest["spec"]["ingressClassName"] = ingress_class_name
        if tls:
            manifest["spec"]["tls"] = tls
        self._manifests.append(manifest)

    def add_service_account(
        self,
        name: str,
        namespace: str,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a ServiceAccount resource"""
        manifest = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": name, "namespace": namespace},
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        self._manifests.append(manifest)

    def add_role(
        self,
        name: str,
        namespace: str,
        rules: list[dict[str, Any]],
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a Role resource"""
        manifest = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {"name": name, "namespace": namespace},
            "rules": rules,
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        self._manifests.append(manifest)

    def add_role_binding(
        self,
        name: str,
        namespace: str,
        role_name: str,
        subjects: list[dict[str, Any]],
        role_kind: str = "Role",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a RoleBinding resource"""
        manifest = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {"name": name, "namespace": namespace},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": role_kind,
                "name": role_name,
            },
            "subjects": subjects,
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        self._manifests.append(manifest)

    def add_cluster_role(
        self,
        name: str,
        rules: list[dict[str, Any]],
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a ClusterRole resource"""
        manifest = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {"name": name},
            "rules": rules,
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        self._manifests.append(manifest)

    def add_cluster_role_binding(
        self,
        name: str,
        role_name: str,
        subjects: list[dict[str, Any]],
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a ClusterRoleBinding resource"""
        manifest = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {"name": name},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": role_name,
            },
            "subjects": subjects,
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        self._manifests.append(manifest)

    def add_custom_resource(self, manifest: dict[str, Any]) -> None:
        """Add a custom Kubernetes resource manifest"""
        if not manifest.get("apiVersion"):
            raise ValueError("Manifest must have apiVersion")
        if not manifest.get("kind"):
            raise ValueError("Manifest must have kind")
        if not manifest.get("metadata") or not manifest["metadata"].get("name"):
            raise ValueError("Manifest must have metadata.name")
        self._manifests.append(manifest)

    def render(self) -> None:
        """
        Render Kubernetes manifests and ArgoCD Application.
        """
        # Render manifests
        self.render_manifests()

        # Write Application manifest if ArgoCD is enabled
        if self.enable_argocd() and self.application_repo_url():
            self._write_application()

    def render_manifests(self) -> None:
        """
        Render all Kubernetes manifests.
        Each manifest will be written to a separate file named after its metadata.name.
        """
        manifests = self.manifests()
        if not manifests:
            print(f"No manifests for {self.name}")
            return

        print(f"\nRendering {len(manifests)} manifests for {self.name}...")
        output_dir = os.path.join(self.manifests_dir(), self.name)
        os.makedirs(output_dir, exist_ok=True)

        for manifest in manifests:
            if not manifest.get("metadata") or not manifest["metadata"].get("name"):
                raise ValueError(f"Manifest {manifest} has no metadata or name")

            if not manifest.get("kind"):
                raise ValueError(f"Manifest {manifest} has no kind")

            manifest_name = manifest["metadata"]["name"]
            manifest_kind = manifest["kind"].lower()
            output_file = os.path.join(output_dir, f"{manifest_name}-{manifest_kind}.yaml")

            if os.path.exists(output_file):
                raise ValueError(
                    f"Skipping {manifest_name}-{manifest_kind} because it already exists"
                )

            print(f"Writing manifest {manifest_name} ({manifest_kind}) to {output_file}")

            with open(output_file, "w") as f:
                yaml.dump(manifest, f)
