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


def _categorize_yaml_files(yaml_files: List[Path]) -> Tuple[List[Path], List[Path]]:
    """
    Categorize YAML files into CRDs and non-CRDs.

    Args:
        yaml_files: List of YAML file paths to categorize

    Returns:
        Tuple of (crd_files, non_crd_files) - both lists are sorted
    """
    crd_files: List[Path] = []
    non_crd_files: List[Path] = []

    for yaml_file in yaml_files:
        if _contains_crd(yaml_file):
            crd_files.append(yaml_file)
        else:
            non_crd_files.append(yaml_file)

    # Sort both lists for consistent ordering
    return sorted(crd_files), sorted(non_crd_files)


def render_templates(manifests_dir: Optional[Path] = None) -> None:
    """
    Render all registered templates to the manifests directory.

    Args:
        manifests_dir: Optional custom directory for manifests output.
                      If None, uses default from Config.

    Raises:
        ValueError: If no templates are registered
        RuntimeError: If rendering fails
    """
    # Set custom manifests directory if provided
    original_dir = None
    if manifests_dir is not None:
        original_dir = Template.manifests_dir()  # Store original
        Template.set_manifests_dir(Path(manifests_dir).resolve())

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
                print(f"✓ Successfully rendered {template_class.__name__}")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to render template {template_class.__name__}: {e}"
                ) from e
    finally:
        # Reset to original directory
        if manifests_dir is not None:
            Template.set_manifests_dir(original_dir)


def apply_manifests(namespace: Optional[str] = None, manifests_dir: Optional[Path] = None) -> None:
    """
    Apply rendered manifests to Kubernetes cluster using kubectl.

    Args:
        namespace: Optional namespace to filter or set context
        manifests_dir: Optional custom directory for manifests.
                      If None, uses default from Config.

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

        # Categorize files into CRDs and non-CRDs
        crd_files, non_crd_files = _categorize_yaml_files(yaml_files)

        print(f"\nApplying manifests from {manifests_dir_path}")
        if namespace:
            print(f"Using namespace: {namespace}")
        print(f"Found {len(yaml_files)} manifest file(s)")
        if crd_files:
            print(f"  - {len(crd_files)} CRD file(s) will be applied first")
            print(f"  - {len(non_crd_files)} other resource file(s)")

        # Apply CRDs first, then other resources
        applied_count = 0
        for yaml_file in crd_files + non_crd_files:
            cmd = ["kubectl", "apply", "-f", str(yaml_file)]
            # Note: CRDs are cluster-scoped, so --namespace flag is ignored for them
            # but we still pass it for consistency (kubectl will ignore it for cluster-scoped resources)
            if namespace:
                cmd.extend(["--namespace", namespace])

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
        print("\n✓ Templates rendered successfully")

        # Apply manifests to cluster
        apply_manifests(namespace=args.namespace, manifests_dir=output_dir)
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
    apply_parser.set_defaults(func=cmd_apply)

    args = parser.parse_args()

    # Call the appropriate command handler
    args.func(args)


if __name__ == "__main__":
    main()
