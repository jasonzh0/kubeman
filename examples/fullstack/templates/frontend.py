"""
Frontend React Application Kubernetes Resource.

This module defines Kubernetes resources for deploying the React frontend
for the fullstack TODO application.
"""

from kubeman import KubernetesResource, TemplateRegistry


@TemplateRegistry.register
class FrontendApp(KubernetesResource):
    """
    React frontend service for the fullstack TODO application.
    """

    def __init__(self):
        super().__init__()
        self.name = "frontend-app"
        self.namespace = "fullstack"

        # Add ConfigMap for frontend runtime configuration
        self.add_configmap(
            name="frontend-config",
            data={
                "config.js": "window.APP_CONFIG = { API_URL: 'http://backend:8000' };",
            },
            labels={"app": "fullstack", "component": "frontend"},
        )

        # Add Deployment
        self.add_deployment(
            name="frontend",
            replicas=1,
            labels={"app": "fullstack", "component": "frontend"},
            containers=[
                {
                    "name": "frontend",
                    "image": "frontend-app:latest",
                    "imagePullPolicy": "Never",
                    "ports": [{"name": "http", "containerPort": 80}],
                    "volumeMounts": [
                        {
                            "name": "config",
                            "mountPath": "/usr/share/nginx/html/config.js",
                            "subPath": "config.js",
                        },
                    ],
                    "resources": {
                        "requests": {"cpu": "50m", "memory": "128Mi"},
                        "limits": {"cpu": "200m", "memory": "256Mi"},
                    },
                    "livenessProbe": {
                        "httpGet": {
                            "path": "/",
                            "port": 80,
                        },
                        "initialDelaySeconds": 10,
                        "periodSeconds": 10,
                    },
                    "readinessProbe": {
                        "httpGet": {
                            "path": "/",
                            "port": 80,
                        },
                        "initialDelaySeconds": 5,
                        "periodSeconds": 5,
                    },
                }
            ],
            volumes=[
                {
                    "name": "config",
                    "configMap": {
                        "name": "frontend-config",
                    },
                },
            ],
        )

        # Add Service
        self.add_service(
            name="frontend",
            service_type="ClusterIP",
            selector={"app": "fullstack", "component": "frontend"},
            ports=[{"name": "http", "port": 80, "targetPort": 80}],
            labels={"app": "fullstack", "component": "frontend"},
        )

        # Add Ingress for external access
        self.add_ingress(
            name="frontend",
            rules=[
                {
                    "host": "todo.local",
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": "frontend",
                                        "port": {"number": 80},
                                    }
                                },
                            }
                        ]
                    },
                }
            ],
            labels={"app": "fullstack", "component": "frontend"},
        )

    def build(self) -> None:
        """Build Docker image for frontend app"""
        from kubeman import DockerManager

        context_path = self.resolve_path("../frontend")
        docker = DockerManager()
        docker.build_image(
            component="frontend-app",
            context_path=context_path,
            tag="latest",
            dockerfile="Dockerfile",
        )
        docker.tag_image(
            source_image=f"{docker.registry}/frontend-app",
            target_image="frontend-app",
            source_tag="latest",
        )

    def load(self) -> None:
        """Load Docker image into kind cluster"""
        from kubeman import DockerManager

        docker = DockerManager()
        docker.kind_load_image("frontend-app", tag="latest")
