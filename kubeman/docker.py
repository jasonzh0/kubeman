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

    def build_image(
        self,
        component: str,
        context_path: str,
        tag: Optional[str] = None,
        dockerfile: Optional[str] = None,
    ) -> str:
        """Build a Docker image for a component.

        Args:
            component: The name of the component (e.g., 'frontend')
            context_path: Path to the Docker context
            tag: Optional specific tag, defaults to 'latest'
            dockerfile: Optional Dockerfile name (defaults to 'Dockerfile')

        Returns:
            Full image name including registry and tag
        """
        tag = tag or "latest"
        image_name = f"{self.registry}/{component}:{tag}"

        context = Path(context_path)
        dockerfile_path = context / (dockerfile or "Dockerfile")

        cmd = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            str(dockerfile_path),
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

        cmd = ["docker", "push", image_name]
        self.executor.run(cmd, check=True)
        return image_name

    def build_and_push(
        self,
        component: str,
        context_path: str,
        tag: Optional[str] = None,
        dockerfile: Optional[str] = None,
    ) -> str:
        """Build and push a Docker image in one go.

        Args:
            component: The name of the component
            context_path: Path to the Docker context
            tag: Optional specific tag
            dockerfile: Optional Dockerfile name (defaults to 'Dockerfile')
        """
        image_name = self.build_image(component, context_path, tag, dockerfile)
        self.push_image(component, tag)
        return image_name

    def tag_image(
        self,
        source_image: str,
        target_image: str,
        source_tag: Optional[str] = None,
        target_tag: Optional[str] = None,
    ) -> None:
        """
        Tag a Docker image with a new name and/or tag.

        Useful for creating local tags from registry images, especially for
        loading into kind clusters.

        Args:
            source_image: Source image name (can include registry path, with or without tag)
            target_image: Target image name (local name, without tag)
            source_tag: Optional source tag (defaults to 'latest' if not in source_image)
            target_tag: Optional target tag (defaults to source_tag or 'latest')
        """
        if ":" in source_image:
            source_parts = source_image.rsplit(":", 1)
            source_name = source_parts[0]
            source_tag_from_name = source_parts[1]
            source_tag = source_tag or source_tag_from_name
        else:
            source_name = source_image
            source_tag = source_tag or "latest"

        target_tag = target_tag or source_tag

        source = f"{source_name}:{source_tag}"
        target = f"{target_image}:{target_tag}"

        cmd = ["docker", "tag", source, target]
        self.executor.run(cmd, check=True)

    def kind_load_image(
        self,
        image_name: str,
        cluster_name: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> None:
        """
        Load a Docker image into a kind cluster.

        This is useful for local development where images need to be loaded
        into a kind cluster after building.

        Args:
            image_name: Name of the Docker image to load (without tag, e.g., "my-app")
            cluster_name: Optional kind cluster name. If not provided, attempts to
                         detect from kubectl context (kind-{cluster-name} format)
            tag: Optional tag (defaults to 'latest')

        Raises:
            RuntimeError: If kind is not available or cluster is not found
            ValueError: If cluster name cannot be determined automatically
        """
        tag = tag or "latest"
        full_image_name = f"{image_name}:{tag}" if ":" not in image_name else image_name
        try:
            self.executor.run(["kind", "version"], check=True, capture_output=True)
        except Exception:
            raise RuntimeError(
                "kind is not installed or not in PATH. Please install kind to use load_image."
            )

        if cluster_name is None:
            try:
                result = self.executor.run(
                    ["kubectl", "config", "current-context"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                context = result.stdout.strip()
                if context.startswith("kind-"):
                    cluster_name = context.replace("kind-", "", 1)
                else:
                    raise ValueError(
                        f"Current kubectl context '{context}' does not appear to be a kind cluster. "
                        "Please specify cluster_name parameter."
                    )
            except Exception as e:
                if isinstance(e, ValueError):
                    raise
                raise ValueError(
                    f"Could not determine kind cluster name: {e}. Please specify cluster_name parameter."
                ) from e

        cmd = ["kind", "load", "docker-image", full_image_name, "--name", cluster_name]
        self.executor.run(cmd, check=True)
