"""
Example Kafka deployment using kubeman with Bitnami Kafka Helm chart.

This example demonstrates how to deploy Kafka to Kubernetes using kubeman.
It uses the Bitnami Kafka Helm chart with custom configuration.

Usage:
    kubeman render --file example/kafka/templates.py
    kubeman apply --file example/kafka/templates.py
    # Or from example/kafka directory:
    kubeman render
    kubeman apply
"""

from kubeman import HelmChart, TemplateRegistry


@TemplateRegistry.register
class KafkaChart(HelmChart):
    """
    Kafka deployment using Bitnami Kafka Helm chart.

    This chart deploys a Kafka cluster with Zookeeper for coordination.
    """

    @property
    def name(self) -> str:
        return "kafka"

    @property
    def repository(self) -> dict:
        """Bitnami Helm repository"""
        return {
            "type": "classic",
            "remote": "https://charts.bitnami.com/bitnami",
        }

    @property
    def namespace(self) -> str:
        return "kafka"

    @property
    def version(self) -> str:
        """Kafka chart version"""
        return "32.4.3"

    def generate_values(self) -> dict:
        """Generate Helm values for Kafka deployment"""
        return {
            # Image configuration - override to use Apache Kafka 4.1.0
            "image": {
                "registry": "docker.io",
                "repository": "apache/kafka",
                "tag": "4.1.0",
                "pullPolicy": "IfNotPresent",
            },
            # Kafka configuration
            "kafka": {
                "replicaCount": 3,
                "listeners": {
                    "client": {
                        "protocol": "PLAINTEXT",
                        "servicePort": 9092,
                    },
                    "external": {
                        "protocol": "PLAINTEXT",
                        "type": "LoadBalancer",
                        "servicePort": 9094,
                    },
                },
                "persistence": {
                    "enabled": True,
                    "size": "20Gi",
                    "storageClass": None,  # Use default storage class
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
                "heapOpts": "-Xmx1024m -Xms1024m",
                "logRetentionHours": 168,  # 7 days
                "logSegmentBytes": 1073741824,  # 1GB
                "offsetsTopicReplicationFactor": 3,
                "transactionStateLogReplicationFactor": 3,
                "transactionStateLogMinIsr": 2,
            },
            # Zookeeper configuration (required for Kafka)
            "zookeeper": {
                "enabled": True,
                "replicaCount": 3,
                "persistence": {
                    "enabled": True,
                    "size": "10Gi",
                    "storageClass": None,
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
            # Metrics configuration (optional)
            "metrics": {
                "kafka": {
                    "enabled": True,
                    "serviceMonitor": {
                        "enabled": False,  # Set to True if using Prometheus Operator
                    },
                },
                "zookeeper": {
                    "enabled": True,
                    "serviceMonitor": {
                        "enabled": False,  # Set to True if using Prometheus Operator
                    },
                },
            },
        }

    def enable_argocd(self) -> bool:
        """Enable ArgoCD Application generation (optional)"""
        # Set to True if you want ArgoCD to manage this deployment
        # Make sure ARGOCD_APP_REPO_URL environment variable is set
        return False
