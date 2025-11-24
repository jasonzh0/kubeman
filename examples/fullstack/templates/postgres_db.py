"""
PostgreSQL Database Kubernetes Resource.

This module defines Kubernetes resources for deploying a PostgreSQL database
for the fullstack TODO application.
"""

from kubeman import KubernetesResource, TemplateRegistry


@TemplateRegistry.register
class PostgresDB(KubernetesResource):
    """
    PostgreSQL database deployment for the fullstack TODO application.
    """

    def __init__(self):
        super().__init__()
        self.name = "postgres-db"
        self.namespace = "fullstack"

        # Add Namespace
        self.add_namespace(
            labels={"app": "fullstack", "component": "database"},
        )

        # Add ConfigMap for database configuration
        self.add_configmap(
            name="postgres-config",
            data={
                "POSTGRES_DB": "todos_db",
                "POSTGRES_USER": "todos_user",
            },
            labels={"app": "fullstack", "component": "database"},
        )

        # Add Secret for database password
        self.add_secret(
            name="postgres-secret",
            string_data={
                "POSTGRES_PASSWORD": "todos_password",
            },
            labels={"app": "fullstack", "component": "database"},
        )

        # Add PersistentVolumeClaim
        self.add_persistent_volume_claim(
            name="postgres-pvc",
            access_modes=["ReadWriteOnce"],
            storage="5Gi",
            labels={"app": "fullstack", "component": "database"},
        )

        # Add Deployment
        self.add_deployment(
            name="postgres",
            replicas=1,
            strategy_type="Recreate",
            labels={"app": "fullstack", "component": "database"},
            containers=[
                {
                    "name": "postgres",
                    "image": "postgres:16-alpine",
                    "ports": [{"name": "postgres", "containerPort": 5432}],
                    "env": [
                        {
                            "name": "POSTGRES_DB",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "postgres-config",
                                    "key": "POSTGRES_DB",
                                },
                            },
                        },
                        {
                            "name": "POSTGRES_USER",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "postgres-config",
                                    "key": "POSTGRES_USER",
                                },
                            },
                        },
                        {
                            "name": "POSTGRES_PASSWORD",
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": "postgres-secret",
                                    "key": "POSTGRES_PASSWORD",
                                },
                            },
                        },
                    ],
                    "volumeMounts": [
                        {"name": "postgres-storage", "mountPath": "/var/lib/postgresql/data"},
                    ],
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "256Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                    },
                    "livenessProbe": {
                        "exec": {
                            "command": ["pg_isready", "-U", "todos_user", "-d", "todos_db"],
                        },
                        "initialDelaySeconds": 30,
                        "periodSeconds": 10,
                    },
                    "readinessProbe": {
                        "exec": {
                            "command": ["pg_isready", "-U", "todos_user", "-d", "todos_db"],
                        },
                        "initialDelaySeconds": 5,
                        "periodSeconds": 5,
                    },
                }
            ],
            volumes=[
                {
                    "name": "postgres-storage",
                    "persistentVolumeClaim": {"claimName": "postgres-pvc"},
                },
            ],
        )

        # Add Service
        self.add_service(
            name="postgres",
            service_type="ClusterIP",
            selector={"app": "fullstack", "component": "database"},
            ports=[{"name": "postgres", "port": 5432, "targetPort": 5432}],
            labels={"app": "fullstack", "component": "database"},
        )

    def extra_manifests(self) -> list[dict]:
        """Add ConfigMap with init.sql for database initialization"""
        init_sql_path = self.resolve_path("../init.sql")
        init_sql_content = init_sql_path.read_text()

        return [
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "postgres-init-sql",
                    "namespace": self.namespace,
                    "labels": {"app": "fullstack", "component": "database"},
                },
                "data": {
                    "init.sql": init_sql_content,
                },
            },
            {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": "postgres-init",
                    "namespace": self.namespace,
                    "labels": {"app": "fullstack", "component": "database-init"},
                },
                "spec": {
                    "backoffLimit": 5,
                    "template": {
                        "spec": {
                            "restartPolicy": "OnFailure",
                            "containers": [
                                {
                                    "name": "init-db",
                                    "image": "postgres:16-alpine",
                                    "command": [
                                        "sh",
                                        "-c",
                                        "until pg_isready -h postgres -U todos_user -d todos_db; do echo 'Waiting for postgres...'; sleep 2; done && psql -h postgres -U todos_user -d todos_db -f /init.sql",
                                    ],
                                    "env": [
                                        {
                                            "name": "PGPASSWORD",
                                            "valueFrom": {
                                                "secretKeyRef": {
                                                    "name": "postgres-secret",
                                                    "key": "POSTGRES_PASSWORD",
                                                },
                                            },
                                        },
                                    ],
                                    "volumeMounts": [
                                        {
                                            "name": "init-sql",
                                            "mountPath": "/init.sql",
                                            "subPath": "init.sql",
                                        },
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "init-sql",
                                    "configMap": {
                                        "name": "postgres-init-sql",
                                    },
                                }
                            ],
                        }
                    },
                },
            },
        ]
