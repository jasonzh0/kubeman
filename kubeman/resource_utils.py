"""
Utility functions and constants for Kubernetes resource classification.
"""

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
