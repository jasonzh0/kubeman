"""
Stock Price Consumer Kubernetes Resource.

This module defines a Kubernetes deployment for a stock price consumer service
that consumes stock prices from Kafka and processes them.
"""

from kubeman import KubernetesResource, TemplateRegistry


@TemplateRegistry.register
class StockPriceConsumer(KubernetesResource):
    """
    Stock Price Consumer service that consumes stock prices from Kafka and processes them.
    """

    def __init__(self):
        super().__init__()
        self.name = "stock-price-consumer"
        self.namespace = "kafka"

        self.add_configmap(
            name="stock-price-consumer-config",
            data={
                "KAFKA_BROKER": "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092",
                "KAFKA_TOPIC": "stock-prices",
                "CONSUMER_GROUP": "stock-price-processors",
            },
            labels={"app": "stock-price-consumer", "component": "consumer"},
        )

        self.add_deployment(
            name="stock-price-consumer",
            containers=[
                {
                    "name": "consumer",
                    "image": "stock-price-consumer:latest",
                    "imagePullPolicy": "Never",
                    "env": [
                        {
                            "name": "KAFKA_BROKER",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "stock-price-consumer-config",
                                    "key": "KAFKA_BROKER",
                                },
                            },
                        },
                        {
                            "name": "KAFKA_TOPIC",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "stock-price-consumer-config",
                                    "key": "KAFKA_TOPIC",
                                },
                            },
                        },
                        {
                            "name": "CONSUMER_GROUP",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "stock-price-consumer-config",
                                    "key": "CONSUMER_GROUP",
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
            labels={"app": "stock-price-consumer", "component": "consumer"},
        )

    def build(self) -> None:
        """Build Docker image for stock price consumer"""
        from kubeman import DockerManager

        context_path = self.resolve_path("..")
        docker = DockerManager()
        docker.build_image(
            component="stock-price-consumer",
            context_path=context_path,
            tag="latest",
            dockerfile="Dockerfile.consumer",
        )
        docker.tag_image(
            source_image=f"{docker.registry}/stock-price-consumer",
            target_image="stock-price-consumer",
            source_tag="latest",
        )

    def load(self) -> None:
        """Load Docker image into kind cluster"""
        from kubeman import DockerManager

        docker = DockerManager()
        docker.kind_load_image("stock-price-consumer", tag="latest")
