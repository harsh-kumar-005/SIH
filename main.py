# Run with: uvicorn main:app --reload
"""
main.py
=======
FastAPI Quantum Simulation & Prediction Service for Egreen-Quanta.

Endpoints:
  - GET  /health                     : Basic uptime and health check
  - POST /users                      : Create a user (convenience for tests & onboarding)
  - POST /circuits/simulate          : Simulates a circuit, persists circuits & simulation_runs records
  - POST /predictions                : Submits a student circuit outcome prediction
  - GET  /predictions/{id}/compare   : Compares student prediction with actual simulation results
"""

import time
import uuid
from typing import Any, Callable, Dict, List, Optional
import numpy as np
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from db.database import get_db
from db.models import User, Circuit, SimulationRun, Prediction

# -----------------------------------------------------------------------------
# 1. Extensible Gate Registry
# -----------------------------------------------------------------------------
GateApplier = Callable[[QuantumCircuit, List[int], Optional[List[float]]], None]
GateFormatter = Callable[[List[int], Optional[List[float]]], str]

GATE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "H": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.h(targets[0]),
        "format": lambda targets, params: f"H(q{targets[0]})",
    },
    "X": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.x(targets[0]),
        "format": lambda targets, params: f"X(q{targets[0]})",
    },
    "Y": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.y(targets[0]),
        "format": lambda targets, params: f"Y(q{targets[0]})",
    },
    "Z": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.z(targets[0]),
        "format": lambda targets, params: f"Z(q{targets[0]})",
    },
    "CNOT": {
        "expected_qubits": 2,
        "apply": lambda qc, targets, params: qc.cx(targets[0], targets[1]),
        "format": lambda targets, params: f"CNOT(q{targets[0]},q{targets[1]})",
    },
    "S": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.s(targets[0]),
        "format": lambda targets, params: f"S(q{targets[0]})",
    },
    "T": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.t(targets[0]),
        "format": lambda targets, params: f"T(q{targets[0]})",
    },
    "RX": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.rx(params[0] if params else 0.0, targets[0]),
        "format": lambda targets, params: f"RX(q{targets[0]},{(params[0] if params else 0.0):.3f})",
    },
}

# -----------------------------------------------------------------------------
# 2. Pydantic Request & Response Schemas
# -----------------------------------------------------------------------------
class GateRequest(BaseModel):
    type: str = Field(..., description="Gate type identifier, e.g., 'H', 'CNOT', 'X'")
    target_qubits: List[int] = Field(..., description="Target qubit indices")
    params: Optional[List[float]] = Field(None, description="Optional rotation parameters")
    step_index: int = Field(0, description="Execution step order in circuit timeline")


class CircuitSimulateRequest(BaseModel):
    qubit_count: int = Field(..., description="Total number of qubits (1-8)")
    gates: List[GateRequest] = Field(default_factory=list, description="List of gates")
    shots: int = Field(1024, description="Measurement shots")
    circuit_id: Optional[uuid.UUID] = Field(None, description="Optional existing circuit ID")
    owner_id: Optional[uuid.UUID] = Field(None, description="Optional owner user ID")


class ComplexAmplitude(BaseModel):
    real: float
    imag: float


class GateState(BaseModel):
    after_gate: str
    statevector: List[ComplexAmplitude]


class CircuitSimulateResponse(BaseModel):
    circuit_id: uuid.UUID
    run_id: uuid.UUID
    qubit_count: int
    gates_applied: List[str]
    per_gate_states: List[GateState]
    final_statevector: List[ComplexAmplitude]
    measurement_counts: Dict[str, int]


class UserCreateRequest(BaseModel):
    email: str
    password_hash: str = "hashed_pw_default"
    role: str = "student"
    display_name: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    display_name: str


class PredictionCreateRequest(BaseModel):
    user_id: uuid.UUID
    circuit_id: uuid.UUID
    predicted_distribution: Dict[str, float]


class PredictionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    circuit_id: uuid.UUID
    predicted_distribution: Dict[str, float]
    actual_run_id: Optional[uuid.UUID] = None


class CompareResponse(BaseModel):
    predicted: Dict[str, float]
    actual: Dict[str, float]
    circuit_id: uuid.UUID
    run_id: uuid.UUID


class CircuitCreateRequest(BaseModel):
    qubit_count: int = Field(..., description="Total number of qubits (1-8)")
    gates: List[GateRequest] = Field(default_factory=list, description="List of gates")
    code_form: Optional[str] = Field(None, description="Optional OpenQASM or Python representation")
    owner_id: Optional[uuid.UUID] = Field(None, description="Optional owner user ID")


class CircuitResponse(BaseModel):
    id: uuid.UUID
    qubit_count: int
    gates: List[Dict[str, Any]]
    owner_id: Optional[uuid.UUID] = None



# -----------------------------------------------------------------------------
# 3. Serialization Helpers
# -----------------------------------------------------------------------------
def complex_to_dict(val: complex, decimals: int = 6) -> ComplexAmplitude:
    return ComplexAmplitude(
        real=round(float(np.real(val)), decimals),
        imag=round(float(np.imag(val)), decimals),
    )


def serialize_statevector(data) -> List[ComplexAmplitude]:
    return [complex_to_dict(c) for c in np.asarray(data)]


# -----------------------------------------------------------------------------
# 4. FastAPI Setup & Middleware
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Egreen-Quanta Simulation & Prediction API",
    description="Full-stack quantum simulation engine with PostgreSQL persistence.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

simulator = AerSimulator()


# -----------------------------------------------------------------------------
# 5. Endpoints
# -----------------------------------------------------------------------------
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Users"])
async def create_user(req: UserCreateRequest, db: AsyncSession = Depends(get_db)):
    """Creates a user record in PostgreSQL."""
    if req.role not in ("student", "instructor"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'student' or 'instructor'"
        )

    # Check for existing email
    stmt = select(User).where(User.email == req.email)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return UserResponse(
            id=existing.id,
            email=existing.email,
            role=existing.role,
            display_name=existing.display_name
        )

    new_user = User(
        email=req.email,
        password_hash=req.password_hash,
        role=req.role,
        display_name=req.display_name
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        display_name=new_user.display_name
    )


@app.post(
    "/circuits",
    response_model=CircuitResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Circuits"]
)
async def create_circuit(
    req: CircuitCreateRequest,
    db: AsyncSession = Depends(get_db)
) -> CircuitResponse:
    """Creates and persists a quantum circuit definition without running a simulation."""
    if req.qubit_count <= 0 or req.qubit_count > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"qubit_count must be between 1 and 8 (inclusive), got {req.qubit_count}",
        )

    sorted_gates = sorted(req.gates, key=lambda g: g.step_index)
    circuit = Circuit(
        id=uuid.uuid4(),
        owner_id=req.owner_id,
        qubit_count=req.qubit_count,
        gates=[g.model_dump() for g in sorted_gates],
        code_form=req.code_form,
    )
    db.add(circuit)
    await db.commit()
    await db.refresh(circuit)

    return CircuitResponse(
        id=circuit.id,
        qubit_count=circuit.qubit_count,
        gates=circuit.gates,
        owner_id=circuit.owner_id,
    )


@app.post(

    "/circuits/simulate",
    response_model=CircuitSimulateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Simulation"]
)
async def simulate_circuit(
    req: CircuitSimulateRequest,
    db: AsyncSession = Depends(get_db)
) -> CircuitSimulateResponse:
    """
    Simulates a quantum circuit, persists the circuit (if new) and append-only simulation run.
    Returns the simulation results alongside circuit_id and run_id.
    """
    start_time = time.perf_counter()

    # 1. Validation
    if req.qubit_count <= 0 or req.qubit_count > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"qubit_count must be between 1 and 8 (inclusive), got {req.qubit_count}",
        )

    if req.shots <= 0 or req.shots > 100000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"shots must be between 1 and 100000, got {req.shots}",
        )

    sorted_gates = sorted(req.gates, key=lambda g: g.step_index)

    for gate in sorted_gates:
        gate_type = gate.type.upper()
        if gate_type not in GATE_REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported gate type '{gate.type}' at step_index {gate.step_index}. "
                       f"Supported gates: {sorted(list(GATE_REGISTRY.keys()))}",
            )

        registry_entry = GATE_REGISTRY[gate_type]
        expected_qubits = registry_entry["expected_qubits"]

        for q in gate.target_qubits:
            if q < 0 or q >= req.qubit_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Gate '{gate.type}' at step_index {gate.step_index} references qubit index {q}, "
                           f"which is out of bounds for qubit_count {req.qubit_count}",
                )

        if gate_type == "CNOT":
            if len(gate.target_qubits) != 2 or gate.target_qubits[0] == gate.target_qubits[1]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CNOT gate at step_index {gate.step_index} requires exactly 2 distinct qubits, "
                           f"got {gate.target_qubits}",
                )
        else:
            if len(gate.target_qubits) != expected_qubits:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Gate '{gate.type}' at step_index {gate.step_index} requires exactly "
                           f"{expected_qubits} target qubit(s), got {gate.target_qubits}",
                )

    # 2. Simulation Execution
    gates_applied: List[str] = []
    per_gate_states: List[GateState] = []
    qc_sim = QuantumCircuit(req.qubit_count)
    step_labels: List[str] = []

    for idx, gate in enumerate(sorted_gates):
        gate_type = gate.type.upper()
        entry = GATE_REGISTRY[gate_type]
        entry["apply"](qc_sim, gate.target_qubits, gate.params)

        formatted_name = entry["format"](gate.target_qubits, gate.params)
        gates_applied.append(formatted_name)

        label = f"step_{idx}"
        qc_sim.save_statevector(label=label)
        step_labels.append((formatted_name, label))

    if not sorted_gates:
        qc_sim.save_statevector(label="step_initial")
        step_labels.append(("INITIAL_STATE", "step_initial"))

    result_sv = simulator.run(qc_sim).result()
    sim_data = result_sv.data()

    for formatted_name, label in step_labels:
        sv_array = sim_data[label]
        per_gate_states.append(
            GateState(
                after_gate=formatted_name,
                statevector=serialize_statevector(sv_array),
            )
        )

    last_label = step_labels[-1][1]
    final_statevector = serialize_statevector(sim_data[last_label])

    # Measurement pass
    qc_meas = QuantumCircuit(req.qubit_count)
    for gate in sorted_gates:
        gate_type = gate.type.upper()
        GATE_REGISTRY[gate_type]["apply"](qc_meas, gate.target_qubits, gate.params)

    qc_meas.measure_all()
    result_meas = simulator.run(qc_meas, shots=req.shots).result()
    raw_counts = result_meas.get_counts(qc_meas)

    total_states = 2 ** req.qubit_count
    measurement_counts: Dict[str, int] = {}
    if total_states <= 16:
        for i in range(total_states):
            bitstring = format(i, f"0{req.qubit_count}b")
            measurement_counts[bitstring] = raw_counts.get(bitstring, 0)
    else:
        measurement_counts = raw_counts

    duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))

    # 3. Database Persistence
    circuit: Optional[Circuit] = None
    if req.circuit_id:
        stmt = select(Circuit).where(Circuit.id == req.circuit_id)
        circuit = (await db.execute(stmt)).scalar_one_or_none()

    if not circuit:
        circuit = Circuit(
            id=req.circuit_id or uuid.uuid4(),
            owner_id=req.owner_id,
            qubit_count=req.qubit_count,
            gates=[g.model_dump() for g in sorted_gates],
            code_form=None,
        )
        db.add(circuit)
        await db.flush()

    run = SimulationRun(
        id=uuid.uuid4(),
        circuit_id=circuit.id,
        backend="aer",
        noise_level=0.0,
        counts=measurement_counts,
        statevector=[amp.model_dump() for amp in final_statevector],
        per_gate_states=[s.model_dump() for s in per_gate_states],
        duration_ms=duration_ms,
    )
    db.add(run)
    await db.commit()
    await db.refresh(circuit)
    await db.refresh(run)

    return CircuitSimulateResponse(
        circuit_id=circuit.id,
        run_id=run.id,
        qubit_count=req.qubit_count,
        gates_applied=gates_applied,
        per_gate_states=per_gate_states,
        final_statevector=final_statevector,
        measurement_counts=measurement_counts,
    )


@app.post(
    "/predictions",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Pedagogy & Predictions"]
)
async def create_prediction(
    req: PredictionCreateRequest,
    db: AsyncSession = Depends(get_db)
) -> PredictionResponse:
    """Submits and locks in a student outcome prediction for a circuit."""
    # Verify user exists
    user_stmt = select(User).where(User.id == req.user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {req.user_id} does not exist",
        )

    # Verify circuit exists
    circuit_stmt = select(Circuit).where(Circuit.id == req.circuit_id)
    circuit = (await db.execute(circuit_stmt)).scalar_one_or_none()
    if not circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit with id {req.circuit_id} does not exist",
        )

    # Find most recent simulation run if already executed
    run_stmt = (
        select(SimulationRun)
        .where(SimulationRun.circuit_id == req.circuit_id)
        .order_by(SimulationRun.created_at.desc())
        .limit(1)
    )
    latest_run = (await db.execute(run_stmt)).scalar_one_or_none()

    prediction = Prediction(
        id=uuid.uuid4(),
        user_id=req.user_id,
        circuit_id=req.circuit_id,
        predicted_distribution=req.predicted_distribution,
        actual_run_id=latest_run.id if latest_run else None,
    )
    db.add(prediction)
    await db.commit()
    await db.refresh(prediction)

    return PredictionResponse(
        id=prediction.id,
        user_id=prediction.user_id,
        circuit_id=prediction.circuit_id,
        predicted_distribution=prediction.predicted_distribution,
        actual_run_id=prediction.actual_run_id,
    )


@app.get(
    "/predictions/{prediction_id}/compare",
    response_model=CompareResponse,
    status_code=status.HTTP_200_OK,
    tags=["Pedagogy & Predictions"]
)
async def compare_prediction(
    prediction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> CompareResponse:
    """Fetches a prediction and compares it side-by-side with the most recent actual simulation run."""
    pred_stmt = select(Prediction).where(Prediction.id == prediction_id)
    prediction = (await db.execute(pred_stmt)).scalar_one_or_none()
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction with id {prediction_id} not found",
        )

    run_stmt = (
        select(SimulationRun)
        .where(SimulationRun.circuit_id == prediction.circuit_id)
        .order_by(SimulationRun.created_at.desc())
        .limit(1)
    )
    latest_run = (await db.execute(run_stmt)).scalar_one_or_none()
    if not latest_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No simulation run exists yet for circuit {prediction.circuit_id}",
        )

    # If prediction wasn't linked to a run yet, link it now
    if not prediction.actual_run_id:
        prediction.actual_run_id = latest_run.id
        await db.commit()

    # Normalize raw measurement counts to probability distribution (0-1 scale)
    raw_counts: Dict[str, int] = latest_run.counts or {}
    total_shots = sum(raw_counts.values())
    if total_shots > 0:
        normalized_actual = {
            k: round(v / total_shots, 3) for k, v in raw_counts.items()
        }
    else:
        normalized_actual = {k: 0.0 for k in raw_counts.keys()}

    return CompareResponse(
        predicted=prediction.predicted_distribution,
        actual=normalized_actual,
        circuit_id=prediction.circuit_id,
        run_id=latest_run.id,
    )

