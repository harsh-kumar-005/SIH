# Session Handover & State (`Handover.md`)

**Current Date & Time:** 2026-09-11 16:15 IST
**Active Model:** Antigravity (Google DeepMind)
**Status:** ADR-017 complete — Concept-level progress tracking and materialized mastery ledger implemented and fully verified across 5 lifecycle stages.

---

## 1. Current State & What Was Accomplished
- Converted alias file `SIH_Quantum_Platform_Backend_Schema.md` to full local UTF-8 document.
- Formalized and established the 15 Core AI Engineering Tenets in [AGENTS.md](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/AGENTS.md).
- Initialized core living project documents ([Architecture.md](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/Architecture.md), [Constraints.md](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/Constraints.md), [Decisions.md](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/Decisions.md), [Flow.md](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/Flow.md), [Handover.md](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/Handover.md)).
- Configured git remote `origin` to `https://github.com/harsh-kumar-005/SIH.git` and synchronized `main`.
- Added `.gitignore` and sanitized repo by untracking `.DS_Store`.
- **Architectural Milestone (ADR-003)**: Formulated and documented the **Trusted Execution Environment (TEE)** Confidential AI & Simulation subsystem across Architecture, Constraints, Execution Flow, and Decisions.
- **Simulation Pipeline (ADR-004)**: Implemented and validated [simulate_bell.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/simulate_bell.py) using Qiskit Aer (`AerSimulator`). Successfully extracts intermediate per-gate statevectors, final statevectors with `{"real", "imag"}` serialization, and 1024-shot measurement counts. Added [requirements.txt](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/requirements.txt).
- **FastAPI Simulation Service (ADR-005)**: Implemented [main.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/main.py) with `GET /health`, `POST /circuits/simulate`, extensible `GATE_REGISTRY` (`H`, `X`, `Y`, `Z`, `CNOT`, `S`, `T`, `RX`), strict validation with custom HTTP 400 messages, and CORS middleware. Verified with 6/6 passing tests in [test_api.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/test_api.py).
- **React Client Pipeline Test (ADR-006)**: Scaffolding minimal Vite React app in [frontend/](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/frontend/). Implemented [App.jsx](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/frontend/src/App.jsx) with "Run Circuit" (valid Bell state) and "Run Invalid Circuit" (400 validation error), live CORS verified against the running FastAPI daemon. Added complete setup instructions to [README.md](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/README.md).
- **AI Tutor Prompt Architecture (ADR-007)**: Formalized empirical Socratic tutor prompt in [tutor_prompt.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/tutor_prompt.py). Implemented context injection formatting and validated two test scenarios: (1) causal Bell state grounding and (2) contradictory data guardrails where the tutor detects and flags mismatches.
- **PostgreSQL Persistence & Predictions Layer (ADR-008)**: Configured async SQLAlchemy 2.0 and Alembic migrations for 4 core tables (`users`, `circuits`, `simulation_runs`, `predictions`) per backend schema. Added [docker-compose.yml](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/docker-compose.yml). Extended `/circuits/simulate` with automatic circuit and run persistence, added `POST /predictions` and `GET /predictions/{id}/compare`. Verified end-to-end with [test_predictions_workflow.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/test_predictions_workflow.py).
- **Probability Normalization & Diagnostics (ADR-009)**: Updated `GET /predictions/{id}/compare` to normalize raw counts to 3-decimal probability distribution matching the predicted 0-1 scale. Added `POST /circuits` for unsimulated draft circuits. Rewrote [test_predictions_workflow.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/test_predictions_workflow.py) to prove distinct 404 handling between unsimulated circuits and non-existent predictions.
- **Interactive 2-Qubit Circuit Builder (ADR-010)**: Replaced placeholder React page with interactive SVG circuit canvas in [App.jsx](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/frontend/src/App.jsx). Features sharp-cornered gate tiles (`H`, `X`, `Y`, `Z`), two-click CNOT placement (control dot → target ⊕), click-to-remove, live simulation dispatch, dynamic 4-bar measurement histogram with percentages, formatted statevector inspector (`real + imag*i`), and inline error display.
- **Full Experiment Workspace UI — Predict→Run→Explain loop (ADR-011)**: Replaced generic styling with full design-token CSS (`index.css`) per UIUX §2 — `#EEF0F4` paper, `#0D0F14` void canvas, JetBrains Mono for data, Literata for prose, flat 1px hairlines, no glass/shadow/gradient. Rewrote `App.jsx` with two-column workspace layout (circuit+prediction+results left; AI Tutor right). Prediction panel: four bar-steppers styled identically to result bars (violet `#6E5AD6`), live sum indicator, Lock button disabled until sum=1.0±0.011. Run+compare chart: prediction bars (violet, left half) animate into measured bars (cobalt `#1B4FE0`, right half) in-place. Build verified: `npm run build` exits 0 in 124ms.
- **AI Tutor Grounding & Token Budget Fix (ADR-012)**: Diagnosed and resolved AI Tutor mid-sentence response truncation (`maxOutputTokens: 2048` prevents Gemini 2.5/3 internal thinking tokens from truncating user explanations). Configured dynamic `.env` reading for `GEMINI_API_KEY`. Selected `gemini-3-flash-preview` for high availability and low latency. Verified end-to-end live response with exact statevector and shot references.
- **Step-by-Step Amplitude Evolution Scrubber (ADR-013)**: Implemented scrubber component directly beneath circuit canvas. Displays `◀ Step 0 / N ▶` with ArrowLeft/ArrowRight support. Labels steps dynamically from `per_gate_states`. Synchronized with circuit canvas to highlight the active gate (`--collapse-cobalt`) and dim future gates (`opacity: 0.35`). Re-renders the statevector table dynamically per step. Automatically defaults to final step on run completion. Build verified: `npm run build` exits 0 in 221ms.
- **Lock Prediction Button Dependency Fix**: Removed stale `!circuitId` check on `btn-lock-prediction` in `App.jsx`. `lockPrediction` creates the circuit via `POST /circuits` on demand, so `circuitId` is legitimately null before locking. Fixed condition to `disabled={!sumOk || predLoading || gates.length === 0}`.
- **Debug Mode & Diagnostic Socratic Tutor (ADR-014)**: Added "Debug Mode" experiment type reusing the circuit builder and AI tutor panel.
  - Backend `GET /experiments/debug/bell-state` serves broken Bell state challenge (`X(q0)` + `CNOT(q0, q1)`) with target distribution (`|00⟩: 0.5, |11⟩: 0.5`).
  - Backend `/tutor/ask` updated with conditional Socratic debug logic: asks diagnostic questions when broken without revealing the solution; affirms and celebrates when fixed.
  - Frontend mode toggle (`Standard` vs `🐞 Debug Mode`), amber prompt banner (`--signal-amber`), Target vs Observed comparison card, auto-fired first-run tutor hint, and unlocked iterative running.
  - End-to-end verified with live Gemini 3 Flash tutor and Qiskit simulation.
- **Noise Lab & Depolarizing Error Simulation (ADR-015)**: Added "Noise Lab" experiment mode with physical decoherence modeling.
  - Backend `POST /circuits/simulate` accepts `noise_level` (0.0–1.0) with strict bounds validation. When `noise_level > 0`, constructs Qiskit Aer `NoiseModel` with `depolarizing_error` scaled by noise level applied exclusively to the measurement/sampling pass. Statevector evolution stays ideal.
  - Backend `POST /tutor/ask` accepts `noise_level` and `ideal_counts`, grounding AI explanations in the exact noise percentage and count deltas.
  - Frontend mode switcher 3-way toggle (`Standard` | `🐞 Debug Mode` | `🔬 Noise Lab`).
  - Fixed read-only Bell state circuit (`H(q0)` + `CNOT(q0, q1)`), horizontal slider `Noise: 0% ———●——— 100%`, debounced dispatch on drag release.
  - Fixed-position dual side-by-side histograms: cached **Ideal (0% Noise)** vs dynamic **Noisy (X% Noise)** with locked basis order (`|00⟩`, `|01⟩`, `|10⟩`, `|11⟩`).
  - Auto-fires grounded AI tutor debrief on noise changes. Verified provably with [test_noise_lab.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/test_noise_lab.py).
- **Real Authentication — Backend + Frontend (ADR-016)**: Replaced anonymous-user pattern with a full signed-JWT auth system.
  - **Backend** (`main.py`): `POST /auth/signup` (bcrypt hash via passlib, 409 on duplicate), `POST /auth/login` (HS256 JWT via python-jose, 24h expiry, 401 generic — no email leak). `get_current_user` dependency extracts JWT from `Authorization: Bearer` header; `require_instructor` RBAC dependency. `POST /circuits`, `POST /predictions`, `POST /tutor/ask` derive ownership from JWT — client never sends `owner_id`/`user_id`. Verified with [test_auth.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/test_auth.py).
  - **Frontend** (`App.jsx`): In-memory-only JWT (`authToken` React state + `authTokenRef` ref — never localStorage). `authFetch()` wrapper injects `Authorization: Bearer` on every API call.
- **Concept-Level Progress Tracking & Mastery Ledger (ADR-017)**:
  - **Database Migration**: Created `concepts` and `concept_mastery` tables via Alembic revision `97ab331c00af`. Seeded `"entanglement"` along with `"superposition"`, `"gates"`, and `"measurement"`.
  - **Mastery Update Logic**: `update_concept_mastery` helper increments attempts on every learning event; increments mastery (+0.1) on success; retains score on incorrect attempt.
  - **Endpoints**: `GET /predictions/{id}/compare` auto-updates entanglement mastery; `POST /progress/event` records explicit debug solve and noise events; `GET /progress/me` returns all concepts with their mastery statuses.
  - **Frontend Integration**: Added `📊 Progress` mode to header mode-toggle group. Shows concept cards with animated mastery bars (0-100%), attempts badge, status tag (`Not Started`, `In Progress`, `Mastered`), and auto-refetches after runs, comparisons, and debug challenge solves.
  - **Automated Verification**: [test_progress.py](file:///Users/sohambanerjee/Desktop/Egreen-Quanta/test_progress.py) passed all 5 stages provably.

---

## 2. In-Flight Work & Active Context
- All four experiment & learning views (Standard, Debug Mode, Noise Lab, Concept Progress) are operational.
- Authentication fully operational: backend JWT flow verified via `test_auth.py`.
- Progress tracking verified via `test_progress.py`.
- Backend running on `http://localhost:8000` (task-358).
- Frontend running on `http://localhost:5173` (task-225/task-694).
- Automated tests passing: `test_auth.py` (all 8 checks passed), `test_progress.py` (all 5 stages passed).

---

## 3. Known Blockers / Open Questions
- Lesson panel (collapsible thin rail per §4 wireframe) not yet implemented.
- Superposition & Gate modules exist as placeholder DB concepts awaiting dedicated curriculum circuits.


---

## 4. Immediate Next Steps
1. Lesson sidebar / collapsible pedagogy rail per §4 wireframe.
2. Additional curriculum challenges: Phase Flip, Superdense Coding, Inverted CNOT.
3. Instructor dashboard (protected by `require_instructor`) showing aggregated student prediction accuracy.
4. Drag-to-set prediction sliders.
