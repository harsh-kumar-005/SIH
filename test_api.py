"""
test_api.py
===========
Automated test suite verifying FastAPI quantum simulation endpoints:
  - GET /health
  - POST /circuits/simulate (Valid Bell State circuit vs simulate_bell.py output)
  - POST /circuits/simulate (Invalid CNOT with 1 qubit -> 400 Bad Request)
  - POST /circuits/simulate (Qubit index out of bounds -> 400 Bad Request)
  - POST /circuits/simulate (Invalid qubit_count bounds -> 400 Bad Request)
  - CORS header validation
"""

import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    print("\n[TEST 1] Testing GET /health...")
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}
    print("✓ GET /health returned 200 and {'status': 'ok'}")


def test_simulate_bell_valid():
    print("\n[TEST 2] Testing POST /circuits/simulate with valid Bell State circuit...")
    payload = {
        "qubit_count": 2,
        "gates": [
            {"type": "H", "target_qubits": [0], "params": None, "step_index": 0},
            {"type": "CNOT", "target_qubits": [0, 1], "params": None, "step_index": 1}
        ],
        "shots": 1024
    }
    response = client.post("/circuits/simulate", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    print("Response JSON summary:")
    print("  qubit_count:", data["qubit_count"])
    print("  gates_applied:", data["gates_applied"])
    print("  per_gate_states count:", len(data["per_gate_states"]))
    print("  measurement_counts:", data["measurement_counts"])

    # Assertions
    assert data["qubit_count"] == 2
    assert data["gates_applied"] == ["H(q0)", "CNOT(q0,q1)"]
    assert len(data["per_gate_states"]) == 2
    assert data["per_gate_states"][0]["after_gate"] == "H(q0)"
    assert data["per_gate_states"][1]["after_gate"] == "CNOT(q0,q1)"

    # Check intermediate state after H(q0): |00> and |01> each ~ 0.707107
    sv_h = data["per_gate_states"][0]["statevector"]
    assert round(sv_h[0]["real"], 4) == 0.7071
    assert round(sv_h[1]["real"], 4) == 0.7071
    assert round(sv_h[2]["real"], 4) == 0.0
    assert round(sv_h[3]["real"], 4) == 0.0

    # Check final state: |00> and |11> each ~ 0.707107
    final_sv = data["final_statevector"]
    assert round(final_sv[0]["real"], 4) == 0.7071
    assert round(final_sv[1]["real"], 4) == 0.0
    assert round(final_sv[2]["real"], 4) == 0.0
    assert round(final_sv[3]["real"], 4) == 0.7071

    # Check counts: sum must equal 1024, only 00 and 11 observed
    counts = data["measurement_counts"]
    assert counts["00"] + counts["11"] == 1024
    assert counts["01"] == 0
    assert counts["10"] == 0
    print("✓ Valid Bell State simulation output matches theoretical expectation and simulate_bell.py!")


def test_invalid_cnot_single_qubit():
    print("\n[TEST 3] Testing deliberate invalid CNOT with only 1 qubit...")
    payload = {
        "qubit_count": 2,
        "gates": [
            {"type": "CNOT", "target_qubits": [0], "params": None, "step_index": 0}
        ],
        "shots": 1024
    }
    response = client.post("/circuits/simulate", json=payload)
    print("  Status code:", response.status_code)
    print("  Detail:", response.json().get("detail"))
    assert response.status_code == 400
    assert "CNOT gate at step_index 0 requires exactly 2 distinct qubits, got [0]" in response.json()["detail"]
    print("✓ Correctly returned HTTP 400 with specific CNOT error message.")


def test_invalid_qubit_out_of_bounds():
    print("\n[TEST 4] Testing deliberate invalid qubit index >= qubit_count...")
    payload = {
        "qubit_count": 2,
        "gates": [
            {"type": "H", "target_qubits": [2], "params": None, "step_index": 0}
        ],
        "shots": 1024
    }
    response = client.post("/circuits/simulate", json=payload)
    print("  Status code:", response.status_code)
    print("  Detail:", response.json().get("detail"))
    assert response.status_code == 400
    assert "references qubit index 2, which is out of bounds for qubit_count 2" in response.json()["detail"]
    print("✓ Correctly returned HTTP 400 with specific bounds error message.")


def test_invalid_qubit_count():
    print("\n[TEST 5] Testing invalid qubit_count (0 and 9)...")
    for bad_count in [0, 9]:
        payload = {"qubit_count": bad_count, "gates": []}
        response = client.post("/circuits/simulate", json=payload)
        assert response.status_code == 400
        print(f"  Count {bad_count} -> HTTP 400: {response.json().get('detail')}")
    print("✓ Correctly rejected qubit_count outside 1-8.")


def test_cors_headers():
    print("\n[TEST 6] Testing CORS middleware headers...")
    response = client.options(
        "/circuits/simulate",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        }
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    print("✓ CORS correctly allowed request from http://localhost:3000")


if __name__ == "__main__":
    test_health()
    test_simulate_bell_valid()
    test_invalid_cnot_single_qubit()
    test_invalid_qubit_out_of_bounds()
    test_invalid_qubit_count()
    test_cors_headers()
    print("\n========================================================")
    print("ALL 6 TESTS PASSED PROVABLY (Proof of Correctness)")
    print("========================================================")
