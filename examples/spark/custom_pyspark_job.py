"""
Custom PySpark Job Kubernetes Resource.

This module defines a SparkApplication CRD for running a custom PySpark job.

Note: This assumes the Spark Operator and RBAC resources (ServiceAccount, Role, RoleBinding)
are already deployed. If deploying standalone, you may need to add those resources similar
to how SparkPiApplication does it.
"""

from kubeman import KubernetesResource, TemplateRegistry


@TemplateRegistry.register
class CustomPySparkJob(KubernetesResource):
    """
    Custom PySpark job that processes data using PySpark.

    This demonstrates how to run a custom PySpark application on Kubernetes.

    Prerequisites:
    - Spark Operator must be installed (via SparkOperator Helm chart)
    - ServiceAccount "spark" with appropriate RBAC must exist in the namespace
    - Docker image "custom-pyspark-job:latest" must be built and available
    """

    def __init__(self):
        super().__init__()
        self.name = "custom-pyspark-job"
        self.namespace = "spark"

    def extra_manifests(self) -> list[dict]:
        """
        Return SparkApplication CRD for custom PySpark job.

        This creates a SparkApplication that runs a Python script from the Docker image.
        The image should contain your PySpark script at /app/pyspark_example.py.
        """
        return [
            {
                "apiVersion": "sparkoperator.k8s.io/v1beta2",
                "kind": "SparkApplication",
                "metadata": {
                    "name": "custom-pyspark-job",
                    "namespace": self.namespace,
                },
                "spec": {
                    "type": "Python",
                    "mode": "cluster",
                    "image": "custom-pyspark-job:latest",
                    "imagePullPolicy": "IfNotPresent",
                    "mainApplicationFile": "local:///app/pyspark_example.py",
                    "sparkVersion": "3.5.0",
                    "restartPolicy": {
                        "type": "Never",
                    },
                    "driver": {
                        "cores": 1,
                        "coreLimit": "1200m",
                        "memory": "512m",
                        "labels": {
                            "version": "3.5.0",
                        },
                        "serviceAccount": "spark",
                        "env": [
                            {
                                "name": "PYSPARK_PYTHON",
                                "value": "python3",
                            }
                        ],
                    },
                    "executor": {
                        "cores": 1,
                        "instances": 2,
                        "memory": "512m",
                        "labels": {
                            "version": "3.5.0",
                        },
                        "env": [
                            {
                                "name": "PYSPARK_PYTHON",
                                "value": "python3",
                            }
                        ],
                    },
                },
            },
        ]

    def enable_argocd(self) -> bool:
        """Enable ArgoCD Application generation (optional)"""
        return False
