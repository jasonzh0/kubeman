"""
Utility functions and constants for Kubernetes resource classification.
"""

import re
from pathlib import Path

# Characters allowed in a name that is used to build a file path. Deliberately
# excludes path separators so a crafted metadata.name cannot escape the output
# directory (e.g. "../../etc/cron.d/evil").
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

# Workload kinds that own a Pod template (and so can be targeted by a Service
# selector, reference ConfigMaps, etc.).
WORKLOAD_KINDS = [
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "Job",
]

# Cluster-scoped resource kinds that don't belong to a namespace
CLUSTER_SCOPED_KINDS = [
    "CustomResourceDefinition",
    "ClusterRole",
    "ClusterRoleBinding",
    "Namespace",
    "PersistentVolume",
    "StorageClass",
]


def is_cluster_scoped(kind: str) -> bool:
    """
    Check if a Kubernetes resource kind is cluster-scoped.

    Args:
        kind: The Kubernetes resource kind (e.g., "Deployment", "Namespace")

    Returns:
        True if the resource is cluster-scoped, False otherwise
    """
    return kind in CLUSTER_SCOPED_KINDS


def validate_path_component(value: str, field: str = "name") -> str:
    """
    Validate a value that will be used as part of an on-disk file path.

    Rejects empty values, ``.``/``..`` and anything containing path separators
    so that an attacker-influenced ``metadata.name`` cannot cause manifests to
    be written outside the intended directory.

    Args:
        value: The value to validate (e.g. a resource name or kind)
        field: Human-readable field name used in the error message

    Returns:
        The validated value unchanged

    Raises:
        ValueError: If the value is unsafe for use in a path
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"Invalid {field}: {value!r} (must be a non-empty string)")
    if value in (".", "..") or len(value) > 253 or not _SAFE_NAME.match(value):
        raise ValueError(
            f"Invalid {field} {value!r}: only letters, digits, '.', '-' and '_' "
            "are allowed (no path separators), max 253 characters."
        )
    return value


def ensure_within(base: Path, target: Path) -> Path:
    """
    Ensure ``target`` resolves to a location inside ``base``.

    Belt-and-suspenders guard against path traversal that complements
    :func:`validate_path_component`.

    Args:
        base: The directory the target must stay within
        target: The candidate path

    Returns:
        The resolved target path

    Raises:
        ValueError: If the resolved target escapes ``base``
    """
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    if base_resolved != target_resolved and base_resolved not in target_resolved.parents:
        raise ValueError(f"Refusing to write outside {base_resolved}: {target_resolved}")
    return target_resolved


def safe_manifest_path(output_dir: Path, name: str, kind: str) -> Path:
    """
    Build the output path for a manifest file, validating the name and kind and
    ensuring the result stays inside ``output_dir``.

    Args:
        output_dir: Directory the manifest will be written to
        name: The manifest's ``metadata.name``
        kind: The (already lowercased) manifest kind

    Returns:
        A validated, resolved path of the form ``output_dir/<name>-<kind>.yaml``
    """
    validate_path_component(name, field="metadata.name")
    validate_path_component(kind, field="kind")
    return ensure_within(output_dir, output_dir / f"{name}-{kind}.yaml")
