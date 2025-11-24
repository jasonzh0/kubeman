from pathlib import Path
import yaml
from typing import Any, Optional
from kubeman.template import Template
from kubeman.output import get_output


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
            class_name = self.__class__.__name__
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

    def _get_namespace(self, namespace: Optional[str] = None) -> str:
        """
        Get namespace, using provided value or falling back to self.namespace.

        Args:
            namespace: Optional namespace parameter

        Returns:
            The namespace to use

        Raises:
            ValueError: If neither namespace parameter nor self.namespace is set
        """
        if namespace is not None:
            return namespace
        if self._namespace is None:
            raise ValueError("Namespace must be set via self.namespace or provided as parameter")
        return self._namespace

    def add_namespace(
        self,
        name: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Add a Namespace resource.

        Args:
            name: Namespace name. Defaults to self.namespace if not provided.
            labels: Optional labels for the namespace
            annotations: Optional annotations for the namespace
        """
        namespace_name = name or self._get_namespace()
        manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": namespace_name},
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        self._manifests.append(manifest)

    def add_configmap(
        self,
        name: str,
        namespace: Optional[str] = None,
        data: Optional[dict[str, str]] = None,
        binary_data: Optional[dict[str, str]] = None,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a ConfigMap resource"""
        ns = self._get_namespace(namespace)
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": name, "namespace": ns},
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
        namespace: Optional[str] = None,
        data: Optional[dict[str, str]] = None,
        string_data: Optional[dict[str, str]] = None,
        secret_type: str = "Opaque",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a Secret resource"""
        ns = self._get_namespace(namespace)
        manifest = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": name, "namespace": ns},
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
        access_modes: list[str],
        storage: str,
        namespace: Optional[str] = None,
        storage_class_name: Optional[str] = None,
        volume_mode: str = "Filesystem",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a PersistentVolumeClaim resource"""
        ns = self._get_namespace(namespace)
        manifest = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": name, "namespace": ns},
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
        containers: list[dict[str, Any]],
        namespace: Optional[str] = None,
        replicas: int = 1,
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
        ns = self._get_namespace(namespace)
        pod_labels = labels or {}
        pod_selector = selector or pod_labels

        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": ns},
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
        selector: dict[str, str],
        ports: list[dict[str, Any]],
        namespace: Optional[str] = None,
        service_type: str = "ClusterIP",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
        cluster_ip: Optional[str] = None,
        external_traffic_policy: Optional[str] = None,
    ) -> None:
        """Add a Service resource"""
        ns = self._get_namespace(namespace)
        manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": ns},
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
        service_name: str,
        containers: list[dict[str, Any]],
        namespace: Optional[str] = None,
        replicas: int = 1,
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
        ns = self._get_namespace(namespace)
        pod_labels = labels or {}
        pod_selector = selector or pod_labels

        manifest = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": name, "namespace": ns},
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
        rules: list[dict[str, Any]],
        namespace: Optional[str] = None,
        ingress_class_name: Optional[str] = None,
        tls: Optional[list[dict[str, Any]]] = None,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add an Ingress resource"""
        ns = self._get_namespace(namespace)
        manifest = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {"name": name, "namespace": ns},
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
        namespace: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a ServiceAccount resource"""
        ns = self._get_namespace(namespace)
        manifest = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": name, "namespace": ns},
        }
        if labels:
            manifest["metadata"]["labels"] = labels
        if annotations:
            manifest["metadata"]["annotations"] = annotations
        self._manifests.append(manifest)

    def add_role(
        self,
        name: str,
        rules: list[dict[str, Any]],
        namespace: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a Role resource"""
        ns = self._get_namespace(namespace)
        manifest = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {"name": name, "namespace": ns},
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
        role_name: str,
        subjects: list[dict[str, Any]],
        namespace: Optional[str] = None,
        role_kind: str = "Role",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a RoleBinding resource"""
        ns = self._get_namespace(namespace)
        manifest = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {"name": name, "namespace": ns},
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
        self.render_manifests()

        if self.enable_argocd() and self.application_repo_url():
            self._write_application()

    def extra_manifests(self) -> list[dict]:
        """
        Return any additional manifests that should be rendered.

        Override this method in subclasses to add extra manifests beyond those
        added via helper methods or the manifests() method.
        """
        return []

    def render_manifests(self) -> None:
        """
        Render all Kubernetes manifests.
        Each manifest will be written to a separate file named after its metadata.name.
        """
        output = get_output()
        manifests = self.manifests()
        extra_manifests = self.extra_manifests()
        all_manifests = manifests + extra_manifests

        if not all_manifests:
            output.print(f"No manifests for {self.name}")
            return

        output.verbose(f"Rendering {len(all_manifests)} manifests for {self.name}")
        manifests_dir = self.manifests_dir()
        if isinstance(manifests_dir, str):
            manifests_dir = Path(manifests_dir)
        output_dir = manifests_dir / self.name
        output_dir.mkdir(parents=True, exist_ok=True)

        for manifest in all_manifests:
            if not manifest.get("metadata") or not manifest["metadata"].get("name"):
                raise ValueError(f"Manifest {manifest} has no metadata or name")

            if not manifest.get("kind"):
                raise ValueError(f"Manifest {manifest} has no kind")

            manifest_name = manifest["metadata"]["name"]
            manifest_kind = manifest["kind"].lower()
            output_file = output_dir / f"{manifest_name}-{manifest_kind}.yaml"

            if output_file.exists():
                output.verbose(
                    f"Overwriting existing manifest {manifest_name} ({manifest_kind}) at {output_file}"
                )
            else:
                output.verbose(
                    f"Writing manifest {manifest_name} ({manifest_kind}) to {output_file}"
                )

            with open(output_file, "w") as f:
                yaml.dump(manifest, f)
