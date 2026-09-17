"""
test_progress.py
================
Verifies concept-level mastery tracking:
1. Fresh user: GET /progress/me returns all concepts at 0 attempts, 0.0 score, "Not Started".
2. Correct prediction + compare on Bell state: entanglement mastery score moves up (+0.1) and attempts=1.
3. Solve Debug Mode challenge (POST /progress/event): another tick (+0.1, score=0.2) and attempts=2.
4. Intentionally incorrect prediction + compare: attempts increments to 3, but score does NOT drop (stays 0.2).
5. Final GET /progress/me output.
"""

import httpx
import json
import uuid

BASE_URL = "http://127.0.0.1:8000"

def run_verification():
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    tag = uuid.uuid4().hex[:6]
    email = f"student_{tag}@egreen.local"
    password = "QuantumPassword123!"

    print("=" * 70)
    print("CONCEPT MASTERY VERIFICATION SUITE")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Step 1: Create fresh user and verify GET /progress/me returns all 0s
    # -------------------------------------------------------------------------
    print("\n[STEP 1] Registering fresh student user and checking initial progress...")
    signup_res = client.post("/auth/signup", json={
        "email": email,
        "password": password,
        "display_name": f"Student {tag}",
        "role": "student"
    })
    assert signup_res.status_code == 201, f"Signup failed: {signup_res.text}"
    user_data = signup_res.json()
    user_id = user_data["id"]
    print(f"✓ Registered student: {email} (id: {user_id})")

    login_res = client.post("/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ Logged in, JWT token acquired.")

    prog_res = client.get("/progress/me", headers=headers)
    assert prog_res.status_code == 200, f"GET /progress/me failed: {prog_res.text}"
    prog_data = prog_res.json()
    print(f"✓ GET /progress/me status 200. Total concepts: {prog_data['total_concepts']}, overall mastered: {prog_data['overall_mastered']}")
    
    for c in prog_data["concepts"]:
        print(f"   • Concept '{c['name']}': score={c['mastery_score']}, attempts={c['attempts']}, status='{c['status']}'")
        assert c["mastery_score"] == 0.0, f"Expected 0.0, got {c['mastery_score']}"
        assert c["attempts"] == 0, f"Expected 0, got {c['attempts']}"
        assert c["status"] == "Not Started", f"Expected 'Not Started', got {c['status']}"

    # -------------------------------------------------------------------------
    # Step 2: Correct prediction + compare on Bell state -> entanglement moves up
    # -------------------------------------------------------------------------
    print("\n[STEP 2] Running Bell circuit + correct prediction + compare...")
    # 1. Run simulation on Bell circuit (H(0), CNOT(0, 1))
    bell_gates = [
        {"type": "H", "target_qubits": [0], "params": None, "step_index": 0},
        {"type": "CNOT", "target_qubits": [0, 1], "params": None, "step_index": 1}
    ]
    sim_res = client.post("/circuits/simulate", json={
        "qubit_count": 2,
        "gates": bell_gates,
        "shots": 1024,
    }, headers=headers)
    assert sim_res.status_code == 200, f"Simulate failed: {sim_res.text}"
    sim_data = sim_res.json()
    circuit_id = sim_data["circuit_id"]
    print(f"✓ Bell state simulated. Circuit ID: {circuit_id}")

    # 2. Lock in correct prediction for Bell state: 50% |00>, 50% |11>
    correct_dist = {"00": 0.5, "11": 0.5, "01": 0.0, "10": 0.0}
    pred_res = client.post("/predictions", json={
        "circuit_id": circuit_id,
        "predicted_distribution": correct_dist,
    }, headers=headers)
    assert pred_res.status_code == 201, f"Prediction failed: {pred_res.text}"
    prediction_id = pred_res.json()["id"]
    print(f"✓ Correct prediction locked: {prediction_id}")

    # 3. Fetch compare (which triggers mastery update)
    cmp_res = client.get(f"/predictions/{prediction_id}/compare", headers=headers)
    assert cmp_res.status_code == 200, f"Compare failed: {cmp_res.text}"
    cmp_data = cmp_res.json()
    print(f"✓ Compare fetched. Actual: {cmp_data['actual']}")

    # 4. Check /progress/me
    prog_res2 = client.get("/progress/me", headers=headers)
    assert prog_res2.status_code == 200
    ent = next(c for c in prog_res2.json()["concepts"] if c["name"] == "entanglement")
    print(f"✓ Concept 'entanglement' updated:")
    print(f"   Score: {ent['mastery_score']} (expected 0.1)")
    print(f"   Attempts: {ent['attempts']} (expected 1)")
    print(f"   Status: '{ent['status']}' (expected 'In Progress')")
    assert ent["mastery_score"] == 0.1, f"Expected 0.1, got {ent['mastery_score']}"
    assert ent["attempts"] == 1, f"Expected 1, got {ent['attempts']}"
    assert ent["status"] == "In Progress"

    # -------------------------------------------------------------------------
    # Step 3: Solve Debug Mode challenge -> another tick
    # -------------------------------------------------------------------------
    print("\n[STEP 3] Solving Debug Mode challenge (triggering event)...")
    event_res = client.post("/progress/event", json={
        "concept": "entanglement",
        "event_type": "debug_solved",
        "success": True
    }, headers=headers)
    assert event_res.status_code == 200, f"Event failed: {event_res.text}"
    event_data = event_res.json()
    print(f"✓ Debug solve event recorded: concept={event_data['name']}, score={event_data['mastery_score']}, attempts={event_data['attempts']}")
    assert event_data["mastery_score"] == 0.2, f"Expected 0.2, got {event_data['mastery_score']}"
    assert event_data["attempts"] == 2, f"Expected 2, got {event_data['attempts']}"

    # -------------------------------------------------------------------------
    # Step 4: Intentionally incorrect prediction -> attempts increments, score doesn't drop
    # -------------------------------------------------------------------------
    print("\n[STEP 4] Submitting intentionally incorrect prediction...")
    wrong_dist = {"01": 0.5, "10": 0.5, "00": 0.0, "11": 0.0}
    wrong_pred_res = client.post("/predictions", json={
        "circuit_id": circuit_id,
        "predicted_distribution": wrong_dist,
    }, headers=headers)
    assert wrong_pred_res.status_code == 201
    wrong_pred_id = wrong_pred_res.json()["id"]

    # Compare incorrect prediction
    cmp_wrong_res = client.get(f"/predictions/{wrong_pred_id}/compare", headers=headers)
    assert cmp_wrong_res.status_code == 200

    # Verify attempts incremented to 3, but score stayed 0.2
    prog_res4 = client.get("/progress/me", headers=headers)
    assert prog_res4.status_code == 200
    ent4 = next(c for c in prog_res4.json()["concepts"] if c["name"] == "entanglement")
    print(f"✓ Concept 'entanglement' after incorrect prediction:")
    print(f"   Score: {ent4['mastery_score']} (retained at 0.2, did NOT drop)")
    print(f"   Attempts: {ent4['attempts']} (incremented to 3)")
    print(f"   Status: '{ent4['status']}'")
    assert ent4["mastery_score"] == 0.2, f"Expected 0.2, got {ent4['mastery_score']}"
    assert ent4["attempts"] == 3, f"Expected 3, got {ent4['attempts']}"

    # -------------------------------------------------------------------------
    # Step 5: Final GET /progress/me output
    # -------------------------------------------------------------------------
    print("\n[STEP 5] Final GET /progress/me output:")
    final_res = client.get("/progress/me", headers=headers)
    assert final_res.status_code == 200
    print(json.dumps(final_res.json(), indent=2))
    print("\n" + "=" * 70)
    print("ALL 5 VERIFICATION STAGES PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()
