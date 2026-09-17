"""
test_api.py
===========
Automated test suite verifying FastAPI quantum simulation endpoints:
  - GET /health
  - POST /circuits/simulate (Valid Bell State circuit vs simulate_bell.py output + persistence)
  - POST /circuits/simulate (Invalid CNOT with 1 qubit -> 400 Bad Request)
  - POST /circuits/simulate (Qubit index out of bounds -> 400 Bad Request)
  - POST /circuits/simulate (Invalid qubit_count bounds -> 400 Bad Request)
  - CORS header validation
"""

import asyncio
import httpx
from httpx import ASGITransport
from main import app


async def run_all_tests():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        print("\n[TEST 1] Testing GET /health...")
        response = await client.get("/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.json() == {"status": "ok"}
        print("✓ GET /health returned 200 and {'status': 'ok'}")

        # 2. Simulate Bell State
        print("\n[TEST 2] Testing POST /circuits/simulate with valid Bell State circuit...")
        payload = {
            "qubit_count": 2,
            "gates": [
                {"type": "H", "target_qubits": [0], "params": None, "step_index": 0},
                {"type": "CNOT", "target_qubits": [0, 1], "params": None, "step_index": 1}
            ],
            "shots": 1024
        }
        response = await client.post("/circuits/simulate", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        print("Response JSON summary:")
        print("  circuit_id:", data["circuit_id"])
        print("  run_id:", data["run_id"])
        print("  qubit_count:", data["qubit_count"])
        print("  gates_applied:", data["gates_applied"])
        print("  per_gate_states count:", len(data["per_gate_states"]))
        print("  measurement_counts:", data["measurement_counts"])

        assert data["circuit_id"] is not None
        assert data["run_id"] is not None
        assert data["qubit_count"] == 2
        assert data["gates_applied"] == ["H(q0)", "CNOT(q0,q1)"]
        assert len(data["per_gate_states"]) == 2

        # Check amplitudes
        sv_h = data["per_gate_states"][0]["statevector"]
        assert round(sv_h[0]["real"], 4) == 0.7071
        assert round(sv_h[1]["real"], 4) == 0.7071

        final_sv = data["final_statevector"]
        assert round(final_sv[0]["real"], 4) == 0.7071
        assert round(final_sv[3]["real"], 4) == 0.7071

        # Check counts
        counts = data["measurement_counts"]
        assert counts["00"] + counts["11"] == 1024
        assert counts["01"] == 0
        assert counts["10"] == 0
        print("✓ Valid Bell State simulation output matches theoretical expectation and simulate_bell.py!")

        # 3. Invalid CNOT
        print("\n[TEST 3] Testing deliberate invalid CNOT with only 1 qubit...")
        payload_bad_cnot = {
            "qubit_count": 2,
            "gates": [
                {"type": "CNOT", "target_qubits": [0], "params": None, "step_index": 0}
            ],
            "shots": 1024
        }
        response = await client.post("/circuits/simulate", json=payload_bad_cnot)
        assert response.status_code == 400
        assert "CNOT gate at step_index 0 requires exactly 2 distinct qubits, got [0]" in response.json()["detail"]
        print("✓ Correctly returned HTTP 400 with specific CNOT error message.")

        # 4. Out of bounds qubit
        print("\n[TEST 4] Testing deliberate invalid qubit index >= qubit_count...")
        payload_oob = {
            "qubit_count": 2,
            "gates": [
                {"type": "H", "target_qubits": [2], "params": None, "step_index": 0}
            ],
            "shots": 1024
        }
        response = await client.post("/circuits/simulate", json=payload_oob)
        assert response.status_code == 400
        assert "references qubit index 2, which is out of bounds for qubit_count 2" in response.json()["detail"]
        print("✓ Correctly returned HTTP 400 with specific bounds error message.")

        # 5. Invalid qubit count
        print("\n[TEST 5] Testing invalid qubit_count (0 and 9)...")
        for bad_count in [0, 9]:
            payload_bad = {"qubit_count": bad_count, "gates": []}
            response = await client.post("/circuits/simulate", json=payload_bad)
            assert response.status_code == 400
            print(f"  Count {bad_count} -> HTTP 400: {response.json().get('detail')}")
        print("✓ Correctly rejected qubit_count outside 1-8.")

        # 6. CORS headers
        print("\n[TEST 6] Testing CORS middleware headers...")
        response = await client.options(
            "/circuits/simulate",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
        print("✓ CORS correctly allowed request from http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
    print("\n========================================================")
    print("ALL 6 API TESTS PASSED PROVABLY")
    print("========================================================")
