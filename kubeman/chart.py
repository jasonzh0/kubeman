from abc import abstractmethod
from pathlib import Path
import tempfile
import yaml
from kubeman.template import Template
from kubeman.executor import get_executor
from kubeman.resource_utils import CLUSTER_SCOPED_KINDS


class HelmChart(Template):
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

    def extra_manifests(self) -> list[dict]:
        """Return any additional manifests that should be rendered with this chart"""
        return []

    def render(self) -> None:
        """
        Render both helm chart and extra manifests.
        """
        # Render helm chart if any
        self.render_helm()

        # Render extra manifests if any
        self.render_extra()

        # Write Application manifest if ArgoCD is enabled
        if self.enable_argocd() and self.application_repo_url():
            self._write_application()

    def ensure_helm_repo(self) -> str:
        """
        Ensure the helm repository is added and updated, then return the repo name.
        """
        executor = get_executor()
        repo_name = f"repo-{self.name}"
        result = executor.run_silent(["helm", "repo", "list"])
        # Split into lines and check for exact match to avoid substring matches
        repo_lines = result.stdout.splitlines()
        repo_exists = any(line.split()[0] == repo_name for line in repo_lines if line.strip())
        if not repo_exists:
            executor.run(
                ["helm", "repo", "add", repo_name, self.repository["remote"]],
                check=True,
            )
        # Always update the repo to ensure we have the latest chart versions
        executor.run(
            ["helm", "repo", "update", repo_name],
            check=True,
        )
        return repo_name

    def full_helm_package_name(self) -> str:
        """Get the full Helm package name based on repository type."""
        if self.repository["type"] == "classic":
            repo_name = self.ensure_helm_repo()
            repo_package = self.repository_package
            return f"{repo_name}/{repo_package}"
        elif self.repository["type"] == "oci":
            repo_name = self.repository["remote"]
            repo_package = self.repository_package
            return f"{repo_name}/{repo_package}"
        elif self.repository["type"] == "none":
            return self.repository.get("remote", "")
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

        executor = get_executor()
        print(f"\nRendering helm chart for {self.name}...")
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write values to temporary file
            values_file = Path(tmpdir) / "values.yaml"
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
                str(values_file),
                "--namespace",
                self.namespace,
                "--include-crds",
            ]

            # Run helm template
            try:
                result = executor.run(cmd, capture_output=True, text=True, check=True)

                # Post-process the output to ensure all namespace-scoped resources have the namespace set
                # Some Helm charts don't include namespace in metadata even when --namespace is specified
                output_content = result.stdout
                if self.namespace:
                    # Parse YAML documents and add namespace to resources that don't have it
                    documents = list(yaml.safe_load_all(output_content))
                    processed_docs = []

                    for doc in documents:
                        if doc is None:
                            continue
                        if not isinstance(doc, dict):
                            processed_docs.append(doc)
                            continue

                        kind = doc.get("kind", "")
                        metadata = doc.get("metadata", {})

                        # Skip cluster-scoped resources
                        if kind in CLUSTER_SCOPED_KINDS:
                            processed_docs.append(doc)
                            continue

                        # Add namespace if not present
                        if isinstance(metadata, dict) and "namespace" not in metadata:
                            metadata["namespace"] = self.namespace
                            doc["metadata"] = metadata

                        processed_docs.append(doc)

                    # Reconstruct YAML
                    output_content = ""
                    for doc in processed_docs:
                        output_content += yaml.dump(doc)
                        output_content += "---\n"

                # Write output to manifests directory
                manifests_dir = self.manifests_dir()
                if isinstance(manifests_dir, str):
                    manifests_dir = Path(manifests_dir)
                output_dir = manifests_dir / self.name
                output_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_dir / f"{self.name}-manifests.yaml"

                print(f"Writing helm output to {output_file}")
                with open(output_file, "w") as f:
                    f.write(output_content)
            except Exception as e:
                raise RuntimeError(f"Helm template failed: {e}")

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
        manifests_dir = self.manifests_dir()
        if isinstance(manifests_dir, str):
            manifests_dir = Path(manifests_dir)
        output_dir = manifests_dir / self.name
        output_dir.mkdir(parents=True, exist_ok=True)

        for manifest in extra_manifests:
            if not manifest.get("metadata") or not manifest["metadata"].get("name"):
                raise ValueError(f"Manifest {manifest} has no metadata or name")

            if not manifest.get("kind"):
                raise ValueError(f"Manifest {manifest} has no kind")

            manifest_name = manifest["metadata"]["name"]
            manifest_kind = manifest["kind"].lower()
            output_file = output_dir / f"{manifest_name}-{manifest_kind}.yaml"

            if output_file.exists():
                print(
                    f"Overwriting existing manifest {manifest_name} ({manifest_kind}) at {output_file}"
                )
            else:
                print(f"Writing manifest {manifest_name} ({manifest_kind}) to {output_file}")

            with open(output_file, "w") as f:
                yaml.dump(manifest, f)
