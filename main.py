# Run with: uvicorn main:app --reload
"""
main.py
=======
FastAPI Quantum Simulation Service for Egreen-Quanta (SIH Platform).

Endpoints:
  - GET  /health             : Basic uptime and health check
  - POST /circuits/simulate  : Validates, transpiles, and simulates an arbitrary quantum circuit
                               using Qiskit Aer, capturing step-by-step statevectors and shot counts.
"""

from typing import Any, Callable, Dict, List, Optional
import numpy as np
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

# -----------------------------------------------------------------------------
# 1. Extensible Gate Registry
# -----------------------------------------------------------------------------
# Adding a new quantum gate in the future (e.g., S, T, RX, RY, RZ, SWAP) only
# requires adding a single dictionary entry to GATE_REGISTRY below.
GateApplier = Callable[[QuantumCircuit, List[int], Optional[List[float]]], None]
GateFormatter = Callable[[List[int], Optional[List[float]]], str]

GATE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "H": {
        "expected_qubits": 1,
        "requires_distinct": True,
        "apply": lambda qc, targets, params: qc.h(targets[0]),
        "format": lambda targets, params: f"H(q{targets[0]})",
    },
    "X": {
        "expected_qubits": 1,
        "requires_distinct": True,
        "apply": lambda qc, targets, params: qc.x(targets[0]),
        "format": lambda targets, params: f"X(q{targets[0]})",
    },
    "Y": {
        "expected_qubits": 1,
        "requires_distinct": True,
        "apply": lambda qc, targets, params: qc.y(targets[0]),
        "format": lambda targets, params: f"Y(q{targets[0]})",
    },
    "Z": {
        "expected_qubits": 1,
        "requires_distinct": True,
        "apply": lambda qc, targets, params: qc.z(targets[0]),
        "format": lambda targets, params: f"Z(q{targets[0]})",
    },
    "CNOT": {
        "expected_qubits": 2,
        "requires_distinct": True,
        "apply": lambda qc, targets, params: qc.cx(targets[0], targets[1]),
        "format": lambda targets, params: f"CNOT(q{targets[0]},q{targets[1]})",
    },
    # Future gate examples easily activated:
    "S": {
        "expected_qubits": 1,
        "requires_distinct": True,
        "apply": lambda qc, targets, params: qc.s(targets[0]),
        "format": lambda targets, params: f"S(q{targets[0]})",
    },
    "T": {
        "expected_qubits": 1,
        "requires_distinct": True,
        "apply": lambda qc, targets, params: qc.t(targets[0]),
        "format": lambda targets, params: f"T(q{targets[0]})",
    },
    "RX": {
        "expected_qubits": 1,
        "requires_distinct": True,
        "apply": lambda qc, targets, params: qc.rx(params[0] if params else 0.0, targets[0]),
        "format": lambda targets, params: f"RX(q{targets[0]},{(params[0] if params else 0.0):.3f})",
    },
}

# -----------------------------------------------------------------------------
# 2. Pydantic Request & Response Schemas
# -----------------------------------------------------------------------------
class GateRequest(BaseModel):
    type: str = Field(..., description="Gate type identifier, e.g., 'H', 'CNOT', 'X'")
    target_qubits: List[int] = Field(..., description="Target qubit indices (e.g., [0] or [0, 1])")
    params: Optional[List[float]] = Field(None, description="Optional parameter list (e.g. rotation angles)")
    step_index: int = Field(0, description="Execution step order in circuit timeline")


class CircuitSimulateRequest(BaseModel):
    qubit_count: int = Field(..., description="Total number of qubits in the circuit (1-8)")
    gates: List[GateRequest] = Field(default_factory=list, description="List of gates to apply")
    shots: int = Field(1024, description="Number of projective measurement shots (default 1024)")


class ComplexAmplitude(BaseModel):
    real: float
    imag: float


class GateState(BaseModel):
    after_gate: str
    statevector: List[ComplexAmplitude]


class CircuitSimulateResponse(BaseModel):
    qubit_count: int
    gates_applied: List[str]
    per_gate_states: List[GateState]
    final_statevector: List[ComplexAmplitude]
    measurement_counts: Dict[str, int]


# -----------------------------------------------------------------------------
# 3. Serialization Helpers
# -----------------------------------------------------------------------------
def complex_to_dict(val: complex, decimals: int = 6) -> ComplexAmplitude:
    """Converts a complex number to a clean, JSON-serializable schema rounded to 6 decimals."""
    return ComplexAmplitude(
        real=round(float(np.real(val)), decimals),
        imag=round(float(np.imag(val)), decimals),
    )


def serialize_statevector(data) -> List[ComplexAmplitude]:
    """Transforms Qiskit statevector / numpy array into a list of ComplexAmplitude items."""
    return [complex_to_dict(c) for c in np.asarray(data)]


# -----------------------------------------------------------------------------
# 4. FastAPI Application Setup & Middleware
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Egreen-Quanta Simulation Engine",
    description="Quantum Circuit Simulation API with step-by-step statevector tracking.",
    version="1.0.0",
)

# CORS middleware allowing requests from localhost / 127.0.0.1 on any port
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared AerSimulator instance for statevector and shot sampling
simulator = AerSimulator()


# -----------------------------------------------------------------------------
# 5. API Endpoints
# -----------------------------------------------------------------------------
@app.get("/health", tags=["System"])
def health_check():
    """Uptime health check endpoint."""
    return {"status": "ok"}


@app.post(
    "/circuits/simulate",
    response_model=CircuitSimulateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Simulation"],
)
def simulate_circuit(req: CircuitSimulateRequest) -> CircuitSimulateResponse:
    """
    Simulates a generic quantum circuit:
      1. Validates qubit counts, gate types, and qubit indexing.
      2. Synthesizes a Qiskit QuantumCircuit in step_index order.
      3. Captures intermediate statevectors after each gate slice.
      4. Samples measurement counts across requested shots.
    """
    # -------------------------------------------------------------------------
    # Validation Rules
    # -------------------------------------------------------------------------
    # Rule 1: Validate qubit_count (must be 1 to 8)
    if req.qubit_count <= 0 or req.qubit_count > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"qubit_count must be between 1 and 8 (inclusive), got {req.qubit_count}",
        )

    # Rule 2: Validate shots (must be positive, reasonable bounds)
    if req.shots <= 0 or req.shots > 100000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"shots must be between 1 and 100000, got {req.shots}",
        )

    # Sort gates by step_index order to ensure deterministic execution timeline
    sorted_gates = sorted(req.gates, key=lambda g: g.step_index)

    # Validate each gate individually
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

        # Rule 3: Check qubit bounds (reject if target index >= qubit_count or < 0)
        for q in gate.target_qubits:
            if q < 0 or q >= req.qubit_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Gate '{gate.type}' at step_index {gate.step_index} references qubit index {q}, "
                           f"which is out of bounds for qubit_count {req.qubit_count}",
                )

        # Rule 4: Validate CNOT specifically (must have exactly 2 distinct qubits)
        if gate_type == "CNOT":
            if len(gate.target_qubits) != 2 or gate.target_qubits[0] == gate.target_qubits[1]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CNOT gate at step_index {gate.step_index} requires exactly 2 distinct qubits, "
                           f"got {gate.target_qubits}",
                )
        else:
            # Validate target qubit count for other gates
            if len(gate.target_qubits) != expected_qubits:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Gate '{gate.type}' at step_index {gate.step_index} requires exactly "
                           f"{expected_qubits} target qubit(s), got {gate.target_qubits}",
                )

    # -------------------------------------------------------------------------
    # Simulation: Step-by-Step Statevector Extraction
    # -------------------------------------------------------------------------
    gates_applied: List[str] = []
    per_gate_states: List[GateState] = []

    # Build the circuit incrementally or in a single pass with save_statevector labels
    qc_sim = QuantumCircuit(req.qubit_count)
    step_labels: List[str] = []

    for idx, gate in enumerate(sorted_gates):
        gate_type = gate.type.upper()
        entry = GATE_REGISTRY[gate_type]

        # Apply gate to circuit
        entry["apply"](qc_sim, gate.target_qubits, gate.params)

        # Format gate representation string (e.g., 'H(q0)', 'CNOT(q0,q1)')
        formatted_name = entry["format"](gate.target_qubits, gate.params)
        gates_applied.append(formatted_name)

        # Tag statevector snapshot after this gate slice
        label = f"step_{idx}"
        qc_sim.save_statevector(label=label)
        step_labels.append((formatted_name, label))

    # If no gates were provided, capture initial ground state |0...0>
    if not sorted_gates:
        qc_sim.save_statevector(label="step_initial")
        step_labels.append(("INITIAL_STATE", "step_initial"))

    # Execute statevector simulation
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

    # Final statevector is the statevector after the last gate (or initial ground state)
    last_label = step_labels[-1][1]
    final_statevector = serialize_statevector(sim_data[last_label])

    # -------------------------------------------------------------------------
    # Simulation: Shot-Based Measurement Sampling
    # -------------------------------------------------------------------------
    # Construct a clean circuit copy with measurements for projective sampling
    qc_meas = QuantumCircuit(req.qubit_count)
    for gate in sorted_gates:
        gate_type = gate.type.upper()
        GATE_REGISTRY[gate_type]["apply"](qc_meas, gate.target_qubits, gate.params)

    qc_meas.measure_all()
    result_meas = simulator.run(qc_meas, shots=req.shots).result()
    raw_counts = result_meas.get_counts(qc_meas)

    # Format measurement counts: for circuits <= 4 qubits, ensure all 2^N basis keys
    # are populated with default 0s to maintain consistent client visualizer bar displays.
    total_states = 2 ** req.qubit_count
    measurement_counts: Dict[str, int] = {}
    if total_states <= 16:
        for i in range(total_states):
            bitstring = format(i, f"0{req.qubit_count}b")
            measurement_counts[bitstring] = raw_counts.get(bitstring, 0)
    else:
        # For larger circuits (> 4 qubits), return non-zero observed counts
        measurement_counts = raw_counts

    return CircuitSimulateResponse(
        qubit_count=req.qubit_count,
        gates_applied=gates_applied,
        per_gate_states=per_gate_states,
        final_statevector=final_statevector,
        measurement_counts=measurement_counts,
    )
