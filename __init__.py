"""
Kubeman - A Python library for rendering Helm charts and ArgoCD applications.
"""

from kubeman.template import Template
from kubeman.chart import HelmChart
from kubeman.kubernetes import KubernetesResource
from kubeman.register import TemplateRegistry
from kubeman.git import GitManager
from kubeman.docker import DockerManager

__all__ = [
    "Template",
    "HelmChart",
    "KubernetesResource",
    "TemplateRegistry",
    "GitManager",
    "DockerManager",
]

__version__ = "0.1.0"
