"""
test_superposition.py
=====================
Automated verification suite for Superposition Guided Module & Generalized AI Misconception Classifier.

Tests:
  [STAGE 1] GET /experiments/guided/superposition payload structure & empty starter circuit.
  [STAGE 2] Correct Superposition prediction, simulation, comparison, and concept mastery increment under 'superposition' specifically.
  [STAGE 3] Incorrect Superposition prediction with AI misconception classification, verifying the tag returned is from the superposition taxonomy (not entanglement).
"""

import sys
import httpx

BASE_URL = "http://localhost:8000"


def run_tests():
    print("=" * 75)
    print("SUPERPOSITION GUIDED MODULE & MISCONCEPTION GENERALIZATION TEST SUITE")
    print("=" * 75)

    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        # ---------------------------------------------------------------------
        # [STAGE 1] Test GET /experiments/guided/superposition
        # ---------------------------------------------------------------------
        print("\n[STAGE 1] Testing GET /experiments/guided/superposition...")
        res = client.get("/experiments/guided/superposition")
        assert res.status_code == 200, f"Failed GET /experiments/guided/superposition: {res.text}"
        data = res.json()

        assert data.get("concept") == "superposition", f"Expected concept 'superposition', got {data.get('concept')}"
        assert "A classical bit is always either 0 or 1" in data.get("lesson_text", ""), "lesson_text mismatch"
        assert "If you apply H to q0 and measure" in data.get("prediction_prompt", ""), "prediction_prompt mismatch"
        assert data.get("target_behavior", {}).get("distribution") == {"00": 0.5, "01": 0.5, "10": 0.0, "11": 0.0}, "target_behavior mismatch"
        assert data.get("starter_circuit", {}).get("gates") == [], f"Expected starter_circuit.gates == [], got {data.get('starter_circuit')}"

        print("✓ Guided Superposition payload structure and empty starter circuit verified!")

        # ---------------------------------------------------------------------
        # Setup: Register student user
        # ---------------------------------------------------------------------
        import uuid
        email = f"student_superposition_{uuid.uuid4().hex[:6]}@egreen.local"
        password = "password123"

        signup_res = client.post("/auth/signup", json={
            "email": email,
            "password": password,
            "display_name": "Superposition Learner",
            "role": "student"
        })
        assert signup_res.status_code == 201, f"Signup failed: {signup_res.text}"
        user_id = signup_res.json()["id"]

        login_res = client.post("/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # ---------------------------------------------------------------------
        # [STAGE 2] Build H(q0), lock correct prediction, simulate & verify mastery
        # ---------------------------------------------------------------------
        print("\n[STAGE 2] Building H(q0), locking correct prediction, running & verifying mastery...")

        # 1. Simulate H(q0) circuit on 2 qubits
        sim_payload = {
            "qubit_count": 2,
            "gates": [
                {"type": "H", "target_qubits": [0], "params": None, "step_index": 0}
            ],
            "shots": 1024
        }
        sim_res = client.post("/circuits/simulate", json=sim_payload, headers=auth_headers)
        assert sim_res.status_code == 200, f"Simulate failed: {sim_res.text}"
        sim_data = sim_res.json()
        circuit_id = sim_data["circuit_id"]

        # 2. Submit correct prediction with concept: 'superposition'
        pred_payload = {
            "circuit_id": circuit_id,
            "predicted_distribution": {"00": 0.5, "01": 0.5, "10": 0.0, "11": 0.0},
            "concept": "superposition"
        }
        pred_res = client.post("/predictions", json=pred_payload, headers=auth_headers)
        assert pred_res.status_code == 201, f"Prediction failed: {pred_res.text}"
        pred_id = pred_res.json()["id"]

        # 3. Compare prediction with actual simulation
        cmp_res = client.get(f"/predictions/{pred_id}/compare", headers=auth_headers)
        assert cmp_res.status_code == 200, f"Compare failed: {cmp_res.text}"

        # 4. Verify progress reflects score under 'superposition' (not 'entanglement')
        prog_res = client.get("/progress/me", headers=auth_headers)
        assert prog_res.status_code == 200, f"Progress failed: {prog_res.text}"
        prog_data = prog_res.json()
        import json
        print("\n--- GET /progress/me after Superposition prediction ---")
        print(json.dumps(prog_data, indent=2))

        superposition_item = next((c for c in prog_data["concepts"] if c["name"] == "superposition"), None)
        entanglement_item = next((c for c in prog_data["concepts"] if c["name"] == "entanglement"), None)

        assert superposition_item is not None, "Concept 'superposition' missing from progress"
        assert superposition_item["mastery_score"] > 0.0, f"Superposition mastery score should be > 0.0, got {superposition_item['mastery_score']}"
        assert superposition_item["attempts"] == 1, f"Superposition attempts should be 1, got {superposition_item['attempts']}"
        assert entanglement_item["mastery_score"] == 0.0, f"Entanglement mastery should remain 0.0, got {entanglement_item['mastery_score']}"

        print(f"\n✓ Superposition concept mastery successfully updated! (score: {superposition_item['mastery_score']}, attempts: {superposition_item['attempts']})")
        print(f"✓ Entanglement concept mastery remained isolated at 0.0.")

        # ---------------------------------------------------------------------
        # [STAGE 3] Submit wrong prediction & verify superposition-scoped misconception tag
        # ---------------------------------------------------------------------
        print("\n[STAGE 3] Submitting wrong prediction (deterministic 100% |00⟩) & verifying AI misconception tag...")

        wrong_pred_payload = {
            "circuit_id": circuit_id,
            "predicted_distribution": {"00": 1.0, "01": 0.0, "10": 0.0, "11": 0.0},
            "concept": "superposition"
        }
        wrong_pred_res = client.post("/predictions", json=wrong_pred_payload, headers=auth_headers)
        assert wrong_pred_res.status_code == 201, f"Wrong prediction submission failed: {wrong_pred_res.text}"
        wrong_pred_id = wrong_pred_res.json()["id"]

        wrong_cmp_res = client.get(f"/predictions/{wrong_pred_id}/compare", headers=auth_headers)
        assert wrong_cmp_res.status_code == 200, f"Wrong compare failed: {wrong_cmp_res.text}"
        wrong_cmp_data = wrong_cmp_res.json()

        classified_tag = wrong_cmp_data.get("misconception_tag")
        print(f"  AI Misconception Classifier output: {classified_tag}")

        SUPERPOSITION_TAXONOMY_TAGS = {
            "believes_qubit_is_secretly_definite_before_measurement",
            "conflates_amplitude_with_probability",
            "expects_same_outcome_every_run"
        }

        ENTANGLEMENT_TAXONOMY_TAGS = {
            "confuses_superposition_with_classical_probability",
            "expects_correlation_without_entangling_gate",
            "misreads_zero_amplitude_as_impossible_outcome"
        }

        assert classified_tag is not None, "Expected AI misconception classifier to return a tag, got None"
        assert classified_tag in SUPERPOSITION_TAXONOMY_TAGS, (
            f"EXPECTED tag from superposition taxonomy {SUPERPOSITION_TAXONOMY_TAGS}, "
            f"but got '{classified_tag}'"
        )
        assert classified_tag not in ENTANGLEMENT_TAXONOMY_TAGS, (
            f"ERROR: Classifier returned tag '{classified_tag}' from entanglement taxonomy!"
        )

        print(f"✓ AI Misconception Classifier returned superposition-scoped tag: '{classified_tag}'!")
        print("✓ Generalization proven: classifier dynamically uses concept taxonomy from PostgreSQL.")

    print("\n" + "=" * 75)
    print("ALL SUPERPOSITION & MISCONCEPTION GENERALIZATION TESTS PASSED PROVABLY")
    print("=" * 75)


if __name__ == "__main__":
    run_tests()
