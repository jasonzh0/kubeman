"""
Backend API Kubernetes Resource.

This module defines Kubernetes resources for deploying the FastAPI backend
for the fullstack TODO application.
"""

from pathlib import Path
from kubeman import KubernetesResource, TemplateRegistry


@TemplateRegistry.register
class BackendAPI(KubernetesResource):
    """
    FastAPI backend service for the fullstack TODO application.
    """

    def __init__(self):
        super().__init__()
        self.name = "backend-api"
        self.namespace = "fullstack"

        # Add ConfigMap for backend configuration
        self.add_configmap(
            name="backend-config",
            data={
                "DATABASE_URL": "postgresql://todos_user:todos_password@postgres:5432/todos_db",
                "PORT": "8000",
            },
            labels={"app": "fullstack", "component": "backend"},
        )

        # Add Deployment
        self.add_deployment(
            name="backend",
            replicas=1,
            labels={"app": "fullstack", "component": "backend"},
            containers=[
                {
                    "name": "backend",
                    "image": "backend-api:latest",
                    "imagePullPolicy": "Never",
                    "ports": [{"name": "http", "containerPort": 8000}],
                    "env": [
                        {
                            "name": "DATABASE_URL",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "backend-config",
                                    "key": "DATABASE_URL",
                                },
                            },
                        },
                        {
                            "name": "PORT",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "backend-config",
                                    "key": "PORT",
                                },
                            },
                        },
                    ],
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "256Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                    },
                    "livenessProbe": {
                        "httpGet": {
                            "path": "/health",
                            "port": 8000,
                        },
                        "initialDelaySeconds": 30,
                        "periodSeconds": 10,
                    },
                    "readinessProbe": {
                        "httpGet": {
                            "path": "/health",
                            "port": 8000,
                        },
                        "initialDelaySeconds": 5,
                        "periodSeconds": 5,
                    },
                }
            ],
        )

        # Add Service
        self.add_service(
            name="backend",
            service_type="ClusterIP",
            selector={"app": "fullstack", "component": "backend"},
            ports=[{"name": "http", "port": 8000, "targetPort": 8000}],
            labels={"app": "fullstack", "component": "backend"},
        )

    def build(self) -> None:
        """Build Docker image for backend API"""
        from kubeman import DockerManager

        backend_dir = Path(__file__).parent / "backend"
        docker = DockerManager()
        docker.build_image(
            component="backend-api",
            context_path=str(backend_dir),
            tag="latest",
            dockerfile="Dockerfile",
        )
        docker.tag_image(
            source_image=f"{docker.registry}/backend-api",
            target_image="backend-api",
            source_tag="latest",
        )

    def load(self) -> None:
        """Load Docker image into kind cluster"""
        from kubeman import DockerManager

        docker = DockerManager()
        docker.kind_load_image("backend-api", tag="latest")

    def enable_argocd(self) -> bool:
        """Disable ArgoCD Application generation for this example"""
        return False
