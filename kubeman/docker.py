from pathlib import Path
from typing import Optional
from kubeman.config import Config
from kubeman.executor import CommandExecutor, get_executor


class DockerManager:
    """
    Manager for Docker image building and pushing operations.

    Supports container registries with configurable authentication.
    """

    def __init__(
        self,
        registry: Optional[str] = None,
        project_id: Optional[str] = None,
        repository_name: Optional[str] = None,
        executor: Optional[CommandExecutor] = None,
    ):
        """
        Initialize the DockerManager.

        Args:
            registry: Custom registry URL (overrides default registry construction)
            project_id: Registry project ID (defaults to DOCKER_PROJECT_ID env var)
            repository_name: Docker repository name (defaults to DOCKER_REPOSITORY_NAME env var)
            executor: CommandExecutor instance (defaults to global executor)
        """
        self.executor = executor or get_executor()
        self.project_id = project_id or Config.docker_project_id()
        repository_name = repository_name or Config.docker_repository_name()
        region = Config.docker_region()

        if registry:
            self.registry = registry
        else:
            self.registry = f"{region}-docker.pkg.dev/{self.project_id}/{repository_name}"
        self.repository = Config.github_repository()

    def build_image(self, component: str, context_path: str, tag: Optional[str] = None) -> str:
        """Build a Docker image for a component.

        Args:
            component: The name of the component (e.g., 'frontend')
            context_path: Path to the Docker context
            tag: Optional specific tag, defaults to 'latest'

        Returns:
            Full image name including registry and tag
        """
        tag = tag or "latest"
        image_name = f"{self.registry}/{component}:{tag}"

        # Ensure authentication is configured before building
        self._ensure_gcloud_auth()

        context = Path(context_path)
        dockerfile = context / "Dockerfile"

        cmd = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            str(dockerfile),
            str(context),
        ]

        self.executor.run(cmd, check=True)
        return image_name

    def push_image(self, component: str, tag: Optional[str] = None) -> str:
        """Push a Docker image to the registry.

        Args:
            component: The name of the component
            tag: Optional specific tag, defaults to 'latest'

        Returns:
            Full image name including registry and tag
        """
        tag = tag or "latest"
        image_name = f"{self.registry}/{component}:{tag}"

        # Ensure authentication is configured before pushing
        self._ensure_gcloud_auth()

        # First check if we're logged into GCP
        self._ensure_gcloud_login()

        cmd = ["docker", "push", image_name]
        self.executor.run(cmd, check=True)
        return image_name

    def build_and_push(self, component: str, context_path: str, tag: Optional[str] = None) -> str:
        """Build and push a Docker image in one go.

        Args:
            component: The name of the component
            context_path: Path to the Docker context
            tag: Optional specific tag
        """
        image_name = self.build_image(component, context_path, tag)
        self.push_image(component, tag)
        return image_name

    def _ensure_gcloud_auth(self):
        """Ensure Docker is authenticated with the container registry."""
        cmd = ["gcloud", "auth", "configure-docker", self.registry, "--quiet"]
        self.executor.run(cmd, check=True)

    def _ensure_gcloud_login(self):
        """Ensure we're logged into the cloud provider."""
        # Check if we're already authenticated
        try:
            self.executor.run(
                ["gcloud", "auth", "print-access-token"],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            # If not authenticated, print helpful message and exit
            print("Error: Not authenticated with cloud provider.")
            print("Please run: gcloud auth login")
            raise ValueError("Cloud provider authentication required")
