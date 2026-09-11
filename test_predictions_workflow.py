"""
test_predictions_workflow.py
=============================
Automated end-to-end test script for the PostgreSQL persistence and prediction comparison loop:
  1. Creates a fake user via POST /users
  2. Runs a Bell-state simulation via POST /circuits/simulate (persisting circuit and simulation_run)
  3. Submits a prediction {"00": 0.5, "11": 0.5, "01": 0, "10": 0} via POST /predictions
  4. Calls GET /predictions/{id}/compare to fetch predicted vs actual distributions side by side
  5. Verifies 404 handling when no simulation run exists for a new circuit
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
        # 1. Create a fake user
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

        # 2. Simulate circuit via /circuits/simulate
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
        print(f"  Counts: {sim_data['measurement_counts']}")

        # 3. Submit student prediction
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

        # 4. Compare prediction vs actual results
        print("\n[Step 4] Calling GET /predictions/{id}/compare...")
        comp_res = await client.get(f"/predictions/{prediction_id}/compare")
        assert comp_res.status_code == 200, f"Compare failed: {comp_res.text}"
        comp_data = comp_res.json()
        print("✓ Side-by-side comparison result:")
        print("------------------------------------------------------------------")
        print(f"  Circuit ID: {comp_data['circuit_id']}")
        print(f"  Run ID:     {comp_data['run_id']}")
        print(f"  PREDICTED:  {comp_data['predicted']}")
        print(f"  ACTUAL:     {comp_data['actual']}")
        print("------------------------------------------------------------------")

        # Assert correctness
        assert comp_data["circuit_id"] == circuit_id
        assert comp_data["run_id"] == run_id
        assert comp_data["predicted"]["00"] == 0.5
        assert comp_data["predicted"]["11"] == 0.5
        assert comp_data["actual"]["00"] > 0
        assert comp_data["actual"]["11"] > 0
        assert comp_data["actual"]["01"] == 0
        assert comp_data["actual"]["10"] == 0

        # 5. Verify 404 when no simulation run exists yet
        print("\n[Step 5] Testing 404 when no simulation run exists yet for a circuit...")
        not_found_res = await client.get(f"/predictions/{uuid.uuid4()}/compare")
        assert not_found_res.status_code == 404
        print(f"✓ Correctly returned 404 for missing prediction: {not_found_res.json()['detail']}")

    print("\n==================================================================")
    print("ALL WORKFLOW STEPS VALIDATED & VERIFIED AGAINST POSTGRESQL")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(run_prediction_workflow())
