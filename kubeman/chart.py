from abc import abstractmethod
from pathlib import Path
import tempfile
import yaml
from kubeman.template import Template
from kubeman.executor import get_executor
from kubeman.resource_utils import (
    CLUSTER_SCOPED_KINDS,
    safe_manifest_path,
    validate_path_component,
)
from kubeman.output import get_output


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

    def split_helm_output(self) -> bool:
        """
        Return whether helm output should be split into one file per resource
        (``<metadata.name>-<kind>.yaml``, like KubernetesResource) instead of a
        single ``<name>-manifests.yaml``. Defaults to False (opt-in).
        """
        return False

    def render(self) -> None:
        """
        Render both helm chart and extra manifests.
        """
        self.render_helm()
        self.render_extra()

        if self.enable_argocd() and self.application_repo_url():
            self._write_application()

    def ensure_helm_repo(self) -> str:
        """
        Ensure the helm repository is added and updated, then return the repo name.
        """
        executor = get_executor()
        repo_name = f"repo-{self.name}"
        result = executor.run_silent(["helm", "repo", "list"])
        repo_lines = result.stdout.splitlines()
        repo_exists = any(line.split()[0] == repo_name for line in repo_lines if line.strip())
        if not repo_exists:
            executor.run(
                ["helm", "repo", "add", repo_name, self.repository["remote"]],
                check=True,
            )
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
        output = get_output()
        output.verbose(f"Rendering helm chart for {self.name}")
        with tempfile.TemporaryDirectory() as tmpdir:
            values_file = Path(tmpdir) / "values.yaml"
            with open(values_file, "w") as f:
                f.write(self.to_values_yaml())

            helm_package_name = self.full_helm_package_name()
            output.verbose(f"Helm package name: {helm_package_name}")
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

            try:
                result = executor.run(cmd, capture_output=True, text=True, check=True)

                output_content = result.stdout
                if self.namespace:
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

                        if kind in CLUSTER_SCOPED_KINDS:
                            processed_docs.append(doc)
                            continue

                        if isinstance(metadata, dict) and "namespace" not in metadata:
                            metadata["namespace"] = self.namespace
                            doc["metadata"] = metadata

                        processed_docs.append(doc)

                    output_content = ""
                    for doc in processed_docs:
                        output_content += yaml.dump(doc)
                        output_content += "---\n"

                manifests_dir = self.manifests_dir()
                if isinstance(manifests_dir, str):
                    manifests_dir = Path(manifests_dir)
                output_dir = manifests_dir / self.name
                output_dir.mkdir(parents=True, exist_ok=True)

                if self.split_helm_output():
                    self._write_split_helm_output(output_content, output_dir)
                else:
                    output_file = output_dir / f"{self.name}-manifests.yaml"
                    output.verbose(f"Writing helm output to {output_file}")
                    with open(output_file, "w") as f:
                        f.write(output_content)
            except Exception as e:
                raise RuntimeError(f"Helm template failed: {e}")

    def _write_split_helm_output(self, output_content: str, output_dir: Path) -> None:
        """
        Write helm output as one file per resource (``<name>-<kind>.yaml``).

        Resources sharing a name and kind (e.g. across namespaces) are grouped
        into the same file as a multi-document YAML. Documents without a usable
        metadata.name/kind fall back to ``<chart name>-manifests.yaml``.
        """
        output = get_output()
        grouped: dict[Path, list] = {}
        fallback_docs: list = []

        for doc in yaml.safe_load_all(output_content):
            if doc is None:
                continue
            metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            manifest_name = metadata.get("name") if isinstance(metadata, dict) else None
            manifest_kind = doc.get("kind") if isinstance(doc, dict) else None
            if not isinstance(manifest_name, str) or not isinstance(manifest_kind, str):
                fallback_docs.append(doc)
                continue
            try:
                output_file = safe_manifest_path(output_dir, manifest_name, manifest_kind.lower())
            except ValueError:
                fallback_docs.append(doc)
                continue
            grouped.setdefault(output_file, []).append(doc)

        output.verbose(f"Splitting helm output for {self.name} into {len(grouped)} file(s)")
        for output_file, docs in grouped.items():
            with open(output_file, "w") as f:
                yaml.dump_all(docs, f)

        if fallback_docs:
            fallback_file = output_dir / f"{self.name}-manifests.yaml"
            output.verbose(f"Writing {len(fallback_docs)} unnamed document(s) to {fallback_file}")
            with open(fallback_file, "w") as f:
                yaml.dump_all(fallback_docs, f)

    def render_extra(self) -> None:
        """
        Render any extra manifests.
        Each manifest will be written to a separate file named after its metadata.name.
        """
        output = get_output()
        extra_manifests = self.extra_manifests()
        if not extra_manifests:
            output.verbose(f"No extra manifests for {self.name}")
            return

        output.verbose(f"Rendering {len(extra_manifests)} extra manifests for {self.name}")
        manifests_dir = self.manifests_dir()
        if isinstance(manifests_dir, str):
            manifests_dir = Path(manifests_dir)
        output_dir = manifests_dir / validate_path_component(self.name, field="template name")
        output_dir.mkdir(parents=True, exist_ok=True)

        for manifest in extra_manifests:
            if not manifest.get("metadata") or not manifest["metadata"].get("name"):
                raise ValueError(f"Manifest {manifest} has no metadata or name")

            if not manifest.get("kind"):
                raise ValueError(f"Manifest {manifest} has no kind")

            manifest_name = manifest["metadata"]["name"]
            manifest_kind = manifest["kind"].lower()
            output_file = safe_manifest_path(output_dir, manifest_name, manifest_kind)

            if output_file.exists():
                output.verbose(
                    f"Overwriting existing manifest {manifest_name} ({manifest_kind}) at {output_file}"
                )
            else:
                output.verbose(
                    f"Writing manifest {manifest_name} ({manifest_kind}) to {output_file}"
                )

            with open(output_file, "w") as f:
                yaml.dump(manifest, f)
