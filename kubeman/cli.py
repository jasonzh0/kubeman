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
from kubeman.visualize import generate_visualization
from kubeman.output import OutputManager, Verbosity, get_output, set_output


def load_templates_file(file_path: str) -> None:
    """
    Dynamically import a kubeman.py file to trigger template registration.

    Args:
        file_path: Path to the kubeman.py file

    Raises:
        FileNotFoundError: If the file doesn't exist
        ImportError: If the file cannot be imported
    """
    file_path_obj = Path(file_path)

    # If path is absolute, use it directly
    if file_path_obj.is_absolute():
        file_path_obj = file_path_obj.resolve()
    else:
        # Try resolving relative to current directory first
        resolved = file_path_obj.resolve()
        if resolved.exists():
            file_path_obj = resolved
        else:
            # If not found, try to find project root and resolve relative to that
            # Look for common project root indicators
            current = Path.cwd()
            project_root = None

            # Walk up the directory tree looking for project root indicators
            for parent in [current] + list(current.parents):
                if (
                    (parent / "pyproject.toml").exists()
                    or (parent / "setup.py").exists()
                    or (parent / ".git").exists()
                    or (parent / "kubeman").is_dir()
                ):
                    project_root = parent
                    break

            if project_root:
                candidate = (project_root / file_path).resolve()
                if candidate.exists():
                    file_path_obj = candidate
                else:
                    # Last attempt: try resolving from current directory as-is
                    file_path_obj = resolved
            else:
                # No project root found, use resolved path
                file_path_obj = resolved

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
    output = get_output()
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

        output.info(f"Found {len(templates)} registered template(s)")

        with output.progress("Rendering templates", total=len(templates)) as progress:
            for idx, template_class in enumerate(templates):
                try:
                    output.print(f"Rendering template: {template_class.__name__}")
                    template = template_class()
                    template.render()
                    rendered_template_names.append(template.name)
                    output.success(f"Successfully rendered {template_class.__name__}")
                    if progress:
                        progress.update(progress.tasks[0].id, advance=1)
                except Exception as e:
                    output.error(
                        f"Failed to render template {template_class.__name__}",
                        suggestion="Check template definition and dependencies",
                    )
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

        output = get_output()
        if template_names is not None:
            yaml_files = _filter_manifests_by_template_names(
                yaml_files, template_names, manifests_dir_path
            )
            if not yaml_files:
                output.warning(
                    f"No manifests found for registered templates: {', '.join(template_names)}"
                )
                return

        crd_only_files, namespace_files, other_files = _categorize_yaml_files(yaml_files)

        crd_extracted_files = []
        files_to_remove = []
        for yaml_file in other_files:
            if _contains_crd(yaml_file):
                crd_file = _extract_crds_from_yaml(yaml_file)
                if crd_file:
                    crd_extracted_files.append(crd_file)

        output.section("Applying Manifests")
        output.info(f"Applying manifests from {manifests_dir_path}")
        output.info(f"Found {len(yaml_files)} manifest file(s)")
        total_crds = len(crd_only_files) + len(crd_extracted_files)
        if total_crds > 0:
            output.print(f"  - {total_crds} CRD file(s) will be applied first")
        if namespace_files:
            output.print(f"  - {len(namespace_files)} Namespace file(s) will be applied next")
        if other_files:
            output.print(f"  - {len(other_files)} other resource file(s)")

        applied_count = 0
        all_files = crd_only_files + crd_extracted_files + namespace_files + other_files
        total_files = len(all_files)

        with output.progress("Applying manifests", total=total_files) as progress:
            for yaml_file in crd_only_files + crd_extracted_files:
                cmd = ["kubectl", "apply", "-f", str(yaml_file)]
                try:
                    output.verbose(f"Applying {yaml_file.name}")
                    executor.run(cmd, check=True, text=True, capture_output=True)
                    applied_count += 1
                    if progress:
                        progress.update(progress.tasks[0].id, advance=1)
                except Exception as e:
                    error_msg = str(e)
                    output.error(
                        f"Failed to apply {yaml_file}",
                        suggestion="Check kubectl configuration and cluster connectivity",
                    )
                    raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

            for yaml_file in namespace_files:
                cmd = ["kubectl", "apply", "-f", str(yaml_file)]
                try:
                    output.verbose(f"Applying {yaml_file.name}")
                    executor.run(cmd, check=True, text=True, capture_output=True)
                    applied_count += 1
                    if progress:
                        progress.update(progress.tasks[0].id, advance=1)
                except Exception as e:
                    error_msg = str(e)
                    output.error(
                        f"Failed to apply {yaml_file}",
                        suggestion="Check kubectl configuration and cluster connectivity",
                    )
                    raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

            for yaml_file in other_files:
                cmd = ["kubectl", "apply", "-f", str(yaml_file)]

                try:
                    output.verbose(f"Applying {yaml_file.name}")
                    executor.run(cmd, check=True, text=True, capture_output=True)
                    applied_count += 1
                    if progress:
                        progress.update(progress.tasks[0].id, advance=1)
                except Exception as e:
                    error_msg = str(e)
                    output.error(
                        f"Failed to apply {yaml_file}",
                        suggestion="Check kubectl configuration and cluster connectivity",
                    )
                    raise RuntimeError(f"kubectl apply failed for {yaml_file}: {error_msg}") from e

        output.success(f"Successfully applied {applied_count} manifest file(s)")
    finally:
        if manifests_dir is not None:
            Template.set_manifests_dir(original_dir)


def cmd_render(args: argparse.Namespace) -> None:
    """Handle the render subcommand."""
    output = get_output()
    try:
        TemplateRegistry.clear()

        # Render command skips builds/loads by default (only render manifests)
        # Use --skip-build flag is ignored for render (builds are always skipped)
        TemplateRegistry.set_skip_builds(True)
        TemplateRegistry.set_skip_loads(True)

        # Load templates file (imports trigger registration)
        templates_file = args.file or "./kubeman.py"
        output.verbose(f"Loading templates from {templates_file}")
        load_templates_file(templates_file)

        # Get optional output directory
        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
                output.verbose(f"Using output directory: {output_dir}")
            except (TypeError, AttributeError):
                output_dir = None

        render_templates(manifests_dir=output_dir)
        output.newline()
        output.success("All templates rendered successfully")
    except FileNotFoundError as e:
        output.error(f"Error: {e}")
        sys.exit(1)
    except ImportError as e:
        output.error(f"Error: {e}")
        sys.exit(1)
    except (ValueError, RuntimeError) as e:
        output.error(f"Error: {e}")
        sys.exit(1)


def cmd_apply(args: argparse.Namespace) -> None:
    """Handle the apply subcommand."""
    output = get_output()
    try:
        TemplateRegistry.clear()

        # Apply command runs builds/loads by default unless --skip-build is specified
        skip_builds = getattr(args, "skip_build", False)
        TemplateRegistry.set_skip_builds(skip_builds)
        # Loads are skipped if builds are skipped
        TemplateRegistry.set_skip_loads(skip_builds)

        templates_file = args.file or "./kubeman.py"
        output.verbose(f"Loading templates from {templates_file}")
        load_templates_file(templates_file)

        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
                output.verbose(f"Using output directory: {output_dir}")
            except (TypeError, AttributeError):
                output_dir = None

        template_names = render_templates(manifests_dir=output_dir)
        output.newline()
        output.success("Templates rendered successfully")

        apply_manifests(manifests_dir=output_dir, template_names=template_names)
    except FileNotFoundError as e:
        output.error(f"Error: {e}")
        sys.exit(1)
    except ImportError as e:
        output.error(f"Error: {e}")
        sys.exit(1)
    except (ValueError, RuntimeError) as e:
        output.error(f"Error: {e}")
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
    output = get_output()
    output.rule("PLAN: What would be built, applied, and loaded")

    # Build operations
    build_count = len(plan["templates_with_build"])
    if build_count > 0:
        rows = (
            [[name] for name in plan["templates_with_build"]]
            if verbose
            else [[", ".join(plan["templates_with_build"])]]
        )
        output.table(
            title="📦 Build Operations",
            columns=["Template"],
            rows=rows,
        )
    else:
        output.info("📦 Build Operations: No build operations would be executed")

    # Load operations
    load_count = len(plan["templates_with_load"])
    if load_count > 0:
        rows = (
            [[name] for name in plan["templates_with_load"]]
            if verbose
            else [[", ".join(plan["templates_with_load"])]]
        )
        output.table(
            title="🚚 Load Operations",
            columns=["Template"],
            rows=rows,
        )
    else:
        output.info("🚚 Load Operations: No load operations would be executed")

    # Render operations
    render_count = len(plan["template_names"])
    if render_count > 0:
        rows = (
            [[name] for name in plan["template_names"]]
            if verbose
            else [[", ".join(plan["template_names"])]]
        )
        output.table(
            title="📝 Render Operations",
            columns=["Template"],
            rows=rows,
        )
    else:
        output.info("📝 Render Operations: No templates would be rendered")

    # Apply operations
    manifest_files = plan["manifest_files"]
    crd_count = len(manifest_files["crd_files"])
    namespace_count = len(manifest_files["namespace_files"])
    other_count = len(manifest_files["other_files"])
    total_manifests = plan["total_manifests"]

    if total_manifests > 0:
        rows = []
        if crd_count > 0:
            if verbose:
                for file_path in manifest_files["crd_files"]:
                    rows.append([f"CRD ({crd_count} total)", file_path])
            else:
                rows.append([f"CRD ({crd_count} total)", f"{crd_count} file(s) - applied first"])
        if namespace_count > 0:
            if verbose:
                for file_path in manifest_files["namespace_files"]:
                    rows.append([f"Namespace ({namespace_count} total)", file_path])
            else:
                rows.append(
                    [
                        f"Namespace ({namespace_count} total)",
                        f"{namespace_count} file(s) - applied next",
                    ]
                )
        if other_count > 0:
            if verbose:
                for file_path in manifest_files["other_files"]:
                    rows.append([f"Other ({other_count} total)", file_path])
            else:
                rows.append([f"Other ({other_count} total)", f"{other_count} file(s)"])

        output.table(
            title=f"⚙️  Apply Operations ({total_manifests} total manifest file(s))",
            columns=["Type", "Details"],
            rows=rows,
        )
    else:
        output.info("⚙️  Apply Operations: No manifests would be applied")

    output.rule()


def cmd_plan(args: argparse.Namespace) -> None:
    """Handle the plan subcommand."""
    output = get_output()
    try:
        TemplateRegistry.clear()

        # Always skip builds and loads for plan command
        TemplateRegistry.set_skip_builds(True)
        TemplateRegistry.set_skip_loads(True)

        # Load templates file (imports trigger registration)
        templates_file = args.file or "./kubeman.py"
        output.verbose(f"Loading templates from {templates_file}")
        load_templates_file(templates_file)

        # Get optional output directory
        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
                output.verbose(f"Using output directory: {output_dir}")
            except (TypeError, AttributeError):
                output_dir = None

        # Generate plan
        with output.spinner("Analyzing templates and generating plan"):
            plan = generate_plan(manifests_dir=output_dir)

        # Display plan
        verbose = getattr(args, "verbose", False) or output.verbosity >= Verbosity.VERBOSE
        display_plan(plan, verbose=verbose)

    except FileNotFoundError as e:
        output.error(f"Error: {e}")
        sys.exit(1)
    except ImportError as e:
        output.error(f"Error: {e}")
        sys.exit(1)
    except (ValueError, RuntimeError) as e:
        output.error(f"Error: {e}")
        sys.exit(1)


def cmd_visualize(args: argparse.Namespace) -> None:
    """Handle the visualize subcommand."""
    output = get_output()
    try:
        TemplateRegistry.clear()

        # Always skip builds and loads for visualize command
        TemplateRegistry.set_skip_builds(True)
        TemplateRegistry.set_skip_loads(True)

        # Load templates file (imports trigger registration)
        templates_file = args.file or "./kubeman.py"
        output.verbose(f"Loading templates from {templates_file}")
        load_templates_file(templates_file)

        # Get optional output directory
        output_dir = None
        if hasattr(args, "output_dir") and args.output_dir is not None:
            try:
                output_dir = Path(args.output_dir).resolve()
                output.verbose(f"Using output directory: {output_dir}")
            except (TypeError, AttributeError):
                output_dir = None

        # Render templates to generate manifests
        template_names = render_templates(manifests_dir=output_dir)
        output.newline()
        output.success("Templates rendered successfully")

        # Get manifests directory
        manifests_dir_path = Template.manifests_dir()
        if isinstance(manifests_dir_path, str):
            manifests_dir_path = Path(manifests_dir_path)

        if not manifests_dir_path.exists():
            raise RuntimeError(
                f"Manifests directory not found: {manifests_dir_path}. "
                "Templates must be rendered before visualization."
            )

        # Generate visualization (only for templates from this kubeman.py file)
        show_crds = getattr(args, "show_crds", False)
        output.section("Generating Visualization")
        output.info(f"Generating visualization from {manifests_dir_path}")
        output.verbose(f"Filtering to templates: {', '.join(template_names)}")
        if show_crds:
            output.info("Including CustomResourceDefinitions in visualization")

        with output.spinner("Analyzing manifests and generating DOT diagram"):
            dot_content = generate_visualization(
                manifests_dir_path, template_names=template_names, show_crds=show_crds
            )

        # Write output
        output_file = getattr(args, "output", None)
        if output_file:
            output_path = Path(output_file).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(dot_content)
            output.success(f"Visualization written to {output_path}")
            output.newline()
            output.info("To render the diagram, run:")
            output.print(f"  dot -Tpng {output_path} -o {output_path.stem}.png")
            output.print(f"  dot -Tsvg {output_path} -o {output_path.stem}.svg")
        else:
            # Write to stdout
            output.print("=" * 60)
            output.print(dot_content)
            output.print("=" * 60)

    except FileNotFoundError as e:
        output.error(f"Error: {e}")
        sys.exit(1)
    except ImportError as e:
        output.error(f"Error: {e}")
        sys.exit(1)
    except (ValueError, RuntimeError) as e:
        output.error(f"Error: {e}")
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
  kubeman visualize --file examples/kafka/kubeman.py --output diagram.dot
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
        help="Skip Docker image build steps during template registration (ignored for render, always skipped)",
    )
    render_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors and final results",
    )
    render_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output including file paths and command execution",
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
    apply_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors and final results",
    )
    apply_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output including file paths and command execution",
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
        "--quiet",
        action="store_true",
        help="Only show errors and final results",
    )
    plan_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output including file paths and template names",
    )
    plan_parser.set_defaults(func=cmd_plan)

    # Visualize subcommand
    visualize_parser = subparsers.add_parser(
        "visualize",
        help="Generate Graphviz DOT diagram showing resource hierarchy and relationships",
    )
    visualize_parser.add_argument(
        "--file",
        help="Path to kubeman.py file (defaults to ./kubeman.py)",
    )
    visualize_parser.add_argument(
        "--output-dir",
        help="Output directory for manifests (defaults to ./manifests or MANIFESTS_DIR env var)",
    )
    visualize_parser.add_argument(
        "--output",
        help="Output file for DOT diagram (defaults to stdout)",
    )
    visualize_parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip Docker image build steps during template registration (ignored for visualize, always skipped)",
    )
    visualize_parser.add_argument(
        "--show-crds",
        action="store_true",
        help="Include CustomResourceDefinitions in the visualization (hidden by default)",
    )
    visualize_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors and final results",
    )
    visualize_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output including file paths and command execution",
    )
    visualize_parser.set_defaults(func=cmd_visualize)

    args = parser.parse_args()

    # Set up verbosity
    if getattr(args, "quiet", False):
        verbosity = Verbosity.QUIET
    elif getattr(args, "verbose", False):
        verbosity = Verbosity.VERBOSE
    else:
        verbosity = Verbosity.NORMAL

    output_manager = OutputManager(verbosity=verbosity)
    set_output(output_manager)

    # Call the appropriate command handler
    args.func(args)


if __name__ == "__main__":
    main()
