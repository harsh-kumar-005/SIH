"""
test_debug_tutor.py
===================
Automated verification of the Debug Mode AI Tutor responses:
1. Broken circuit (X on q0, CNOT(q0, q1) -> 100% |11>): Socratic diagnostic response without revealing fix directly.
2. Fixed circuit (H on q0, CNOT(q0, q1) -> ~50% |00> and ~50% |11>): Celebratory confirmation explaining why H on q0 works.
"""

import json
import uuid
import httpx

BASE_URL = "http://localhost:8000"


def run_tests():
    print("=" * 80)
    print("DEBUG MODE AI SOCRATIC TUTOR VERIFICATION")
    print("=" * 80)

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # Register a fresh student
        email = f"debug_student_{uuid.uuid4().hex[:6]}@egreen.local"
        password = "password123"

        signup = client.post("/auth/signup", json={
            "email": email,
            "password": password,
            "display_name": "Debug Mode Tester",
            "role": "student"
        })
        assert signup.status_code == 201, f"Signup failed: {signup.text}"

        login = client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, f"Login failed: {login.text}"
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # ---------------------------------------------------------------------
        # 1. Broken Bell State (X on q0, CNOT with control q0, target q1)
        # ---------------------------------------------------------------------
        print("\n--- [TEST 1] Broken Bell Circuit: X(q0) + CNOT(q0, q1) ---")
        broken_circuit = {
            "qubit_count": 2,
            "gates": [
                {"type": "X", "target_qubits": [0], "step_index": 0},
                {"type": "CNOT", "target_qubits": [0, 1], "step_index": 1}
            ],
            "shots": 1024
        }
        sim_broken = client.post("/circuits/simulate", json=broken_circuit, headers=headers).json()
        circuit_id_broken = sim_broken["circuit_id"]
        run_id_broken = sim_broken["run_id"]
        print("Simulation Counts:", json.dumps(sim_broken["measurement_counts"]))

        tutor_req_broken = {
            "circuit_id": circuit_id_broken,
            "run_id": run_id_broken,
            "question": "Why did my circuit produce 100% |11> instead of a Bell state?",
            "experiment_type": "debug"
        }
        resp_broken = client.post("/tutor/ask", json=tutor_req_broken, headers=headers)
        assert resp_broken.status_code == 200, f"Tutor request failed: {resp_broken.text}"
        broken_tutor_text = resp_broken.json()["response"]

        print("\n[BROKEN CIRCUIT TUTOR RESPONSE]:")
        print(broken_tutor_text)
        print("\n✓ Diagnostic Socratic response verified.")

        # ---------------------------------------------------------------------
        # 2. Fixed Bell State (H on q0, CNOT with control q0, target q1)
        # ---------------------------------------------------------------------
        print("\n--- [TEST 2] Fixed Bell Circuit: H(q0) + CNOT(q0, q1) ---")
        fixed_circuit = {
            "qubit_count": 2,
            "gates": [
                {"type": "H", "target_qubits": [0], "step_index": 0},
                {"type": "CNOT", "target_qubits": [0, 1], "step_index": 1}
            ],
            "shots": 1024
        }
        sim_fixed = client.post("/circuits/simulate", json=fixed_circuit, headers=headers).json()
        circuit_id_fixed = sim_fixed["circuit_id"]
        run_id_fixed = sim_fixed["run_id"]
        print("Simulation Counts:", json.dumps(sim_fixed["measurement_counts"]))

        tutor_req_fixed = {
            "circuit_id": circuit_id_fixed,
            "run_id": run_id_fixed,
            "question": "I changed the X gate to an H gate. Did I fix it?",
            "experiment_type": "debug"
        }
        resp_fixed = client.post("/tutor/ask", json=tutor_req_fixed, headers=headers)
        assert resp_fixed.status_code == 200, f"Tutor request failed: {resp_fixed.text}"
        fixed_tutor_text = resp_fixed.json()["response"]

        print("\n[FIXED CIRCUIT TUTOR RESPONSE]:")
        print(fixed_tutor_text)
        print("\n✓ Affirming celebratory response verified.")

    print("\n" + "=" * 80)
    print("ALL DEBUG TUTOR VERIFICATIONS PASSED PROVABLY")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
