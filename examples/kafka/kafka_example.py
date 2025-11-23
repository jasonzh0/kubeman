"""
Example Kafka deployment using kubeman with Strimzi Kafka Operator.

This example demonstrates how to deploy Kafka to Kubernetes using kubeman.
It uses the Strimzi Kafka Operator from https://github.com/strimzi/strimzi-kafka-operator.

The deployment consists of:
1. Strimzi Cluster Operator (installed via Helm)
2. Kafka cluster (created via Kafka CRD)

Usage:
    kubeman render --file examples/kafka/templates.py
    kubeman apply --file examples/kafka/templates.py
    # Or from examples/kafka directory:
    kubeman render
    kubeman apply
"""

from kubeman import HelmChart, KubernetesResource, TemplateRegistry


@TemplateRegistry.register
class StrimziOperator(HelmChart):
    """
    Strimzi Kafka Operator installation.

    This installs the Strimzi Cluster Operator which manages Kafka clusters via CRDs.
    """

    @property
    def name(self) -> str:
        return "strimzi-kafka-operator"

    @property
    def repository(self) -> dict:
        """Strimzi Helm repository"""
        return {
            "type": "classic",
            "remote": "https://strimzi.io/charts/",
        }

    @property
    def namespace(self) -> str:
        return "kafka"

    @property
    def version(self) -> str:
        """Strimzi operator chart version"""
        return "0.49.0"

    def generate_values(self) -> dict:
        """Generate Helm values for Strimzi operator"""
        return {
            # Watch all namespaces by default
            "watchAnyNamespace": True,
        }

    def enable_argocd(self) -> bool:
        """Enable ArgoCD Application generation (optional)"""
        return False


@TemplateRegistry.register
class KafkaCluster(KubernetesResource):
    """
    Kafka cluster deployment using Strimzi Kafka CRD.

    This creates a Kafka cluster managed by the Strimzi operator.
    Supports Kafka 4.1.0 and uses KRaft mode (no Zookeeper).
    """

    @property
    def namespace(self) -> str:
        return "kafka"

    def manifests(self) -> list[dict]:
        """Generate Kafka cluster CRD manifest using KRaft mode"""
        return [
            # Kafka cluster (KRaft mode - no Zookeeper)
            {
                "apiVersion": "kafka.strimzi.io/v1beta2",
                "kind": "Kafka",
                "metadata": {
                    "name": "my-cluster",
                    "namespace": self.namespace,
                },
                "spec": {
                    "kafka": {
                        "version": "4.1.0",
                        "listeners": [
                            {
                                "name": "plain",
                                "port": 9092,
                                "type": "internal",
                                "tls": False,
                            },
                        ],
                        "config": {
                            "offsets.topic.replication.factor": 3,
                            "transaction.state.log.replication.factor": 3,
                            "transaction.state.log.min.isr": 2,
                        },
                    },
                    "entityOperator": {
                        "topicOperator": {},
                        "userOperator": {},
                    },
                },
            },
            # KafkaNodePool for brokers
            {
                "apiVersion": "kafka.strimzi.io/v1beta2",
                "kind": "KafkaNodePool",
                "metadata": {
                    "name": "brokers",
                    "namespace": self.namespace,
                    "labels": {
                        "strimzi.io/cluster": "my-cluster",
                    },
                },
                "spec": {
                    "replicas": 3,
                    "roles": ["broker"],
                    "storage": {
                        "type": "persistent-claim",
                        "size": "20Gi",
                        "deleteClaim": False,
                    },
                    "resources": {
                        "requests": {
                            "cpu": "500m",
                            "memory": "1Gi",
                        },
                        "limits": {
                            "cpu": "2000m",
                            "memory": "2Gi",
                        },
                    },
                },
            },
            # KafkaNodePool for controllers
            {
                "apiVersion": "kafka.strimzi.io/v1beta2",
                "kind": "KafkaNodePool",
                "metadata": {
                    "name": "controllers",
                    "namespace": self.namespace,
                    "labels": {
                        "strimzi.io/cluster": "my-cluster",
                    },
                },
                "spec": {
                    "replicas": 3,
                    "roles": ["controller"],
                    "storage": {
                        "type": "persistent-claim",
                        "size": "10Gi",
                        "deleteClaim": False,
                    },
                    "resources": {
                        "requests": {
                            "cpu": "250m",
                            "memory": "512Mi",
                        },
                        "limits": {
                            "cpu": "1000m",
                            "memory": "1Gi",
                        },
                    },
                },
            },
        ]

    def enable_argocd(self) -> bool:
        """Enable ArgoCD Application generation (optional)"""
        return False
