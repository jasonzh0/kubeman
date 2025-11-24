"""
Centralized configuration management for kubeman.

Provides a unified interface for accessing environment variables and
configuration with defaults and validation.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """
    Centralized configuration management.

    Provides access to environment variables and configuration with
    sensible defaults and validation.
    """

    @staticmethod
    def get(key: str, default: Optional[str] = None, required: bool = False) -> str:
        """
        Get an environment variable with optional default and validation.

        Args:
            key: Environment variable name
            default: Default value if not set
            required: If True, raise ValueError if not set

        Returns:
            Environment variable value or default

        Raises:
            ValueError: If required=True and variable is not set
        """
        value = os.getenv(key, default)
        if required and value is None:
            raise ValueError(f"Required environment variable {key} is not set")
        return value or ""

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """
        Get a boolean environment variable.

        Args:
            key: Environment variable name
            default: Default value if not set

        Returns:
            Boolean value
        """
        value = os.getenv(key, "").lower()
        if value in ("true", "1", "yes", "on"):
            return True
        elif value in ("false", "0", "no", "off", ""):
            return False
        return default

    @staticmethod
    def manifests_dir() -> Path:
        """
        Get the base directory for rendered manifests.

        Checks MANIFESTS_DIR environment variable first, then defaults
        to a 'manifests' directory relative to the current working directory.

        Returns:
            Path to manifests directory
        """
        env_dir = os.getenv("MANIFESTS_DIR")
        if env_dir:
            return Path(env_dir).resolve()
        # Default to manifests directory in current working directory
        return Path.cwd() / "manifests"

    @staticmethod
    def git_commit() -> str:
        """
        Get the current git commit hash from environment.

        Returns:
            Git commit hash

        Raises:
            ValueError: If STABLE_GIT_COMMIT is not set
        """
        return Config.get("STABLE_GIT_COMMIT", required=True)

    @staticmethod
    def git_branch() -> str:
        """
        Get the current git branch name from environment.

        Returns:
            Git branch name

        Raises:
            ValueError: If STABLE_GIT_BRANCH is not set
        """
        return Config.get("STABLE_GIT_BRANCH", required=True)

    @staticmethod
    def rendered_manifest_dir() -> str:
        """
        Get the rendered manifest directory from environment.

        Returns:
            Path to rendered manifest directory

        Raises:
            ValueError: If RENDERED_MANIFEST_DIR is not set
        """
        return Config.get("RENDERED_MANIFEST_DIR", required=True)

    @staticmethod
    def manifest_repo_url() -> Optional[str]:
        """
        Get the manifest repository URL from environment.

        Returns:
            Repository URL or None if not set
        """
        return Config.get("MANIFEST_REPO_URL") or None

    @staticmethod
    def argocd_app_repo_url() -> str:
        """
        Get the ArgoCD application repository URL from environment.

        Returns:
            Repository URL or empty string if not set
        """
        return Config.get("ARGOCD_APP_REPO_URL", "")

    @staticmethod
    def argocd_apps_subdir() -> str:
        """
        Get the ArgoCD applications subdirectory.

        Returns:
            Subdirectory name (defaults to "apps")
        """
        return Config.get("ARGOCD_APPS_SUBDIR", "apps")

    @staticmethod
    def docker_project_id() -> Optional[str]:
        """
        Get the Docker registry project ID from environment.

        Returns:
            Project ID or None if not set
        """
        return Config.get("DOCKER_PROJECT_ID") or None

    @staticmethod
    def docker_region() -> str:
        """
        Get the Docker registry region from environment.

        Returns:
            Region (defaults to "us-central1")
        """
        return Config.get("DOCKER_REGION", "us-central1")

    @staticmethod
    def docker_repository_name() -> str:
        """
        Get the Docker repository name from environment.

        Returns:
            Repository name (defaults to "default")
        """
        return Config.get("DOCKER_REPOSITORY_NAME", "default")

    @staticmethod
    def github_repository() -> str:
        """
        Get the GitHub repository name from environment.

        Returns:
            Repository name or empty string if not set
        """
        return Config.get("GITHUB_REPOSITORY", "")


# Global config instance for convenience
config = Config()
