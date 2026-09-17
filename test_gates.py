"""
test_gates.py
=============
Verification suite for Gates Guided Module & AI Misconception Classifier.

Verifies:
  1. Raw JSON from GET /experiments/guided/gates
  2. X(q0) simulation, locking correct prediction {"01": 1.0}, compare result (~100% |01⟩)
  3. /progress/me showing gates mastery ticked, superposition/entanglement unchanged
  4. Deliberately wrong prediction {"00": 0.5, "01": 0.5} -> AI classifier returns 'believes_x_creates_superposition'
"""

import json
import uuid
import httpx

BASE_URL = "http://localhost:8000"


def run_tests():
    print("=" * 80)
    print("GATES GUIDED MODULE & MISCONCEPTION CLASSIFIER VERIFICATION")
    print("=" * 80)

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # ---------------------------------------------------------------------
        # 1. Raw response from GET /experiments/guided/gates
        # ---------------------------------------------------------------------
        print("\n--- [ITEM 1] Raw Response from GET /experiments/guided/gates ---")
        res = client.get("/experiments/guided/gates")
        assert res.status_code == 200, f"GET /experiments/guided/gates failed: {res.text}"
        guided_gates_data = res.json()
        print(json.dumps(guided_gates_data, indent=2))

        assert guided_gates_data.get("concept") == "gates"
        assert guided_gates_data.get("target_behavior", {}).get("distribution") == {
            "00": 0.0, "01": 1.0, "10": 0.0, "11": 0.0
        }

        # ---------------------------------------------------------------------
        # Register a fresh student user for clean mastery baseline
        # ---------------------------------------------------------------------
        email = f"student_gates_{uuid.uuid4().hex[:6]}@egreen.local"
        password = "password123"

        signup_res = client.post("/auth/signup", json={
            "email": email,
            "password": password,
            "display_name": "Gates Learner",
            "role": "student"
        })
        assert signup_res.status_code == 201, f"Signup failed: {signup_res.text}"

        login_res = client.post("/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Baseline progress check (all should be 0.0)
        base_prog = client.get("/progress/me", headers=auth_headers).json()
        print("\n--- Baseline Progress (/progress/me before runs) ---")
        print(json.dumps(base_prog, indent=2))

        # ---------------------------------------------------------------------
        # 2. Build X(q0) only, lock correct prediction, simulate & compare
        # ---------------------------------------------------------------------
        print("\n--- [ITEM 2] Build X(q0) only, lock prediction, run & compare ---")
        # Step A: Simulate circuit X on q0
        sim_payload = {
            "qubit_count": 2,
            "gates": [
                {"type": "X", "target_qubits": [0], "params": None, "step_index": 0}
            ],
            "shots": 1024
        }
        sim_res = client.post("/circuits/simulate", json=sim_payload, headers=auth_headers)
        assert sim_res.status_code == 200, f"Simulate failed: {sim_res.text}"
        sim_data = sim_res.json()
        circuit_id = sim_data["circuit_id"]

        # Step B: Lock correct prediction {"00": 0.0, "01": 1.0, "10": 0.0, "11": 0.0}
        pred_payload = {
            "circuit_id": circuit_id,
            "predicted_distribution": {"00": 0.0, "01": 1.0, "10": 0.0, "11": 0.0},
            "concept": "gates"
        }
        pred_res = client.post("/predictions", json=pred_payload, headers=auth_headers)
        assert pred_res.status_code == 201, f"Prediction failed: {pred_res.text}"
        pred_id = pred_res.json()["id"]

        # Step C: Compare
        cmp_res = client.get(f"/predictions/{pred_id}/compare", headers=auth_headers)
        assert cmp_res.status_code == 200, f"Compare failed: {cmp_res.text}"
        cmp_data = cmp_res.json()
        print("Comparison output (GET /predictions/{id}/compare):")
        print(json.dumps(cmp_data, indent=2))

        actual_dist = cmp_data.get("actual", {})
        assert actual_dist.get("01", 0) >= 0.95, f"Expected |01⟩ ~ 1.0, got {actual_dist}"

        # ---------------------------------------------------------------------
        # 3. GET /progress/me showing gates mastery ticked, others unchanged
        # ---------------------------------------------------------------------
        print("\n--- [ITEM 3] GET /progress/me after correct Gates prediction ---")
        prog_res = client.get("/progress/me", headers=auth_headers)
        assert prog_res.status_code == 200, f"Progress failed: {prog_res.text}"
        prog_data = prog_res.json()
        print(json.dumps(prog_data, indent=2))

        gates_item = next((c for c in prog_data["concepts"] if c["name"] == "gates"), None)
        superposition_item = next((c for c in prog_data["concepts"] if c["name"] == "superposition"), None)
        entanglement_item = next((c for c in prog_data["concepts"] if c["name"] == "entanglement"), None)

        assert gates_item is not None, "Concept 'gates' not in progress response"
        assert gates_item["mastery_score"] > 0.0, f"Gates mastery should be > 0, got {gates_item['mastery_score']}"
        assert gates_item["attempts"] == 1, f"Gates attempts should be 1, got {gates_item['attempts']}"
        assert superposition_item["mastery_score"] == 0.0, f"Superposition mastery should be 0.0, got {superposition_item['mastery_score']}"
        assert entanglement_item["mastery_score"] == 0.0, f"Entanglement mastery should be 0.0, got {entanglement_item['mastery_score']}"

        # ---------------------------------------------------------------------
        # 4. Submit wrong prediction {"00": 0.5, "01": 0.5} (confusing X with H)
        # ---------------------------------------------------------------------
        print("\n--- [ITEM 4] Submit wrong prediction {'00': 0.5, '01': 0.5} & verify classifier ---")
        wrong_pred_payload = {
            "circuit_id": circuit_id,
            "predicted_distribution": {"00": 0.5, "01": 0.5, "10": 0.0, "11": 0.0},
            "concept": "gates"
        }
        wrong_pred_res = client.post("/predictions", json=wrong_pred_payload, headers=auth_headers)
        assert wrong_pred_res.status_code == 201, f"Wrong prediction submission failed: {wrong_pred_res.text}"
        wrong_pred_id = wrong_pred_res.json()["id"]

        wrong_cmp_res = client.get(f"/predictions/{wrong_pred_id}/compare", headers=auth_headers)
        assert wrong_cmp_res.status_code == 200, f"Wrong compare failed: {wrong_cmp_res.text}"
        wrong_cmp_data = wrong_cmp_res.json()
        print("Comparison output for wrong prediction:")
        print(json.dumps(wrong_cmp_data, indent=2))

        classified_tag = wrong_cmp_data.get("misconception_tag")
        print(f"\nAI Misconception Tag Returned: '{classified_tag}'")

        assert classified_tag is not None, "Expected classifier to return a non-null tag"
        assert classified_tag == "believes_x_creates_superposition", (
            f"Expected 'believes_x_creates_superposition', got '{classified_tag}'"
        )

        print("\n" + "=" * 80)
        print("SUCCESS: ALL 4 GATES VERIFICATION CRITERIA VALIDATED PROVABLY")
        print("=" * 80)


if __name__ == "__main__":
    run_tests()
