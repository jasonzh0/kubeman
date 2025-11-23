# Spark Deployment Example

This example demonstrates how to deploy Apache Spark to Kubernetes using kubeman with the Kubeflow Spark Operator.

## Overview

The example includes:
- **Spark Operator** for managing Spark applications on Kubernetes
- **Service Account and RBAC** configured for Spark applications
- **Sample Spark Application** (SparkPi) that calculates π using Monte Carlo method
- **Resource limits** configured for production-like workloads

## Prerequisites

1. **kubectl** configured to access your Kubernetes cluster
2. **Helm** installed (version 3.x)
3. **kubeman** installed (see main README for installation instructions)
4. **Kubernetes cluster** (version 1.16 or higher)

## Usage

### 1. Render Manifests

Render the Kubernetes manifests without applying them:

```bash
# From the examples/spark directory:
cd examples/spark
kubeman render

# Or with explicit path from project root:
kubeman render --file examples/spark/templates.py

# Optionally specify custom output directory:
kubeman render --file examples/spark/templates.py --output-dir ./custom-manifests
```

This will generate manifests in the `manifests/` directory (or the specified output directory).

### 2. Apply to Kubernetes

Render and apply the manifests to your cluster:

```bash
# From the examples/spark directory:
cd examples/spark
kubeman apply

# Or with explicit path from project root:
kubeman apply --file examples/spark/templates.py

# Optionally specify custom output directory:
kubeman apply --file examples/spark/templates.py --output-dir ./custom-manifests
```

This will:
1. Render the Helm chart templates for the Spark Operator
2. Apply all manifests to the `spark` namespace
3. Create the namespace if it doesn't exist
4. Install the Spark Operator
5. Create the SparkPi application

**Note**: The `templates.py` file imports all template modules (`spark_operator.py`, `spark_application.py`) which automatically register themselves via the `@TemplateRegistry.register` decorator. This allows all templates to be rendered and applied in a single command.

### 3. Verify Deployment

Check the status of the Spark deployment:

```bash
# Check pods (Spark Operator, SparkPi driver and executors)
kubectl get pods -n spark

# Check services
kubectl get svc -n spark

# Check SparkApplication status
kubectl get sparkapplication -n spark

# Check SparkApplication details
kubectl describe sparkapplication spark-pi -n spark

# Check Spark Operator logs
kubectl logs -n spark -l app.kubernetes.io/name=spark-operator

# Check SparkPi driver logs
kubectl logs -n spark spark-pi-driver
```

## Configuration

The example is configured with:

- **Spark Operator version**: 1.1.27
- **Spark version**: 3.5.0
- **Driver resources**: 1 core, 512m memory
- **Executor resources**: 1 core per executor, 512m memory, 2 instances
- **Namespace**: spark

### Customizing the Configuration

Edit `spark_operator.py` and modify the `generate_values()` method to customize:

- Operator resource limits
- Webhook configuration
- Service account settings

Edit `spark_application.py` and modify the `manifests()` method to customize:

- Spark version
- Driver/executor resources
- Number of executor instances
- Spark application image
- Main class and application file

## Running Spark Applications

### SparkPi Example

The example includes a SparkPi application that calculates π using Monte Carlo method. Once deployed, it will automatically start running.

### Custom PySpark Jobs

To run a custom PySpark job, follow these steps:

#### 1. Create Your PySpark Script

Create a Python file with your PySpark code (e.g., `pyspark_example.py`):

```python
from pyspark.sql import SparkSession

def main():
    spark = SparkSession.builder \
        .appName("MyCustomJob") \
        .getOrCreate()

    # Your PySpark code here
    # ...

    spark.stop()

if __name__ == "__main__":
    main()
```

#### 2. Build a Docker Image

Create a `Dockerfile` for your PySpark application:

```dockerfile
FROM apache/spark:3.5.0
WORKDIR /app
COPY pyspark_example.py /app/pyspark_example.py
ENV PYTHONPATH=/app:$PYTHONPATH
```

Build the image:

```bash
docker build -f Dockerfile.pyspark -t custom-pyspark-job:latest .
```

**Note**: In production, push the image to a container registry and update the image reference in the SparkApplication.

#### 3. Create a SparkApplication Template

Create a new file (e.g., `custom_pyspark_job.py`) following the pattern in `spark_application.py`:

```python
from kubeman import KubernetesResource, TemplateRegistry

@TemplateRegistry.register
class CustomPySparkJob(KubernetesResource):
    def __init__(self):
        super().__init__()
        self.name = "custom-pyspark-job"
        self.namespace = "spark"

    def extra_manifests(self) -> list[dict]:
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
                    "restartPolicy": {"type": "Never"},
                    "driver": {
                        "cores": 1,
                        "memory": "512m",
                        "serviceAccount": "spark",
                    },
                    "executor": {
                        "cores": 1,
                        "instances": 2,
                        "memory": "512m",
                    },
                },
            },
        ]
```

#### 4. Register the Template

Add the import to `templates.py`:

```python
import custom_pyspark_job  # noqa: F401
```

#### 5. Deploy Using Kubeman

```bash
kubeman apply --file examples/spark/templates.py --namespace spark
```

#### 6. View Results

Check the job status and logs:

```bash
# Check SparkApplication status
kubectl get sparkapplication custom-pyspark-job -n spark

# View driver logs
kubectl logs -n spark -l spark-role=driver,sparkoperator.k8s.io/app-name=custom-pyspark-job
```

#### Example Files

The example includes:
- `pyspark_example.py` - Sample PySpark script
- `Dockerfile.pyspark` - Dockerfile for building the image
- `custom_pyspark_job.py` - SparkApplication template

You can use these as a starting point for your own PySpark jobs.

**Monitor the application:**

```bash
# Watch SparkApplication status
kubectl get sparkapplication spark-pi -n spark -w

# Check driver pod logs
kubectl logs -n spark spark-pi-driver -f

# Check executor pod logs
kubectl logs -n spark -l spark-role=executor -f
```

**View results:**

The SparkPi application outputs the calculated value of π. You can view it in the driver logs:

```bash
kubectl logs -n spark spark-pi-driver | grep -i "pi"
```

### Creating Custom Spark Applications

To create your own Spark application, you can:

1. **Modify the existing SparkApplication** in `spark_application.py`:
   - Change the `mainClass` to your application's main class
   - Update `mainApplicationFile` to point to your JAR file
   - Adjust resources as needed

2. **Create a new SparkApplication class** following the same pattern:

```python
@TemplateRegistry.register
class MySparkApp(KubernetesResource):
    def __init__(self):
        super().__init__()
        self.name = "my-spark-app"
        self.namespace = "spark"

    def manifests(self) -> list[dict]:
        return [
            {
                "apiVersion": "sparkoperator.k8s.io/v1beta2",
                "kind": "SparkApplication",
                "metadata": {
                    "name": "my-spark-app",
                    "namespace": self.namespace,
                },
                "spec": {
                    # Your Spark application configuration
                },
            },
        ]
```

3. **Import and register** the new class in `templates.py`

### Spark Application Modes

The example uses `cluster` mode, which runs both driver and executors in the cluster. You can also use:

- **client mode**: Driver runs locally, executors in cluster
- **cluster mode**: Both driver and executors run in cluster (default in this example)

## Accessing Spark UI

The Spark UI is available through port-forwarding to the driver pod:

```bash
# Get the driver pod name
DRIVER_POD=$(kubectl get pods -n spark -l spark-role=driver -o jsonpath='{.items[0].metadata.name}')

# Port forward to Spark UI (default port 4040)
kubectl port-forward -n spark $DRIVER_POD 4040:4040
```

Then access the Spark UI at `http://localhost:4040`

## ArgoCD Integration (Optional)

To enable ArgoCD Application generation:

1. Set the `ARGOCD_APP_REPO_URL` environment variable:
   ```bash
   export ARGOCD_APP_REPO_URL="https://github.com/your-org/manifests-repo"
   ```

2. Modify `spark_operator.py` or `spark_application.py` and set `enable_argocd()` to return `True`:
   ```python
   def enable_argocd(self) -> bool:
       return True
   ```

3. Render the manifests using `kubeman render` - ArgoCD Applications will be generated in `manifests/apps/`

## Troubleshooting

### Spark Operator not starting

Check operator logs:
```bash
kubectl logs -n spark -l app.kubernetes.io/name=spark-operator
```

Verify the operator pod is running:
```bash
kubectl get pods -n spark -l app.kubernetes.io/name=spark-operator
```

### SparkApplication not creating pods

Check SparkApplication status:
```bash
kubectl describe sparkapplication spark-pi -n spark
```

Verify service account and RBAC:
```bash
kubectl get serviceaccount spark -n spark
kubectl get role spark-role -n spark
kubectl get rolebinding spark-role-binding -n spark
```

### Driver pod failing

Check driver pod logs:
```bash
kubectl logs -n spark spark-pi-driver
kubectl describe pod spark-pi-driver -n spark
```

Common issues:
- Image pull errors: Verify the Spark image is accessible
- Resource constraints: Check if cluster has enough resources
- Service account permissions: Verify RBAC is correctly configured

### Executor pods not starting

Check executor pod status:
```bash
kubectl get pods -n spark -l spark-role=executor
```

Check driver logs for executor scheduling issues:
```bash
kubectl logs -n spark spark-pi-driver | grep -i executor
```

### Image pull errors

If you encounter image pull errors, you may need to:

1. Use a different image registry that's accessible from your cluster
2. Configure image pull secrets
3. Use a private registry with proper authentication

Update the image in `spark_application.py`:
```python
"image": "your-registry/spark:v3.5.0",
```

### Resource constraints

If pods are pending due to resource constraints:

1. Check available resources:
   ```bash
   kubectl describe nodes
   ```

2. Reduce resource requests in `spark_application.py`:
   ```python
   "driver": {
       "cores": 0.5,
       "memory": "256m",
   },
   "executor": {
       "cores": 0.5,
       "instances": 1,
       "memory": "256m",
   },
   ```

## Further Reading

- [Kubeflow Spark Operator Documentation](https://github.com/kubeflow/spark-operator)
- [Apache Spark on Kubernetes Documentation](https://spark.apache.org/docs/latest/running-on-kubernetes.html)
- [Spark Application CRD Specification](https://github.com/kubeflow/spark-operator/blob/master/docs/api-docs.md)
- [kubeman Documentation](../README.md)
