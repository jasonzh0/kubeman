# Fullstack TODO Application Example

This example demonstrates how to deploy a complete fullstack application to Kubernetes using kubeman. The application consists of a React TypeScript frontend, FastAPI backend, and PostgreSQL database.

## Overview

The example includes:
- **PostgreSQL Database** - Persistent database with schema initialization
- **FastAPI Backend** - REST API with CRUD operations for TODO management
- **React TypeScript Frontend** - Modern frontend built with Vite and TypeScript
- **Automatic Docker builds** - Images are built automatically during deployment
- **Health checks** - Liveness and readiness probes for all services
- **Ingress** - External access to the frontend application

## Architecture

```
┌─────────────┐
│   Ingress   │
└──────┬──────┘
       │
┌──────▼──────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────▶│   Backend   │────▶│  PostgreSQL │
│  (React)    │     │  (FastAPI)  │     │   Database  │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Prerequisites

1. **kubectl** configured to access your Kubernetes cluster
2. **kubeman** installed (see main README for installation instructions)
3. **Docker** installed (for building application images)
4. **Node.js** and **npm** (for local frontend development, optional)

## Usage

### Render and Apply Manifests

The fullstack example includes automatic Docker image build steps for both the frontend and backend. When you run `kubeman render` or `kubeman apply`, build steps execute automatically, then templates are rendered to manifests, and for `apply`, manifests are applied to the cluster.

```bash
# From the examples/fullstack directory:
cd examples/fullstack
kubeman apply

# Or with explicit path from project root:
kubeman apply --file examples/fullstack/kubeman.py

# For kind clusters, set Docker environment variables:
DOCKER_PROJECT_ID=test-project DOCKER_REGION=us-central1 DOCKER_REPOSITORY_NAME=default \
  kubeman apply --file examples/fullstack/kubeman.py

# Skip build steps if images are already built:
kubeman apply --file examples/fullstack/kubeman.py --skip-build
```

**Note**: The `kubeman.py` file imports all template modules which automatically register themselves via the `@TemplateRegistry.register` decorator. Build steps execute automatically during registration, before rendering.

### Render Only (Without Applying)

To render manifests without applying them:

```bash
# From the examples/fullstack directory:
cd examples/fullstack
kubeman render

# Or with explicit path from project root:
kubeman render --file examples/fullstack/kubeman.py

# Optionally specify custom output directory:
kubeman render --file examples/fullstack/kubeman.py --output-dir ./custom-manifests
```

This builds the Docker images for frontend and backend (if not skipped) and renders all templates to the `manifests/` directory.

### Verify Deployment

Check the status of the deployment:

```bash
# Check pods (database, backend, frontend)
kubectl get pods -n fullstack

# Check services
kubectl get svc -n fullstack

# Check persistent volume claims
kubectl get pvc -n fullstack

# Check backend logs
kubectl logs -n fullstack -l app=fullstack,component=backend

# Check frontend logs
kubectl logs -n fullstack -l app=fullstack,component=frontend

# Check database logs
kubectl logs -n fullstack -l app=fullstack,component=database
```

### Access the Application

#### Using Port Forwarding

```bash
# Forward frontend service
kubectl port-forward -n fullstack svc/frontend 3000:80

# Forward backend service (optional, for direct API access)
kubectl port-forward -n fullstack svc/backend 8000:8000
```

Then access the application at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

#### Using Ingress

If you have an ingress controller installed, the application is accessible at:
- Frontend: http://todo.local (or configure your `/etc/hosts` to point to your cluster)

## Configuration

The example is configured with:
- **Database**: PostgreSQL 16-alpine with 5Gi persistent storage
- **Backend**: FastAPI with async PostgreSQL connection pooling
- **Frontend**: React TypeScript with Vite, served via nginx
- **Namespace**: `fullstack`
- **Replicas**: 1 for each service (can be scaled)

### Database Configuration

- Database name: `todos_db`
- Username: `todos_user`
- Password: `todos_password` (change in production!)
- Storage: 5Gi persistent volume

### Backend Configuration

- Port: 8000
- Database connection: Uses asyncpg for async PostgreSQL access
- CORS: Enabled for all origins (configure in production)
- Health endpoint: `/health`

### Frontend Configuration

- Port: 80 (nginx)
- API URL: Configured via `VITE_API_URL` environment variable
- Build: Production-optimized Vite build

### Customizing the Configuration

Edit the respective template files to customize:
- `postgres_db.py` - Database configuration, storage size, resources
- `backend.py` - Backend replicas, resources, environment variables
- `frontend.py` - Frontend replicas, resources, ingress configuration

## API Endpoints

The backend provides the following REST API endpoints:

- `GET /health` - Health check endpoint
- `GET /todos` - List all todos
- `POST /todos` - Create a new todo
  ```json
  {
    "title": "My new todo"
  }
  ```
- `DELETE /todos/{id}` - Delete a todo by ID

## Database Schema

The database is initialized with the following schema:

```sql
CREATE TABLE todos (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## Development

### Local Backend Development

```bash
cd examples/fullstack/backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Local Frontend Development

```bash
cd examples/fullstack/frontend
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8000` in `.env` file for local development.

## Troubleshooting

### Pods not starting

Check pod logs:
```bash
# Check database logs
kubectl logs -n fullstack -l app=fullstack,component=database

# Check backend logs
kubectl logs -n fullstack -l app=fullstack,component=backend

# Check frontend logs
kubectl logs -n fullstack -l app=fullstack,component=frontend
```

### Backend not connecting to database

Ensure the database is ready:
```bash
# Check database pod status
kubectl get pods -n fullstack -l app=fullstack,component=database

# Check database service
kubectl get svc -n fullstack postgres

# Test database connection from backend pod
kubectl exec -it -n fullstack -l app=fullstack,component=backend -- \
  python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://todos_user:todos_password@postgres:5432/todos_db'))"
```

### Frontend not connecting to backend

Check backend service:
```bash
# Verify backend service exists
kubectl get svc -n fullstack backend

# Check backend endpoint
kubectl get endpoints -n fullstack backend

# Test backend from frontend pod
kubectl exec -it -n fullstack -l app=fullstack,component=frontend -- \
  wget -qO- http://backend:8000/health
```

### Database initialization issues

Check if the init script ran:
```bash
# Check init pod logs
kubectl logs -n fullstack -l app=fullstack,component=database-init

# Manually run init script
kubectl exec -it -n fullstack -l app=fullstack,component=database -- \
  psql -U todos_user -d todos_db -f /init.sql
```

### Storage issues

Verify persistent volume claims:
```bash
kubectl describe pvc -n fullstack postgres-pvc
```

### Build issues

If Docker builds fail:
```bash
# Check Docker daemon is running
docker ps

# Try building manually
cd examples/fullstack/backend
docker build -t backend-api:latest .

cd ../frontend
docker build -t frontend-app:latest .
```

## Further Reading

- [kubeman Documentation](../../README.md)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Vite Documentation](https://vitejs.dev/)
