#!/usr/bin/env python3
"""
Command-line interface for kubeman.

Provides commands to render and apply Kubernetes manifests using kubeman.py files.
"""

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import yaml

from kubeman.register import TemplateRegistry
from kubeman.template import Template
from kubeman.executor import get_executor
from kubeman.resource_utils import CLUSTER_SCOPED_KINDS


def load_templates_file(file_path: str) -> None:
    """
    Dynamically import a kubeman.py file to trigger template registration.

    Args:
        file_path: Path to the kubeman.py file

    Raises:
        FileNotFoundError: If the file doesn't exist
        ImportError: If the file cannot be imported
    """
    file_path_obj = Path(file_path).resolve()

    if not file_path_obj.exists():
        raise FileNotFoundError(f"Templates file not found: {file_path_obj}")

    if file_path_obj.suffix != ".py":
        raise ValueError(f"Templates file must be a Python file (.py): {file_path_obj}")

    # If the file is named kubeman.py, use a unique module name to avoid conflicts
    # with the kubeman package
    if file_path_obj.stem == "kubeman":
        module_name = f"kubeman_templates_{id(file_path_obj)}"
    else:
        module_name = file_path_obj.stem

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
            documents = list(yaml.safe_load_all(f))

            for doc in documents:
                if doc is None:
                    continue
                if isinstance(doc, dict) and doc.get("kind") == "CustomResourceDefinition":
                    return True
    except (yaml.YAMLError, IOError, OSError):
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
            file_namespace = _extract_namespace_from_yaml(yaml_file)
            if file_namespace:
                other_files.append(yaml_file)
            else:
                crd_only_files.append(yaml_file)
        else:
            other_files.append(yaml_file)

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

                kind = doc.get("kind", "")

                if kind in CLUSTER_SCOPED_KINDS:
                    continue

                metadata = doc.get("metadata", {})
                if isinstance(metadata, dict):
                    namespace = metadata.get("namespace")
                    if namespace:
                        return namespace
    except (yaml.YAMLError, IOError, OSError):
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

    manifests_dir_path = manifests_dir_path.resolve()
    template_name_set = set(template_names)

    filtered_files: List[Path] = []
    for yaml_file in yaml_files:
        yaml_file_resolved = yaml_file.resolve()

        relative_path = yaml_file_resolved.relative_to(manifests_dir_path)
        path_parts = relative_path.parts

        if len(path_parts) >= 2:
            template_dir_name = path_parts[0]
            if template_dir_name in template_name_set:
                filtered_files.append(yaml_file)
                continue

        if len(path_parts) >= 2 and path_parts[0] == "apps":
            app_filename = path_parts[1]
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

        if file_namespace == namespace_filter:
            filtered_files.append(yaml_file)
        elif namespace_resource_name == namespace_filter:
            filtered_files.append(yaml_file)
        elif file_namespace is None and namespace_resource_name is None:
            filtered_files.append(yaml_file)

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
    original_dir = None
    if manifests_dir is not None:
        original_dir = Template.manifests_dir()
        Template.set_manifests_dir(Path(manifests_dir).resolve())

    rendered_template_names: List[str] = []

    try:
        templates = TemplateRegistry.get_registered_templates()

        if not templates:
            raise ValueError(
                "No templates registered. Make sure your kubeman.py file registers templates using @TemplateRegistry.register"
            )

        print(f"Found {len(templates)} registered template(s)")

        for template_class in templates:
            try:
                print(f"\nRendering template: {template_class.__name__}")
                template = template_class()
                template.render()
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
    manifests_dir: Optional[Path] = None,
    template_names: Optional[List[str]] = None,
) -> None:
    """
    Apply rendered manifests to Kubernetes cluster using kubectl.

    Args:
        manifests_dir: Optional custom directory for manifests.
                      If None, uses default from Config.
        template_names: Optional list of template names to filter by.
                       If provided, only manifests from these templates will be applied.
                       If None, all manifests in the directory will be applied (backward compatible).

    Raises:
        FileNotFoundError: If kubectl is not found
        RuntimeError: If kubectl apply fails
    """
    original_dir = None
    if manifests_dir is not None:
        original_dir = Template.manifests_dir()
        Template.set_manifests_dir(Path(manifests_dir).resolve())

    try:
        executor = get_executor()

        try:
            executor.run(["kubectl", "version", "--client"], check=True, capture_output=True)
        except Exception:
            raise FileNotFoundError(
                "kubectl not found. Please install kubectl and ensure it's in your PATH."
            )

        manifests_dir_path = Template.manifests_dir()
        if isinstance(manifests_dir_path, str):
            manifests_dir_path = Path(manifests_dir_path)

        if not manifests_dir_path.exists():
            raise RuntimeError(
                f"Manifests directory not found: {manifests_dir_path}. "
                "Templates must be rendered before applying."
            )

        yaml_files = list(manifests_dir_path.rglob("*.yaml")) + list(
            manifests_dir_path.rglob("*.yml")
        )

        if not yaml_files:
            raise RuntimeError(
                f"No YAML files found in {manifests_dir_path}. "
                "Templates must be rendered before applying."
            )

        if template_names is not None:
            yaml_files = _filter_manifests_by_template_names(
                yaml_files, template_names, manifests_dir_path
            )
            if not yaml_files:
                print(f"\nNo manifests found for registered templates: {', '.join(template_names)}")
                return

        crd_only_files, namespace_files, other_files = _categorize_yaml_files(yaml_files)

        crd_extracted_files = []
        files_to_remove = []
        for yaml_file in other_files:
            if _contains_crd(yaml_file):
                crd_file = _extract_crds_from_yaml(yaml_file)
                if crd_file:
                    crd_extracted_files.append(crd_file)

        print(f"\nApplying manifests from {manifests_dir_path}")
        print(f"Found {len(yaml_files)} manifest file(s)")
        total_crds = len(crd_only_files) + len(crd_extracted_files)
        if total_crds > 0:
            print(f"  - {total_crds} CRD file(s) will be applied first")
        if namespace_files:
            print(f"  - {len(namespace_files)} Namespace file(s) will be applied next")
        if other_files:
            print(f"  - {len(other_files)} other resource file(s)")

        applied_count = 0

        for yaml_file in crd_only_files + crd_extracted_files:
            cmd = ["kubectl", "apply", "-f", str(yaml_file)]
            try:
                executor.run(cmd, check=True, text=True, capture_output=True)
                applied_count += 1
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Failed to apply {yaml_file}: {error_msg}", file=sys.stderr)
                raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

        for yaml_file in namespace_files:
            cmd = ["kubectl", "apply", "-f", str(yaml_file)]
            try:
                executor.run(cmd, check=True, text=True, capture_output=True)
                applied_count += 1
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Failed to apply {yaml_file}: {error_msg}", file=sys.stderr)
                raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

        for yaml_file in other_files:
            cmd = ["kubectl", "apply", "-f", str(yaml_file)]

            try:
                executor.run(cmd, check=True, text=True, capture_output=True)
                applied_count += 1
            except Exception as e:
                error_msg = str(e)
                print(f"✗ Failed to apply {yaml_file}: {error_msg}", file=sys.stderr)
                raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

        print(f"✓ Successfully applied {applied_count} manifest file(s)")
    finally:
        if manifests_dir is not None:
            Template.set_manifests_dir(original_dir)


def cmd_render(args: argparse.Namespace) -> None:
    """Handle the render subcommand."""
    try:
        TemplateRegistry.clear()

        skip_builds = getattr(args, "skip_build", False)
        TemplateRegistry.set_skip_builds(skip_builds)

        # Load templates file (imports trigger registration)
        templates_file = args.file or "./kubeman.py"
        load_templates_file(templates_file)

        # Get optional output directory
        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
            except (TypeError, AttributeError):
                output_dir = None

        render_templates(manifests_dir=output_dir)
        print("\n✓ All templates rendered successfully")
    except (FileNotFoundError, ImportError, ValueError, RuntimeError) as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_apply(args: argparse.Namespace) -> None:
    """Handle the apply subcommand."""
    try:
        TemplateRegistry.clear()

        skip_builds = getattr(args, "skip_build", False)
        TemplateRegistry.set_skip_builds(skip_builds)

        templates_file = args.file or "./kubeman.py"
        load_templates_file(templates_file)

        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
            except (TypeError, AttributeError):
                output_dir = None

        template_names = render_templates(manifests_dir=output_dir)
        print("\n✓ Templates rendered successfully")

        apply_manifests(manifests_dir=output_dir, template_names=template_names)
    except (FileNotFoundError, ImportError, ValueError, RuntimeError) as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def generate_plan(
    manifests_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Generate a plan showing what would be built, applied, and loaded.

    Args:
        manifests_dir: Optional custom directory for manifests.
                      If None, uses default from Config.

    Returns:
        Dictionary containing plan information with keys:
        - templates_with_build: List of template names that would build images
        - templates_with_load: List of template names that would load images
        - template_names: List of all template names that would be rendered
        - manifest_files: Dictionary with categorized manifest files
          - crd_files: List of CRD file paths
          - namespace_files: List of Namespace file paths
          - other_files: List of other resource file paths
        - total_manifests: Total count of manifest files
    """
    original_dir = None
    if manifests_dir is not None:
        original_dir = Template.manifests_dir()
        Template.set_manifests_dir(Path(manifests_dir).resolve())

    plan: Dict[str, Any] = {
        "templates_with_build": [],
        "templates_with_load": [],
        "template_names": [],
        "manifest_files": {
            "crd_files": [],
            "namespace_files": [],
            "other_files": [],
        },
        "total_manifests": 0,
    }

    try:
        templates = TemplateRegistry.get_registered_templates()

        if not templates:
            return plan

        # Detect templates with build/load methods
        for template_class in templates:
            template_instance = template_class()
            template_name = template_instance.name
            plan["template_names"].append(template_name)

            if TemplateRegistry._has_custom_build(template_class):
                plan["templates_with_build"].append(template_name)

            if TemplateRegistry._has_custom_load(template_class):
                plan["templates_with_load"].append(template_name)

        # Render templates to see what manifests would be generated
        rendered_template_names = []
        for template_class in templates:
            try:
                template = template_class()
                template.render()
                rendered_template_names.append(template.name)
            except Exception as e:
                # Continue with other templates even if one fails
                # The plan should show what would succeed
                continue

        # Analyze rendered manifests (only from the templates we just rendered)
        manifests_dir_path = Template.manifests_dir()
        if isinstance(manifests_dir_path, str):
            manifests_dir_path = Path(manifests_dir_path)

        if manifests_dir_path.exists():
            yaml_files = list(manifests_dir_path.rglob("*.yaml")) + list(
                manifests_dir_path.rglob("*.yml")
            )

            # Filter by template names
            if rendered_template_names:
                yaml_files = _filter_manifests_by_template_names(
                    yaml_files, rendered_template_names, manifests_dir_path
                )

            crd_only_files, namespace_files, other_files = _categorize_yaml_files(yaml_files)

            plan["manifest_files"]["crd_files"] = [str(f) for f in crd_only_files] + [
                f"(extracted from {f})" for f in other_files if _contains_crd(f)
            ]
            plan["manifest_files"]["namespace_files"] = [str(f) for f in namespace_files]
            plan["manifest_files"]["other_files"] = [str(f) for f in other_files]
            plan["total_manifests"] = len(yaml_files)

    finally:
        # Reset to original directory
        if manifests_dir is not None:
            Template.set_manifests_dir(original_dir)

    return plan


def display_plan(plan: Dict[str, Any], verbose: bool = False) -> None:
    """
    Display the plan in a human-readable format.

    Args:
        plan: Plan dictionary from generate_plan()
        verbose: If True, show detailed output including file paths
    """
    print("\n" + "=" * 60)
    print("PLAN: What would be built, applied, and loaded")
    print("=" * 60)

    # Build operations
    print(f"\n📦 Build Operations:")
    build_count = len(plan["templates_with_build"])
    if build_count > 0:
        print(f"  {build_count} template(s) would build Docker images:")
        if verbose:
            for template_name in plan["templates_with_build"]:
                print(f"    - {template_name}")
        else:
            print(f"    Templates: {', '.join(plan['templates_with_build'])}")
    else:
        print("  No build operations would be executed")

    # Load operations
    print(f"\n🚚 Load Operations:")
    load_count = len(plan["templates_with_load"])
    if load_count > 0:
        print(f"  {load_count} template(s) would load Docker images into kind cluster:")
        if verbose:
            for template_name in plan["templates_with_load"]:
                print(f"    - {template_name}")
        else:
            print(f"    Templates: {', '.join(plan['templates_with_load'])}")
    else:
        print("  No load operations would be executed")

    # Render operations
    print(f"\n📝 Render Operations:")
    render_count = len(plan["template_names"])
    if render_count > 0:
        print(f"  {render_count} template(s) would be rendered:")
        if verbose:
            for template_name in plan["template_names"]:
                print(f"    - {template_name}")
        else:
            print(f"    Templates: {', '.join(plan['template_names'])}")
    else:
        print("  No templates would be rendered")

    # Apply operations
    print(f"\n⚙️  Apply Operations:")
    manifest_files = plan["manifest_files"]
    crd_count = len(manifest_files["crd_files"])
    namespace_count = len(manifest_files["namespace_files"])
    other_count = len(manifest_files["other_files"])
    total_manifests = plan["total_manifests"]

    if total_manifests > 0:
        print(f"  {total_manifests} manifest file(s) would be applied:")
        if crd_count > 0:
            print(f"    - {crd_count} CRD file(s) (applied first)")
            if verbose:
                for file_path in manifest_files["crd_files"]:
                    print(f"      • {file_path}")
        if namespace_count > 0:
            print(f"    - {namespace_count} Namespace file(s) (applied next)")
            if verbose:
                for file_path in manifest_files["namespace_files"]:
                    print(f"      • {file_path}")
        if other_count > 0:
            print(f"    - {other_count} other resource file(s)")
            if verbose:
                for file_path in manifest_files["other_files"]:
                    print(f"      • {file_path}")
    else:
        print("  No manifests would be applied")

    print("\n" + "=" * 60)


def cmd_plan(args: argparse.Namespace) -> None:
    """Handle the plan subcommand."""
    try:
        TemplateRegistry.clear()

        # Always skip builds and loads for plan command
        TemplateRegistry.set_skip_builds(True)
        TemplateRegistry.set_skip_loads(True)

        # Load templates file (imports trigger registration)
        templates_file = args.file or "./kubeman.py"
        load_templates_file(templates_file)

        # Get optional output directory
        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
            except (TypeError, AttributeError):
                output_dir = None

        # Generate plan
        plan = generate_plan(manifests_dir=output_dir)

        # Display plan
        verbose = getattr(args, "verbose", False)
        display_plan(plan, verbose=verbose)

    except (FileNotFoundError, ImportError, ValueError, RuntimeError) as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for kubeman CLI."""
    parser = argparse.ArgumentParser(
        description="Kubeman - Render and apply Kubernetes manifests using kubeman.py files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  kubeman render --file examples/kafka/kubeman.py
  kubeman apply --file examples/kafka/kubeman.py
  kubeman plan --file examples/kafka/kubeman.py
  kubeman render
  kubeman apply
  kubeman plan --verbose

The kubeman.py file should import template modules to trigger registration via
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
        help="Path to kubeman.py file (defaults to ./kubeman.py)",
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
        help="Path to kubeman.py file (defaults to ./kubeman.py)",
    )
    apply_parser.add_argument(
        "--output-dir",
        help="Output directory for manifests (defaults to ./manifests or MANIFESTS_DIR env var)",
    )
    apply_parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip Docker image build steps during template registration",
    )
    apply_parser.set_defaults(func=cmd_apply)

    # Plan subcommand
    plan_parser = subparsers.add_parser(
        "plan",
        help="Show what would be built, applied, and loaded without executing",
    )
    plan_parser.add_argument(
        "--file",
        help="Path to kubeman.py file (defaults to ./kubeman.py)",
    )
    plan_parser.add_argument(
        "--output-dir",
        help="Output directory for manifests (defaults to ./manifests or MANIFESTS_DIR env var)",
    )
    plan_parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip Docker image build steps during template registration (ignored for plan, always skipped)",
    )
    plan_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output including file paths and template names",
    )
    plan_parser.set_defaults(func=cmd_plan)

    args = parser.parse_args()

    # Call the appropriate command handler
    args.func(args)


if __name__ == "__main__":
    main()
