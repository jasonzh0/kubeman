"""
Spark Application Kubernetes Resource.

This module defines a SparkApplication CRD for running Spark jobs on Kubernetes.
"""

from kubeman import KubernetesResource, TemplateRegistry


@TemplateRegistry.register
class SparkPiApplication(KubernetesResource):
    """
    SparkPi example application that calculates π using Monte Carlo method.

    This demonstrates how to run a Spark job using the Spark Operator.
    """

    def __init__(self):
        super().__init__()
        self.name = "spark-pi"
        self.namespace = "spark"

        self.add_namespace(
            labels={"app": "spark", "component": "spark-operator"},
        )

        self.add_service_account(
            name="spark",
            labels={"app": "spark", "component": "service-account"},
        )

        self.add_role(
            name="spark-role",
            rules=[
                {
                    "apiGroups": [""],
                    "resources": ["pods"],
                    "verbs": ["get", "list", "watch", "create", "delete", "deletecollection"],
                },
                {
                    "apiGroups": [""],
                    "resources": ["configmaps"],
                    "verbs": ["get", "list", "watch", "create", "delete", "deletecollection"],
                },
                {
                    "apiGroups": [""],
                    "resources": ["services"],
                    "verbs": ["get", "list", "watch", "create", "delete", "deletecollection"],
                },
                {
                    "apiGroups": [""],
                    "resources": ["persistentvolumeclaims"],
                    "verbs": ["get", "list", "watch", "create", "delete", "deletecollection"],
                },
            ],
            labels={"app": "spark", "component": "role"},
        )

        self.add_role_binding(
            name="spark-role-binding",
            role_name="spark-role",
            subjects=[
                {
                    "kind": "ServiceAccount",
                    "name": "spark",
                    "namespace": "spark",
                }
            ],
            labels={"app": "spark", "component": "role-binding"},
        )

    def extra_manifests(self) -> list[dict]:
        """Return SparkApplication CRD as an extra manifest"""
        return [
            {
                "apiVersion": "sparkoperator.k8s.io/v1beta2",
                "kind": "SparkApplication",
                "metadata": {
                    "name": "spark-pi",
                    "namespace": self.namespace,
                },
                "spec": {
                    "type": "Scala",
                    "mode": "cluster",
                    "image": "apache/spark:3.5.0",
                    "imagePullPolicy": "IfNotPresent",
                    "mainClass": "org.apache.spark.examples.SparkPi",
                    "mainApplicationFile": "local:///opt/spark/examples/jars/spark-examples_2.12-3.5.0.jar",
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
