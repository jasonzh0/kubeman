"""
ArgoCD Application manifest generation.

Extracted from template.py to separate ArgoCD concerns from core template logic.
"""

import os
from typing import Optional, Dict, Any
from kubeman.config import Config


class ArgoCDApplicationGenerator:
    """
    Generates ArgoCD Application manifests for templates.

    Handles all ArgoCD-specific logic separately from core template rendering.
    """

    def __init__(self, template_name: str, namespace: str):
        """
        Initialize the ArgoCD application generator.

        Args:
            template_name: Name of the template/chart
            namespace: Kubernetes namespace
        """
        self.template_name = template_name
        self.namespace = namespace

    def generate(
        self,
        repo_url: Optional[str] = None,
        target_revision: Optional[str] = None,
        path: Optional[str] = None,
        ignore_differences: Optional[list] = None,
        managed_namespace_metadata: Optional[Dict[str, str]] = None,
        apps_subdir: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate an ArgoCD Application manifest.

        Args:
            repo_url: Repository URL (defaults to ARGOCD_APP_REPO_URL env var)
            target_revision: Target revision/branch (defaults to git branch)
            path: Path in repository (defaults to template name)
            ignore_differences: List of ignore difference specs
            managed_namespace_metadata: Labels to add to managed namespaces
            apps_subdir: Subdirectory for applications (defaults to "apps")

        Returns:
            ArgoCD Application manifest dict or None if repo_url is not set
        """
        # Get repo URL from parameter or environment
        repo_url = repo_url or Config.argocd_app_repo_url()
        if not repo_url:
            return None

        # Get target revision (default to git branch)
        if target_revision is None:
            try:
                target_revision = Config.git_branch()
            except ValueError:
                # If git branch not available, use "main" as fallback
                target_revision = "main"

        # Default path to template name
        path = path or self.template_name

        # Build the application manifest
        app: Dict[str, Any] = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": self.template_name,
                "namespace": "argocd",  # ArgoCD applications always live in argocd namespace
            },
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": repo_url,
                    "targetRevision": target_revision,
                    "path": path,
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
            },
        }

        # Add ignore differences if provided
        if ignore_differences:
            app["spec"]["ignoreDifferences"] = ignore_differences

        # Add managed namespace metadata if provided
        if managed_namespace_metadata:
            app["spec"]["syncPolicy"]["managedNamespaceMetadata"] = {
                "labels": managed_namespace_metadata
            }

        return app
