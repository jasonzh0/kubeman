from abc import ABC, abstractmethod
import os
import tempfile
import subprocess
import yaml
from kubeman.git import GitManager


class HelmChart(ABC):
    def __init__(self):
        self._version = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the chart"""
        pass

    @property
    @abstractmethod
    def repository(self) -> dict:
        """Return the repository information as a dictionary with type and remote fields"""
        pass

    @property
    @abstractmethod
    def namespace(self) -> str:
        """Return the namespace where the chart should be installed"""
        pass

    @property
    def repository_package(self) -> str:
        """
        Return the package name in the repository.
        Defaults to the chart name, but can be overridden for repos with different naming.
        """
        return self.name

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the version of the chart to install"""
        pass

    @abstractmethod
    def generate_values(self) -> dict:
        """Generate the values.yaml content for this chart"""
        pass

    def to_values_yaml(self) -> str:
        """Convert the values dict to YAML format"""
        values = self.generate_values()
        return yaml.dump(values, default_flow_style=False)

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
        """Generate the ArgoCD Application manifest for this chart"""
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

    def extra_manifests(self) -> list[dict]:
        """Return any additional manifests that should be rendered with this chart"""
        return []

    def apps_subdirectory(self) -> str:
        """Return the subdirectory name for applications. Override to customize."""
        return os.getenv("ARGOCD_APPS_SUBDIR", "apps")

    def render(self) -> None:
        """
        Render both helm chart and extra manifests.
        """
        # Ensure apps directory exists
        apps_dir = os.path.join(self.manifests_dir(), self.apps_subdirectory())
        os.makedirs(apps_dir, exist_ok=True)

        # Render helm chart if any
        self.render_helm()

        # Render extra manifests if any
        self.render_extra()

        # Write Application manifest
        app_file = os.path.join(apps_dir, f"{self.name}-application.yaml")
        with open(app_file, "w") as f:
            yaml.dump(self.generate_application(), f)

    def ensure_helm_repo(self) -> str:
        """
        Ensure the helm repository is added and return the repo name.
        """
        repo_name = f"repo-{self.name}"
        result = subprocess.run(["helm", "repo", "list"], capture_output=True, text=True)
        # Split into lines and check for exact match to avoid substring matches
        repo_lines = result.stdout.splitlines()
        repo_exists = any(line.split()[0] == repo_name for line in repo_lines if line.strip())
        if not repo_exists:
            subprocess.run(
                ["helm", "repo", "add", repo_name, self.repository["remote"]],
                check=True,
            )
        return repo_name

    def full_helm_package_name(self) -> str:
        # Add helm repo if needed
        if self.repository["type"] == "classic":
            repo_name = self.ensure_helm_repo()
            repo_package = self.repository_package
            return f"{repo_name}/{repo_package}"
        if self.repository["type"] == "oci":
            repo_name = self.repository["remote"]
            repo_package = self.repository_package
            return f"{repo_name}/{repo_package}"
            return self.repository["remote"]
        else:
            raise ValueError(f"Unknown repository type: {self.repository['type']}")

    def render_helm(self) -> None:
        """
        Render the helm chart using helm template.
        Creates a temporary directory for values.yaml, runs helm template,
        and writes output to manifests directory.
        """
        if self.repository["type"] == "none":
            return

        print(f"\nRendering helm chart for {self.name}...")
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write values to temporary file
            values_file = os.path.join(tmpdir, "values.yaml")
            with open(values_file, "w") as f:
                f.write(self.to_values_yaml())

            # Build helm template command
            helm_package_name = self.full_helm_package_name()
            print(f"helm package name: {helm_package_name}")
            cmd = [
                "helm",
                "template",
                self.name,
                helm_package_name,
                "--version",
                self.version,
                "--values",
                values_file,
                "--namespace",
                self.namespace,
                "--include-crds",
            ]

            # Run helm template
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                # Write output to manifests directory
                output_dir = os.path.join(self.manifests_dir(), self.name)
                os.makedirs(output_dir, exist_ok=True)
                output_file = os.path.join(output_dir, f"{self.name}-manifests.yaml")

                print(f"Writing helm output to {output_file}")
                with open(output_file, "w") as f:
                    f.write(result.stdout)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Helm template failed: {e.stderr}")

    def render_extra(self) -> None:
        """
        Render any extra manifests.
        Each manifest will be written to a separate file named after its metadata.name.
        """
        extra_manifests = self.extra_manifests()
        if not extra_manifests:
            print(f"No extra manifests for {self.name}")
            return

        print(f"\nRendering {len(extra_manifests)} extra manifests for {self.name}...")
        output_dir = os.path.join(self.manifests_dir(), self.name)
        os.makedirs(output_dir, exist_ok=True)

        for manifest in extra_manifests:
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
