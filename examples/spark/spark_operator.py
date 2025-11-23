"""
Example Spark Operator deployment using kubeman with Kubeflow Spark Operator.

This example demonstrates how to deploy the Spark Operator to Kubernetes using kubeman.
It uses the Kubeflow Spark Operator from https://github.com/kubeflow/spark-operator.

The deployment consists of:
1. Spark Operator (installed via Helm)
2. Service account and RBAC for Spark applications

Usage:
    kubeman render --file examples/spark/templates.py
    kubeman apply --file examples/spark/templates.py
    kubeman render
    kubeman apply
"""

from kubeman import HelmChart, TemplateRegistry


@TemplateRegistry.register
class SparkOperator(HelmChart):
    """
    Spark Operator installation.

    This installs the Spark Operator which manages Spark applications via CRDs.
    """

    @property
    def name(self) -> str:
        return "spark-operator"

    @property
    def repository(self) -> dict:
        """Kubeflow Spark Operator Helm repository"""
        return {
            "type": "classic",
            "remote": "https://kubeflow.github.io/spark-operator",
        }

    @property
    def namespace(self) -> str:
        return "spark"

    @property
    def version(self) -> str:
        """Spark operator chart version"""
        return "1.1.27"

    def generate_values(self) -> dict:
        """Generate Helm values for Spark operator"""
        return {
            "namespace": self.namespace,
            "webhook": {
                "enable": False,
            },
            "sparkServiceAccount": "spark",
            "resources": {
                "limits": {
                    "cpu": "500m",
                    "memory": "1Gi",
                },
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                },
            },
        }
