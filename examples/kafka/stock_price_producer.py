"""
Stock Price Producer Kubernetes Resource.

This module defines a Kubernetes deployment for a stock price producer service
that generates mock stock prices and publishes them to Kafka.
"""

from kubeman import KubernetesResource, TemplateRegistry


@TemplateRegistry.register
class StockPriceProducer(KubernetesResource):
    """
    Stock Price Producer service that fetches live stock prices and publishes to Kafka.
    """

    def __init__(self):
        super().__init__()
        self.name = "stock-price-producer"
        self.namespace = "kafka"

        # Add Namespace
        self.add_namespace(
            labels={"app": "kafka", "component": "stock-price-processing"},
        )

        # Add ConfigMap for producer configuration
        self.add_configmap(
            name="stock-price-producer-config",
            data={
                "STOCK_SYMBOLS": "AAPL,GOOGL,MSFT,TSLA",
                "KAFKA_BROKER": "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092",
                "KAFKA_TOPIC": "stock-prices",
                "FETCH_INTERVAL": "5",
            },
            labels={"app": "stock-price-producer", "component": "producer"},
        )

        # Add Deployment
        self.add_deployment(
            name="stock-price-producer",
            containers=[
                {
                    "name": "producer",
                    "image": "stock-price-producer:latest",
                    "imagePullPolicy": "Never",
                    "env": [
                        {
                            "name": "STOCK_SYMBOLS",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "stock-price-producer-config",
                                    "key": "STOCK_SYMBOLS",
                                },
                            },
                        },
                        {
                            "name": "KAFKA_BROKER",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "stock-price-producer-config",
                                    "key": "KAFKA_BROKER",
                                },
                            },
                        },
                        {
                            "name": "KAFKA_TOPIC",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "stock-price-producer-config",
                                    "key": "KAFKA_TOPIC",
                                },
                            },
                        },
                        {
                            "name": "FETCH_INTERVAL",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "stock-price-producer-config",
                                    "key": "FETCH_INTERVAL",
                                },
                            },
                        },
                    ],
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                    },
                }
            ],
            replicas=1,
            labels={"app": "stock-price-producer", "component": "producer"},
        )

    def build(self) -> None:
        """Build Docker image for stock price producer"""
        from pathlib import Path
        from kubeman import DockerManager

        # Get the directory containing this file (examples/kafka)
        kafka_dir = Path(__file__).parent
        docker = DockerManager()
        docker.build_image(
            component="stock-price-producer",
            context_path=str(kafka_dir),
            tag="latest",
            dockerfile="Dockerfile.producer",
        )

    def enable_argocd(self) -> bool:
        """Enable ArgoCD Application generation (optional)"""
        return False
