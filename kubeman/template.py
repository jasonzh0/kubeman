from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union
import inspect
import yaml
from kubeman.config import Config
from kubeman.argocd import ArgoCDApplicationGenerator

# Context variable for custom manifests directory (set by CLI)
_custom_manifests_dir: Optional[Path] = None


class Template(ABC):
    """
    Abstract base class for all template types (Helm Charts and Kubernetes Resources).

    Provides common functionality for:
    - Optional ArgoCD Application generation
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
    def manifests_dir() -> Path:
        """
        Return the base directory for manifests.

        Uses custom manifests directory if set (via set_manifests_dir()),
        otherwise uses Config.manifests_dir() which checks MANIFESTS_DIR environment
        variable or defaults to 'manifests' in the current working directory.

        Returns:
            Path to manifests directory
        """
        global _custom_manifests_dir
        if _custom_manifests_dir is not None:
            return _custom_manifests_dir
        return Config.manifests_dir()

    @staticmethod
    def set_manifests_dir(path: Optional[Path]) -> None:
        """
        Set a custom manifests directory for this execution.

        Args:
            path: Path to manifests directory, or None to use default
        """
        global _custom_manifests_dir
        _custom_manifests_dir = path

    def enable_argocd(self) -> bool:
        """Return whether ArgoCD Application generation is enabled. Defaults to False (opt-in)."""
        return False

    def argo_ignore_spec(self) -> list:
        """Return any ignore specs for ArgoCD application. Empty list by default."""
        return []

    def application_repo_url(self) -> str:
        """Return the repository URL for ArgoCD applications. Override to customize."""
        return Config.argocd_app_repo_url()

    def application_target_revision(self) -> str:
        """Return the target revision for ArgoCD applications. Override to customize."""
        try:
            return Config.git_branch()
        except ValueError:
            return "main"

    def managed_namespace_metadata(self) -> dict:
        """Return managed namespace metadata labels. Override to customize."""
        return {}

    def apps_subdirectory(self) -> str:
        """Return the subdirectory name for applications. Override to customize."""
        return Config.argocd_apps_subdir()

    def generate_application(self) -> dict | None:
        """
        Generate the ArgoCD Application manifest for this template.

        Uses ArgoCDApplicationGenerator for cleaner separation of concerns.
        Returns None if ArgoCD is disabled or no repo URL is configured.

        Returns:
            ArgoCD Application manifest dict or None
        """
        if not self.enable_argocd():
            return None

        generator = ArgoCDApplicationGenerator(self.name, self.namespace)
        return generator.generate(
            repo_url=self.application_repo_url() or None,
            target_revision=self.application_target_revision(),
            path=self.name,
            ignore_differences=self.argo_ignore_spec() or None,
            managed_namespace_metadata=self.managed_namespace_metadata() or None,
            apps_subdir=self.apps_subdirectory(),
        )

    def resolve_path(self, relative_path: Union[str, Path]) -> Path:
        """
        Resolve a path relative to the template file's directory.

        This helper method automatically resolves paths relative to where the
        template class is defined, making it easy to reference component directories
        without manual path construction.

        Args:
            relative_path: Path relative to the template file's directory.
                          Can be a string or Path object.
                          Use "../" to go up from the template file's directory.

        Returns:
            Resolved absolute Path object

        Example:
            # If template is at examples/fullstack/templates/frontend.py
            # and you want to reference examples/fullstack/frontend/
            context_path = self.resolve_path("../frontend")

            # To reference the templates directory itself
            templates_dir = self.resolve_path(".")

        Note:
            The path is resolved relative to the template file's directory
            (the directory containing the template file).
        """
        # Get the file where this template class is defined
        template_file = Path(inspect.getfile(self.__class__))
        # Resolve relative to the template file's directory
        base_dir = template_file.parent
        return (base_dir / relative_path).resolve()

    def build(self) -> None:
        """
        Build Docker images for this template.

        Override this method to define build steps that should execute
        when the template is registered. Build steps run sequentially
        in registration order.

        By default, this method does nothing. Subclasses can override it
        to implement build steps.

        Example:
            def build(self) -> None:
                from kubeman import DockerManager
                docker = DockerManager()
                # Use resolve_path to automatically find component directory
                context_path = self.resolve_path("frontend")
                docker.build_image("my-component", context_path, tag="latest")
        """
        pass

    def load(self) -> None:
        """
        Load Docker images into the Kubernetes cluster for this template.

        Override this method to define image loading steps that should execute
        when the template is registered. Load steps run sequentially after build
        steps, in registration order.

        This is particularly useful for local development with kind clusters,
        where images need to be loaded into the cluster after building.

        By default, this method does nothing. Subclasses can override it
        to implement load steps.

        Example:
            def load(self) -> None:
                from kubeman import DockerManager
                docker = DockerManager()
                docker.kind_load_image("my-component", tag="latest", cluster_name="my-cluster")
        """
        pass

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
        Skips writing if ArgoCD is disabled or no repo URL is configured.
        """
        app = self.generate_application()
        if app is None:
            return

        manifests_dir = self.manifests_dir()
        if isinstance(manifests_dir, str):
            manifests_dir = Path(manifests_dir)
        apps_dir = manifests_dir / self.apps_subdirectory()
        apps_dir.mkdir(parents=True, exist_ok=True)

        app_file = apps_dir / f"{self.name}-application.yaml"
        with open(app_file, "w") as f:
            yaml.dump(app, f)
