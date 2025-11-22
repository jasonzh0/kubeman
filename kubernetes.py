from abc import ABC, abstractmethod
import os
import yaml
from kubeman.git import GitManager


class KubernetesResource(ABC):
    """
    Abstract base class for managing raw Kubernetes resources without Helm.
    This class provides a simplified interface for projects that don't need Helm
    but still want ArgoCD Application generation and manifest management.
    """

    def __init__(self):
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the resource collection"""
        pass

    @property
    @abstractmethod
    def namespace(self) -> str:
        """Return the namespace where resources should be deployed"""
        pass

    @abstractmethod
    def manifests(self) -> list[dict]:
        """Return list of Kubernetes manifest dictionaries to be rendered"""
        pass

    @staticmethod
    def manifests_dir() -> str:
        """Return the base directory for manifests"""
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../manifests"))

    def argo_ignore_spec(self) -> list:
        """Return any ignore specs for ArgoCD application. Empty list by default."""
        return []

    def application_repo_url(self) -> str:
        """Return the repository URL for ArgoCD applications. Override to customize."""
        return os.getenv("ARGOCD_APP_REPO_URL", "")

    def application_target_revision(self) -> str:
        """Return the target revision for ArgoCD applications. Override to customize."""
        return GitManager().fetch_branch_name()

    def managed_namespace_metadata(self) -> dict:
        """Return managed namespace metadata labels. Override to customize."""
        return {}

    def generate_application(self) -> dict:
        """Generate the ArgoCD Application manifest for this resource"""
        repo_url = self.application_repo_url()
        if not repo_url:
            raise ValueError(
                "application_repo_url() must return a valid repository URL, "
                "or set ARGOCD_APP_REPO_URL environment variable"
            )

        app = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": self.name,
                "namespace": "argocd",  # ArgoCD applications always live in argocd namespace
            },
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": repo_url,
                    "targetRevision": self.application_target_revision(),
                    "path": f"{self.name}",
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": self.namespace,
                },
                "syncPolicy": {
                    "automated": {
                        "prune": True,
                        "selfHeal": True,
                    },
                    "syncOptions": ["CreateNamespace=true", "ServerSideApply=true"],
                },
                "ignoreDifferences": self.argo_ignore_spec(),
            },
        }

        # Add managed namespace metadata if provided
        managed_metadata = self.managed_namespace_metadata()
        if managed_metadata:
            app["spec"]["syncPolicy"]["managedNamespaceMetadata"] = {"labels": managed_metadata}

        return app

    def apps_subdirectory(self) -> str:
        """Return the subdirectory name for applications. Override to customize."""
        return os.getenv("ARGOCD_APPS_SUBDIR", "apps")

    def render(self) -> None:
        """
        Render Kubernetes manifests and ArgoCD Application.
        """
        # Ensure apps directory exists
        apps_dir = os.path.join(self.manifests_dir(), self.apps_subdirectory())
        os.makedirs(apps_dir, exist_ok=True)

        # Render manifests
        self.render_manifests()

        # Write Application manifest
        app_file = os.path.join(apps_dir, f"{self.name}-application.yaml")
        with open(app_file, "w") as f:
            yaml.dump(self.generate_application(), f)

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
