"""
Kubeman - A Python library for rendering Helm charts and Kubernetes resources with optional ArgoCD Application generation.
"""

from kubeman.template import Template
from kubeman.chart import HelmChart
from kubeman.kubernetes import KubernetesResource
from kubeman.register import TemplateRegistry
from kubeman.git import GitManager
from kubeman.docker import DockerManager
from kubeman.executor import CommandExecutor, get_executor
from kubeman.config import Config, config
from kubeman.argocd import ArgoCDApplicationGenerator
from kubeman.cli import render_templates, apply_manifests

__all__ = [
    "Template",
    "HelmChart",
    "KubernetesResource",
    "TemplateRegistry",
    "GitManager",
    "DockerManager",
    "CommandExecutor",
    "get_executor",
    "Config",
    "config",
    "ArgoCDApplicationGenerator",
    "render_templates",
    "apply_manifests",
]

__version__ = "0.5.1"
