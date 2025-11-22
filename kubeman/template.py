from abc import ABC, abstractmethod
import os
import yaml
from kubeman.git import GitManager


class Template(ABC):
    """
    Abstract base class for all template types (Helm Charts and Kubernetes Resources).

    Provides common functionality for:
    - ArgoCD Application generation
    - Manifest directory management
    - Rendering to filesystem
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the template"""
        pass

    @property
    @abstractmethod
    def namespace(self) -> str:
        """Return the namespace where resources should be deployed"""
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

    def apps_subdirectory(self) -> str:
        """Return the subdirectory name for applications. Override to customize."""
        return os.getenv("ARGOCD_APPS_SUBDIR", "apps")

    def generate_application(self) -> dict:
        """Generate the ArgoCD Application manifest for this template"""
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

    @abstractmethod
    def render(self) -> None:
        """
        Render the template to the filesystem.
        Subclasses must implement their specific rendering logic.
        """
        pass

    def _write_application(self) -> None:
        """
        Write the ArgoCD Application manifest.
        This is a common helper method that subclasses can call.
        """
        apps_dir = os.path.join(self.manifests_dir(), self.apps_subdirectory())
        os.makedirs(apps_dir, exist_ok=True)

        app_file = os.path.join(apps_dir, f"{self.name}-application.yaml")
        with open(app_file, "w") as f:
            yaml.dump(self.generate_application(), f)
