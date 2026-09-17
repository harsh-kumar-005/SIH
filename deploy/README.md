# Egreen-Quanta Cloud Deployment Guide

This guide details how to deploy Egreen-Quanta to containerized staging and production environments in accordance with the Smart India Hackathon (SIH) Cloud Deployment requirements.

---

## 1. System Architecture Overview

Egreen-Quanta is architected as a modular 3-tier containerized stack:

```
                      ┌─────────────────────────────────────────┐
                      │            Browser Clients              │
                      └────────────────────┬────────────────────┘
                                           │ HTTP / Port 3000 (or 80/443)
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │         Frontend Web Tier               │
                      │  - Nginx 1.25 Alpine reverse proxy     │
                      │  - React 19 SPA (Vite compiled)         │
                      │  - Gzip compression & security headers  │
                      └────────────────────┬────────────────────┘
                                           │ HTTP / Port 8000
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │         Backend API Tier                │
                      │  - Python 3.12 Slim (FastAPI)           │
                      │  - Qiskit Aer Statevector & Noise Engine│
                      │  - Google Gemini AI Socratic Tutor      │
                      │  - JWT Auth & Misconception Classifier  │
                      └────────────────────┬────────────────────┘
                                           │ PostgreSQL Async Protocol / Port 5432
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │         Database Persistence Tier       │
                      │  - PostgreSQL 15 Alpine                 │
                      │  - Alembic auto-migrations              │
                      │  - Append-only simulation audit ledger  │
                      └─────────────────────────────────────────┘
```

---

## 2. Quickstart: Turnkey Docker Compose Deployment

### Prerequisites
- Docker Engine 24.0+ & Docker Compose v2.20+
- A Google AI Studio API Key ([makersuite.google.com](https://makersuite.google.com/))

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/harsh-kumar-005/SIH.git egreen-quanta
cd egreen-quanta

# Copy environment template
cp .env.example .env

# Edit .env and paste your GEMINI_API_KEY and a secure JWT_SECRET_KEY:
nano .env
```

### Step 2: Build and Launch Stack
```bash
# Build images and start all three containers in the background:
docker compose up --build -d
```

### Step 3: Verify Deployment
Check the status and healthchecks of the services:
```bash
docker compose ps
```
Output should show all services `healthy`:
```
NAME                    IMAGE                   COMMAND                  SERVICE    STATUS
egreen_quanta_postgres  postgres:15-alpine      "docker-entrypoint.s…"   postgres   Up (healthy)
egreen_quanta_backend   egreen-quanta-backend   "/app/docker-entrypo…"   backend    Up (healthy)
egreen_quanta_frontend  egreen-quanta-frontend  "/docker-entrypoint.…"   frontend   Up (healthy)
```

Access the applications:
- **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- **Backend API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **System Healthcheck**: [http://localhost:8000/health](http://localhost:8000/health)

### Step 4: Stop / Teardown
```bash
docker compose down
# To also delete the persistent database volume:
docker compose down -v
```

---

## 3. Production Cloud Deployments

### Option A: Google Cloud Platform (GCP Cloud Run + Cloud SQL)
Best for auto-scaling serverless deployments with native Google infrastructure:

1. **Database**:
   - Provision a **Cloud SQL for PostgreSQL 15** instance.
   - Configure private IP VPC connector or Cloud SQL Auth Proxy.

2. **Backend**:
   - Build backend container:
     ```bash
     gcloud builds submit --tag gcr.io/[PROJECT_ID]/egreen-quanta-backend .
     ```
   - Deploy to Cloud Run:
     ```bash
     gcloud run deploy egreen-quanta-backend \
       --image gcr.io/[PROJECT_ID]/egreen-quanta-backend \
       --platform managed \
       --region us-central1 \
       --set-env-vars DATABASE_URL="postgresql+asyncpg://[USER]:[PASS]@[CLOUD_SQL_IP]:5432/egreen_quanta" \
       --set-env-vars GEMINI_API_KEY="[YOUR_KEY]" \
       --set-env-vars JWT_SECRET_KEY="[SECURE_SECRET]" \
       --allow-unauthenticated
     ```

3. **Frontend**:
   - Build frontend pointing to Cloud Run backend URL:
     ```bash
     gcloud builds submit \
       --substitutions=_VITE_API_URL="https://egreen-quanta-backend-[ID].a.run.app" \
       --tag gcr.io/[PROJECT_ID]/egreen-quanta-frontend ./frontend
     ```
   - Deploy frontend to Cloud Run or Firebase Hosting.

---

### Option B: AWS (ECS Fargate + RDS PostgreSQL)
Enterprise cloud deployment with dedicated container sizing:

1. **Amazon RDS**:
   - Create PostgreSQL 15 db.t4g.micro instance in your VPC.

2. **Amazon ECR & ECS**:
   - Push backend and frontend images to AWS ECR.
   - Create an ECS Task Definition with two containers:
     - `backend` (0.5 vCPU, 1 GB RAM): configured with RDS credentials and Gemini API Key stored in AWS Secrets Manager.
     - `frontend` (0.25 vCPU, 0.5 GB RAM).
   - Configure Application Load Balancer (ALB) routing:
     - Route `/circuits/*`, `/predictions/*`, `/auth/*`, `/tutor/*`, `/health` to backend target group.
     - Route default `/*` to frontend target group.

---

### Option C: PaaS (Railway / Render)
Fastest one-click deployment for hackathons and demos:

1. Create a **PostgreSQL** service on Railway/Render.
2. Create a **Web Service** from root repository:
   - Root Directory: `.`
   - Dockerfile: `Dockerfile`
   - Set environment variables: `DATABASE_URL` (using `asyncpg` scheme), `GEMINI_API_KEY`, `JWT_SECRET_KEY`.
3. Create a second **Web Service** for frontend:
   - Root Directory: `frontend`
   - Dockerfile: `Dockerfile`
   - Set build argument: `VITE_API_URL` to backend service URL.

---

## 4. Environment Variables Reference

| Variable | Required | Default / Example | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://postgres:postgrespassword@localhost:5432/egreen_quanta` | Async PostgreSQL database connection string |
| `POSTGRES_USER` | Docker only | `postgres` | PostgreSQL root user |
| `POSTGRES_PASSWORD` | Docker only | `postgrespassword` | PostgreSQL password |
| `POSTGRES_DB` | Docker only | `egreen_quanta` | Database name |
| `JWT_SECRET_KEY` | Yes (Prod) | `egreen-quanta-jwt-secret-key-2026-prod` | Secret key for signing HS256 auth tokens |
| `GEMINI_API_KEY` | Yes | *(your key)* | Google AI Studio key for AI Tutor and Misconception Classifier |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | LLM model for Socratic dialogues |
| `CORS_ORIGINS` | No | `*` | Allowed CORS origins (comma-separated for production) |
| `VITE_API_URL` | Frontend | `http://localhost:8000` | Backend API base address |

---

## 5. Automated Database Migrations & Healthchecks

- **Auto-Migrate**: The backend entrypoint (`docker-entrypoint.sh`) runs `alembic upgrade head` before booting the server, ensuring zero-touch schema sync on container start.
- **Liveness & Readiness**:
  - `GET /health` returns `{"status": "ok"}` with HTTP 200.
  - Docker Compose uses `pg_isready` for Postgres and `curl -f http://localhost:8000/health` for the backend before starting downstream tiers.
