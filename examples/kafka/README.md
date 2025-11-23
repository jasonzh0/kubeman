# Kafka Deployment Example

This example demonstrates how to deploy Apache Kafka to Kubernetes using kubeman with the Bitnami Kafka Helm chart.

## Overview

The example includes:
- **Kafka cluster** with 3 replicas for high availability
- **Zookeeper** cluster with 3 replicas (required for Kafka coordination)
- **Persistent storage** for both Kafka and Zookeeper
- **Resource limits** configured for production-like workloads
- **Metrics** enabled for monitoring (Prometheus-compatible)
- **Stock Price Processing**: Producer and consumer services for processing live stock prices

## Prerequisites

1. **kubectl** configured to access your Kubernetes cluster
2. **Helm** installed (version 3.x)
3. **kubeman** installed (see main README for installation instructions)
4. **Docker** installed (for building stock price producer/consumer images)

## Usage

### 1. Build Docker Images (for Stock Price Processing)

If you want to use the stock price processing features, first build the Docker images:

```bash
cd examples/kafka

# Build producer image
docker build -f Dockerfile.producer -t stock-price-producer:latest .

# Build consumer image
docker build -f Dockerfile.consumer -t stock-price-consumer:latest .
```

**Note**: In a production environment, you would push these images to a container registry and update the image references in the Kubernetes resources.

### 2. Render Manifests

Render the Kubernetes manifests without applying them:

```bash
# From the examples/kafka directory:
cd examples/kafka
kubeman render

# Or with explicit path from project root:
kubeman render --file examples/kafka/templates.py

# Optionally specify custom output directory:
kubeman render --file examples/kafka/templates.py --output-dir ./custom-manifests
```

This will generate manifests in the `manifests/` directory (or the specified output directory).

### 3. Apply to Kubernetes

Render and apply the manifests to your cluster:

```bash
# From the examples/kafka directory:
cd examples/kafka
kubeman apply

# Or with explicit path from project root:
kubeman apply --file examples/kafka/templates.py

# Optionally specify custom output directory:
kubeman apply --file examples/kafka/templates.py --output-dir ./custom-manifests
```

This will:
1. Render the Helm chart templates
2. Apply all manifests to the `kafka` namespace
3. Create the namespace if it doesn't exist

**Note**: The `templates.py` file imports all template modules (`kafka_example.py`, `stock_price_producer.py`, `stock_price_consumer.py`) which automatically register themselves via the `@TemplateRegistry.register` decorator. This allows all templates to be rendered and applied in a single command.

### 4. Verify Deployment

Check the status of the Kafka deployment:

```bash
# Check pods (Kafka, Zookeeper, Producer, Consumer)
kubectl get pods -n kafka

# Check services
kubectl get svc -n kafka

# Check persistent volume claims
kubectl get pvc -n kafka

# Check producer logs
kubectl logs -n kafka -l app=stock-price-producer

# Check consumer logs
kubectl logs -n kafka -l app=stock-price-consumer
```

## Configuration

The example is configured with:

- **Kafka replicas**: 3
- **Zookeeper replicas**: 3
- **Kafka storage**: 20Gi per pod
- **Zookeeper storage**: 10Gi per pod
- **Kafka resources**: 500m-2000m CPU, 1Gi-2Gi memory
- **Zookeeper resources**: 250m-1000m CPU, 512Mi-1Gi memory

### Customizing the Configuration

Edit `kafka_example.py` and modify the `generate_values()` method to customize:

- Replica counts
- Storage sizes
- Resource requests/limits
- Kafka configuration (retention, segment size, etc.)
- Listener configuration (internal/external access)

## Accessing Kafka

### Internal Access (within cluster)

Kafka is accessible at:
- **Service**: `kafka.kafka.svc.cluster.local:9092`
- **Port**: 9092 (client protocol)

### External Access (LoadBalancer)

If your cluster supports LoadBalancer services, Kafka is also exposed externally:
- **Service**: `kafka-external.kafka.svc.cluster.local:9094`
- **Port**: 9094

### Testing Kafka

You can test Kafka using the built-in Kafka tools:

```bash
# Create a topic
kubectl exec -it kafka-0 -n kafka -- kafka-topics.sh \
  --create \
  --bootstrap-server localhost:9092 \
  --replication-factor 3 \
  --partitions 3 \
  --topic test-topic

# List topics
kubectl exec -it kafka-0 -n kafka -- kafka-topics.sh \
  --list \
  --bootstrap-server localhost:9092

# Produce messages
kubectl exec -it kafka-0 -n kafka -- kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic test-topic

# Consume messages (in another terminal)
kubectl exec -it kafka-0 -n kafka -- kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic test-topic \
  --from-beginning
```

## Stock Price Processing

This example includes a complete stock price processing pipeline:

### Stock Price Producer

The producer service (`stock_price_producer.py`) fetches live stock prices from Yahoo Finance and publishes them to Kafka.

**Features:**
- Fetches prices for configurable stock symbols (default: AAPL, GOOGL, MSFT, TSLA)
- Publishes JSON messages to Kafka topic `stock-prices`
- Configurable fetch interval (default: 5 seconds)
- Automatic retry on Kafka connection failures

**Configuration:**
- `STOCK_SYMBOLS`: Comma-separated list of stock symbols
- `KAFKA_BROKER`: Kafka broker address (default: `kafka.kafka.svc.cluster.local:9092`)
- `KAFKA_TOPIC`: Kafka topic name (default: `stock-prices`)
- `FETCH_INTERVAL`: Seconds between price fetches (default: `5`)

**Message Format:**
```json
{
  "symbol": "AAPL",
  "price": 150.25,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Stock Price Consumer

The consumer service (`stock_price_consumer.py`) consumes stock prices from Kafka and processes them.

**Features:**
- Consumes messages from the `stock-prices` topic
- Processes each message (logs by default, can be extended)
- Consumer group coordination for scaling
- Automatic offset management

**Configuration:**
- `KAFKA_BROKER`: Kafka broker address
- `KAFKA_TOPIC`: Kafka topic name (default: `stock-prices`)
- `CONSUMER_GROUP`: Consumer group ID (default: `stock-price-processors`)

**Extending the Consumer:**

The consumer can be extended to:
- Store prices to a database
- Calculate moving averages or other metrics
- Trigger alerts for price changes
- Aggregate statistics
- Integrate with other systems

### Creating the Kafka Topic

Before the producer can publish messages, you may need to create the topic:

```bash
# Create the stock-prices topic
kubectl exec -it kafka-0 -n kafka -- kafka-topics.sh \
  --create \
  --bootstrap-server localhost:9092 \
  --replication-factor 3 \
  --partitions 3 \
  --topic stock-prices

# Verify topic was created
kubectl exec -it kafka-0 -n kafka -- kafka-topics.sh \
  --list \
  --bootstrap-server localhost:9092
```

### Monitoring Stock Price Processing

```bash
# Watch producer logs
kubectl logs -n kafka -f -l app=stock-price-producer

# Watch consumer logs
kubectl logs -n kafka -f -l app=stock-price-consumer

# Check message count in topic
kubectl exec -it kafka-0 -n kafka -- kafka-run-class.sh \
  kafka.tools.GetOffsetShell \
  --bootstrap-server localhost:9092 \
  --topic stock-prices
```

### Customizing Stock Symbols

Edit the ConfigMap to change which stocks are tracked:

```bash
kubectl edit configmap stock-price-producer-config -n kafka
```

Or modify `stock_price_producer.py` and update the `STOCK_SYMBOLS` value in the ConfigMap.

## ArgoCD Integration (Optional)

To enable ArgoCD Application generation:

1. Set the `ARGOCD_APP_REPO_URL` environment variable:
   ```bash
   export ARGOCD_APP_REPO_URL="https://github.com/your-org/manifests-repo"
   ```

2. Modify `kafka_example.py` and set `enable_argocd()` to return `True`:
   ```python
   def enable_argocd(self) -> bool:
       return True
   ```

3. Render the manifests using `kubeman render` - an ArgoCD Application will be generated in `manifests/apps/kafka-application.yaml`

## Troubleshooting

### Pods not starting

Check pod logs:
```bash
kubectl logs -n kafka kafka-0
kubectl logs -n kafka zookeeper-0
kubectl logs -n kafka -l app=stock-price-producer
kubectl logs -n kafka -l app=stock-price-consumer
```

### Producer not connecting to Kafka

Ensure Kafka is running and the broker address is correct:
```bash
# Check if Kafka pods are ready
kubectl get pods -n kafka

# Verify Kafka service
kubectl get svc -n kafka kafka

# Test connectivity from producer pod
kubectl exec -it -n kafka -l app=stock-price-producer -- \
  python -c "from kafka import KafkaProducer; p = KafkaProducer(bootstrap_servers=['kafka.kafka.svc.cluster.local:9092']); print('Connected!')"
```

### Consumer not receiving messages

Check if messages are being produced:
```bash
# Check producer logs for published messages
kubectl logs -n kafka -l app=stock-price-producer | grep Published

# Verify topic exists and has messages
kubectl exec -it kafka-0 -n kafka -- kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic stock-prices \
  --from-beginning \
  --max-messages 10
```

### Storage issues

Verify persistent volume claims:
```bash
kubectl describe pvc -n kafka
```

### Network issues

Check services and endpoints:
```bash
kubectl get svc -n kafka
kubectl get endpoints -n kafka
```

## Further Reading

- [Bitnami Kafka Chart Documentation](https://github.com/bitnami/charts/tree/main/bitnami/kafka)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [kubeman Documentation](../README.md)
