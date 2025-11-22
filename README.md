# Kubeman

A Python library for rendering Helm charts and ArgoCD applications.

## Features

- Abstract base class for defining Helm charts
- Abstract base class for raw Kubernetes resources (no Helm required)
- Chart registry for managing multiple charts and resources
- Git operations for manifest repository management
- Docker image build and push utilities
- Automatic ArgoCD Application manifest generation

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

Install development dependencies:

```bash
uv sync --dev
```

Format code:

```bash
uv tool run black .
```

### Pre-commit Hooks

This project uses pre-commit hooks to automatically format code with black before commits.

Install pre-commit as a tool (recommended):

```bash
uv tool install pre-commit
```

This installs pre-commit globally and makes it available in your PATH. Then install the git hooks:

```bash
pre-commit install
```

Now, every time you commit, black will automatically format your Python files. You can also run the hooks manually:

```bash
pre-commit run --all-files
```

**Alternative:** If you prefer to use pre-commit from the virtual environment, you can install it as a dev dependency and use the Python module:

```bash
uv sync --dev
uv run python -m pre_commit install
uv run python -m pre_commit run --all-files
```

## Usage

### Creating a Helm Chart

To create a Helm chart, subclass `HelmChart` and implement the required abstract methods:

```python
from kubeman import HelmChart, ChartRegistry

@ChartRegistry.register
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

For projects that don't need Helm but still want ArgoCD Application generation and manifest management, use the `KubernetesResource` class:

```python
from kubeman import KubernetesResource, ChartRegistry

@ChartRegistry.register
class MyKubernetesResources(KubernetesResource):
    @property
    def name(self) -> str:
        return "my-app"

    @property
    def namespace(self) -> str:
        return "production"

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
                    "CACHE_ENABLED": "true"
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
            },
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": "my-app",
                    "namespace": "production"
                },
                "spec": {
                    "selector": {"app": "my-app"},
                    "ports": [{
                        "port": 80,
                        "targetPort": 8080
                    }]
                }
            }
        ]
```

The `KubernetesResource` class provides a simpler interface than `HelmChart` when you don't need Helm's templating capabilities. It still generates ArgoCD Applications and integrates with the `ChartRegistry` system.

### Rendering Charts and Resources

Once your charts and resources are registered, you can render them:

```python
from kubeman import ChartRegistry

# Get all registered charts and resources
charts = ChartRegistry.get_registered_charts()

# Render each chart/resource
for chart_class in charts:
    chart = chart_class()
    chart.render()  # Generates manifests and ArgoCD Application
```

The `render()` method will:

**For HelmChart:**
1. Render the Helm chart templates to `manifests/{chart-name}/{chart-name}-manifests.yaml`
2. Write any extra manifests to `manifests/{chart-name}/`
3. Generate an ArgoCD Application manifest to `manifests/apps/{chart-name}-application.yaml`

**For KubernetesResource:**
1. Write each Kubernetes manifest to `manifests/{name}/{manifest-name}-{kind}.yaml`
2. Generate an ArgoCD Application manifest to `manifests/apps/{name}-application.yaml`

### Advanced Chart Configuration

#### Custom Repository Package Name

If your repository uses a different package name than the chart name:

```python
@property
def repository_package(self) -> str:
    return "different-package-name"
```

#### OCI Registry Support

For OCI-based Helm repositories:

```python
@property
def repository(self) -> dict:
    return {
        "type": "oci",
        "remote": "oci://registry.example.com/charts"
    }
```

#### Extra Manifests

Add additional Kubernetes manifests alongside your Helm chart:

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

#### Custom ArgoCD Application Settings

Customize the ArgoCD Application generation:

```python
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

The `push_manifests()` method will:
1. Clone the manifests repository
2. Checkout or create the branch matching `STABLE_GIT_BRANCH`
3. Copy rendered manifests from `RENDERED_MANIFEST_DIR`
4. Commit and push the changes

### Docker Operations

The `DockerManager` class helps build and push Docker images to Google Container Registry:

```python
from kubeman import DockerManager

# Initialize with project ID (or set GOOGLE_PROJECT_ID env var)
docker = DockerManager(
    project_id="my-gcp-project",
    repository_name="my-repo"  # Optional, defaults to "default"
)

# Build an image
image_name = docker.build_image(
    component="frontend",
    context_path="./frontend",
    tag="v1.0.0"
)

# Push an image
docker.push_image(component="frontend", tag="v1.0.0")

# Build and push in one step
image_name = docker.build_and_push(
    component="backend",
    context_path="./backend",
    tag="latest"
)
```

## Environment Variables

### Required for Git Operations

- `STABLE_GIT_COMMIT` - Current git commit hash
- `STABLE_GIT_BRANCH` - Current git branch name
- `RENDERED_MANIFEST_DIR` - Path to directory containing rendered manifests
- `MANIFEST_REPO_URL` - Git repository URL for pushing manifests (optional if passed to `push_manifests()`)

### Required for ArgoCD Applications

- `ARGOCD_APP_REPO_URL` - Repository URL for ArgoCD applications (or override `application_repo_url()`)
- `ARGOCD_APPS_SUBDIR` - Subdirectory for applications (defaults to "apps")

### Required for Docker Operations

- `GOOGLE_PROJECT_ID` - Google Cloud project ID (or pass to `DockerManager` constructor)
- `GOOGLE_REGION` - GCP region (defaults to "us-central1")
- `DOCKER_REPOSITORY_NAME` - Docker repository name (defaults to "default")
- `GITHUB_REPOSITORY` - GitHub repository name (optional)

## Complete Example

Here's a complete example that ties everything together, using both `HelmChart` and `KubernetesResource`:

```python
from kubeman import HelmChart, KubernetesResource, ChartRegistry, GitManager, DockerManager

# Define a Helm chart for a third-party application
@ChartRegistry.register
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

# Define custom Kubernetes resources for your application
@ChartRegistry.register
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

# Build and push Docker images
docker = DockerManager()
docker.build_and_push("my-app", "./app", tag="v1.0.0")

# Render all registered charts and resources
for chart_class in ChartRegistry.get_registered_charts():
    chart = chart_class()
    chart.render()

# Push manifests to repository
git = GitManager()
git.push_manifests()
```

## Publishing

This package is automatically published to PyPI via GitHub Actions when:

1. **A new release is published** on GitHub
2. **A version tag is pushed** (e.g., `v0.1.0`, `v1.0.0`)
3. **Manual trigger** via the GitHub Actions workflow

### Setup for Publishing

The workflow uses PyPI trusted publishing (OIDC). To enable it:

1. Go to [PyPI Account Settings](https://pypi.org/manage/account/)
2. Navigate to "API tokens" → "Add a pending project"
3. Add your project name: `kubeman`
4. Copy the "Trusted publisher" configuration
5. In your GitHub repository, go to Settings → Secrets and variables → Actions
6. Add the PyPI project name and repository owner as environment variables (if needed)

Alternatively, you can use an API token:
1. Create an API token on PyPI
2. Add it as a secret named `PYPI_API_TOKEN` in your GitHub repository

### Manual Publishing

To publish manually:

```bash
# Build the package
python -m build

# Check the package
python -m twine check dist/*

# Upload to PyPI (requires credentials)
python -m twine upload dist/*
```

### Installing from PyPI

Once published, users can install the package with:

```bash
pip install kubeman
```

Or with `uv`:

```bash
uv pip install kubeman
```

## License

MIT
