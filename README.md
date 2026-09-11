# Egreen-Quanta: Quantum Algorithm Learning Platform (SIH)

An interactive, circuit-aware quantum computing learning platform featuring a FastAPI quantum simulation engine, PostgreSQL persistence with async SQLAlchemy and Alembic, and a minimal React client pipeline test.

---

## 1. Quickstart & Setup Instructions

### Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- Node.js 18+ & npm
- PostgreSQL 15+ (Local installation or Docker)

---

### Database Setup (PostgreSQL + Docker / Local)

#### Option A: Run PostgreSQL via Docker Compose
1. **Start the PostgreSQL container in the background:**
   ```bash
   docker compose up -d
   ```
   This provisions a PostgreSQL 15 instance exposed on `localhost:5432` with database `egreen_quanta`, user `postgres`, and password `postgrespassword`.

#### Option B: Local PostgreSQL (Homebrew / System)
1. **Create the database:**
   ```bash
   psql -U postgres -c "CREATE DATABASE egreen_quanta;"
   ```

#### Apply Alembic Migrations
Run the initial migration to create the `users`, `circuits`, `simulation_runs`, and `predictions` tables:
```bash
alembic upgrade head
```

---

### Backend Setup (FastAPI + Qiskit Aer)
1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Start the FastAPI simulation server:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   The backend will be live at `http://localhost:8000`. You can inspect the interactive OpenAPI documentation at `http://localhost:8000/docs`.

4. **Run Backend Test Suites:**
   ```bash
   # Run simulation engine unit & CORS tests
   python3 test_api.py

   # Run end-to-end user, simulation persistence, and prediction comparison workflow test
   python3 test_predictions_workflow.py
   ```

---

### Frontend Setup (Vite + React)
1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```
2. **Install Node dependencies:**
   ```bash
   npm install
   ```
3. **Start the Vite development server:**
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

---

## 2. API Endpoints & Data Model

### Core Endpoints
- `GET /health`: Uptime health check returning `{"status": "ok"}`.
- `POST /users`: Creates a student or instructor user account.
- `POST /circuits/simulate`: Validates circuit AST, simulates via Qiskit Aer, captures step-by-step statevectors, executes shot-based sampling, and persists rows in `circuits` and `simulation_runs` (returning `circuit_id` and `run_id`).
- `POST /predictions`: Submits and locks a student probability prediction distribution for a circuit (`user_id`, `circuit_id`, `predicted_distribution`).
- `GET /predictions/{id}/compare`: Compares the student's prediction side-by-side with the most recent actual simulation run (`{"predicted": {...}, "actual": {...}, "circuit_id": ..., "run_id": ...}`).

### Database Tables (PostgreSQL)
1. **`users`**: User identity, role (`student` / `instructor`), display name, timestamps.
2. **`circuits`**: Dynamic circuit definition with JSONB gate arrays, qubit count (1-8), owner FK.
3. **`simulation_runs`**: **Append-only** execution ledger tracking backend (`aer`), shots counts, pure statevector, and execution duration.
4. **`predictions`**: Pedagogical hypothesis ledger tracking student expectations for comparison against empirical quantum outcomes.
