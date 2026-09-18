# Run with: uvicorn main:app --reload
"""
main.py
=======
FastAPI Quantum Simulation & Prediction Service for Egreen-Quanta.

Endpoints:
  - GET  /health                     : Basic uptime and health check
  - POST /users                      : Create a user (convenience for tests & onboarding)
  - POST /circuits/simulate          : Simulates a circuit, persists circuits & simulation_runs records
  - POST /predictions                : Submits a student circuit outcome prediction
  - GET  /predictions/{id}/compare   : Compares student prediction with actual simulation results
"""

import asyncio
import os
import secrets
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Literal, Optional

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
from passlib.context import CryptContext
from jose import jwt, JWTError

from db.database import get_db
from db.models import (
    User, Circuit, SimulationRun, Prediction, Concept, ConceptMastery,
    MisconceptionTag, MisconceptionEvent
)
from tutor_prompt import SYSTEM_PROMPT, format_tutor_user_message

# -----------------------------------------------------------------------------
# 1. Extensible Gate Registry
# -----------------------------------------------------------------------------
GateApplier = Callable[[QuantumCircuit, List[int], Optional[List[float]]], None]
GateFormatter = Callable[[List[int], Optional[List[float]]], str]

GATE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "H": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.h(targets[0]),
        "format": lambda targets, params: f"H(q{targets[0]})",
    },
    "X": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.x(targets[0]),
        "format": lambda targets, params: f"X(q{targets[0]})",
    },
    "Y": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.y(targets[0]),
        "format": lambda targets, params: f"Y(q{targets[0]})",
    },
    "Z": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.z(targets[0]),
        "format": lambda targets, params: f"Z(q{targets[0]})",
    },
    "CNOT": {
        "expected_qubits": 2,
        "apply": lambda qc, targets, params: qc.cx(targets[0], targets[1]),
        "format": lambda targets, params: f"CNOT(q{targets[0]},q{targets[1]})",
    },
    "S": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.s(targets[0]),
        "format": lambda targets, params: f"S(q{targets[0]})",
    },
    "T": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.t(targets[0]),
        "format": lambda targets, params: f"T(q{targets[0]})",
    },
    "RX": {
        "expected_qubits": 1,
        "apply": lambda qc, targets, params: qc.rx(params[0] if params else 0.0, targets[0]),
        "format": lambda targets, params: f"RX(q{targets[0]},{(params[0] if params else 0.0):.3f})",
    },
}

# -----------------------------------------------------------------------------
# 2. Pydantic Request & Response Schemas
# -----------------------------------------------------------------------------
class GateRequest(BaseModel):
    type: str = Field(..., description="Gate type identifier, e.g., 'H', 'CNOT', 'X'")
    target_qubits: List[int] = Field(..., description="Target qubit indices")
    params: Optional[List[float]] = Field(None, description="Optional rotation parameters")
    step_index: int = Field(0, description="Execution step order in circuit timeline")


class CircuitSimulateRequest(BaseModel):
    qubit_count: int = Field(..., description="Total number of qubits (1-8)")
    gates: List[GateRequest] = Field(default_factory=list, description="List of gates")
    shots: int = Field(1024, description="Measurement shots")
    noise_level: float = Field(0.0, description="Depolarizing noise level (0.0 - 1.0)")
    circuit_id: Optional[uuid.UUID] = Field(None, description="Optional existing circuit ID")
    owner_id: Optional[uuid.UUID] = Field(None, description="Optional owner user ID")


class ComplexAmplitude(BaseModel):
    real: float
    imag: float


class GateState(BaseModel):
    after_gate: str
    statevector: List[ComplexAmplitude]


class CircuitSimulateResponse(BaseModel):
    circuit_id: uuid.UUID
    run_id: uuid.UUID
    qubit_count: int
    gates_applied: List[str]
    per_gate_states: List[GateState]
    final_statevector: List[ComplexAmplitude]
    measurement_counts: Dict[str, int]


class UserCreateRequest(BaseModel):
    email: str
    password_hash: str = "hashed_pw_default"
    role: str = "student"
    display_name: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    display_name: str
    profile_picture: Optional[str] = None
    auth_provider: str = "email"


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=255)
    role: Literal["student", "instructor"] = Field("student", description="Role restricted to student or instructor")


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PredictionCreateRequest(BaseModel):
    circuit_id: uuid.UUID
    predicted_distribution: Dict[str, float]
    user_id: Optional[uuid.UUID] = None
    concept: Optional[str] = Field(None, description="Target concept, e.g. 'superposition' or 'entanglement'. Omit to skip mastery routing (backward-compat: compare falls back to 'entanglement' for old records with no _concept sentinel).")


class PredictionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    circuit_id: uuid.UUID
    predicted_distribution: Dict[str, float]
    actual_run_id: Optional[uuid.UUID] = None


class CompareResponse(BaseModel):
    predicted: Dict[str, float]
    actual: Dict[str, float]
    circuit_id: uuid.UUID
    run_id: uuid.UUID
    misconception_tag: Optional[str] = None


class CircuitCreateRequest(BaseModel):
    qubit_count: int = Field(..., description="Total number of qubits (1-8)")
    gates: List[GateRequest] = Field(default_factory=list, description="List of gates")
    code_form: Optional[str] = Field(None, description="Optional OpenQASM or Python representation")
    owner_id: Optional[uuid.UUID] = Field(None, description="Optional owner user ID")


class CircuitResponse(BaseModel):
    id: uuid.UUID
    qubit_count: int
    gates: List[Dict[str, Any]]
    owner_id: Optional[uuid.UUID] = None


class TutorAskRequest(BaseModel):
    circuit_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    question: str = Field(..., min_length=1, max_length=2000)
    experiment_type: Optional[str] = Field(None, description="Optional experiment type: e.g. 'debug', 'noise'")
    target_behavior: Optional[Dict[str, Any]] = Field(None, description="Optional target behavior")
    ideal_counts: Optional[Dict[str, int]] = Field(None, description="Optional ideal noise-free counts for comparison")
    noise_level: Optional[float] = Field(None, description="Optional noise level (0.0 - 1.0)")


class TutorAskResponse(BaseModel):
    response: str


class ConceptProgressItem(BaseModel):
    concept_id: uuid.UUID
    name: str
    description: str
    mastery_score: float = Field(0.0, ge=0.0, le=1.0)
    attempts: int = Field(0, ge=0)
    status: Literal["Not Started", "In Progress", "Mastered"]
    last_updated: Optional[datetime] = None


class UserProgressResponse(BaseModel):
    concepts: List[ConceptProgressItem]
    overall_mastered: int
    total_concepts: int


class ProgressEventRequest(BaseModel):
    concept: str = Field("entanglement", description="Name of concept, e.g. 'entanglement'")
    event_type: str = Field(..., description="Event type, e.g. 'debug_solved', 'noise_lab_completed'")
    success: bool = Field(True, description="Whether event was successful")


class MostMissedConcept(BaseModel):
    concept_name: str
    avg_mastery: float
    total_attempts: int


class MostCommonMisconception(BaseModel):
    tag_name: str
    display_label: str
    event_count: int


class StudentInterventionItem(BaseModel):
    student_id: uuid.UUID
    name: str
    email: str
    concept_name: str
    attempts: int
    mastery_score: float
    most_recent_misconception: Optional[str] = "None recorded"


class InstructorDashboardResponse(BaseModel):
    status: str = "ok"
    message: str
    instructor_id: uuid.UUID
    most_missed_concept: Optional[MostMissedConcept] = None
    most_common_misconception: Optional[MostCommonMisconception] = None
    students_needing_intervention: List[StudentInterventionItem] = Field(default_factory=list)
    total_students: int = 0




# -----------------------------------------------------------------------------
# 3. Serialization Helpers
# -----------------------------------------------------------------------------
def complex_to_dict(val: complex, decimals: int = 6) -> ComplexAmplitude:
    return ComplexAmplitude(
        real=round(float(np.real(val)), decimals),
        imag=round(float(np.imag(val)), decimals),
    )


def serialize_statevector(data) -> List[ComplexAmplitude]:
    return [complex_to_dict(c) for c in np.asarray(data)]


# -----------------------------------------------------------------------------
# 4. FastAPI Setup & Middleware
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Egreen-Quanta Simulation & Prediction API",
    description="Full-stack quantum simulation engine with PostgreSQL persistence.",
    version="1.0.0",
)

raw_cors = os.getenv("CORS_ORIGINS", "*")
cors_origins = ["*"] if raw_cors.strip() == "*" else [orig.strip() for orig in raw_cors.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# 4.5. Authentication & Security Configuration
# -----------------------------------------------------------------------------
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "egreen-quanta-jwt-secret-key-2026-prod")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_bearer = HTTPBearer(auto_error=False)

# -----------------------------------------------------------------------------
# 4.6. Google OAuth 2.0 Configuration
# -----------------------------------------------------------------------------
# Credentials MUST be set as environment variables — never hardcoded.
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
# Default redirect URI for local Docker Compose development.
# Override with GOOGLE_REDIRECT_URI env var in production.
GOOGLE_REDIRECT_URI  = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/auth/google/callback"
)
# After callback, redirect browser to this frontend URL with token in fragment
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Google OAuth 2.0 endpoint URLs (stable, from discovery document)
GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# In-memory CSRF state store: {state_token: expires_at_unix_float}
# Each state token is a 32-byte cryptographically-random hex string.
# It expires after 10 minutes — the OAuth flow must complete within that window.
# In a multi-process production deployment, replace this with Redis.
_oauth_state_store: Dict[str, float] = {}
OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extracts and validates JWT from Authorization: Bearer <token>, loading the User."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or malformed authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Validates Bearer token if provided; returns None if omitted."""
    if not credentials or not credentials.credentials:
        return None
    return await get_current_user(credentials=credentials, db=db)


async def require_instructor(user: User = Depends(get_current_user)) -> User:
    """Requires that the authenticated user has the 'instructor' role."""
    if user.role != "instructor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: instructor role required",
        )
    return user


# -----------------------------------------------------------------------------
# 4.7. Google OAuth Helper Functions
# -----------------------------------------------------------------------------
def _make_user_response(user: User) -> "UserResponse":
    """Builds a UserResponse from a User ORM object, including optional Google fields."""
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        profile_picture=user.profile_picture,
        auth_provider=user.auth_provider or "email",
    )


def _generate_oauth_state() -> str:
    """Generates a cryptographically secure CSRF state token and stores it with TTL."""
    state = secrets.token_hex(32)
    # Purge expired states to prevent unbounded memory growth
    now = time.time()
    expired = [k for k, exp in _oauth_state_store.items() if exp < now]
    for k in expired:
        del _oauth_state_store[k]
    _oauth_state_store[state] = now + OAUTH_STATE_TTL_SECONDS
    return state


def _validate_oauth_state(state: str) -> bool:
    """
    Validates and consumes a CSRF state token.
    Returns True if valid and not expired, False otherwise.
    One-time use: valid state is deleted from the store on first check.
    """
    expires_at = _oauth_state_store.pop(state, None)
    if expires_at is None:
        return False  # Unknown state — possible CSRF or replay
    if time.time() > expires_at:
        return False  # Expired state
    return True


async def _exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """
    Exchanges the authorization code from Google for access_token + id_token.
    All secrets remain server-side; the frontend never sees them.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange code with Google token endpoint",
        )
    return resp.json()


def _verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """
    Verifies a Google id_token using google-auth's transport-agnostic verifier.
    Checks: signature (against Google's JWKS), audience (client_id), expiry, issuer.
    Returns the verified claims dict on success; raises HTTPException on failure.
    """
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        # google-auth raises ValueError for invalid/expired tokens
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google id_token verification failed: {exc}",
        )
    # Double-check issuer (google-auth validates this, but belt-and-suspenders)
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google id_token has unexpected issuer",
        )
    return claims


async def _upsert_google_user(db: AsyncSession, claims: Dict[str, Any]) -> User:
    """
    Atomic find-or-create for a Google-authenticated user.

    Strategy (in order):
      1. Look up by google_id — existing Google user, log them in.
      2. Look up by email — existing email/password user, link Google to their account.
      3. Create new user — first-time Google login.

    Race-condition safety: If two simultaneous requests for the same new Google
    account both reach step 3, the second INSERT will hit the UNIQUE constraint
    on google_id (or email) and raise IntegrityError. We catch that and re-fetch
    the row created by the first request — so only ONE account is ever created.
    """
    google_id   = claims["sub"]          # Google's stable, unique subject identifier
    email       = claims["email"].strip().lower()
    name        = claims.get("name", email.split("@")[0])
    picture_url = claims.get("picture")  # Profile photo URL

    # ── Step 1: Look up by google_id ──────────────────────────────────────────
    stmt = select(User).where(User.google_id == google_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user:
        # Refresh profile picture in case Google updated it
        if picture_url and user.profile_picture != picture_url:
            user.profile_picture = picture_url
            await db.commit()
            await db.refresh(user)
        return user

    # ── Step 2: Look up by email — link existing account ─────────────────────
    stmt = select(User).where(User.email == email)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user:
        # Link Google identity to the existing email/password account.
        # This is safe because Google has verified the email is theirs.
        if user.google_id and user.google_id != google_id:
            # Edge case: this account is linked to a DIFFERENT Google account.
            # Treat as error — do not silently take over another Google account.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is linked to a different Google account",
            )
        user.google_id      = google_id
        user.profile_picture = picture_url
        user.auth_provider  = "google"  # Now primarily a Google account
        try:
            await db.commit()
            await db.refresh(user)
        except IntegrityError:
            await db.rollback()
            # Another request linked this google_id concurrently — fetch result
            stmt = select(User).where(User.google_id == google_id)
            user = (await db.execute(stmt)).scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Account link conflict — please try again",
                )
        return user

    # ── Step 3: Create new user ───────────────────────────────────────────────
    new_user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=None,    # Google-only: no local password
        google_id=google_id,
        profile_picture=picture_url,
        role="student",         # Default role for new Google signups
        display_name=name,
        auth_provider="google",
    )
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
        return new_user
    except IntegrityError:
        # Race condition: another concurrent request just created this user.
        # Roll back and fetch the winner's row — still one account total.
        await db.rollback()
        stmt = select(User).where(User.google_id == google_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if not user:
            stmt = select(User).where(User.email == email)
            user = (await db.execute(stmt)).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User creation conflict — please try again",
            )
        return user


simulator = AerSimulator()


# -----------------------------------------------------------------------------
# 5. Endpoints
# -----------------------------------------------------------------------------
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}


@app.post(
    "/auth/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"]
)
async def auth_signup(req: SignupRequest, db: AsyncSession = Depends(get_db)) -> UserResponse:
    """Registers a new student or instructor user with bcrypt password hashing."""
    email_clean = req.email.strip().lower()
    stmt = select(User).where(User.email == email_clean)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        # Give a specific message when the account was created via Google:
        # the user should click "Continue with Google" instead.
        if existing.auth_provider == "google" and not existing.password_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is registered via Google. Please use 'Continue with Google' to log in.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        id=uuid.uuid4(),
        email=email_clean,
        password_hash=hash_password(req.password),
        role=req.role,
        display_name=req.display_name.strip(),
        auth_provider="email",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return _make_user_response(user)


@app.post(
    "/auth/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"]
)
async def auth_login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Verifies credentials and returns a 24-hour signed JWT access token."""
    email_clean = req.email.strip().lower()
    stmt = select(User).where(User.email == email_clean)
    user = (await db.execute(stmt)).scalar_one_or_none()

    generic_401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not user:
        raise generic_401

    # Guard: Google-only accounts have no password hash.
    # Return a clear message so the user knows to use Google login.
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account was created with Google. Please use 'Continue with Google' to log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(req.password, user.password_hash):
        raise generic_401

    token = create_access_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=_make_user_response(user),
    )


# -----------------------------------------------------------------------------
# Google OAuth 2.0 Endpoints
# -----------------------------------------------------------------------------
@app.get(
    "/auth/google",
    tags=["Authentication"],
    summary="Initiate Google OAuth 2.0 login flow",
    description="Redirects the browser to Google's consent screen. "
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured.",
)
async def auth_google_initiate() -> RedirectResponse:
    """
    Step 1 of Google OAuth: generate CSRF state token and redirect to Google.
    The frontend simply navigates `window.location.href` to this endpoint.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Google OAuth is not configured on this server. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
            ),
        )

    state = _generate_oauth_state()

    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        # openid  — required for id_token (verified identity)
        # email   — we need the email address
        # profile — display name and profile picture
        "scope":         "openid email profile",
        "state":         state,
        # online access_type — we don't need refresh tokens
        "access_type":   "online",
    }
    google_url = GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=google_url, status_code=302)


@app.get(
    "/auth/google/callback",
    tags=["Authentication"],
    summary="Google OAuth 2.0 callback — validates code, upserts user, issues JWT",
)
async def auth_google_callback(
    code:  Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    Step 2 of Google OAuth: Google redirects here with ?code=...&state=... after consent.

    Security validations (in order):
      1. User did not cancel (no ?error=access_denied from Google)
      2. state matches a known, non-expired CSRF token (prevents CSRF attacks)
      3. id_token is cryptographically verified against Google's JWKS

    On success: issues JWT, redirects browser to FRONTEND_URL/#token=<jwt>
    On failure: redirects browser to FRONTEND_URL/#error=<code>
    Fragment (#...) is never sent to the server — it's client-side only.
    """
    # ── Google reported an error (e.g., user cancelled consent) ───────────────
    if error:
        error_code = "google_cancelled" if error == "access_denied" else "google_error"
        return RedirectResponse(url=f"{FRONTEND_URL}/#error={error_code}", status_code=302)

    # ── Missing required parameters ────────────────────────────────────────────
    if not code or not state:
        return RedirectResponse(url=f"{FRONTEND_URL}/#error=token_invalid", status_code=302)

    # ── CSRF state validation — one-time use, TTL-checked ─────────────────────
    if not _validate_oauth_state(state):
        return RedirectResponse(url=f"{FRONTEND_URL}/#error=token_invalid", status_code=302)

    # ── Exchange authorization code for tokens ─────────────────────────────────
    try:
        token_data = await _exchange_code_for_tokens(code)
    except HTTPException:
        return RedirectResponse(url=f"{FRONTEND_URL}/#error=google_error", status_code=302)

    id_token_str = token_data.get("id_token")
    if not id_token_str:
        return RedirectResponse(url=f"{FRONTEND_URL}/#error=google_error", status_code=302)

    # ── Cryptographically verify the id_token ─────────────────────────────────
    # This is the authoritative proof of identity — we NEVER trust frontend claims.
    try:
        claims = _verify_google_id_token(id_token_str)
    except HTTPException:
        return RedirectResponse(url=f"{FRONTEND_URL}/#error=token_invalid", status_code=302)

    # ── Google must have verified the email ────────────────────────────────────
    if not claims.get("email_verified"):
        return RedirectResponse(url=f"{FRONTEND_URL}/#error=google_error", status_code=302)

    # ── Upsert user (find-or-create, race-safe) ────────────────────────────────
    try:
        user = await _upsert_google_user(db, claims)
    except HTTPException as exc:
        error_code = "email_conflict" if exc.status_code == 409 else "google_error"
        return RedirectResponse(url=f"{FRONTEND_URL}/#error={error_code}", status_code=302)

    # ── Issue JWT (identical format to email/password login) ───────────────────
    jwt_token = create_access_token(user.id, user.role)

    # ── Redirect frontend with token in URL fragment ───────────────────────────
    # Fragment (#...) is never sent to the server — the frontend reads it, stores
    # it in React state (in-memory only), then immediately clears it from the URL.
    return RedirectResponse(url=f"{FRONTEND_URL}/#token={jwt_token}", status_code=302)


@app.get(
    "/auth/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Return current authenticated user info from JWT",
)
async def auth_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Returns the currently authenticated user's profile.
    Useful for the frontend to display user info without a full re-login.
    """
    return _make_user_response(current_user)


@app.get(
    "/instructor/dashboard",
    response_model=InstructorDashboardResponse,
    status_code=status.HTTP_200_OK,
    tags=["Instructor"]
)
async def instructor_dashboard(
    instructor: User = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> InstructorDashboardResponse:
    """
    Cohort-wide analytics for instructors:
    - Most-missed concept (lowest average mastery across students)
    - Most common misconception (highest-frequency tag in misconception_events)
    - Students needing intervention (attempts >= 3 and mastery_score < 0.3)
    """
    # 1. Total students count
    total_students_stmt = select(func.count(User.id)).where(User.role == "student")
    total_students = (await db.execute(total_students_stmt)).scalar() or 0

    # 2. Most-missed concept (lowest average mastery among attempted concepts)
    missed_stmt = (
        select(
            Concept.name,
            func.avg(ConceptMastery.mastery_score).label("avg_score"),
            func.sum(ConceptMastery.attempts).label("tot_attempts")
        )
        .join(ConceptMastery, Concept.id == ConceptMastery.concept_id)
        .group_by(Concept.id, Concept.name)
        .order_by(func.avg(ConceptMastery.mastery_score).asc())
        .limit(1)
    )
    missed_res = (await db.execute(missed_stmt)).first()
    most_missed = None
    if missed_res:
        most_missed = MostMissedConcept(
            concept_name=missed_res[0],
            avg_mastery=round(float(missed_res[1]), 3),
            total_attempts=int(missed_res[2] or 0),
        )

    # 3. Most common misconception (highest-count tag from misconception_events)
    tag_stmt = (
        select(
            MisconceptionTag.name,
            MisconceptionTag.display_label,
            func.count(MisconceptionEvent.id).label("event_count")
        )
        .join(MisconceptionEvent, MisconceptionTag.id == MisconceptionEvent.tag_id)
        .group_by(MisconceptionTag.id, MisconceptionTag.name, MisconceptionTag.display_label)
        .order_by(func.count(MisconceptionEvent.id).desc())
        .limit(1)
    )
    tag_res = (await db.execute(tag_stmt)).first()
    most_common = None
    if tag_res:
        most_common = MostCommonMisconception(
            tag_name=tag_res[0],
            display_label=tag_res[1],
            event_count=int(tag_res[2]),
        )

    # 4. Students needing intervention (attempts >= 3 and mastery_score < 0.3)
    interv_stmt = (
        select(
            User.id,
            User.display_name,
            User.email,
            Concept.name,
            ConceptMastery.attempts,
            ConceptMastery.mastery_score
        )
        .join(User, ConceptMastery.user_id == User.id)
        .join(Concept, ConceptMastery.concept_id == Concept.id)
        .where(ConceptMastery.attempts >= 3, ConceptMastery.mastery_score < 0.3)
        .order_by(ConceptMastery.mastery_score.asc(), ConceptMastery.attempts.desc())
    )
    interv_res = (await db.execute(interv_stmt)).all()
    students_needing_intervention = []
    for row in interv_res:
        user_id_val = row[0]
        latest_event_stmt = (
            select(MisconceptionTag.display_label)
            .join(MisconceptionEvent, MisconceptionTag.id == MisconceptionEvent.tag_id)
            .where(MisconceptionEvent.user_id == user_id_val)
            .order_by(MisconceptionEvent.created_at.desc())
            .limit(1)
        )
        latest_tag = (await db.execute(latest_event_stmt)).scalar_one_or_none()
        students_needing_intervention.append(
            StudentInterventionItem(
                student_id=user_id_val,
                name=row[1],
                email=row[2],
                concept_name=row[3],
                attempts=row[4],
                mastery_score=round(float(row[5]), 2),
                most_recent_misconception=latest_tag or "None recorded",
            )
        )

    return InstructorDashboardResponse(
        status="ok",
        message=f"Welcome instructor {instructor.display_name}",
        instructor_id=instructor.id,
        most_missed_concept=most_missed,
        most_common_misconception=most_common,
        students_needing_intervention=students_needing_intervention,
        total_students=total_students,
    )



@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Users"])
async def create_user(req: UserCreateRequest, db: AsyncSession = Depends(get_db)):
    """Creates a user record in PostgreSQL."""
    if req.role not in ("student", "instructor"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'student' or 'instructor'"
        )

    # Check for existing email
    stmt = select(User).where(User.email == req.email)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return UserResponse(
            id=existing.id,
            email=existing.email,
            role=existing.role,
            display_name=existing.display_name
        )

    new_user = User(
        email=req.email,
        password_hash=req.password_hash,
        role=req.role,
        display_name=req.display_name
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        display_name=new_user.display_name
    )


@app.post(
    "/circuits",
    response_model=CircuitResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Circuits"]
)
async def create_circuit(
    req: CircuitCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> CircuitResponse:
    """Creates and persists a quantum circuit definition owned by authenticated user."""
    if req.qubit_count <= 0 or req.qubit_count > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"qubit_count must be between 1 and 8 (inclusive), got {req.qubit_count}",
        )

    sorted_gates = sorted(req.gates, key=lambda g: g.step_index)
    circuit = Circuit(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        qubit_count=req.qubit_count,
        gates=[g.model_dump() for g in sorted_gates],
        code_form=req.code_form,
    )
    db.add(circuit)
    await db.commit()
    await db.refresh(circuit)

    return CircuitResponse(
        id=circuit.id,
        qubit_count=circuit.qubit_count,
        gates=circuit.gates,
        owner_id=circuit.owner_id,
    )


@app.post(
    "/circuits/simulate",
    response_model=CircuitSimulateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Simulation"]
)
async def simulate_circuit(
    req: CircuitSimulateRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db)
) -> CircuitSimulateResponse:
    """
    Simulates a quantum circuit, persists the circuit (if new) and append-only simulation run.
    Returns the simulation results alongside circuit_id and run_id.
    """
    start_time = time.perf_counter()

    # 1. Validation
    if req.qubit_count < 1 or req.qubit_count > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"qubit_count must be between 1 and 8, got {req.qubit_count}",
        )

    if req.noise_level < 0.0 or req.noise_level > 1.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"noise_level must be between 0.0 and 1.0, got {req.noise_level}",
        )

    if req.shots <= 0 or req.shots > 100000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"shots must be between 1 and 100000, got {req.shots}",
        )

    sorted_gates = sorted(req.gates, key=lambda g: g.step_index)

    for gate in sorted_gates:
        gate_type = gate.type.upper()
        if gate_type not in GATE_REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported gate type '{gate.type}' at step_index {gate.step_index}. "
                       f"Supported gates: {sorted(list(GATE_REGISTRY.keys()))}",
            )

        registry_entry = GATE_REGISTRY[gate_type]
        expected_qubits = registry_entry["expected_qubits"]

        for q in gate.target_qubits:
            if q < 0 or q >= req.qubit_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Gate '{gate.type}' at step_index {gate.step_index} references qubit index {q}, "
                           f"which is out of bounds for qubit_count {req.qubit_count}",
                )

        if gate_type == "CNOT":
            if len(gate.target_qubits) != 2 or gate.target_qubits[0] == gate.target_qubits[1]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"CNOT gate at step_index {gate.step_index} requires exactly 2 distinct qubits, "
                           f"got {gate.target_qubits}",
                )
        else:
            if len(gate.target_qubits) != expected_qubits:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Gate '{gate.type}' at step_index {gate.step_index} requires exactly "
                           f"{expected_qubits} target qubit(s), got {gate.target_qubits}",
                )

    # 2. Simulation Execution
    gates_applied: List[str] = []
    per_gate_states: List[GateState] = []
    qc_sim = QuantumCircuit(req.qubit_count)
    step_labels: List[str] = []

    for idx, gate in enumerate(sorted_gates):
        gate_type = gate.type.upper()
        entry = GATE_REGISTRY[gate_type]
        entry["apply"](qc_sim, gate.target_qubits, gate.params)

        formatted_name = entry["format"](gate.target_qubits, gate.params)
        gates_applied.append(formatted_name)

        label = f"step_{idx}"
        qc_sim.save_statevector(label=label)
        step_labels.append((formatted_name, label))

    if not sorted_gates:
        qc_sim.save_statevector(label="step_initial")
        step_labels.append(("INITIAL_STATE", "step_initial"))

    result_sv = simulator.run(qc_sim).result()
    sim_data = result_sv.data()

    for formatted_name, label in step_labels:
        sv_array = sim_data[label]
        per_gate_states.append(
            GateState(
                after_gate=formatted_name,
                statevector=serialize_statevector(sv_array),
            )
        )

    last_label = step_labels[-1][1]
    final_statevector = serialize_statevector(sim_data[last_label])

    # Measurement pass
    qc_meas = QuantumCircuit(req.qubit_count)
    for gate in sorted_gates:
        gate_type = gate.type.upper()
        GATE_REGISTRY[gate_type]["apply"](qc_meas, gate.target_qubits, gate.params)

    qc_meas.measure_all()
    if req.noise_level > 0.0:
        noise_model = NoiseModel()
        error_1q = depolarizing_error(req.noise_level, 1)
        error_2q = depolarizing_error(req.noise_level, 2)
        noise_model.add_all_qubit_quantum_error(error_1q, ["h", "x", "y", "z", "s", "t", "rx"])
        noise_model.add_all_qubit_quantum_error(error_2q, ["cx"])
        meas_sim = AerSimulator(noise_model=noise_model)
        result_meas = meas_sim.run(qc_meas, shots=req.shots).result()
    else:
        result_meas = simulator.run(qc_meas, shots=req.shots).result()
    raw_counts = result_meas.get_counts(qc_meas)

    total_states = 2 ** req.qubit_count
    measurement_counts: Dict[str, int] = {}
    if total_states <= 16:
        for i in range(total_states):
            bitstring = format(i, f"0{req.qubit_count}b")
            measurement_counts[bitstring] = raw_counts.get(bitstring, 0)
    else:
        measurement_counts = raw_counts

    duration_ms = max(1, int((time.perf_counter() - start_time) * 1000))

    # 3. Database Persistence
    effective_owner_id = current_user.id if current_user else (req.owner_id or None)
    circuit: Optional[Circuit] = None
    if req.circuit_id:
        stmt = select(Circuit).where(Circuit.id == req.circuit_id)
        circuit = (await db.execute(stmt)).scalar_one_or_none()

    if not circuit:
        circuit = Circuit(
            id=req.circuit_id or uuid.uuid4(),
            owner_id=effective_owner_id,
            qubit_count=req.qubit_count,
            gates=[g.model_dump() for g in sorted_gates],
            code_form=None,
        )
        db.add(circuit)
        await db.flush()

    run = SimulationRun(
        id=uuid.uuid4(),
        circuit_id=circuit.id,
        backend="aer",
        noise_level=req.noise_level,
        counts=measurement_counts,
        statevector=[amp.model_dump() for amp in final_statevector],
        per_gate_states=[s.model_dump() for s in per_gate_states],
        duration_ms=duration_ms,
    )
    db.add(run)
    await db.commit()
    await db.refresh(circuit)
    await db.refresh(run)

    return CircuitSimulateResponse(
        circuit_id=circuit.id,
        run_id=run.id,
        qubit_count=req.qubit_count,
        gates_applied=gates_applied,
        per_gate_states=per_gate_states,
        final_statevector=final_statevector,
        measurement_counts=measurement_counts,
    )


@app.post(
    "/predictions",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Pedagogy & Predictions"]
)
async def create_prediction(
    req: PredictionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> PredictionResponse:
    """Submits and locks in a student outcome prediction for a circuit."""
    # User is guaranteed by get_current_user
    user = current_user

    # Verify circuit exists
    circuit_stmt = select(Circuit).where(Circuit.id == req.circuit_id)
    circuit = (await db.execute(circuit_stmt)).scalar_one_or_none()
    if not circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit with id {req.circuit_id} does not exist",
        )

    # Find most recent simulation run if already executed
    run_stmt = (
        select(SimulationRun)
        .where(SimulationRun.circuit_id == req.circuit_id)
        .order_by(SimulationRun.created_at.desc())
        .limit(1)
    )
    latest_run = (await db.execute(run_stmt)).scalar_one_or_none()

    dist_to_store = dict(req.predicted_distribution)
    if req.concept:
        dist_to_store["_concept"] = req.concept

    prediction = Prediction(
        id=uuid.uuid4(),
        user_id=current_user.id,
        circuit_id=req.circuit_id,
        predicted_distribution=dist_to_store,
        actual_run_id=latest_run.id if latest_run else None,
    )
    db.add(prediction)
    await db.commit()
    await db.refresh(prediction)

    return PredictionResponse(
        id=prediction.id,
        user_id=prediction.user_id,
        circuit_id=prediction.circuit_id,
        predicted_distribution={k: v for k, v in prediction.predicted_distribution.items() if not k.startswith("_")},
        actual_run_id=prediction.actual_run_id,
    )


@app.get(
    "/predictions/{prediction_id}/compare",
    response_model=CompareResponse,
    status_code=status.HTTP_200_OK,
    tags=["Pedagogy & Predictions"]
)
async def compare_prediction(
    prediction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> CompareResponse:
    """Fetches a prediction and compares it side-by-side with the most recent actual simulation run."""
    pred_stmt = select(Prediction).where(Prediction.id == prediction_id)
    prediction = (await db.execute(pred_stmt)).scalar_one_or_none()
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction with id {prediction_id} not found",
        )

    run_stmt = (
        select(SimulationRun)
        .where(SimulationRun.circuit_id == prediction.circuit_id)
        .order_by(SimulationRun.created_at.desc())
        .limit(1)
    )
    latest_run = (await db.execute(run_stmt)).scalar_one_or_none()
    if not latest_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No simulation run exists yet for circuit {prediction.circuit_id}",
        )

    # If prediction wasn't linked to a run yet, link it now
    if not prediction.actual_run_id:
        prediction.actual_run_id = latest_run.id
        await db.commit()

    # Normalize raw measurement counts to probability distribution (0-1 scale)
    raw_counts: Dict[str, int] = latest_run.counts or {}
    total_shots = sum(raw_counts.values())
    if total_shots > 0:
        normalized_actual = {
            k: round(v / total_shots, 3) for k, v in raw_counts.items()
        }
    else:
        normalized_actual = {k: 0.0 for k in raw_counts.keys()}

    # Evaluate prediction accuracy against actual distribution (tolerance 0.08)
    is_correct = True
    if not prediction.predicted_distribution:
        is_correct = False
    else:
        for state, pred_p in prediction.predicted_distribution.items():
            if state.startswith("_"):
                continue
            act_p = normalized_actual.get(state, 0.0)
            if abs(pred_p - act_p) > 0.08:
                is_correct = False
                break

    # Extract concept name stored as _concept sentinel in predicted_distribution JSONB.
    # Falls back to 'entanglement' to preserve backward compatibility with older records.
    concept_name = prediction.predicted_distribution.get("_concept", "entanglement")

    # Update concept mastery for the student using the concept derived from this prediction.
    await update_concept_mastery(
        db=db,
        user_id=prediction.user_id,
        concept_name=concept_name,
        is_success=is_correct,
    )

    print(f"[DEBUG compare_prediction] is_correct={is_correct}, concept_name={concept_name}", flush=True)

    # If prediction was incorrect, classify misconception via LLM asynchronously
    classified_tag = None
    if not is_correct:
        try:
            classified_tag = await classify_misconception(
                db=db,
                user_id=prediction.user_id,
                prediction_dist={k: v for k, v in prediction.predicted_distribution.items() if not k.startswith("_")},
                actual_dist=normalized_actual,
                concept_name=concept_name,
            )
        except Exception as exc:
            print(f"[ERROR classify_misconception] {exc}", flush=True)

    return CompareResponse(
        predicted={k: v for k, v in prediction.predicted_distribution.items() if not k.startswith("_")},
        actual=normalized_actual,
        circuit_id=prediction.circuit_id,
        run_id=latest_run.id,
        misconception_tag=classified_tag,
    )



# -----------------------------------------------------------------------------
# 6. Anonymous User Helper
# -----------------------------------------------------------------------------
ANONYMOUS_EMAIL = "anonymous@egreen.local"


@app.get("/users/anonymous", response_model=UserResponse, tags=["Users"])
async def get_or_create_anonymous_user(db: AsyncSession = Depends(get_db)):
    """Returns the anonymous student user, creating it if it doesn't exist."""
    stmt = select(User).where(User.email == ANONYMOUS_EMAIL)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        user = User(
            email=ANONYMOUS_EMAIL,
            password_hash="anon_no_password",
            role="student",
            display_name="Anonymous Student",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
    )


# -----------------------------------------------------------------------------
# 6.5. Experiments / Debug Challenges
# -----------------------------------------------------------------------------
@app.get(
    "/experiments/debug/bell-state",
    status_code=status.HTTP_200_OK,
    tags=["Experiments"],
)
async def get_debug_bell_state() -> Dict[str, Any]:
    """
    Returns a hardcoded broken circuit meant to produce a Bell state but doesn't.
    X gate on q0 instead of H puts q0 in |1⟩, so CNOT flips q1 -> |11⟩ at 100%.
    """
    return {
        "prompt": "This circuit is supposed to create a Bell state (equal 00/11 measurement). Find and fix the bug.",
        "target_behavior": {
            "distribution": {"00": 0.5, "11": 0.5, "01": 0.0, "10": 0.0},
            "tolerance": 0.05,
        },
        "starter_circuit": {
            "qubit_count": 2,
            "gates": [
                {"type": "X", "target_qubits": [0], "params": None, "step_index": 0},
                {"type": "CNOT", "target_qubits": [0, 1], "params": None, "step_index": 1},
            ],
        },
    }


@app.get(
    "/experiments/guided/superposition",
    status_code=status.HTTP_200_OK,
    tags=["Experiments"],
)
async def get_guided_superposition() -> Dict[str, Any]:
    """
    Returns the guided Superposition module scaffold.

    Pedagogical intent: distinguish quantum superposition from classical
    ignorance. The H gate puts q0 into |+⟩ = (|0⟩+|1⟩)/√2. Measuring a
    2-qubit register where only q0 has H applied gives |00⟩ and |01⟩ each
    with 50% probability (Qiskit bit-ordering: rightmost bit = q0).
    """
    return {
        "concept": "superposition",
        "lesson_text": (
            "A classical bit is always either 0 or 1. A qubit can be in a superposition of both "
            "at once — not 'secretly one of the two and we just don't know which,' but genuinely "
            "in a combined state until it's measured. The Hadamard (H) gate takes a qubit starting "
            "at |0⟩ and puts it into an equal superposition of |0⟩ and |1⟩. When you measure it, "
            "you get 0 or 1 each with 50% probability — but before measurement, it isn't correct "
            "to say the qubit 'is' one or the other."
        ),
        "prediction_prompt": "If you apply H to q0 and measure, what distribution do you expect?",
        "target_behavior": {
            "distribution": {"00": 0.5, "01": 0.5, "10": 0.0, "11": 0.0},
            "tolerance": 0.05,
        },
        "starter_circuit": {
            "qubit_count": 2,
            "gates": [],
        },
    }


@app.get(
    "/experiments/guided/gates",
    status_code=status.HTTP_200_OK,
    tags=["Experiments"],
)
async def get_guided_gates() -> Dict[str, Any]:
    """
    Returns the guided Gates module scaffold.

    Pedagogical intent: introduce single-qubit gates (X, Z) and contrast
    deterministic state transitions (X gate) with superposition (H gate).
    X flips q0 from |0⟩ to |1⟩ deterministically: measuring a 2-qubit register
    gives |01⟩ with 100% probability (Qiskit bit-ordering: rightmost bit = q0).
    """
    return {
        "concept": "gates",
        "lesson_text": (
            "You've already used H (creates superposition) and CNOT (creates entanglement between two qubits). "
            "There are other single-qubit gates worth knowing: X flips |0⟩ and |1⟩ (like a classical NOT). "
            "Z leaves |0⟩ alone but flips the sign of |1⟩'s amplitude — this doesn't change measurement probabilities "
            "on its own, but it matters once qubits interfere with each other. Try applying gates in different orders "
            "and see how the final state changes — gate order matters in quantum circuits, just like it does with "
            "matrix multiplication."
        ),
        "prediction_prompt": "If you apply X to q0 then measure, what do you expect?",
        "target_behavior": {
            "distribution": {"00": 0.0, "01": 1.0, "10": 0.0, "11": 0.0},
            "tolerance": 0.05,
        },
        "starter_circuit": {
            "qubit_count": 2,
            "gates": [],
        },
    }


# -----------------------------------------------------------------------------
# 7. AI Tutor Endpoint
# -----------------------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def get_gemini_api_key() -> str:
    """Retrieve Gemini API key from environment variable or .env file."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


@app.post(
    "/tutor/ask",
    response_model=TutorAskResponse,
    status_code=status.HTTP_200_OK,
    tags=["AI Tutor"]
)
async def tutor_ask(
    req: TutorAskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TutorAskResponse:
    """
    AI Tutor: answers student questions grounded in the actual circuit and simulation data.
    Uses Gemini 2.5 Flash via REST API. Reuses tutor_prompt.py's exact prompt template.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GEMINI_API_KEY is not configured on the server.",
        )

    # 1. Load circuit from DB
    circuit_stmt = select(Circuit).where(Circuit.id == req.circuit_id)
    circuit = (await db.execute(circuit_stmt)).scalar_one_or_none()
    if not circuit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit with id {req.circuit_id} not found",
        )

    # 2. Load simulation run (specific run_id or most recent)
    if req.run_id:
        run_stmt = select(SimulationRun).where(SimulationRun.id == req.run_id)
    else:
        run_stmt = (
            select(SimulationRun)
            .where(SimulationRun.circuit_id == req.circuit_id)
            .order_by(SimulationRun.created_at.desc())
            .limit(1)
        )
    sim_run = (await db.execute(run_stmt)).scalar_one_or_none()
    if not sim_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No simulation run exists yet for circuit {req.circuit_id}",
        )

    # 3. Load most recent prediction for this circuit (optional context)
    pred_stmt = (
        select(Prediction)
        .where(Prediction.circuit_id == req.circuit_id)
        .order_by(Prediction.locked_at.desc())
        .limit(1)
    )
    prediction = (await db.execute(pred_stmt)).scalar_one_or_none()

    # 4. Derive gates_applied strings from circuit.gates JSONB
    gates_applied = []
    sorted_gates = sorted(circuit.gates, key=lambda g: g.get("step_index", 0))
    for g in sorted_gates:
        gate_type = g["type"].upper()
        entry = GATE_REGISTRY.get(gate_type)
        if entry:
            gates_applied.append(entry["format"](g["target_qubits"], g.get("params")))
        else:
            gates_applied.append(f"{g['type']}({g['target_qubits']})")

    # 5. Extract statevector as flat list of floats from sim_run.statevector JSONB
    sv_flat = []
    if sim_run.statevector:
        for amp in sim_run.statevector:
            if isinstance(amp, dict):
                sv_flat.append(amp.get("real", 0.0))
            else:
                sv_flat.append(float(amp))

    # 6. Assemble prompt using tutor_prompt.py's exact template
    user_message = format_tutor_user_message(
        gates_applied=gates_applied,
        statevector=sv_flat,
        measurement_counts=sim_run.counts or {},
        student_question=req.question,
    )

    # Optionally append prediction context if available
    if prediction:
        user_message += f"\n\nStudent's prior prediction: {prediction.predicted_distribution}"

    # Debug Mode System Prompt Adjustment
    system_prompt = SYSTEM_PROMPT
    if req.experiment_type == "debug":
        counts = sim_run.counts or {}
        total_shots = sum(counts.values()) or 1
        p00 = counts.get("00", 0) / total_shots
        p11 = counts.get("11", 0) / total_shots
        # Target is equal 00/11 (~50% each)
        is_fixed = (abs(p00 - 0.5) <= 0.08 and abs(p11 - 0.5) <= 0.08)

        if is_fixed:
            system_prompt += (
                "\n\nThis is a debugging exercise. The student has successfully fixed the circuit to produce the target Bell state "
                "with an equal ~50/50 split on |00⟩ and |11⟩! Confirm that the circuit is now correct, celebrate that they resolved "
                "the bug, and concisely explain why their fix (superposition on q0 before CNOT) works."
            )
            user_message += "\n\nContext: Student's circuit now achieves the target Bell state behavior (|00⟩ ≈ 50%, |11⟩ ≈ 50%)."
        else:
            system_prompt += (
                "\n\nThis is a debugging exercise. The student's circuit does not match the target behavior. "
                "Your first response must NOT reveal the fix directly — ask a diagnostic question that points them "
                "toward inspecting the specific part of the circuit likely causing the mismatch, based on the actual "
                "gates and actual vs. target distributions provided. Only if the student explicitly asks for the answer "
                "or says they're stuck after a hint, may you state the fix directly."
            )
            user_message += (
                "\n\nContext: Debugging mode. Target behavior is a Bell state: equal 50% distribution between |00⟩ and |11⟩. "
                f"Observed distribution: {counts}. The circuit has NOT yet achieved the target."
            )

    # Superposition Module System Prompt Adjustment
    if req.experiment_type == "superposition":
        counts = sim_run.counts or {}
        total_shots = sum(counts.values()) or 1
        p00 = counts.get("00", 0) / total_shots
        p01 = counts.get("01", 0) / total_shots
        # Target: equal 50/50 on |00⟩ and |01⟩ (H on q0 only, q1 stays |0⟩)
        is_superposition_correct = (abs(p00 - 0.5) <= 0.08 and abs(p01 - 0.5) <= 0.08)

        if is_superposition_correct:
            system_prompt += (
                "\n\nThis is a Superposition guided module. The student has correctly predicted or "
                "observed an equal 50/50 distribution on |00⟩ and |01⟩ — the signature of a single "
                "qubit in a Hadamard superposition. Confirm their understanding is correct. Emphasize "
                "that this is NOT classical ignorance: the qubit was genuinely in both states until "
                "measurement collapsed it. Optionally hint at the next concept: what happens if you "
                "entangle two qubits in superposition (Bell state)."
            )
        else:
            system_prompt += (
                "\n\nThis is a Superposition guided module. The student's circuit or prediction does "
                "not yet show the expected equal 50/50 split on |00⟩ and |01⟩. Ask a Socratic "
                "diagnostic question about which gate creates superposition and what that means for "
                "the measurement distribution. Do NOT directly tell them to use H — guide them to "
                "realize it through a question about the qubit's state before measurement."
            )
        user_message += (
            f"\n\nContext: Superposition module. Target is |00⟩ ≈ 50%, |01⟩ ≈ 50% (H on q0). "
            f"Observed distribution: {counts}."
        )

    # Gates Module System Prompt Adjustment
    if req.experiment_type == "gates":
        counts = sim_run.counts or {}
        total_shots = sum(counts.values()) or 1
        p01 = counts.get("01", 0) / total_shots
        # Target: deterministic 100% on |01⟩ (X on q0, q1 stays |0⟩)
        is_gates_correct = p01 >= 0.92

        if is_gates_correct:
            system_prompt += (
                "\n\nThis is a Gates guided module. The student has correctly observed or predicted "
                "that the X gate deterministically flips q0 from |0⟩ to |1⟩, resulting in state |01⟩ ~ 100%. "
                "Confirm their understanding is correct: emphasize that X is a deterministic bit-flip, "
                "in contrast to H which creates a superposition."
            )
        else:
            system_prompt += (
                "\n\nThis is a Gates guided module. The student's circuit or prediction does not yet show "
                "the deterministic bit-flip result (|01⟩ = 1.0). Ask a Socratic diagnostic question "
                "about what the X gate does compared to H or classical NOT, without giving away the direct answer."
            )
        user_message += (
            f"\n\nContext: Gates module. Target is |01⟩ = 1.0 (X on q0). "
            f"Observed distribution: {counts}."
        )

    # Noise Lab System Prompt Adjustment
    if req.experiment_type == "noise" or req.noise_level is not None:
        noise_pct = int(round((req.noise_level if req.noise_level is not None else (sim_run.noise_level or 0.0)) * 100))
        counts = sim_run.counts or {}
        ideal_str = str(req.ideal_counts) if req.ideal_counts else "Ideal Bell state (00: ~50%, 11: ~50%, 01: 0%, 10: 0%)"
        system_prompt += (
            "\n\nThis is a Noise Lab experiment. The student is investigating the effect of depolarizing quantum noise on the circuit. "
            "Explain specifically how this depolarizing noise percentage caused the observed count discrepancies between the ideal and noisy runs "
            "(specifically noting why bitstrings like |01⟩ and |10⟩ that have 0 amplitude in the ideal statevector begin to leak into the measurement distribution). "
            "You MUST ground your response directly in the actual noise percentage and the exact measurement count numbers provided, "
            "avoiding generic statements like 'noise causes errors'."
        )
        user_message += (
            f"\n\nContext: Noise Lab. Depolarizing noise level: {noise_pct}%. "
            f"Ideal noise-free counts: {ideal_str}. "
            f"Noisy observed counts: {counts}."
        )

    # 7. Call Gemini 2.5 Flash REST API
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GEMINI_URL,
                params={"key": api_key},
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()

        # Extract text from Gemini response
        candidates = result.get("candidates", [])
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini API returned no candidates.",
            )
        parts = candidates[0].get("content", {}).get("parts", [])
        text = parts[0].get("text", "") if parts else ""
        if not text:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini API returned empty response text.",
            )

        return TutorAskResponse(response=text)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            # 429 → 503: transient quota exhaustion, not a permanent gateway failure.
            # Clients / tests should treat 503 as "retry later" and skip-not-fail.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI Tutor is momentarily busy (rate limit reached). Please wait a moment and try asking again.",
            )
        detail = f"AI Tutor service error ({e.response.status_code})."
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach Gemini API: {str(e)}",
        )


# -----------------------------------------------------------------------------
# 8. Concept Progress & Mastery Helper and Endpoints
# -----------------------------------------------------------------------------
async def update_concept_mastery(
    db: AsyncSession,
    user_id: uuid.UUID,
    concept_name: str,
    is_success: bool,
    delta: float = 0.1,
) -> Optional[ConceptMastery]:
    """
    Updates or initializes student concept mastery:
    - Increments attempts on every evaluated learning event.
    - If is_success is True: increments mastery_score by delta (default +0.1, capped at 1.0).
    - If is_success is False: attempts incremented, mastery_score does NOT decrease.
    """
    concept_stmt = select(Concept).where(func.lower(Concept.name) == concept_name.lower())
    concept = (await db.execute(concept_stmt)).scalar_one_or_none()
    if not concept:
        return None

    mastery_stmt = select(ConceptMastery).where(
        ConceptMastery.user_id == user_id,
        ConceptMastery.concept_id == concept.id,
    )
    mastery = (await db.execute(mastery_stmt)).scalar_one_or_none()

    if not mastery:
        init_score = min(1.0, round(delta, 2)) if is_success else 0.0
        mastery = ConceptMastery(
            user_id=user_id,
            concept_id=concept.id,
            mastery_score=init_score,
            attempts=1,
        )
        db.add(mastery)
    else:
        mastery.attempts += 1
        if is_success:
            mastery.mastery_score = min(1.0, round(mastery.mastery_score + delta, 2))
        mastery.last_updated = func.now()

    await db.commit()
    await db.refresh(mastery)
    return mastery


async def classify_misconception(
    db: AsyncSession,
    user_id: uuid.UUID,
    prediction_dist: Dict[str, float],
    actual_dist: Dict[str, float],
    concept_name: str = "entanglement",
) -> Optional[str]:
    print(f"[DEBUG classify_misconception ENTRY] concept_name='{concept_name}'", flush=True)
    """
    Calls LLM (Gemini) when a student prediction diverges beyond tolerance.
    Constrains choice to the fixed taxonomy of misconception tags for the concept.
    Logs result to misconception_events (source: 'ai_classified').
    Fail-safe: if LLM fails, times out, or returns invalid tag, logs nothing and returns None.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        print("[DEBUG classify_misconception] GEMINI_API_KEY is missing or empty!", flush=True)
        return None

    try:
        concept_stmt = select(Concept).where(func.lower(Concept.name) == concept_name.lower())
        concept = (await db.execute(concept_stmt)).scalar_one_or_none()
        if not concept:
            print(f"[DEBUG classify_misconception] concept '{concept_name}' not found", flush=True)
            return None

        tags_stmt = select(MisconceptionTag).where(MisconceptionTag.concept_id == concept.id)
        tags = (await db.execute(tags_stmt)).scalars().all()
        if not tags:
            print(f"[DEBUG classify_misconception] no tags for concept '{concept.name}'", flush=True)
            return None

        TAG_DESCRIPTIONS: Dict[str, str] = {
            "confuses_superposition_with_classical_probability": (
                "The student treats quantum superposition as a deterministic classical outcome "
                "(e.g. predicting 100% certainty on a single basis state like |00⟩=1.0) or misunderstands quantum probability as classical certainty."
            ),
            "expects_correlation_without_entangling_gate": (
                "The student expects independent, uncorrelated uniform probabilities across all basis states "
                "(e.g., |00⟩=0.25, |01⟩=0.25, |10⟩=0.25, |11⟩=0.25) as if qubits were in independent superpositions without entanglement."
            ),
            "misreads_zero_amplitude_as_impossible_outcome": (
                "The student misinterprets destructive interference or zero amplitude as an intrinsically impossible measurement basis."
            ),
            "believes_qubit_is_secretly_definite_before_measurement": (
                "The student believes the qubit was secretly in a definite 0 or 1 state all along prior to measurement "
                "(e.g. predicting 100% certainty on a single basis state like |00⟩=1.0 when measuring a superposition)."
            ),
            "conflates_amplitude_with_probability": (
                "The student treats the complex amplitude value directly as the measurement probability without squaring the magnitude."
            ),
            "expects_same_outcome_every_run": (
                "The student expects a deterministic, identical outcome on every run "
                "(e.g. predicting 100% certainty on a single basis state like |00⟩=1.0 when measuring a superposition)."
            ),
            "believes_x_creates_superposition": (
                "The student confuses the Pauli-X gate with the Hadamard (H) gate, incorrectly predicting a superposition "
                "(e.g. predicting a 50/50 split like |00⟩=0.5, |01⟩=0.5) when X acts deterministically as a bit flip."
            ),
            "ignores_gate_order": (
                "The student does not account for gate application order affecting the resulting quantum state and measurement probabilities."
            ),
            "expects_z_to_change_measurement_probability": (
                "The student expects the Pauli-Z gate to alter measurement outcome probabilities in the computational basis on its own, "
                "confusing relative phase with measurement statistics."
            ),
        }

        tag_names = [t.name for t in tags]
        tag_lines = "\n".join([f"- {t.name}: {TAG_DESCRIPTIONS.get(t.name, t.display_label)}" for t in tags])

        prompt = (
            f"You are an expert quantum education diagnostic system analyzing a student's misconception.\n\n"
            f"Context: Student is exploring the quantum concept '{concept.name}'.\n"
            f"Expected ideal distribution: {actual_dist}\n"
            f"Student's predicted distribution: {prediction_dist}\n\n"
            f"Available Misconception Taxonomy for '{concept.name}':\n"
            f"{tag_lines}\n\n"
            f"CRITICAL RULES:\n"
            f"1. Compare the student's predicted distribution {prediction_dist} with the expected ideal distribution {actual_dist}.\n"
            f"2. If the student's prediction clearly matches one of the misconceptions above, return ONLY that exact tag name.\n"
            f"3. If NONE of the available tags fit (e.g. if the student predicted an anti-correlated state |01⟩ and |10⟩ when expecting |00⟩ and |11⟩, which is an unlisted phase/correlation error), you MUST respond with 'none'.\n"
            f"4. Do NOT force-fit a tag if none fits. Respond ONLY with a single tag identifier ({', '.join(tag_names)}) or 'none'. No markdown, no punctuation, no extra words."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 1024,
            },
        }

        data = None
        for attempt in range(4):
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    GEMINI_URL,
                    params={"key": api_key},
                    json=payload,
                )
                print(f"[DEBUG classify_misconception] attempt {attempt+1} status={resp.status_code}", flush=True)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                elif resp.status_code in (429, 503):
                    wait_time = 3.0 * (attempt + 1)
                    print(f"[DEBUG classify_misconception] rate limit hit (status {resp.status_code}), waiting {wait_time}s...", flush=True)
                    await asyncio.sleep(wait_time)
                else:
                    print(f"[DEBUG classify_misconception] Gemini error body: {resp.text}", flush=True)
                    return None

        if not data:
            return None

        candidates = data.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        raw_text = parts[0].get("text", "").strip().lower() if parts else ""
        cleaned = raw_text.replace("`", "").replace('"', "").replace("'", "").strip()
        print(f"[DEBUG classify_misconception] raw_text='{raw_text}', cleaned='{cleaned}'", flush=True)

        if cleaned == "none" or "none" in cleaned:
            return None

        matched_tag = next((t for t in tags if t.name.lower() == cleaned), None)
        if not matched_tag:
            matched_tag = next((t for t in tags if t.name.lower() in cleaned), None)

        if matched_tag:
            event = MisconceptionEvent(
                id=uuid.uuid4(),
                user_id=user_id,
                tag_id=matched_tag.id,
                source="ai_classified",
            )
            db.add(event)
            await db.commit()
            return matched_tag.name

        return None
    except Exception:
        return None



@app.post(
    "/progress/event",
    response_model=ConceptProgressItem,
    status_code=status.HTTP_200_OK,
    tags=["Progress Tracking"]
)
async def record_progress_event(
    req: ProgressEventRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConceptProgressItem:
    """
    Records a learning progress event (e.g., debug challenge solved, noise lab session completed).
    Increments attempts and updates concept mastery score.
    """
    mastery = await update_concept_mastery(
        db=db,
        user_id=current_user.id,
        concept_name=req.concept,
        is_success=req.success,
    )
    if not mastery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept '{req.concept}' not found",
        )

    concept = (await db.execute(select(Concept).where(Concept.id == mastery.concept_id))).scalar_one()
    status_tag = "Not Started" if mastery.attempts == 0 else ("Mastered" if mastery.mastery_score >= 0.8 else "In Progress")
    return ConceptProgressItem(
        concept_id=concept.id,
        name=concept.name,
        description=concept.description,
        mastery_score=mastery.mastery_score,
        attempts=mastery.attempts,
        status=status_tag,
        last_updated=mastery.last_updated,
    )


@app.get(
    "/progress/me",
    response_model=UserProgressResponse,
    status_code=status.HTTP_200_OK,
    tags=["Progress Tracking"]
)
async def get_my_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserProgressResponse:
    """
    Returns mastery status across all domain concepts for the authenticated student.
    Unattempted concepts return mastery_score 0.0 and status 'Not Started'.
    """
    concepts_stmt = select(Concept).order_by(Concept.name.asc())
    concepts = (await db.execute(concepts_stmt)).scalars().all()

    mastery_stmt = select(ConceptMastery).where(ConceptMastery.user_id == current_user.id)
    masteries = (await db.execute(mastery_stmt)).scalars().all()
    mastery_map = {m.concept_id: m for m in masteries}

    items: List[ConceptProgressItem] = []
    overall_mastered = 0

    for c in concepts:
        m = mastery_map.get(c.id)
        if m:
            score = m.mastery_score
            attempts = m.attempts
            last_updated = m.last_updated
            if attempts == 0:
                status_tag = "Not Started"
            elif score >= 0.8:
                status_tag = "Mastered"
                overall_mastered += 1
            else:
                status_tag = "In Progress"
        else:
            score = 0.0
            attempts = 0
            last_updated = None
            status_tag = "Not Started"

        items.append(
            ConceptProgressItem(
                concept_id=c.id,
                name=c.name,
                description=c.description,
                mastery_score=score,
                attempts=attempts,
                status=status_tag,
                last_updated=last_updated,
            )
        )

    return UserProgressResponse(
        concepts=items,
        overall_mastered=overall_mastered,
        total_concepts=len(concepts),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)



