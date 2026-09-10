# Technical Requirements Document (TRD)
## Interactive Quantum Algorithm Learning Platform (SIH)

**Status:** Draft v1
**Companion to:** SIH_Quantum_Platform_PRD.md
**Last updated:** September 11, 2026

---

## 1. Purpose & Scope

This document defines *how* the platform described in the PRD gets built: architecture, data models, APIs, backend integrations, AI tutor design, infrastructure, and non-functional requirements. It is the engineering-facing counterpart to the PRD's product-facing requirements.

Scope covers the MVP + WOW-tier features from the PRD. STRETCH features are noted but not designed in depth here.

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Web App)                        │
│  Circuit Builder UI | Code Editor | Visualizations | Dashboards │
└───────────────────────────────┬───────────────────────────────┘
                                 │ HTTPS / REST + WebSocket
┌───────────────────────────────▼───────────────────────────────┐
│                        API Gateway / BFF                        │
└───────┬──────────┬───────────┬───────────┬──────────┬─────────┘
        │           │           │           │          │
   ┌────▼───┐  ┌────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌───▼────┐
   │  Auth  │  │ Circuit │  │   Sim   │  │   AI    │  │Progress│
   │Service │  │ Service │  │Execution│  │ Tutor   │  │  &     │
   │        │  │         │  │ Service │  │ Service │  │Grading │
   └────────┘  └─────────┘  └────┬────┘  └────┬────┘  └────────┘
                                  │            │
                        ┌─────────▼──────┐  ┌──▼──────────────┐
                        │ Backend Adapter │  │ Knowledge Base   │
                        │      Layer      │  │ (curated content │
                        └────────┬────────┘  │ + circuit meta)  │
                 ┌───────────────┼──────────────┐  └──────────────┘
                 ▼               ▼              ▼
          Qiskit Aer      PennyLane/Cirq   Real QPU (IBM/qBraid,
          (MVP default)   (adapters)        optional, cached)
```

---

## 3. Tech Stack (proposed)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + TypeScript | Circuit builder as a canvas/SVG component; state visualizations via a charting lib (e.g. Plotly/D3) |
| Backend API | Python (FastAPI) | Natural fit alongside Qiskit/PennyLane/Cirq, which are all Python-native |
| Realtime updates | WebSocket (or polling fallback) | For near-instant circuit recompute feedback |
| Simulation | Qiskit Aer (MVP), PennyLane/Cirq adapters (stretch) | Run in a sandboxed worker process, not inline in the request thread |
| AI Tutor | LLM API (Claude) with structured context injection + retrieval from curated knowledge base | Never call the LLM with an unconstrained open prompt for physics claims |
| Knowledge base | Small structured store (JSON/DB) of verified concept explanations, algorithm definitions, circuit metadata | Faculty-reviewed content only |
| Database | PostgreSQL | Users, progress, circuits, submissions, misconception tags |
| Auth | JWT-based session auth, 2 roles (student, instructor) | No SSO/multi-tenant for MVP |
| Deployment | Containerized (Docker), deployed to a cloud provider (per PS cloud requirement) | Separate scaling for API vs. simulation workers |
| Real hardware (optional) | IBM Quantum / qBraid API, invoked offline and cached — not a live demo dependency | See §9 |

---

## 4. Core Data Models

### 4.1 User
```
User {
  id, email, password_hash, role [student|instructor],
  created_at
}
```

### 4.2 Circuit
```
Circuit {
  id, owner_id, module_id (nullable),
  representation: {
    qubits: int,
    gates: [ { type, target_qubits[], params?, step_index } ]
  },
  code_form: string,           // generated/edited Qiskit code
  created_at, updated_at
}
```

### 4.3 SimulationRun
```
SimulationRun {
  id, circuit_id, backend [aer|pennylane|cirq|real_ibm],
  noise_level: float (0.0–1.0, default 0),
  result: {
    statevector: [...],
    counts: { "00": int, "11": int, ... },
    per_gate_states: [ statevector_after_each_gate ]  // for amplitude scrubber
  },
  duration_ms, created_at
}
```

### 4.4 Prediction
```
Prediction {
  id, user_id, experiment_id, circuit_id,
  predicted_distribution: { "00": float, ... } | selected_option_id,
  actual_run_id (fk → SimulationRun),
  created_at
}
```

### 4.5 Experiment / Module
```
Module { id, title, concept_tags[], order }
Experiment {
  id, module_id, prompt, target_behavior,
  starter_circuit_id (nullable), type [guided|debug|challenge]
}
```

### 4.6 Progress / Mastery
```
ConceptMastery {
  user_id, concept_id, mastery_score (0–1),
  attempts, last_updated
}
```

### 4.7 Misconception Tag
```
MisconceptionEvent {
  id, user_id, experiment_id, tag_id,
  tag_id → { name, description }  // e.g. "confuses superposition with classical probability"
  created_at
}
```

### 4.8 AI Tutor Interaction (for audit/debugging)
```
TutorInteraction {
  id, user_id, experiment_id,
  context_snapshot: { circuit, code, sim_result, prediction, lesson_id, history_summary },
  question, response, grounded_sources[],
  created_at
}
```

---

## 5. API Surface (representative, not exhaustive)

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/login`, `/auth/signup` | POST | Basic auth |
| `/modules` | GET | List learning modules |
| `/experiments/{id}` | GET | Fetch experiment definition |
| `/circuits` | POST/PUT | Create/update a circuit (visual or code form) |
| `/circuits/{id}/simulate` | POST | Run simulation; body includes backend + noise_level |
| `/circuits/{id}/simulate/steps` | GET | Per-gate state sequence for amplitude scrubber |
| `/predictions` | POST | Submit a prediction before run |
| `/predictions/{id}/compare` | GET | Prediction vs. actual result diff |
| `/tutor/ask` | POST | Ask the AI tutor a question; server auto-attaches context |
| `/challenges/{id}/submit` | POST | Submit code/circuit for auto-grading |
| `/progress/{user_id}` | GET | Concept-level mastery |
| `/instructor/dashboard` | GET | Aggregate misconceptions, failure rates, students needing intervention |
| `/hardware/cached-comparison/{circuit_id}` | GET | Pre-computed real-hardware comparison (see §9) — **not** a live submission endpoint for the demo path |

**Design rule:** the client never talks to Qiskit/PennyLane/Cirq/LLM APIs directly — everything routes through the backend so context injection, grounding, and grading logic stay server-side and auditable.

---

## 6. Backend Adapter Layer (multi-framework design)

To satisfy the PS's multi-framework requirement without coupling the learning layer to any one library:

```python
class SimulationBackend(Protocol):
    def run(self, circuit: InternalCircuit, noise_level: float = 0.0) -> SimulationResult: ...
    def run_stepwise(self, circuit: InternalCircuit) -> list[StatevectorSnapshot]: ...

class QiskitAerBackend(SimulationBackend): ...
class PennyLaneBackend(SimulationBackend): ...   # stretch
class CirqBackend(SimulationBackend): ...        # stretch
class RealHardwareBackend(SimulationBackend): ...  # optional, offline-run only for MVP demo
```

- `InternalCircuit` is the shared representation (gates + qubit indices + params) built from either the visual builder or the code editor.
- Each backend translates `InternalCircuit` → its native circuit object, executes, and normalizes results back to `SimulationResult`.
- Adding a new backend = implementing one adapter class; no changes to the learning/assessment layers.

---

## 7. AI Tutor Service Design

**Goal:** grounded, circuit-aware responses — not a generic chatbot.

### 7.1 Context assembly (server-side, per request)
```
TutorContext = {
  lesson: current_module_and_concept,
  circuit: { visual_form, code_form },
  simulation_result: latest SimulationResult for this circuit,
  prediction: student's stated prediction (if any),
  student_history_summary: recent mastery + misconception tags,
  retrieved_knowledge: top-k matches from curated Knowledge Base for the current concept
}
```

### 7.2 Prompt construction
- System instructions fix the tutor's role: explain *this* circuit and *this* result using *only* the retrieved knowledge base content plus the supplied circuit/simulation data; do not introduce unverified claims about physics.
- The retrieved knowledge base entries act as the grounding source — curated and faculty-reviewed (see PRD §11 open questions).

### 7.3 Misconception detection
- After each tutor interaction or graded submission, a lightweight classification step tags the interaction against the misconception taxonomy (§4.7) — either via a rules pass on known error patterns (e.g. specific wrong-gate placements) or an LLM classification call constrained to the fixed tag list.

### 7.4 Guardrails
- Tutor responses for "debug" experiments must begin with a diagnostic question/hint, never the direct fix (enforced via prompt + a lightweight post-check).
- All tutor responses are logged (`TutorInteraction`) for later review/audit against faculty-validated content.

---

## 8. Real-Time Circuit Feedback

- For qubit counts within the "instant feedback" range (≤5–6 qubits, per PRD §6.2), recompute on every gate edit should feel immediate.
- Implementation approach: debounce edits client-side (~150–250ms), send diffed circuit to a lightweight sync endpoint, return updated state without a full page reload. Full "Run" semantics (with prediction-lock, grading, etc.) remain an explicit action.
- Heavier computations (noise sweeps, stepwise scrubber over many gates) can run as background jobs with a loading state rather than blocking the UI thread.

---

## 9. Real-Hardware Integration (optional, non-blocking)

Per product discussion: hardware access is **not required** for the PS or MVP. If included:

- Integration is via the IBM Quantum (Qiskit) or qBraid cloud API — a standard API call, not physical hardware access. Swapping `backend=aer_simulator` for a real device name is the only functional difference from the existing simulation flow.
- **For the live demo:** do not call the real-device API live. Run the chosen circuit(s) against the free-tier queue ahead of time, store the resulting histogram/statevector as a cached `SimulationRun` record with `backend=real_ibm`, and surface it exactly like any other cached comparison.
- **Rationale:** free-tier queue times are unpredictable (can range from seconds to a long wait depending on load) and represent an unacceptable live-demo risk; caching removes that risk while still letting the product show a real-hardware-vs-simulation comparison.
- If time allows post-MVP, a genuinely live (non-cached) submission path can be added behind a feature flag, decoupled from the core demo path.

---

## 10. Auto-Grading Logic (Coding Challenges)

- Each challenge defines a `target_behavior` (expected statevector or measurement distribution within tolerance, or a set of required gate properties).
- Grading pipeline:
  1. Parse submitted code/circuit → `InternalCircuit`.
  2. Run on the default backend (Aer).
  3. Compare result against `target_behavior` within a defined tolerance (e.g. ±3–5% on measurement probabilities, or exact statevector fidelity threshold).
  4. Generate structured feedback (not just pass/fail) — e.g., "Your circuit produces 01/10 with equal probability but the target was 00/11 — check your entangling gate placement."
- Partial credit: award based on how many required properties are satisfied (e.g., correct superposition step but wrong entangling qubit pair).

---

## 11. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | Simulation round-trip ≤2s for ≤5 qubits, ideal case, on the demo path |
| Reliability | Live demo must have a cached fallback for both AI tutor calls and any hardware comparison, in case of network/API failure |
| Scalability | Simulation execution isolated in worker processes so heavy runs don't block the API/UI thread; architecture should tolerate a classroom-sized concurrent load (tens of students), not necessarily production scale |
| Security | Passwords hashed (bcrypt/argon2); JWT session expiry; no plaintext secrets in client code; LLM API keys server-side only |
| Data integrity | Every `SimulationRun` and `TutorInteraction` is immutable and logged for auditability/grading disputes |
| Accessibility | Circuit builder and visualizations should be usable via keyboard navigation at a baseline level; color choices in histograms/Bloch spheres should not rely on color alone (colorblind-safe palette) |
| Deployment | Containerized; environment-config driven (no hardcoded backend URLs/keys); deployable to a standard cloud provider per PS requirement |

---

## 12. Testing Strategy

| Layer | Approach |
|---|---|
| Backend adapters | Unit tests comparing `InternalCircuit` → known statevector/measurement outputs against hand-verified reference values for canonical circuits (Bell state, GHZ, Deutsch–Jozsa on small inputs) |
| Grading logic | Test suite covering exact-match, tolerance-band, and partial-credit cases |
| AI tutor grounding | Regression set of Q&A pairs checked against expected grounded facts; flag responses that introduce claims not present in the knowledge base or circuit/sim context |
| Frontend | Component tests for circuit builder edit → recompute cycle; end-to-end test of the full Learn→Predict→Build→Run→Explain loop for at least one concept |
| Demo path | Full rehearsal run with network conditions simulated (throttled/offline) to confirm cached fallbacks work |

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Live LLM/API calls fail mid-demo | Cache a full golden-path run (circuit, sim result, tutor response) as a guaranteed fallback |
| Real-hardware queue delays | Never call hardware live in the demo; always pre-cached (§9) |
| AI tutor hallucinates physics claims | Ground all tutor responses in curated, faculty-reviewed knowledge base + actual circuit/sim data; log all interactions for review |
| Scope creep beyond MVP timeline | Enforce MVP/WOW/STRETCH tiers from PRD strictly; adapter architecture allows adding backends later without redesign |
| Simulation performance degrades UX for "instant feedback" builder | Cap real-time recompute to small qubit counts; push heavier runs to background jobs with explicit loading state |

---

## 14. Open Technical Questions

- Final choice of LLM provider/model for the tutor service and expected latency budget per request.
- Exact tolerance thresholds for auto-grading (needs input from faculty/domain review, per PRD §11).
- Whether PennyLane/Cirq adapters are built for MVP demo or deferred entirely to post-SIH (recommend: defer unless timeline allows, since Aer alone satisfies core loop).
- Hosting/cloud provider selection (constrained by team's free-tier credits/access).

---

*This TRD should be read alongside SIH_Quantum_Platform_PRD.md. Update both together if feature scope changes.*
