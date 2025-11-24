# Kubeman

![PyPI - Version](https://img.shields.io/pypi/v/kubeman)

A Python library for rendering Helm charts and Kubernetes resources with optional ArgoCD Application generation. Features an abstract Template base class for consistent template management.

## Features

- Abstract `Template` base class for all template types
- `HelmChart` class for defining Helm charts
- `KubernetesResource` class for raw Kubernetes resources (no Helm required)
- `TemplateRegistry` for managing multiple templates (charts and resources)
- Command-line interface (CLI) for rendering and applying manifests
- Automatic Docker image build and load steps (executed sequentially during template registration)
- Git operations for manifest repository management
- Docker image build and push utilities with custom Dockerfile support
- Optional ArgoCD Application manifest generation (opt-in)

## Installation

### From Source

Using `uv` (recommended):
```bash
uv pip install -e .
```

Or using `pip`:
```bash
pip install -e .
```

### Development Setup

Install development dependencies and format code:
```bash
uv sync --dev
uv tool run black .
```

### Pre-commit Hooks

Install pre-commit globally:
```bash
uv tool install pre-commit
pre-commit install
```

This automatically formats code with black before commits. Run manually:
```bash
pre-commit run --all-files
```

**Alternative:** Install as dev dependency:
```bash
uv sync --dev
uv run python -m pre_commit install
```

## Usage

### Template Architecture

Both `HelmChart` and `KubernetesResource` inherit from the abstract `Template` base class, providing common functionality for ArgoCD Application generation (opt-in), manifest directory management, namespace/name properties, rendering to filesystem, and optional Docker image build steps executed sequentially during template registration.

### Creating a Helm Chart

Subclass `HelmChart` and implement the required abstract methods:

```python
from kubeman import HelmChart, TemplateRegistry

@TemplateRegistry.register
class MyChart(HelmChart):
    @property
    def name(self) -> str:
        return "my-chart"

    @property
    def repository(self) -> dict:
        """Return repository information"""
        return {
            "type": "classic",  # or "oci" or "none"
            "remote": "https://charts.example.com"
        }

    @property
    def namespace(self) -> str:
        return "my-namespace"

    @property
    def version(self) -> str:
        return "1.0.0"

    def generate_values(self) -> dict:
        """Generate values.yaml content"""
        return {
            "replicaCount": 3,
            "image": {
                "repository": "my-app",
                "tag": "latest"
            }
        }
```

### Creating a Kubernetes Resource (Without Helm)

For projects that don't need Helm but want optional ArgoCD Application generation and manifest management, use `KubernetesResource`. Supports two patterns:

#### Pattern 1: Using Helper Methods (Recommended)

Use built-in helper methods to build Kubernetes resources:

```python
from kubeman import KubernetesResource, TemplateRegistry

@TemplateRegistry.register
class DogBreedsDbChart(KubernetesResource):
    """Dog Breeds PostgreSQL database resources."""

    def __init__(self):
        super().__init__()
        self.namespace = "dog-breeds"

        # Add Namespace
        self.add_namespace(
            name="dog-breeds",
            labels={"app": "dog-breeds", "component": "database"},
        )

        # Add ConfigMap for database configuration
        self.add_configmap(
            name="dog-breeds-db-config",
            namespace="dog-breeds",
            data={
                "POSTGRES_DB": "dog_breeds_db",
                "POSTGRES_USER": "airflow",
            },
            labels={"app": "dog-breeds", "component": "database"},
        )

        # Add Secret for database password
        self.add_secret(
            name="dog-breeds-db-secret",
            namespace="dog-breeds",
            string_data={
                "POSTGRES_PASSWORD": "airflow",
            },
            labels={"app": "dog-breeds", "component": "database"},
        )

        # Add PersistentVolumeClaim
        self.add_persistent_volume_claim(
            name="dog-breeds-db-pvc",
            namespace="dog-breeds",
            access_modes=["ReadWriteOnce"],
            storage="5Gi",
            labels={"app": "dog-breeds", "component": "database"},
        )

        # Add Deployment
        self.add_deployment(
            name="dog-breeds-db",
            namespace="dog-breeds",
            replicas=1,
            strategy_type="Recreate",
            labels={"app": "dog-breeds", "component": "database"},
            containers=[
                {
                    "name": "postgres",
                    "image": "postgres:16-alpine",
                    "ports": [{"name": "postgres", "containerPort": 5432}],
                    "env": [
                        {
                            "name": "POSTGRES_PASSWORD",
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": "dog-breeds-db-secret",
                                    "key": "POSTGRES_PASSWORD",
                                },
                            },
                        },
                    ],
                    "volumeMounts": [
                        {"name": "postgres-storage", "mountPath": "/var/lib/postgresql/data"},
                    ],
                }
            ],
            volumes=[
                {"name": "postgres-storage", "persistentVolumeClaim": {"claimName": "dog-breeds-db-pvc"}},
            ],
            init_containers=[
                {
                    "name": "init-db",
                    "image": "busybox:latest",
                    "command": ["sh", "-c", "echo Initializing database schema"],
                }
            ],
        )

        # Add Service
        self.add_service(
            name="dog-breeds-db",
            namespace="dog-breeds",
            service_type="ClusterIP",
            selector={"app": "dog-breeds", "component": "database"},
            ports=[{"name": "postgres", "port": 5432, "targetPort": 5432}],
            labels={"app": "dog-breeds", "component": "database"},
        )
```

**Available Helper Methods:** `add_namespace()`, `add_configmap()`, `add_secret()`, `add_persistent_volume_claim()`, `add_deployment()`, `add_statefulset()`, `add_service()`, `add_ingress()`, `add_service_account()`, `add_role()`, `add_role_binding()`, `add_cluster_role()`, `add_cluster_role_binding()`, `add_custom_resource()`

#### Pattern 2: Override manifests() Method

For complex logic or custom manifest generation, override the `manifests()` method:

```python
from kubeman import KubernetesResource, TemplateRegistry

@TemplateRegistry.register
class MyAppResources(KubernetesResource):
    def __init__(self):
        super().__init__()
        self.namespace = "production"

    def manifests(self) -> list[dict]:
        """Return list of Kubernetes manifests"""
        return [
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "my-app-config",
                    "namespace": "production"
                },
                "data": {
                    "DATABASE_URL": "postgres://db:5432/myapp",
                }
            },
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "my-app",
                    "namespace": "production"
                },
                "spec": {
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "my-app"}},
                    "template": {
                        "metadata": {"labels": {"app": "my-app"}},
                        "spec": {
                            "containers": [{
                                "name": "my-app",
                                "image": "gcr.io/my-project/my-app:v1.0.0",
                                "envFrom": [{
                                    "configMapRef": {"name": "my-app-config"}
                                }]
                            }]
                        }
                    }
                }
            }
        ]
```

### Build and Load Steps

Templates can define Docker image build and load steps that execute automatically when templates are imported. Steps run sequentially in registration order: build steps first, then load steps.

#### Build Steps

Override the `build()` method to add build steps:

```python
from kubeman import KubernetesResource, TemplateRegistry, DockerManager

@TemplateRegistry.register
class MyApp(KubernetesResource):
    def __init__(self):
        super().__init__()
        self.name = "my-app"
        self.namespace = "production"

    def build(self) -> None:
        """Build Docker images for this template."""
        docker = DockerManager()
        docker.build_image(
            component="my-app",
            context_path="./app",
            tag="latest",
            dockerfile="Dockerfile.prod"  # Optional: custom Dockerfile name
        )
        # Tag with local name for kind clusters
        docker.tag_image(
            source_image=f"{docker.registry}/my-app",
            target_image="my-app",
            source_tag="latest"
        )
```

#### Load Steps

For local development with kind clusters, add load steps:

```python
def load(self) -> None:
    """Load Docker images into kind cluster."""
    docker = DockerManager()
    docker.kind_load_image("my-app", tag="latest")
```

**Key points:** Build steps execute automatically when templates are imported. Load steps execute after build steps. Use `--skip-build` flag to skip build/load steps during render/apply. If a build or load fails, template registration fails with a clear error message.

### Rendering Charts and Resources

Render templates using the CLI or Python API.

#### Using the CLI (Recommended)

```bash
# Render all templates from a Python file
kubeman render --file kubeman.py

# Render without executing build steps
kubeman render --file kubeman.py --skip-build

# Render and apply to Kubernetes cluster (builds execute automatically)
kubeman apply --file kubeman.py

# Apply without executing build steps
kubeman apply --file kubeman.py --skip-build
```

The CLI imports your template file (containing `@TemplateRegistry.register` decorated classes), discovers all registered templates, renders each to the `manifests/` directory, and for `apply`, runs `kubectl apply` on the rendered manifests.

**Example template file (`kubeman.py`):**
```python
from kubeman import KubernetesResource, TemplateRegistry

@TemplateRegistry.register
class MyAppResources(KubernetesResource):
    def __init__(self):
        super().__init__()
        self.namespace = "production"
        # ... add resources using helper methods ...
```

#### Using the Python API

```python
from kubeman import TemplateRegistry

# Get all registered templates (charts and resources)
templates = TemplateRegistry.get_registered_templates()

# Render each template
for template_class in templates:
    template = template_class()
    template.render()  # Generates manifests and ArgoCD Application
```

**For HelmChart:** Renders to `manifests/{chart-name}/{chart-name}-manifests.yaml`, writes extra manifests to `manifests/{chart-name}/`, and generates ArgoCD Application to `manifests/apps/{chart-name}-application.yaml` (if enabled).

**For KubernetesResource:** Writes each manifest to `manifests/{name}/{manifest-name}-{kind}.yaml` and generates ArgoCD Application to `manifests/apps/{name}-application.yaml` (if enabled).

### Advanced Chart Configuration

#### Custom Repository Package Name

```python
@property
def repository_package(self) -> str:
    return "different-package-name"
```

#### OCI Registry Support

```python
@property
def repository(self) -> dict:
    return {
        "type": "oci",
        "remote": "oci://registry.example.com/charts"
    }
```

#### Extra Manifests

```python
def extra_manifests(self) -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "my-config"},
            "data": {"key": "value"}
        }
    ]
```

#### Enabling ArgoCD Application Generation (Opt-In)

ArgoCD Application generation is disabled by default. Enable via environment variable:
```bash
export ARGOCD_APP_REPO_URL="https://github.com/org/manifests-repo"
```

Or override `enable_argocd()` method:
```python
@TemplateRegistry.register
class MyChart(HelmChart):
    def enable_argocd(self) -> bool:
        """Enable ArgoCD Application generation for this chart"""
        return True
```

If `ARGOCD_APP_REPO_URL` is not set and `enable_argocd()` returns `True`, override `application_repo_url()` to provide the repository URL.

#### Custom ArgoCD Application Settings

```python
def enable_argocd(self) -> bool:
    """Enable ArgoCD Application generation (opt-in)"""
    return True

def application_repo_url(self) -> str:
    """Override the repository URL for ArgoCD applications"""
    return "https://github.com/org/manifests-repo"

def application_target_revision(self) -> str:
    """Override the target revision (defaults to current branch)"""
    return "main"

def managed_namespace_metadata(self) -> dict:
    """Add labels to managed namespaces"""
    return {
        "app.kubernetes.io/managed-by": "argocd"
    }

def argo_ignore_spec(self) -> list:
    """Configure ArgoCD ignore differences"""
    return [
        {
            "group": "apps",
            "kind": "Deployment",
            "jsonPointers": ["/spec/replicas"]
        }
    ]
```

### Git Operations

The `GitManager` class provides utilities for working with Git repositories:

```python
from kubeman import GitManager

git = GitManager()

# Get current commit hash (from STABLE_GIT_COMMIT env var)
commit_hash = git.fetch_commit_hash()

# Get current branch name (from STABLE_GIT_BRANCH env var)
branch_name = git.fetch_branch_name()

# Push rendered manifests to a repository
git.push_manifests(repo_url="https://github.com/org/manifests-repo")
```

The `push_manifests()` method clones the manifests repository, checks out or creates the branch matching `STABLE_GIT_BRANCH`, copies rendered manifests from `RENDERED_MANIFEST_DIR`, and commits and pushes the changes.

### Docker Operations

The `DockerManager` class helps build and push Docker images:

```python
from kubeman import DockerManager

# Initialize with project ID (or set DOCKER_PROJECT_ID env var)
docker = DockerManager(
    project_id="my-project",
    repository_name="my-repo"  # Optional, defaults to "default"
)

# Build an image
image_name = docker.build_image(
    component="frontend",
    context_path="./frontend",
    tag="v1.0.0"
)

# Build with custom Dockerfile name
image_name = docker.build_image(
    component="frontend",
    context_path="./frontend",
    tag="v1.0.0",
    dockerfile="Dockerfile.prod"  # Optional: defaults to "Dockerfile"
)

# Tag an image (useful for creating local tags from registry images)
docker.tag_image(
    source_image=f"{docker.registry}/frontend",
    target_image="frontend",
    source_tag="v1.0.0",
    target_tag="latest"  # Optional: defaults to source_tag
)

# Load image into kind cluster (for local development)
docker.kind_load_image(
    image_name="frontend",
    tag="latest",
    cluster_name="my-cluster"  # Optional: auto-detected from kubectl context
)

# Push an image
docker.push_image(component="frontend", tag="v1.0.0")

# Build and push in one step
image_name = docker.build_and_push(
    component="backend",
    context_path="./backend",
    tag="latest",
    dockerfile="Dockerfile"  # Optional: custom Dockerfile name
)
```

## Environment Variables

### Required for Git Operations
- `STABLE_GIT_COMMIT` - Current git commit hash
- `STABLE_GIT_BRANCH` - Current git branch name
- `RENDERED_MANIFEST_DIR` - Path to directory containing rendered manifests
- `MANIFEST_REPO_URL` - Git repository URL for pushing manifests (optional if passed to `push_manifests()`)

### Optional for ArgoCD Applications
ArgoCD Application generation is opt-in and disabled by default. To enable:
- `ARGOCD_APP_REPO_URL` - Repository URL for ArgoCD applications (or override `application_repo_url()`). Required if ArgoCD is enabled.
- `ARGOCD_APPS_SUBDIR` - Subdirectory for applications (defaults to "apps")

You can also enable ArgoCD by overriding the `enable_argocd()` method in your template class to return `True`.

### Required for Docker Operations
- `DOCKER_PROJECT_ID` - Registry project ID (or pass to `DockerManager` constructor)
- `DOCKER_REGION` - Registry region (defaults to "us-central1")
- `DOCKER_REPOSITORY_NAME` - Docker repository name (defaults to "default")
- `GITHUB_REPOSITORY` - GitHub repository name (optional)

## Complete Example

Complete example using both `HelmChart` and `KubernetesResource`:

```python
from kubeman import HelmChart, KubernetesResource, TemplateRegistry, GitManager, DockerManager

# Define a Helm chart for a third-party application
@TemplateRegistry.register
class PostgresChart(HelmChart):
    @property
    def name(self) -> str:
        return "postgres"

    @property
    def repository(self) -> dict:
        return {
            "type": "classic",
            "remote": "https://charts.bitnami.com/bitnami"
        }

    @property
    def namespace(self) -> str:
        return "database"

    @property
    def version(self) -> str:
        return "12.5.0"

    def generate_values(self) -> dict:
        return {
            "auth": {
                "postgresPassword": "changeme"
            },
            "persistence": {
                "enabled": True,
                "size": "10Gi"
            }
        }

    def enable_argocd(self) -> bool:
        """Enable ArgoCD Application generation (opt-in)"""
        return True

# Define custom Kubernetes resources for your application
@TemplateRegistry.register
class MyAppResources(KubernetesResource):
    @property
    def name(self) -> str:
        return "my-app"

    @property
    def namespace(self) -> str:
        return "production"

    def manifests(self) -> list[dict]:
        return [
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": "my-app-config", "namespace": "production"},
                "data": {"DATABASE_HOST": "postgres.database.svc.cluster.local"}
            },
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "my-app", "namespace": "production"},
                "spec": {
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "my-app"}},
                    "template": {
                        "metadata": {"labels": {"app": "my-app"}},
                        "spec": {
                            "containers": [{
                                "name": "my-app",
                                "image": "gcr.io/my-project/my-app:v1.0.0",
                                "envFrom": [{"configMapRef": {"name": "my-app-config"}}]
                            }]
                        }
                    }
                }
            }
        ]

# Option 1: Use CLI to render and apply
# Build steps execute automatically when templates are imported
# kubeman render --file kubeman.py
# kubeman apply --file kubeman.py

# Option 2: Skip build steps if images are already built
# kubeman render --file kubeman.py --skip-build
# kubeman apply --file kubeman.py --skip-build

# Option 3: Render programmatically
for template_class in TemplateRegistry.get_registered_templates():
    template = template_class()
    template.render()

# Push manifests to repository
git = GitManager()
git.push_manifests()
```

## Publishing

This package is automatically published to PyPI via GitHub Actions when:
1. A new release is published on GitHub
2. Manual trigger via the GitHub Actions workflow

## License

[MIT](LICENSE)
