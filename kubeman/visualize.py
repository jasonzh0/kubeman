"""
Visualization module for generating Graphviz DOT diagrams of Kubernetes resources.

This module analyzes rendered Kubernetes manifests to extract resource relationships
and generate visual diagrams showing the hierarchy and dependencies.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import sys
import re
import yaml
from collections import defaultdict


class ResourceNode:
    """Represents a Kubernetes resource node in the graph."""

    def __init__(
        self,
        kind: str,
        name: str,
        namespace: Optional[str] = None,
        template_name: Optional[str] = None,
    ):
        self.kind = kind
        self.name = name
        self.namespace = namespace
        self.template_name = template_name
        self.manifest: Optional[Dict[str, Any]] = None

    def __hash__(self) -> int:
        return hash((self.kind, self.name, self.namespace))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ResourceNode):
            return False
        return (
            self.kind == other.kind
            and self.name == other.name
            and self.namespace == other.namespace
        )

    def __repr__(self) -> str:
        ns = f" ({self.namespace})" if self.namespace else ""
        return f"ResourceNode({self.kind}/{self.name}{ns})"

    def node_id(self) -> str:
        """Generate a unique node ID for Graphviz."""
        parts = [self.kind.lower(), self.name]
        if self.namespace:
            parts.append(self.namespace)
        return "_".join(parts).replace("-", "_").replace(".", "_")

    def display_name(self) -> str:
        """Generate a display name for the node."""
        name = f"{self.kind}\n{self.name}"
        if self.template_name and self.template_name != "unknown":
            name += f"\n[{self.template_name}]"
        return name


class ResourceRelationship:
    """Represents a relationship between two resources."""

    def __init__(
        self,
        source: ResourceNode,
        target: ResourceNode,
        relationship_type: str,
        label: Optional[str] = None,
        address: Optional[str] = None,
    ):
        self.source = source
        self.target = target
        self.relationship_type = relationship_type
        self.address = address
        # Include address in label if provided
        if address and label:
            self.label = f"{label}\n{address}"
        elif address:
            self.label = f"{relationship_type}\n{address}"
        else:
            self.label = label or relationship_type

    def __repr__(self) -> str:
        addr = f" ({self.address})" if self.address else ""
        return (
            f"ResourceRelationship({self.source} -> {self.target}: {self.relationship_type}{addr})"
        )


class ResourceAnalyzer:
    """Analyzes Kubernetes manifests to extract resources and relationships."""

    def __init__(
        self,
        manifests_dir: Path,
        template_names: Optional[List[str]] = None,
        show_crds: bool = False,
    ):
        self.manifests_dir = manifests_dir
        self.template_names = template_names
        self.show_crds = show_crds
        self.resources: Dict[Tuple[str, str, Optional[str]], ResourceNode] = {}
        self.relationships: List[ResourceRelationship] = []
        self.namespace_to_resources: Dict[str, List[ResourceNode]] = defaultdict(list)

    def analyze(self) -> Tuple[Dict[str, List[ResourceNode]], List[ResourceRelationship]]:
        """
        Analyze all manifests in the directory and extract resources and relationships.

        Returns:
            Tuple of (namespace_to_resources dict, relationships list)
        """
        yaml_files = list(self.manifests_dir.rglob("*.yaml")) + list(
            self.manifests_dir.rglob("*.yml")
        )

        for yaml_file in yaml_files:
            # Skip ArgoCD application files
            if "application" in yaml_file.name.lower() and "argocd" in str(yaml_file.parent):
                continue

            # Determine template name from directory structure
            template_name = self._extract_template_name(yaml_file)

            # Filter by template names if specified
            if self.template_names is not None:
                # Check if this file belongs to one of the specified templates
                if template_name not in self.template_names:
                    # Also check if it's in the apps directory (ArgoCD applications)
                    if template_name != "argocd-apps":
                        continue
                    else:
                        # For ArgoCD apps, check if the filename matches a template
                        relative_path = yaml_file.relative_to(self.manifests_dir)
                        if len(relative_path.parts) >= 2 and relative_path.parts[0] == "apps":
                            app_filename = relative_path.parts[1]
                            # Check if this app file matches any template name
                            matches_template = any(
                                app_filename == f"{tname}-application.yaml"
                                for tname in self.template_names
                            )
                            if not matches_template:
                                continue

            try:
                with open(yaml_file, "r") as f:
                    documents = list(yaml.safe_load_all(f))

                for doc in documents:
                    if doc is None or not isinstance(doc, dict):
                        continue

                    resource = self._parse_resource(doc, template_name)
                    if resource:
                        # Skip CustomResourceDefinitions unless show_crds is True
                        if resource.kind == "CustomResourceDefinition" and not self.show_crds:
                            continue

                        key = (resource.kind, resource.name, resource.namespace)
                        self.resources[key] = resource
                        # Group by namespace (use "cluster-scoped" for cluster-scoped resources)
                        namespace_key = resource.namespace or "cluster-scoped"
                        self.namespace_to_resources[namespace_key].append(resource)
            except (yaml.YAMLError, IOError, OSError) as e:
                print(f"Warning: Could not parse {yaml_file}: {e}", file=sys.stderr)
                continue

        # Extract relationships
        for resource in self.resources.values():
            if resource.manifest:
                self._extract_relationships(resource)
                # Also check ConfigMap data for network connections
                if resource.kind == "ConfigMap":
                    self._extract_configmap_network_connections(resource)

        return dict(self.namespace_to_resources), self.relationships

    def _extract_template_name(self, yaml_file: Path) -> str:
        """Extract template name from file path."""
        try:
            relative_path = yaml_file.relative_to(self.manifests_dir)
            parts = relative_path.parts

            # Skip apps directory (ArgoCD applications)
            if parts[0] == "apps":
                return "argocd-apps"

            # First directory is usually the template name
            if len(parts) > 1:
                return parts[0]
        except ValueError:
            pass

        return "unknown"

    def _parse_resource(
        self, manifest: Dict[str, Any], template_name: str
    ) -> Optional[ResourceNode]:
        """Parse a manifest into a ResourceNode."""
        kind = manifest.get("kind", "")
        metadata = manifest.get("metadata", {})
        name = metadata.get("name", "")
        namespace = metadata.get("namespace")

        if not kind or not name:
            return None

        resource = ResourceNode(kind, name, namespace, template_name)
        resource.manifest = manifest
        return resource

    def _extract_relationships(self, resource: ResourceNode) -> None:
        """Extract relationships from a resource's manifest."""
        if not resource.manifest:
            return

        kind = resource.kind
        manifest = resource.manifest

        if kind == "Deployment" or kind == "StatefulSet" or kind == "Job" or kind == "DaemonSet":
            self._extract_pod_spec_relationships(resource, manifest)
        elif kind == "Service":
            self._extract_service_relationships(resource, manifest)
        elif kind == "Ingress":
            self._extract_ingress_relationships(resource, manifest)
        elif kind == "RoleBinding":
            self._extract_role_binding_relationships(resource, manifest)
        elif kind == "ClusterRoleBinding":
            self._extract_cluster_role_binding_relationships(resource, manifest)

    def _extract_pod_spec_relationships(
        self, resource: ResourceNode, manifest: Dict[str, Any]
    ) -> None:
        """Extract relationships from Pod spec (Deployment, StatefulSet, Job, etc.)."""
        spec = manifest.get("spec", {})
        template = spec.get("template", {})
        pod_spec = template.get("spec", {})

        # ServiceAccount
        service_account_name = pod_spec.get("serviceAccountName")
        if service_account_name:
            target = self._find_resource("ServiceAccount", service_account_name, resource.namespace)
            if target:
                self.relationships.append(
                    ResourceRelationship(resource, target, "uses-serviceaccount")
                )

        # Containers
        containers = pod_spec.get("containers", []) + pod_spec.get("initContainers", [])

        for container in containers:
            # Environment variables from ConfigMaps/Secrets
            env = container.get("env", [])
            for env_var in env:
                # Check for direct value (not from ConfigMap/Secret)
                env_value = env_var.get("value")
                if env_value:
                    self._detect_network_connections(resource, env_value)

                value_from = env_var.get("valueFrom", {})
                if "configMapKeyRef" in value_from:
                    cm_ref = value_from["configMapKeyRef"]
                    cm_name = cm_ref.get("name")
                    if cm_name:
                        target = self._find_resource("ConfigMap", cm_name, resource.namespace)
                        if target:
                            self.relationships.append(
                                ResourceRelationship(resource, target, "uses-configmap")
                            )
                            # Also check ConfigMap data for network connections
                            if target.manifest:
                                cm_data = target.manifest.get("data", {})
                                for key, value in cm_data.items():
                                    if isinstance(value, str):
                                        self._detect_network_connections(resource, value, target)
                if "secretKeyRef" in value_from:
                    secret_ref = value_from["secretKeyRef"]
                    secret_name = secret_ref.get("name")
                    if secret_name:
                        target = self._find_resource("Secret", secret_name, resource.namespace)
                        if target:
                            self.relationships.append(
                                ResourceRelationship(resource, target, "uses-secret")
                            )

            # envFrom
            env_from = container.get("envFrom", [])
            for env_from_item in env_from:
                if "configMapRef" in env_from_item:
                    cm_ref = env_from_item["configMapRef"]
                    cm_name = cm_ref.get("name")
                    if cm_name:
                        target = self._find_resource("ConfigMap", cm_name, resource.namespace)
                        if target:
                            self.relationships.append(
                                ResourceRelationship(resource, target, "uses-configmap")
                            )
                            # Check ConfigMap data for network connections
                            if target.manifest:
                                cm_data = target.manifest.get("data", {})
                                for key, value in cm_data.items():
                                    if isinstance(value, str):
                                        self._detect_network_connections(resource, value, target)
                if "secretRef" in env_from_item:
                    secret_ref = env_from_item["secretRef"]
                    secret_name = secret_ref.get("name")
                    if secret_name:
                        target = self._find_resource("Secret", secret_name, resource.namespace)
                        if target:
                            self.relationships.append(
                                ResourceRelationship(resource, target, "uses-secret")
                            )

        # Volumes
        volumes = pod_spec.get("volumes", [])
        for volume in volumes:
            # PersistentVolumeClaim
            if "persistentVolumeClaim" in volume:
                pvc_ref = volume["persistentVolumeClaim"]
                pvc_name = pvc_ref.get("claimName")
                if pvc_name:
                    target = self._find_resource(
                        "PersistentVolumeClaim", pvc_name, resource.namespace
                    )
                    if target:
                        self.relationships.append(
                            ResourceRelationship(resource, target, "uses-pvc")
                        )

            # ConfigMap volume
            if "configMap" in volume:
                cm_ref = volume["configMap"]
                cm_name = cm_ref.get("name")
                if cm_name:
                    target = self._find_resource("ConfigMap", cm_name, resource.namespace)
                    if target:
                        self.relationships.append(
                            ResourceRelationship(resource, target, "uses-configmap")
                        )

            # Secret volume
            if "secret" in volume:
                secret_ref = volume["secret"]
                secret_name = secret_ref.get("name")
                if secret_name:
                    target = self._find_resource("Secret", secret_name, resource.namespace)
                    if target:
                        self.relationships.append(
                            ResourceRelationship(resource, target, "uses-secret")
                        )

    def _extract_service_relationships(
        self, resource: ResourceNode, manifest: Dict[str, Any]
    ) -> None:
        """Extract relationships from Service (selector matching to Deployments)."""
        spec = manifest.get("spec", {})
        selector = spec.get("selector", {})

        if not selector:
            return

        # Find deployments/statefulsets with matching labels
        for other_resource in self.resources.values():
            if other_resource.kind not in ["Deployment", "StatefulSet", "DaemonSet"]:
                continue

            if other_resource.namespace != resource.namespace:
                continue

            if not other_resource.manifest:
                continue

            other_spec = other_resource.manifest.get("spec", {})
            other_template = other_spec.get("template", {})
            other_labels = other_template.get("metadata", {}).get("labels", {})

            # Check if selector matches labels
            if self._selector_matches(selector, other_labels):
                self.relationships.append(ResourceRelationship(resource, other_resource, "selects"))

    def _extract_ingress_relationships(
        self, resource: ResourceNode, manifest: Dict[str, Any]
    ) -> None:
        """Extract relationships from Ingress (references to Services)."""
        spec = manifest.get("spec", {})
        rules = spec.get("rules", [])

        for rule in rules:
            http = rule.get("http", {})
            paths = http.get("paths", [])

            for path in paths:
                backend = path.get("backend", {})
                service = backend.get("service", {})
                service_name = service.get("name")

                if service_name:
                    target = self._find_resource("Service", service_name, resource.namespace)
                    if target:
                        self.relationships.append(
                            ResourceRelationship(resource, target, "routes-to")
                        )

    def _extract_role_binding_relationships(
        self, resource: ResourceNode, manifest: Dict[str, Any]
    ) -> None:
        """Extract relationships from RoleBinding."""
        role_ref = manifest.get("roleRef", {})
        role_kind = role_ref.get("kind")
        role_name = role_ref.get("name")

        if role_name:
            if role_kind == "ClusterRole":
                target = self._find_resource("ClusterRole", role_name, None)
            else:
                target = self._find_resource("Role", role_name, resource.namespace)

            if target:
                self.relationships.append(ResourceRelationship(resource, target, "references-role"))

        # Subjects (ServiceAccounts)
        subjects = manifest.get("subjects", [])
        for subject in subjects:
            if subject.get("kind") == "ServiceAccount":
                sa_name = subject.get("name")
                sa_namespace = subject.get("namespace") or resource.namespace
                if sa_name:
                    target = self._find_resource("ServiceAccount", sa_name, sa_namespace)
                    if target:
                        self.relationships.append(
                            ResourceRelationship(resource, target, "binds-to")
                        )

    def _extract_cluster_role_binding_relationships(
        self, resource: ResourceNode, manifest: Dict[str, Any]
    ) -> None:
        """Extract relationships from ClusterRoleBinding."""
        role_ref = manifest.get("roleRef", {})
        role_name = role_ref.get("name")

        if role_name:
            target = self._find_resource("ClusterRole", role_name, None)
            if target:
                self.relationships.append(ResourceRelationship(resource, target, "references-role"))

        # Subjects (ServiceAccounts)
        subjects = manifest.get("subjects", [])
        for subject in subjects:
            if subject.get("kind") == "ServiceAccount":
                sa_name = subject.get("name")
                sa_namespace = subject.get("namespace")
                if sa_name:
                    target = self._find_resource("ServiceAccount", sa_name, sa_namespace)
                    if target:
                        self.relationships.append(
                            ResourceRelationship(resource, target, "binds-to")
                        )

    def _find_resource(
        self, kind: str, name: str, namespace: Optional[str]
    ) -> Optional[ResourceNode]:
        """Find a resource by kind, name, and namespace."""
        key = (kind, name, namespace)
        return self.resources.get(key)

    def _selector_matches(self, selector: Dict[str, str], labels: Dict[str, str]) -> bool:
        """Check if a selector matches labels."""
        for key, value in selector.items():
            if labels.get(key) != value:
                return False
        return True

    def _extract_configmap_network_connections(self, configmap: ResourceNode) -> None:
        """Extract network connections from ConfigMap data that reference services."""
        if not configmap.manifest:
            return

        data = configmap.manifest.get("data", {})
        for key, value in data.items():
            if isinstance(value, str):
                # Find all resources that use this ConfigMap
                for resource in self.resources.values():
                    if resource == configmap:
                        continue
                    # Check if this resource uses the ConfigMap
                    if self._resource_uses_configmap(resource, configmap):
                        self._detect_network_connections(resource, value, configmap)

    def _resource_uses_configmap(self, resource: ResourceNode, configmap: ResourceNode) -> bool:
        """Check if a resource uses a specific ConfigMap."""
        if not resource.manifest or resource.kind not in [
            "Deployment",
            "StatefulSet",
            "Job",
            "DaemonSet",
        ]:
            return False

        spec = resource.manifest.get("spec", {})
        template = spec.get("template", {})
        pod_spec = template.get("spec", {})
        containers = pod_spec.get("containers", []) + pod_spec.get("initContainers", [])

        for container in containers:
            # Check env with configMapKeyRef
            env = container.get("env", [])
            for env_var in env:
                value_from = env_var.get("valueFrom", {})
                if "configMapKeyRef" in value_from:
                    cm_ref = value_from["configMapKeyRef"]
                    if cm_ref.get("name") == configmap.name:
                        return True

            # Check envFrom
            env_from = container.get("envFrom", [])
            for env_from_item in env_from:
                if "configMapRef" in env_from_item:
                    cm_ref = env_from_item["configMapRef"]
                    if cm_ref.get("name") == configmap.name:
                        return True

            # Check volumes
            volumes = pod_spec.get("volumes", [])
            for volume in volumes:
                if "configMap" in volume:
                    cm_ref = volume["configMap"]
                    if cm_ref.get("name") == configmap.name:
                        return True

        return False

    def _detect_network_connections(
        self,
        source: ResourceNode,
        text: str,
        intermediate_resource: Optional[ResourceNode] = None,
    ) -> None:
        """
        Detect network connections in text (environment variables, ConfigMap data, etc.).

        Looks for patterns like:
        - service-name:port
        - service-name.namespace.svc.cluster.local:port
        - URLs containing service names (http://, https://, postgresql://, etc.)
        """
        if not text or not isinstance(text, str):
            return

        # Pattern to match service names in various formats:
        # - service-name:port
        # - service-name.namespace.svc.cluster.local:port
        # - URLs: http://service-name:port, postgresql://user@service-name:port/db
        # - Just service-name (common in Kubernetes)
        service_patterns = [
            # Full DNS: service.namespace.svc.cluster.local
            r"([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.svc\.cluster\.local",
            # Short form: service:port or service.namespace:port
            r"([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?::\d+)?",
        ]

        # Also check for URLs with service names
        url_pattern = r"(?:https?|postgresql?|mysql|redis|mongodb|kafka)://[^@]*@?([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?::(\d+))?"

        found_services = set()

        # Extract service names and addresses from URLs
        url_matches = re.finditer(url_pattern, text, re.IGNORECASE)
        for match in url_matches:
            service_name = match.group(1)
            port = match.group(2)
            if service_name and len(service_name) > 1:  # Avoid matching single characters
                # Extract the full connection string from URL
                full_url = match.group(0)
                # Extract host:port from URL
                url_host_match = re.search(
                    r"://[^@]*@?([^:/]+)(?::(\d+))?(?:/|$)", full_url, re.IGNORECASE
                )
                if url_host_match:
                    host = url_host_match.group(1)
                    url_port = url_host_match.group(2) or port
                    address = f"{host}:{url_port}" if url_port else host
                    found_services.add((service_name, address))

        # Extract service names from DNS patterns
        dns_matches = re.finditer(service_patterns[0], text, re.IGNORECASE)
        for match in dns_matches:
            service_name = match.group(1)
            full_match = match.group(0)
            if service_name:
                found_services.add((service_name, full_match))

        # Extract simple service names (service:port or just service)
        # This is more permissive, so we'll be careful
        simple_pattern = r"\b([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?::(\d+))?\b"
        simple_matches = re.finditer(simple_pattern, text, re.IGNORECASE)
        for match in simple_matches:
            potential_service = match.group(1)
            port = match.group(2)
            # Filter out common non-service words and very short matches
            if (
                potential_service
                and len(potential_service) > 2
                and potential_service not in ["http", "https", "tcp", "udp", "port", "localhost"]
                and not potential_service.isdigit()
            ):
                # Check if this looks like a service name (contains hyphens or is a known pattern)
                if "-" in potential_service or len(potential_service) >= 4:
                    address = f"{potential_service}:{port}" if port else potential_service
                    found_services.add((potential_service, address))

        # Try to find matching Service resources
        for service_name, address in found_services:
            # Use the extracted address
            display_address = address

            # Try in the same namespace first
            target = self._find_resource("Service", service_name, source.namespace)
            if target:
                # Create connection relationship with address
                rel_type = "connects-to"
                if intermediate_resource:
                    # If connection is through a ConfigMap, note that
                    rel_type = "connects-to-via-config"
                self.relationships.append(
                    ResourceRelationship(source, target, rel_type, address=display_address)
                )
            else:
                # Try in other namespaces (for cross-namespace connections)
                # We'll search all resources to find services with this name
                for other_resource in self.resources.values():
                    if (
                        other_resource.kind == "Service"
                        and other_resource.name == service_name
                        and other_resource.namespace != source.namespace
                    ):
                        rel_type = "connects-to"
                        if intermediate_resource:
                            rel_type = "connects-to-via-config"
                        self.relationships.append(
                            ResourceRelationship(
                                source, other_resource, rel_type, address=display_address
                            )
                        )
                        break


class DOTGenerator:
    """Generates Graphviz DOT format from resource graph."""

    # Color scheme for different resource kinds
    KIND_COLORS: Dict[str, str] = {
        "Namespace": "#E8F4F8",
        "Deployment": "#FFE5B4",
        "StatefulSet": "#FFE5B4",
        "DaemonSet": "#FFE5B4",
        "Job": "#FFE5B4",
        "Service": "#B4E5FF",
        "ConfigMap": "#E5FFE5",
        "Secret": "#FFE5E5",
        "PersistentVolumeClaim": "#E5E5FF",
        "ServiceAccount": "#FFF5E5",
        "Role": "#F0E5FF",
        "ClusterRole": "#F0E5FF",
        "RoleBinding": "#F5E5FF",
        "ClusterRoleBinding": "#F5E5FF",
        "Ingress": "#E5FFF5",
    }

    # Shape for different resource kinds
    KIND_SHAPES: Dict[str, str] = {
        "Namespace": "ellipse",
        "Deployment": "box",
        "StatefulSet": "box",
        "DaemonSet": "box",
        "Job": "box",
        "Service": "diamond",
        "ConfigMap": "note",
        "Secret": "note",
        "PersistentVolumeClaim": "cylinder",
        "ServiceAccount": "ellipse",
        "Role": "hexagon",
        "ClusterRole": "hexagon",
        "RoleBinding": "parallelogram",
        "ClusterRoleBinding": "parallelogram",
        "Ingress": "trapezium",
    }

    # Namespace cluster colors
    NAMESPACE_COLORS = [
        "#E8F4F8",
        "#FFF5E5",
        "#E5FFE5",
        "#FFE5E5",
        "#E5E5FF",
        "#F0E5FF",
        "#E5FFF5",
        "#FFE5B4",
        "#B4E5FF",
    ]

    def __init__(
        self,
        namespace_to_resources: Dict[str, List[ResourceNode]],
        relationships: List[ResourceRelationship],
    ):
        self.namespace_to_resources = namespace_to_resources
        self.relationships = relationships

    def generate(self) -> str:
        """Generate Graphviz DOT format string."""
        lines = ["digraph G {", '    rankdir="TB";', '    node [fontname="Arial"];', ""]

        # Add namespace clusters
        namespace_names = sorted(self.namespace_to_resources.keys())
        for i, namespace_name in enumerate(namespace_names):
            color = self.NAMESPACE_COLORS[i % len(self.NAMESPACE_COLORS)]
            cluster_id = f"cluster_{namespace_name.replace('-', '_').replace('.', '_')}"

            lines.append(f"    subgraph {cluster_id} {{")
            lines.append(f'        label="Namespace: {namespace_name}";')
            lines.append(f'        style="filled";')
            lines.append(f'        color="{color}";')
            lines.append(f'        fontcolor="black";')
            lines.append("")

            resources = self.namespace_to_resources[namespace_name]
            for resource in resources:
                node_id = resource.node_id()
                display_name = resource.display_name()
                color = self.KIND_COLORS.get(resource.kind, "#FFFFFF")
                shape = self.KIND_SHAPES.get(resource.kind, "box")

                # Escape quotes in display name
                display_name_escaped = display_name.replace('"', '\\"')

                lines.append(
                    f'        {node_id} [label="{display_name_escaped}", '
                    f'style="filled", fillcolor="{color}", shape="{shape}"];'
                )

            lines.append("    }")
            lines.append("")

        # Add relationships
        for rel in self.relationships:
            source_id = rel.source.node_id()
            target_id = rel.target.node_id()

            # Only add edge if both nodes exist
            if rel.source in self._all_resources() and rel.target in self._all_resources():
                # Escape quotes and preserve newlines for multi-line labels
                label_escaped = rel.label.replace('"', '\\"').replace("\n", "\\n")
                lines.append(f'    {source_id} -> {target_id} [label="{label_escaped}"];')

        lines.append("}")
        return "\n".join(lines)

    def _all_resources(self) -> Set[ResourceNode]:
        """Get all resources from all namespaces."""
        resources = set()
        for resource_list in self.namespace_to_resources.values():
            resources.update(resource_list)
        return resources


def generate_visualization(
    manifests_dir: Path,
    template_names: Optional[List[str]] = None,
    show_crds: bool = False,
) -> str:
    """
    Generate a Graphviz DOT visualization from rendered manifests.

    Args:
        manifests_dir: Path to directory containing rendered manifests
        template_names: Optional list of template names to filter by.
                       If provided, only resources from these templates will be visualized.
        show_crds: If True, include CustomResourceDefinitions in the visualization.
                  Defaults to False.

    Returns:
        Graphviz DOT format string
    """
    analyzer = ResourceAnalyzer(manifests_dir, template_names=template_names, show_crds=show_crds)
    namespace_to_resources, relationships = analyzer.analyze()

    generator = DOTGenerator(namespace_to_resources, relationships)
    return generator.generate()
