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
4. **Docker** installed (for building custom PySpark job images)
5. **Kubernetes cluster** (version 1.16 or higher)
6. **kind** installed (optional, for local development with kind clusters)

## Usage

### Render and Apply Manifests

The Spark example includes automatic Docker image build and load steps. When you run `kubeman render` or `kubeman apply`, the `CustomPySparkJob` template builds the Docker image using `Dockerfile.pyspark`, loads the image into your kind cluster (if using kind), renders all templates to manifests, and for `apply`, applies manifests to the cluster.

```bash
# From the examples/spark directory:
cd examples/spark
kubeman apply

# Or with explicit path from project root:
kubeman apply --file examples/spark/kubeman.py

# For kind clusters, set Docker environment variables:
DOCKER_PROJECT_ID=test-project DOCKER_REGION=us-central1 DOCKER_REPOSITORY_NAME=default \
  kubeman apply --file examples/spark/kubeman.py

# Skip build/load steps if images are already built:
kubeman apply --file examples/spark/kubeman.py --skip-build
```

**Note**: The `kubeman.py` file imports all template modules which automatically register themselves via the `@TemplateRegistry.register` decorator. Build and load steps execute automatically during registration, before rendering.

### Render Only (Without Applying)

To render manifests without applying them:

```bash
# From the examples/spark directory:
cd examples/spark
kubeman render

# Or with explicit path from project root:
kubeman render --file examples/spark/kubeman.py

# Optionally specify custom output directory:
kubeman render --file examples/spark/kubeman.py --output-dir ./custom-manifests
```

This builds the Docker image for `CustomPySparkJob` (if not skipped), loads the image into kind cluster (if not skipped), and renders all templates to the `manifests/` directory.

### Verify Deployment

Check the status of the Spark deployment:

```bash
# Check pods (Spark Operator, SparkPi driver, CustomPySparkJob driver and executors)
kubectl get pods -n spark

# Check services
kubectl get svc -n spark

# Check SparkApplication status
kubectl get sparkapplication -n spark

# Check SparkApplication details
kubectl describe sparkapplication spark-pi -n spark
kubectl describe sparkapplication custom-pyspark-job -n spark

# Check Spark Operator logs
kubectl logs -n spark -l app.kubernetes.io/name=spark-operator

# Check SparkPi driver logs
kubectl logs -n spark -l spark-role=driver,sparkoperator.k8s.io/app-name=spark-pi

# Check CustomPySparkJob driver logs
kubectl logs -n spark -l spark-role=driver,sparkoperator.k8s.io/app-name=custom-pyspark-job
```

## Build and Load Steps

The `CustomPySparkJob` template includes build and load steps that execute sequentially during template registration, ensuring the image is built and loaded before the SparkApplication is deployed.

### Customizing Build Steps

To modify the build or load behavior, edit `custom_pyspark_job.py`:

```python
def build(self) -> None:
    """Build Docker image for custom PySpark job"""
    from pathlib import Path
    from kubeman import DockerManager

    spark_dir = Path(__file__).parent
    docker = DockerManager()
    docker.build_image(
        component="custom-pyspark-job",
        context_path=str(spark_dir),
        tag="latest",
        dockerfile="Dockerfile.pyspark",
    )
    # Tag with local name for kind cluster
    docker.tag_image(
        source_image=f"{docker.registry}/custom-pyspark-job",
        target_image="custom-pyspark-job",
        source_tag="latest",
    )

def load(self) -> None:
    """Load Docker image into kind cluster"""
    from kubeman import DockerManager

    docker = DockerManager()
    docker.kind_load_image("custom-pyspark-job", tag="latest")
```

## Configuration

The example is configured with:
- **Spark Operator version**: 1.1.27
- **Spark version**: 3.5.0
- **Driver resources**: 1 core, 512m memory
- **Executor resources**: 1 core per executor, 512m memory, 2 instances
- **Namespace**: spark
- **Custom PySpark Job**: Automatically builds and loads Docker image

### Customizing the Configuration

Edit `spark_operator.py` and modify the `generate_values()` method to customize operator resource limits, webhook configuration, and service account settings.

Edit `spark_application.py` and modify the `manifests()` method to customize Spark version, driver/executor resources, number of executor instances, Spark application image, and main class/application file.

## Running Spark Applications

### SparkPi Example

The example includes a SparkPi application that calculates π using Monte Carlo method. Once deployed, it automatically starts running. View results in the driver logs:

```bash
kubectl logs -n spark spark-pi-driver | grep -i "pi"
```

Monitor the application:
```bash
# Watch SparkApplication status
kubectl get sparkapplication spark-pi -n spark -w

# Check driver pod logs
kubectl logs -n spark spark-pi-driver -f

# Check executor pod logs
kubectl logs -n spark -l spark-role=executor -f
```

### Custom PySpark Jobs

To run a custom PySpark job:

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

#### 4. Register and Deploy

Add the import to `kubeman.py`:
```python
import custom_pyspark_job  # noqa: F401
```

Deploy using kubeman:
```bash
kubeman apply --file examples/spark/kubeman.py
```

#### 5. View Results

Check the job status and logs:
```bash
# Check SparkApplication status
kubectl get sparkapplication custom-pyspark-job -n spark

# View driver logs
kubectl logs -n spark -l spark-role=driver,sparkoperator.k8s.io/app-name=custom-pyspark-job
```

**Example Files:** The example includes `pyspark_example.py`, `Dockerfile.pyspark`, and `custom_pyspark_job.py` as starting points for your own PySpark jobs.

**Creating Custom Spark Applications:** You can modify the existing SparkApplication in `spark_application.py` (change `mainClass`, update `mainApplicationFile`, adjust resources) or create a new SparkApplication class following the same pattern and import it in `kubeman.py`.

### Spark Application Modes

The example uses `cluster` mode (both driver and executors run in cluster). You can also use `client` mode (driver runs locally, executors in cluster).

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

Common issues: Image pull errors (verify Spark image is accessible), resource constraints (check cluster resources), service account permissions (verify RBAC configuration).

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

If you encounter image pull errors, use a different image registry accessible from your cluster, configure image pull secrets, or use a private registry with proper authentication. Update the image in `spark_application.py`:
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
