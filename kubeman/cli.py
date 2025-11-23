#!/usr/bin/env python3
"""
Command-line interface for kubeman.

Provides commands to render and apply Kubernetes manifests using templates.py files.
"""

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Optional, Tuple, List
import yaml

from kubeman.register import TemplateRegistry
from kubeman.template import Template
from kubeman.executor import get_executor
from kubeman.resource_utils import CLUSTER_SCOPED_KINDS


def load_templates_file(file_path: str) -> None:
    """
    Dynamically import a templates.py file to trigger template registration.

    Args:
        file_path: Path to the templates.py file

    Raises:
        FileNotFoundError: If the file doesn't exist
        ImportError: If the file cannot be imported
    """
    file_path_obj = Path(file_path).resolve()

    if not file_path_obj.exists():
        raise FileNotFoundError(f"Templates file not found: {file_path_obj}")

    if file_path_obj.suffix != ".py":
        raise ValueError(f"Templates file must be a Python file (.py): {file_path_obj}")

    # Get module name from file path
    module_name = file_path_obj.stem

    # Load the module
    spec = importlib.util.spec_from_file_location(module_name, str(file_path_obj))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from file: {file_path_obj}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(f"Error importing templates file {file_path_obj}: {e}") from e


def _contains_crd(yaml_file: Path) -> bool:
    """
    Check if a YAML file contains any CustomResourceDefinition resources.

    Handles both single-document and multi-document YAML files.

    Args:
        yaml_file: Path to the YAML file to check

    Returns:
        True if the file contains at least one CRD, False otherwise
    """
    try:
        with open(yaml_file, "r") as f:
            # Handle multi-document YAML files
            documents = list(yaml.safe_load_all(f))

            for doc in documents:
                if doc is None:
                    continue
                if isinstance(doc, dict) and doc.get("kind") == "CustomResourceDefinition":
                    return True
    except (yaml.YAMLError, IOError, OSError):
        # If we can't parse the file, assume it's not a CRD
        # This allows the apply to proceed and kubectl will handle the error
        return False

    return False


def _extract_crds_from_yaml(yaml_file: Path) -> Optional[Path]:
    """
    Extract CRDs from a multi-document YAML file to a temporary file.

    Args:
        yaml_file: Path to the YAML file

    Returns:
        Path to temporary file with CRDs only, or None if no CRDs found
    """
    import tempfile

    try:
        with open(yaml_file, "r") as f:
            documents = list(yaml.safe_load_all(f))

        crd_docs = []
        for doc in documents:
            if doc is None:
                continue
            if isinstance(doc, dict) and doc.get("kind") == "CustomResourceDefinition":
                crd_docs.append(doc)

        if not crd_docs:
            return None

        # Create temporary file with CRDs only
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, dir=yaml_file.parent
        )
        for doc in crd_docs:
            yaml.dump(doc, temp_file)
            temp_file.write("---\n")
        temp_file.close()

        return Path(temp_file.name)
    except (yaml.YAMLError, IOError, OSError):
        return None


def _contains_namespace(yaml_file: Path) -> bool:
    """
    Check if a YAML file contains a Namespace resource.

    Args:
        yaml_file: Path to the YAML file to check

    Returns:
        True if the file contains at least one Namespace, False otherwise
    """
    try:
        with open(yaml_file, "r") as f:
            documents = list(yaml.safe_load_all(f))

            for doc in documents:
                if doc is None:
                    continue
                if isinstance(doc, dict) and doc.get("kind") == "Namespace":
                    return True
    except (yaml.YAMLError, IOError, OSError):
        return False

    return False


def _categorize_yaml_files(yaml_files: List[Path]) -> Tuple[List[Path], List[Path], List[Path]]:
    """
    Categorize YAML files into CRDs, Namespaces, and other resources.

    Files that contain CRDs are categorized as CRD files, but if they also contain
    namespace-scoped resources, they need to be applied after namespaces exist.

    Args:
        yaml_files: List of YAML file paths to categorize

    Returns:
        Tuple of (crd_only_files, namespace_files, other_files) - all lists are sorted
        Note: Files with both CRDs and namespace-scoped resources go in other_files
    """
    crd_only_files: List[Path] = []
    namespace_files: List[Path] = []
    other_files: List[Path] = []

    for yaml_file in yaml_files:
        has_crd = _contains_crd(yaml_file)
        has_namespace = _contains_namespace(yaml_file)

        if has_namespace:
            namespace_files.append(yaml_file)
        elif has_crd:
            # Check if file also has namespace-scoped resources
            # If it does, put it in other_files so it's applied after namespaces
            file_namespace = _extract_namespace_from_yaml(yaml_file)
            if file_namespace:
                # File has CRDs but also namespace-scoped resources
                other_files.append(yaml_file)
            else:
                # File only has CRDs (cluster-scoped)
                crd_only_files.append(yaml_file)
        else:
            other_files.append(yaml_file)

    # Sort all lists for consistent ordering
    return sorted(crd_only_files), sorted(namespace_files), sorted(other_files)


def _extract_namespace_from_yaml(yaml_file: Path) -> Optional[str]:
    """
    Extract namespace from a YAML file by parsing the first resource's metadata.

    Args:
        yaml_file: Path to the YAML file

    Returns:
        Namespace string if found, None otherwise (for cluster-scoped resources)
    """
    try:
        with open(yaml_file, "r") as f:
            documents = list(yaml.safe_load_all(f))

            for doc in documents:
                if doc is None or not isinstance(doc, dict):
                    continue

                # Check if this is a cluster-scoped resource
                kind = doc.get("kind", "")

                if kind in CLUSTER_SCOPED_KINDS:
                    continue  # Cluster-scoped, no namespace

                # Extract namespace from metadata
                metadata = doc.get("metadata", {})
                if isinstance(metadata, dict):
                    namespace = metadata.get("namespace")
                    if namespace:
                        return namespace
    except (yaml.YAMLError, IOError, OSError):
        # If we can't parse, return None and let kubectl handle it
        pass

    return None


def _extract_namespace_resource_name(yaml_file: Path) -> Optional[str]:
    """
    Extract the name of a Namespace resource from a YAML file.

    Args:
        yaml_file: Path to the YAML file

    Returns:
        Namespace name if the file contains a Namespace resource, None otherwise
    """
    try:
        with open(yaml_file, "r") as f:
            documents = list(yaml.safe_load_all(f))

            for doc in documents:
                if doc is None or not isinstance(doc, dict):
                    continue
                if doc.get("kind") == "Namespace":
                    metadata = doc.get("metadata", {})
                    if isinstance(metadata, dict):
                        return metadata.get("name")
    except (yaml.YAMLError, IOError, OSError):
        pass

    return None


def _filter_manifests_by_template_names(
    yaml_files: List[Path], template_names: List[str], manifests_dir_path: Path
) -> List[Path]:
    """
    Filter manifest files to only include those belonging to the specified templates.

    Args:
        yaml_files: List of YAML file paths
        template_names: List of template names to filter by
        manifests_dir_path: Base path to the manifests directory

    Returns:
        Filtered list of YAML files that belong to the specified templates
    """
    if not template_names:
        return yaml_files

    # Normalize paths for comparison
    manifests_dir_path = manifests_dir_path.resolve()
    template_name_set = set(template_names)

    filtered_files: List[Path] = []
    for yaml_file in yaml_files:
        yaml_file_resolved = yaml_file.resolve()

        # Check if file is in a template directory: manifests/{template_name}/*
        relative_path = yaml_file_resolved.relative_to(manifests_dir_path)
        path_parts = relative_path.parts

        # Check if file is in a template subdirectory
        if len(path_parts) >= 2:
            # Path structure: {template_name}/filename.yaml
            template_dir_name = path_parts[0]
            if template_dir_name in template_name_set:
                filtered_files.append(yaml_file)
                continue

        # Check if file is an ArgoCD application file: manifests/apps/{template_name}-application.yaml
        if len(path_parts) >= 2 and path_parts[0] == "apps":
            # Path structure: apps/{template_name}-application.yaml
            app_filename = path_parts[1]
            # Check if filename matches pattern: {template_name}-application.yaml
            for template_name in template_name_set:
                if app_filename == f"{template_name}-application.yaml":
                    filtered_files.append(yaml_file)
                    break

    return filtered_files


def _filter_manifests_by_namespace(
    yaml_files: List[Path], namespace_filter: Optional[str]
) -> List[Path]:
    """
    Filter manifest files by namespace if a namespace filter is provided.

    Args:
        yaml_files: List of YAML file paths
        namespace_filter: Optional namespace to filter by

    Returns:
        Filtered list of YAML files that match the namespace (or all if no filter)
    """
    if namespace_filter is None:
        return yaml_files

    filtered_files: List[Path] = []
    for yaml_file in yaml_files:
        file_namespace = _extract_namespace_from_yaml(yaml_file)
        namespace_resource_name = _extract_namespace_resource_name(yaml_file)

        # Include if:
        # 1. File namespace matches filter
        # 2. File contains a Namespace resource with name matching the filter
        # 3. File has no namespace and is not a Namespace resource (cluster-scoped like CRDs)
        if file_namespace == namespace_filter:
            filtered_files.append(yaml_file)
        elif namespace_resource_name == namespace_filter:
            # This is a Namespace resource with the matching name
            filtered_files.append(yaml_file)
        elif file_namespace is None and namespace_resource_name is None:
            # Cluster-scoped resource that's not a Namespace (e.g., CRD, ClusterRole)
            filtered_files.append(yaml_file)
        # Exclude: Namespace resources with different names, or namespace-scoped resources in different namespaces

    return filtered_files


def render_templates(manifests_dir: Optional[Path] = None) -> List[str]:
    """
    Render all registered templates to the manifests directory.

    Args:
        manifests_dir: Optional custom directory for manifests output.
                      If None, uses default from Config.

    Returns:
        List of template names (strings) that were successfully rendered.

    Raises:
        ValueError: If no templates are registered
        RuntimeError: If rendering fails
    """
    # Set custom manifests directory if provided
    original_dir = None
    if manifests_dir is not None:
        original_dir = Template.manifests_dir()  # Store original
        Template.set_manifests_dir(Path(manifests_dir).resolve())

    rendered_template_names: List[str] = []

    try:
        templates = TemplateRegistry.get_registered_templates()

        if not templates:
            raise ValueError(
                "No templates registered. Make sure your templates.py file registers templates using @TemplateRegistry.register"
            )

        print(f"Found {len(templates)} registered template(s)")

        for template_class in templates:
            try:
                print(f"\nRendering template: {template_class.__name__}")
                template = template_class()
                template.render()
                # Track the template name after successful rendering
                rendered_template_names.append(template.name)
                print(f"✓ Successfully rendered {template_class.__name__}")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to render template {template_class.__name__}: {e}"
                ) from e
    finally:
        # Reset to original directory
        if manifests_dir is not None:
            Template.set_manifests_dir(original_dir)

    return rendered_template_names


def apply_manifests(
    namespace: Optional[str] = None,
    manifests_dir: Optional[Path] = None,
    template_names: Optional[List[str]] = None,
) -> None:
    """
    Apply rendered manifests to Kubernetes cluster using kubectl.

    Args:
        namespace: Optional namespace to filter or set context
        manifests_dir: Optional custom directory for manifests.
                      If None, uses default from Config.
        template_names: Optional list of template names to filter by.
                       If provided, only manifests from these templates will be applied.
                       If None, all manifests in the directory will be applied (backward compatible).

    Raises:
        FileNotFoundError: If kubectl is not found
        RuntimeError: If kubectl apply fails
    """
    # Set custom manifests directory if provided
    original_dir = None
    if manifests_dir is not None:
        original_dir = Template.manifests_dir()  # Store original
        Template.set_manifests_dir(Path(manifests_dir).resolve())

    try:
        executor = get_executor()

        # Check if kubectl is available
        try:
            executor.run(["kubectl", "version", "--client"], check=True, capture_output=True)
        except Exception:
            raise FileNotFoundError(
                "kubectl not found. Please install kubectl and ensure it's in your PATH."
            )

        # Get manifests directory
        manifests_dir_path = Template.manifests_dir()
        if isinstance(manifests_dir_path, str):
            manifests_dir_path = Path(manifests_dir_path)

        if not manifests_dir_path.exists():
            raise RuntimeError(
                f"Manifests directory not found: {manifests_dir_path}. "
                "Templates must be rendered before applying."
            )

        # Find all YAML files recursively
        yaml_files = list(manifests_dir_path.rglob("*.yaml")) + list(
            manifests_dir_path.rglob("*.yml")
        )

        if not yaml_files:
            raise RuntimeError(
                f"No YAML files found in {manifests_dir_path}. "
                "Templates must be rendered before applying."
            )

        # Filter manifests by template names if provided
        if template_names is not None:
            yaml_files = _filter_manifests_by_template_names(
                yaml_files, template_names, manifests_dir_path
            )
            if not yaml_files:
                print(f"\nNo manifests found for registered templates: {', '.join(template_names)}")
                return

        # Filter manifests by namespace if provided
        if namespace:
            yaml_files = _filter_manifests_by_namespace(yaml_files, namespace)
            if not yaml_files:
                print(f"\nNo manifests found matching namespace: {namespace}")
                return

        # Categorize files into CRD-only files, Namespaces, and other resources
        # Files with both CRDs and namespace-scoped resources go in other_files
        crd_only_files, namespace_files, other_files = _categorize_yaml_files(yaml_files)

        # Extract CRDs from files that have both CRDs and other resources
        # These need to be applied first
        crd_extracted_files = []
        files_to_remove = []
        for yaml_file in other_files:
            if _contains_crd(yaml_file):
                crd_file = _extract_crds_from_yaml(yaml_file)
                if crd_file:
                    crd_extracted_files.append(crd_file)
                    # Note: We'll still apply the original file later for non-CRD resources

        print(f"\nApplying manifests from {manifests_dir_path}")
        if namespace:
            print(f"Filtering to namespace: {namespace}")
        print(f"Found {len(yaml_files)} manifest file(s)")
        total_crds = len(crd_only_files) + len(crd_extracted_files)
        if total_crds > 0:
            print(f"  - {total_crds} CRD file(s) will be applied first")
        if namespace_files:
            print(f"  - {len(namespace_files)} Namespace file(s) will be applied next")
        if other_files:
            print(f"  - {len(other_files)} other resource file(s)")

        # Apply in order: CRDs first (from CRD-only files and extracted from mixed files),
        # then Namespaces, then other resources
        # Namespaces must be created before any namespace-scoped resources
        # Each manifest is applied to its own namespace as specified in the file
        applied_count = 0

        # First apply all CRDs (cluster-scoped, no namespace needed)
        for yaml_file in crd_only_files + crd_extracted_files:
            cmd = ["kubectl", "apply", "-f", str(yaml_file)]
            try:
                executor.run(cmd, check=True, text=True, capture_output=True)
                applied_count += 1
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Failed to apply {yaml_file}: {error_msg}", file=sys.stderr)
                raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

        # Then apply Namespaces (must exist before namespace-scoped resources)
        for yaml_file in namespace_files:
            cmd = ["kubectl", "apply", "-f", str(yaml_file)]
            try:
                executor.run(cmd, check=True, text=True, capture_output=True)
                applied_count += 1
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Failed to apply {yaml_file}: {error_msg}", file=sys.stderr)
                raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

        # Finally apply other resources (which may depend on namespaces existing)
        for yaml_file in other_files:
            cmd = ["kubectl", "apply", "-f", str(yaml_file)]
            # Don't force namespace - let each manifest use its own namespace from metadata
            # kubectl will automatically use the namespace from the manifest file

            try:
                executor.run(cmd, check=True, text=True, capture_output=True)
                applied_count += 1
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Failed to apply {yaml_file}: {error_msg}", file=sys.stderr)
                raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

        print(f"✓ Successfully applied {applied_count} manifest file(s)")
    finally:
        # Reset to original directory
        if manifests_dir is not None:
            Template.set_manifests_dir(original_dir)


def cmd_render(args: argparse.Namespace) -> None:
    """Handle the render subcommand."""
    try:
        # Clear registry before loading
        TemplateRegistry.clear()

        # Set skip_builds flag if requested
        skip_builds = getattr(args, "skip_build", False)
        TemplateRegistry.set_skip_builds(skip_builds)

        # Load templates file (imports trigger registration)
        templates_file = args.file or "./templates.py"
        load_templates_file(templates_file)

        # Get optional output directory
        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
            except (TypeError, AttributeError):
                # If output_dir is not a valid path (e.g., Mock object), ignore it
                output_dir = None

        # Render all registered templates
        render_templates(manifests_dir=output_dir)
        print("\n✓ All templates rendered successfully")
    except (FileNotFoundError, ImportError, ValueError, RuntimeError) as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_apply(args: argparse.Namespace) -> None:
    """Handle the apply subcommand."""
    try:
        # Clear registry before loading
        TemplateRegistry.clear()

        # Set skip_builds flag if requested
        skip_builds = getattr(args, "skip_build", False)
        TemplateRegistry.set_skip_builds(skip_builds)

        # Load templates file (imports trigger registration)
        templates_file = args.file or "./templates.py"
        load_templates_file(templates_file)

        # Get optional output directory
        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
            except (TypeError, AttributeError):
                # If output_dir is not a valid path (e.g., Mock object), ignore it
                output_dir = None

        # Render all registered templates and get their names
        template_names = render_templates(manifests_dir=output_dir)
        print("\n✓ Templates rendered successfully")

        # Apply manifests to cluster (only from registered templates)
        apply_manifests(
            namespace=args.namespace, manifests_dir=output_dir, template_names=template_names
        )
    except (FileNotFoundError, ImportError, ValueError, RuntimeError) as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for kubeman CLI."""
    parser = argparse.ArgumentParser(
        description="Kubeman - Render and apply Kubernetes manifests using templates.py files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  kubeman render --file examples/kafka/templates.py
  kubeman apply --file examples/kafka/templates.py
  # Or from examples/kafka directory:
  kubeman render
  kubeman apply

The templates.py file should import template modules to trigger registration via
@TemplateRegistry.register decorators.
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Render subcommand
    render_parser = subparsers.add_parser(
        "render",
        help="Render all registered templates to manifests directory",
    )
    render_parser.add_argument(
        "--file",
        help="Path to templates.py file (defaults to ./templates.py)",
    )
    render_parser.add_argument(
        "--output-dir",
        help="Output directory for manifests (defaults to ./manifests or MANIFESTS_DIR env var)",
    )
    render_parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip Docker image build steps during template registration",
    )
    render_parser.set_defaults(func=cmd_render)

    # Apply subcommand
    apply_parser = subparsers.add_parser(
        "apply",
        help="Render templates and apply manifests to Kubernetes cluster",
    )
    apply_parser.add_argument(
        "--file",
        help="Path to templates.py file (defaults to ./templates.py)",
    )
    apply_parser.add_argument(
        "--output-dir",
        help="Output directory for manifests (defaults to ./manifests or MANIFESTS_DIR env var)",
    )
    apply_parser.add_argument(
        "--namespace",
        help="Kubernetes namespace to use for apply",
    )
    apply_parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip Docker image build steps during template registration",
    )
    apply_parser.set_defaults(func=cmd_apply)

    args = parser.parse_args()

    # Call the appropriate command handler
    args.func(args)


if __name__ == "__main__":
    main()
