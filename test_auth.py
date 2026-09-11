"""
test_auth.py - Comprehensive test suite for backend authentication, JWT tokens, and RBAC.
"""

import httpx
import uuid

BASE_URL = "http://127.0.0.1:8000"

def test_auth_pipeline():
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # Unique email per test run
    run_tag = uuid.uuid4().hex[:6]
    student_email = f"student_{run_tag}@egreen.local"
    instructor_email = f"prof_{run_tag}@egreen.local"
    password = "QuantumPassword123!"

    print("\n[TEST 1] Testing POST /auth/signup for Student...")
    signup_payload = {
        "email": student_email,
        "password": password,
        "display_name": "Alice Student",
        "role": "student"
    }
    r = client.post("/auth/signup", json=signup_payload)
    assert r.status_code == 201, f"Signup failed: {r.status_code} {r.text}"
    student_data = r.json()
    student_id = student_data["id"]
    assert "password" not in student_data and "password_hash" not in student_data
    assert student_data["email"] == student_email
    assert student_data["role"] == "student"
    print(f"✓ Student registered: {student_id} ({student_email}), password hash omitted from response.")

    print("\n[TEST 2] Testing duplicate email rejection (409 Conflict)...")
    r_dup = client.post("/auth/signup", json=signup_payload)
    assert r_dup.status_code == 409, f"Expected 409, got {r_dup.status_code}: {r_dup.text}"
    print(f"✓ Duplicate email rejected with 409 Conflict: {r_dup.json()['detail']}")

    print("\n[TEST 3] Testing invalid role rejection...")
    r_bad_role = client.post("/auth/signup", json=dict(signup_payload, email=f"bad_{run_tag}@egreen.local", role="hacker"))
    assert r_bad_role.status_code in (400, 422), f"Expected 400/422, got {r_bad_role.status_code}"
    print("✓ Invalid role 'hacker' correctly rejected.")

    print("\n[TEST 4] Testing POST /auth/login with wrong credentials (generic 401)...")
    r_wrong_pw = client.post("/auth/login", json={"email": student_email, "password": "WrongPassword!"})
    assert r_wrong_pw.status_code == 401, f"Expected 401, got {r_wrong_pw.status_code}"
    assert r_wrong_pw.json()["detail"] == "Invalid email or password"

    r_wrong_email = client.post("/auth/login", json={"email": "nonexistent@egreen.local", "password": password})
    assert r_wrong_email.status_code == 401
    assert r_wrong_email.json()["detail"] == "Invalid email or password"
    print("✓ Invalid login safely returned generic 401 without leaking email existence.")

    print("\n[TEST 5] Testing POST /auth/login with valid credentials...")
    r_login = client.post("/auth/login", json={"email": student_email, "password": password})
    assert r_login.status_code == 200, f"Login failed: {r_login.status_code} {r_login.text}"
    login_data = r_login.json()
    student_token = login_data["access_token"]
    assert login_data["token_type"] == "bearer"
    assert login_data["user"]["id"] == student_id
    print("✓ Login succeeded, 24-hour access token received.")

    auth_headers = {"Authorization": f"Bearer {student_token}"}

    print("\n[TEST 6] Testing protected endpoints without token (negative case: 401)...")
    circ_payload = {
        "qubit_count": 2,
        "gates": [
            {"type": "H", "target_qubits": [0], "step_index": 0},
            {"type": "CNOT", "target_qubits": [0, 1], "step_index": 1}
        ]
    }
    r_unauth_circ = client.post("/circuits", json=circ_payload)
    assert r_unauth_circ.status_code == 401, f"Expected 401, got {r_unauth_circ.status_code}"

    pred_payload = {
        "circuit_id": str(uuid.uuid4()),
        "predicted_distribution": {"00": 0.5, "11": 0.5, "01": 0.0, "10": 0.0}
    }
    r_unauth_pred = client.post("/predictions", json=pred_payload)
    assert r_unauth_pred.status_code == 401, f"Expected 401, got {r_unauth_pred.status_code}"
    print("✓ Protected endpoints (/circuits, /predictions) properly rejected unauthenticated requests with 401.")

    print("\n[TEST 7] Testing authenticated circuit creation & simulation with user_id derivation...")
    r_circ = client.post("/circuits", json=circ_payload, headers=auth_headers)
    assert r_circ.status_code == 201, f"Expected 201, got {r_circ.status_code}: {r_circ.text}"
    circuit_data = r_circ.json()
    circuit_id = circuit_data["id"]
    assert circuit_data["owner_id"] == student_id, f"Expected owner_id {student_id}, got {circuit_data['owner_id']}"
    print(f"✓ Circuit {circuit_id} created with owner_id matching authenticated user ({student_id}).")

    # Simulate circuit with auth
    r_sim = client.post("/circuits/simulate", json=dict(circ_payload, circuit_id=circuit_id), headers=auth_headers)
    assert r_sim.status_code == 200, f"Expected 200, got {r_sim.status_code}: {r_sim.text}"
    print("✓ Circuit simulated with Bearer token attached.")

    # Prediction creation with auth (user_id derived from token)
    pred_payload["circuit_id"] = circuit_id
    # Attempt to spoof another user_id in body
    pred_payload["user_id"] = str(uuid.uuid4())
    r_pred = client.post("/predictions", json=pred_payload, headers=auth_headers)
    assert r_pred.status_code == 201, f"Expected 201, got {r_pred.status_code}: {r_pred.text}"
    pred_data = r_pred.json()
    assert pred_data["user_id"] == student_id, f"user_id was spoofed! Expected {student_id}, got {pred_data['user_id']}"
    print(f"✓ Prediction {pred_data['id']} derived user_id directly from JWT ({student_id}), ignoring client spoof attempt.")

    print("\n[TEST 8] Testing Role-Based Access Control (require_instructor)...")
    # Student hits instructor route -> 403
    r_forbid = client.get("/instructor/dashboard", headers=auth_headers)
    assert r_forbid.status_code == 403, f"Expected 403, got {r_forbid.status_code}: {r_forbid.text}"
    print(f"✓ Student correctly denied access to instructor dashboard with 403: {r_forbid.json()['detail']}")

    # Instructor signup and login
    r_inst_signup = client.post("/auth/signup", json={
        "email": instructor_email,
        "password": password,
        "display_name": "Prof. Erwin",
        "role": "instructor"
    })
    assert r_inst_signup.status_code == 201
    r_inst_login = client.post("/auth/login", json={"email": instructor_email, "password": password})
    assert r_inst_login.status_code == 200
    inst_token = r_inst_login.json()["access_token"]
    inst_headers = {"Authorization": f"Bearer {inst_token}"}

    # Instructor hits instructor route -> 200
    r_inst_dash = client.get("/instructor/dashboard", headers=inst_headers)
    assert r_inst_dash.status_code == 200, f"Expected 200, got {r_inst_dash.status_code}: {r_inst_dash.text}"
    print(f"✓ Instructor successfully accessed instructor dashboard with 200: {r_inst_dash.json()['message']}")

    print("\n========================================================")
    print("ALL AUTHENTICATION & RBAC TESTS PASSED PROVABLY")
    print("========================================================\n")

if __name__ == "__main__":
    test_auth_pipeline()
