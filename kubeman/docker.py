import subprocess
import os
from typing import Optional


class DockerManager:
    def __init__(
        self,
        registry: str = None,
        project_id: Optional[str] = None,
        repository_name: Optional[str] = None,
    ):
        self.project_id = project_id or os.getenv("GOOGLE_PROJECT_ID")
        if not self.project_id:
            raise ValueError(
                "Google Cloud project ID must be provided or set in GOOGLE_PROJECT_ID environment variable"
            )

        repository_name = repository_name or os.getenv("DOCKER_REPOSITORY_NAME", "default")
        region = os.getenv("GOOGLE_REGION", "us-central1")
        if registry:
            self.registry = registry
        else:
            self.registry = f"{region}-docker.pkg.dev/{self.project_id}/{repository_name}"
        self.repository = os.getenv("GITHUB_REPOSITORY", "")

    def build_image(self, component: str, context_path: str, tag: Optional[str] = None) -> str:
        """Build a Docker image for a component.

        Args:
            component: The name of the component (e.g., 'frontend')
            context_path: Path to the Docker context
            tag: Optional specific tag, defaults to 'latest'
        """
        tag = tag or "latest"
        image_name = f"{self.registry}/{component}:{tag}"

        # Ensure authentication is configured before building
        self._ensure_gcloud_auth()

        cmd = [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            f"{context_path}/Dockerfile",
            context_path,
        ]

        subprocess.run(cmd, check=True)
        return image_name

    def push_image(self, component: str, tag: Optional[str] = None) -> str:
        """Push a Docker image to the registry.

        Args:
            component: The name of the component
            tag: Optional specific tag, defaults to 'latest'
        """
        tag = tag or "latest"
        image_name = f"{self.registry}/{component}:{tag}"

        # Ensure authentication is configured before pushing
        self._ensure_gcloud_auth()

        # First check if we're logged into GCP
        self._ensure_gcloud_login()

        cmd = ["docker", "push", image_name]
        subprocess.run(cmd, check=True)
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
        """Ensure Docker is authenticated with Google Container Registry."""
        cmd = ["gcloud", "auth", "configure-docker", self.registry, "--quiet"]
        subprocess.run(cmd, check=True)

    def _ensure_gcloud_login(self):
        """Ensure we're logged into GCP."""
        # Check if we're already authenticated
        try:
            subprocess.run(
                ["gcloud", "auth", "print-access-token"], check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError:
            # If not authenticated, print helpful message and exit
            print("Error: Not authenticated with Google Cloud.")
            print("Please run: gcloud auth login")
            raise ValueError("GCP authentication required")
