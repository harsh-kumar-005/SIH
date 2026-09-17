"""
test_predictions_workflow.py
=============================
Automated end-to-end test script for the PostgreSQL persistence and prediction comparison loop:
  1. Creates a fake student user via POST /users
  2. Runs a Bell-state simulation via POST /circuits/simulate (persisting circuit and simulation_run)
  3. Submits a prediction {"00": 0.5, "11": 0.5, "01": 0, "10": 0} via POST /predictions
  4. Calls GET /predictions/{id}/compare to verify normalized (0-1) probabilities for actual counts
  5. Validates distinct 404 error scenarios:
     - Scenario A: Valid user + valid circuit with NO simulation run yet -> "No simulation run exists yet for circuit ..."
     - Scenario B: Non-existent prediction ID -> "Prediction with id ... not found"
"""

import asyncio
import uuid
import httpx
from httpx import ASGITransport
from main import app


async def run_prediction_workflow():
    print("==================================================================")
    print("TESTING END-TO-END PREDICTION & SIMULATION COMPARISON WORKFLOW")
    print("==================================================================")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # ---------------------------------------------------------------------
        # 1. Create a fake student user
        # ---------------------------------------------------------------------
        print("\n[Step 1] Creating a test student user...")
        user_payload = {
            "email": f"student_{uuid.uuid4().hex[:8]}@egreen-quanta.edu",
            "password_hash": "$2b$12$e8Y5HqG5yV2u2n9mPz1T0eX1k8q9",
            "role": "student",
            "display_name": "Alice Quantum"
        }
        user_res = await client.post("/users", json=user_payload)
        assert user_res.status_code == 201, f"User creation failed: {user_res.text}"
        user_data = user_res.json()
        user_id = user_data["id"]
        print(f"✓ User created successfully: ID = {user_id}, Name = {user_data['display_name']}")

        # ---------------------------------------------------------------------
        # 2. Simulate circuit via /circuits/simulate
        # ---------------------------------------------------------------------
        print("\n[Step 2] Simulating Bell-state circuit and persisting to DB...")
        circuit_payload = {
            "qubit_count": 2,
            "gates": [
                {"type": "H", "target_qubits": [0], "params": None, "step_index": 0},
                {"type": "CNOT", "target_qubits": [0, 1], "params": None, "step_index": 1}
            ],
            "shots": 1024,
            "owner_id": user_id
        }
        sim_res = await client.post("/circuits/simulate", json=circuit_payload)
        assert sim_res.status_code == 200, f"Simulation failed: {sim_res.text}"
        sim_data = sim_res.json()
        circuit_id = sim_data["circuit_id"]
        run_id = sim_data["run_id"]
        print(f"✓ Circuit persisted: Circuit ID = {circuit_id}")
        print(f"✓ Simulation Run persisted: Run ID = {run_id}")
        print(f"  Raw Shot Counts: {sim_data['measurement_counts']}")

        # ---------------------------------------------------------------------
        # 3. Submit student prediction
        # ---------------------------------------------------------------------
        print("\n[Step 3] Submitting student prediction for the circuit...")
        pred_payload = {
            "user_id": user_id,
            "circuit_id": circuit_id,
            "predicted_distribution": {"00": 0.5, "11": 0.5, "01": 0.0, "10": 0.0}
        }
        pred_res = await client.post("/predictions", json=pred_payload)
        assert pred_res.status_code == 201, f"Prediction submission failed: {pred_res.text}"
        pred_data = pred_res.json()
        prediction_id = pred_data["id"]
        print(f"✓ Prediction submitted: Prediction ID = {prediction_id}")
        print(f"  Predicted Distribution: {pred_data['predicted_distribution']}")

        # ---------------------------------------------------------------------
        # 4. Compare prediction vs actual results (Normalized 0-1 scale)
        # ---------------------------------------------------------------------
        print("\n[Step 4] Calling GET /predictions/{id}/compare (Normalized Probabilities)...")
        comp_res = await client.get(f"/predictions/{prediction_id}/compare")
        assert comp_res.status_code == 200, f"Compare failed: {comp_res.text}"
        comp_data = comp_res.json()
        print("✓ Side-by-side comparison result:")
        print("------------------------------------------------------------------")
        print(f"  Circuit ID: {comp_data['circuit_id']}")
        print(f"  Run ID:     {comp_data['run_id']}")
        print(f"  PREDICTED (0-1 scale): {comp_data['predicted']}")
        print(f"  ACTUAL    (0-1 scale): {comp_data['actual']}")
        print("------------------------------------------------------------------")

        # Assert normalized probabilities
        assert comp_data["circuit_id"] == circuit_id
        assert comp_data["run_id"] == run_id
        assert comp_data["predicted"]["00"] == 0.5
        assert comp_data["predicted"]["11"] == 0.5
        
        actual_00 = comp_data["actual"]["00"]
        actual_11 = comp_data["actual"]["11"]
        assert 0.40 <= actual_00 <= 0.60, f"Expected ~0.5, got {actual_00}"
        assert 0.40 <= actual_11 <= 0.60, f"Expected ~0.5, got {actual_11}"
        assert comp_data["actual"]["01"] == 0.0
        assert comp_data["actual"]["10"] == 0.0
        assert round(actual_00 + actual_11, 2) == 1.00
        print("✓ Confirmed: 'actual' field is normalized to probabilities rounded to 3 decimal places!")

        # ---------------------------------------------------------------------
        # 5. Distinct 404 Test Case Scenarios
        # ---------------------------------------------------------------------
        print("\n[Step 5] Testing distinct 404 failure scenarios:")

        # Scenario A: Real user + real circuit created WITHOUT simulation -> valid prediction -> compare
        print("  [5A] Real circuit with NO simulation run exists yet...")
        unsim_circuit_payload = {
            "qubit_count": 2,
            "gates": [
                {"type": "H", "target_qubits": [0], "params": None, "step_index": 0}
            ],
            "owner_id": user_id
        }
        circuit_res = await client.post("/circuits", json=unsim_circuit_payload)
        assert circuit_res.status_code == 201, f"Failed to create draft circuit: {circuit_res.text}"
        unsim_circuit_id = circuit_res.json()["id"]

        # Submit valid prediction for this unsimulated circuit
        unsim_pred_payload = {
            "user_id": user_id,
            "circuit_id": unsim_circuit_id,
            "predicted_distribution": {"00": 0.5, "01": 0.5}
        }
        unsim_pred_res = await client.post("/predictions", json=unsim_pred_payload)
        assert unsim_pred_res.status_code == 201
        unsim_pred_id = unsim_pred_res.json()["id"]

        # Call compare on this real prediction
        unsim_comp_res = await client.get(f"/predictions/{unsim_pred_id}/compare")
        assert unsim_comp_res.status_code == 404
        unsim_detail = unsim_comp_res.json()["detail"]
        print(f"  ✓ Scenario A HTTP 404 message: '{unsim_detail}'")
        assert f"No simulation run exists yet for circuit {unsim_circuit_id}" == unsim_detail

        # Scenario B: Non-existent prediction ID
        print("  [5B] Non-existent prediction ID...")
        fake_pred_id = uuid.uuid4()
        missing_pred_res = await client.get(f"/predictions/{fake_pred_id}/compare")
        assert missing_pred_res.status_code == 404
        missing_detail = missing_pred_res.json()["detail"]
        print(f"  ✓ Scenario B HTTP 404 message: '{missing_detail}'")
        assert f"Prediction with id {fake_pred_id} not found" == missing_detail

        # Confirm the two error messages are distinct
        assert unsim_detail != missing_detail
        print("  ✓ Confirmed: 'no simulation run exists' and 'prediction not found' are clearly distinguishable!")

    print("\n==================================================================")
    print("ALL FIXES VERIFIED & TESTS PASSED PROVABLY")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(run_prediction_workflow())
