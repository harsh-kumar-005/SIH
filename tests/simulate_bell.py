#!/usr/bin/env python3
"""
simulate_bell.py
================
Self-contained script to build, simulate, and inspect a 2-qubit Bell State circuit
using Qiskit and Qiskit Aer.

Quantum Circuit Description:
  - 2 Qubits initialized to ground state |00>
  - Gate 1: Hadamard (H) on Qubit 0 -> creates equal superposition (|0> + |1>)/sqrt(2)
  - Gate 2: Controlled-NOT (CNOT / CX) with Q0 as control and Q1 as target -> entangles Q0 and Q1
  - Final Theoretical State: Bell State |Phi+> = (|00> + |11>) / sqrt(2)

Simulations:
  1. Ideal Statevector Simulation: Exact complex amplitudes with zero shot noise.
  2. Step-by-Step Gate Statevector Extraction: Amplitudes after H(q0), then after CNOT(q0, q1).
  3. QASM Shot-based Measurement: 1024 shots sampling projective measurements in computational basis.

Note on Qiskit Qubit Ordering (Little-Endian):
  Qiskit represents multi-qubit basis states as |q_{n-1} ... q_1 q_0>.
  - Basis index 0 -> |00> (q1=0, q0=0)
  - Basis index 1 -> |01> (q1=0, q0=1)
  - Basis index 2 -> |10> (q1=1, q0=0)
  - Basis index 3 -> |11> (q1=1, q0=1)
"""

import json
import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator


def complex_to_dict(val: complex, decimals: int = 6) -> dict:
    """
    Serializes a complex number into a JSON-compliant dict with real and imaginary parts.
    Rounds to clean precision to avoid IEEE 754 floating point noise (e.g. 1e-16).
    """
    real = float(np.real(val))
    imag = float(np.imag(val))
    return {
        "real": round(real, decimals),
        "imag": round(imag, decimals)
    }


def serialize_statevector(statevector_data) -> list:
    """Converts a Qiskit statevector or numpy array of complex numbers to JSON format."""
    return [complex_to_dict(c) for c in np.asarray(statevector_data)]


def main():
    # -------------------------------------------------------------------------
    # 1. Initialize Simulator
    # -------------------------------------------------------------------------
    # AerSimulator supports both statevector methods (ideal math) and shot simulation
    aer_sim = AerSimulator()

    gates_applied = ["H(q0)", "CNOT(q0,q1)"]
    per_gate_states = []

    # -------------------------------------------------------------------------
    # 2. Step 1: Apply H(q0) and capture intermediate statevector
    # -------------------------------------------------------------------------
    qc_step1 = QuantumCircuit(2)
    # Apply Hadamard on qubit 0
    qc_step1.h(0)

    # Instruct Aer to save the exact mathematical statevector
    qc_step1_sim = qc_step1.copy()
    qc_step1_sim.save_statevector()
    result_step1 = aer_sim.run(qc_step1_sim).result()
    sv_step1 = result_step1.get_statevector(qc_step1_sim)

    per_gate_states.append({
        "after_gate": "H(q0)",
        "statevector": serialize_statevector(sv_step1)
    })

    # -------------------------------------------------------------------------
    # 3. Step 2: Apply CNOT(control=q0, target=q1) and capture statevector
    # -------------------------------------------------------------------------
    # Build complete Bell State circuit: H on q0, then CX from q0 to q1
    bell_circuit = QuantumCircuit(2)
    bell_circuit.h(0)
    bell_circuit.cx(0, 1)

    # Extract exact final statevector after both gates
    bell_circuit_sv = bell_circuit.copy()
    bell_circuit_sv.save_statevector()
    result_final_sv = aer_sim.run(bell_circuit_sv).result()
    final_sv = result_final_sv.get_statevector(bell_circuit_sv)

    per_gate_states.append({
        "after_gate": "CNOT(q0,q1)",
        "statevector": serialize_statevector(final_sv)
    })

    # -------------------------------------------------------------------------
    # 4. Shot-based Measurement Simulation (1024 shots)
    # -------------------------------------------------------------------------
    # Measure both qubits into classical register bits
    bell_meas = bell_circuit.copy()
    bell_meas.measure_all()

    shots = 1024
    result_meas = aer_sim.run(bell_meas, shots=shots).result()
    raw_counts = result_meas.get_counts(bell_meas)

    # Standardize all 2-qubit basis outcomes ("00", "01", "10", "11") with zero defaults
    measurement_counts = {
        "00": raw_counts.get("00", 0),
        "11": raw_counts.get("11", 0),
        "01": raw_counts.get("01", 0),
        "10": raw_counts.get("10", 0),
    }

    # -------------------------------------------------------------------------
    # 5. Output JSON Assembly
    # -------------------------------------------------------------------------
    output_data = {
        "gates_applied": gates_applied,
        "per_gate_states": per_gate_states,
        "final_statevector": serialize_statevector(final_sv),
        "measurement_counts": measurement_counts
    }

    # Print formatted JSON to stdout
    print(json.dumps(output_data, indent=2))


if __name__ == "__main__":
    main()
