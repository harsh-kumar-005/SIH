# Egreen-Quanta: Quantum Algorithm Learning Platform (SIH)

An interactive, circuit-aware quantum computing learning platform featuring a FastAPI quantum simulation engine and a minimal React client pipeline test.

---

## 1. Quickstart & Setup Instructions

### Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- Node.js 18+ & npm

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

4. **Run Backend Automated Test Suite:**
   ```bash
   python3 test_api.py
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

## 2. Pipeline Verification & Endpoints

### Endpoints
- `GET /health`: Uptime health check returning `{"status": "ok"}`.
- `POST /circuits/simulate`: Validates circuit AST, captures step-by-step statevectors after each gate slice via Qiskit Aer, and returns shot-based measurement counts.

### Frontend Buttons
- **Run Circuit**: Dispatches a 2-qubit Bell State circuit (`H(q0)`, `CNOT(q0, q1)`) to `http://localhost:8000/circuits/simulate` and displays the raw JSON output (`qubit_count`, `gates_applied`, `per_gate_states`, `final_statevector`, `measurement_counts`).
- **Run Invalid Circuit**: Dispatches an invalid circuit (CNOT with only 1 target qubit) to verify that the backend's HTTP 400 error message is caught and rendered in red in the UI.
