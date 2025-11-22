#!/usr/bin/env python3
"""
Command-line interface for kubeman.

Provides commands to render and apply Kubernetes manifests.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from kubeman.register import TemplateRegistry
from kubeman.template import Template


def load_template_file(file_path: str) -> None:
    """
    Dynamically import a Python file containing template definitions.

    Args:
        file_path: Path to the Python file to import

    Raises:
        FileNotFoundError: If the file doesn't exist
        ImportError: If the file cannot be imported
    """
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Template file not found: {file_path}")

    if not file_path.endswith(".py"):
        raise ValueError(f"Template file must be a Python file (.py): {file_path}")

    # Get module name from file path
    module_name = os.path.splitext(os.path.basename(file_path))[0]

    # Load the module
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from file: {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(f"Error importing template file {file_path}: {e}") from e


def render_templates() -> None:
    """
    Render all registered templates to the manifests directory.

    Raises:
        ValueError: If no templates are registered
        RuntimeError: If rendering fails
    """
    templates = TemplateRegistry.get_registered_templates()

    if not templates:
        raise ValueError(
            "No templates registered. Make sure your template file registers templates using @TemplateRegistry.register"
        )

    print(f"Found {len(templates)} registered template(s)")

    for template_class in templates:
        try:
            print(f"\nRendering template: {template_class.__name__}")
            template = template_class()
            template.render()
            print(f"✓ Successfully rendered {template_class.__name__}")
        except Exception as e:
            raise RuntimeError(f"Failed to render template {template_class.__name__}: {e}") from e


def apply_manifests(namespace: Optional[str] = None) -> None:
    """
    Apply rendered manifests to Kubernetes cluster using kubectl.

    Args:
        namespace: Optional namespace to filter or set context

    Raises:
        FileNotFoundError: If kubectl is not found
        RuntimeError: If kubectl apply fails
    """
    # Check if kubectl is available
    try:
        subprocess.run(["kubectl", "version", "--client"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise FileNotFoundError(
            "kubectl not found. Please install kubectl and ensure it's in your PATH."
        )

    # Get manifests directory
    manifests_dir = Template.manifests_dir()

    if not os.path.exists(manifests_dir):
        raise RuntimeError(
            f"Manifests directory not found: {manifests_dir}. "
            "Run 'kubeman render' first to generate manifests."
        )

    # Build kubectl apply command
    cmd = ["kubectl", "apply", "-f", manifests_dir]

    if namespace:
        cmd.extend(["--namespace", namespace])

    print(f"\nApplying manifests from {manifests_dir}")
    if namespace:
        print(f"Using namespace: {namespace}")

    try:
        subprocess.run(cmd, check=True, text=True)
        print("✓ Successfully applied manifests")
    except subprocess.CalledProcessError as e:
        print(f"✗ kubectl apply failed: {e.stderr}", file=sys.stderr)
        raise RuntimeError(f"kubectl apply failed with exit code {e.returncode}") from e


def cmd_render(args: argparse.Namespace) -> None:
    """Handle the render subcommand."""
    try:
        load_template_file(args.file)
        render_templates()
        print("\n✓ All templates rendered successfully")
    except (FileNotFoundError, ImportError, ValueError, RuntimeError) as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_apply(args: argparse.Namespace) -> None:
    """Handle the apply subcommand."""
    try:
        # Render first
        load_template_file(args.file)
        render_templates()
        print("\n✓ Templates rendered successfully")

        # Then apply
        apply_manifests(namespace=args.namespace)
    except (FileNotFoundError, ImportError, ValueError, RuntimeError) as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for kubeman CLI."""
    parser = argparse.ArgumentParser(
        description="Kubeman - Render and apply Kubernetes manifests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Render subcommand
    render_parser = subparsers.add_parser(
        "render",
        help="Render all registered templates to manifests directory",
    )
    render_parser.add_argument(
        "--file",
        required=True,
        help="Path to Python file containing template definitions",
    )
    render_parser.set_defaults(func=cmd_render)

    # Apply subcommand
    apply_parser = subparsers.add_parser(
        "apply",
        help="Render templates and apply manifests to Kubernetes cluster",
    )
    apply_parser.add_argument(
        "--file",
        required=True,
        help="Path to Python file containing template definitions",
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
