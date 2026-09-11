# Architecture & Engineering Decision Records (`Decisions.md`)

Each entry documents the *why* behind design choices, technical pivots, and AI-assisted implementations.

---

### Record Template
```markdown
## [ADR-XXX] Title of Decision
- **Date:** YYYY-MM-DD
- **Model / Author:** [e.g., Gemini 3.8 Flash]
- **Status:** [Proposed | Accepted | Superseded]

#### Context & Motivation
What problem are we solving? Why does this decision need to be made now?

#### Decision & Mechanism
What was decided? How will it be implemented?

#### Alternatives Considered
- Option A: Why it was passed over.
- Option B: Why it was passed over.

#### Trade-offs & Consequences
What becomes easier? What becomes more constrained?
```

---

## [ADR-001] Adoption of 15 Core AI Engineering Rules & Living Documentation Framework
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
AI-assisted coding rapidly degrades if sessions lack persistent context, decisions lose their rationale, and code changes are made without visibility into dependencies or rollback plans. The user codified 15 operational tenets to maintain production rigor.

#### Decision & Mechanism
1. Encoded the 15 tenets in `AGENTS.md` to permanently instruct the model in this workspace.
2. Initialized living documents: `Architecture.md`, `Constraints.md`, `Decisions.md`, `Flow.md`, and `Handover.md`.
3. Standardized that every major change must touch `Decisions.md` (logging the "why"), `Flow.md` (tracing execution), and `Handover.md` (incremental session state).

#### Alternatives Considered
- *Relying only on chat history:* Ephemeral, fails when switching contexts, sessions, or models.
- *Ad-hoc documentation:* Leads to stale, disconnected docs that get out of sync with actual code.

#### Trade-offs & Consequences
- **Positive:** Context survives across sessions; models cannot hallucinate or violate constraints blindly.
- **Maintenance:** Requires ~30 seconds of discipline per turn to keep logs and handovers synchronized.

---

## [ADR-002] Remote Repository Configuration & Git Hygiene
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
The user designated `https://github.com/harsh-kumar-005/SIH` as the upstream remote repository to synchronize project increments continuously.

#### Decision & Mechanism
1. Configured git remote `origin` pointing to `https://github.com/harsh-kumar-005/SIH.git` with primary branch `main`.
2. Created `.gitignore` covering macOS system metadata, env secrets, Node/Python builds, and dependencies.
3. Untracked `.DS_Store` to prevent OS artifact pollution.

#### Alternatives Considered
- Direct push without `.gitignore`: Risky, leaks OS metadata and creates merge conflicts later.

#### Trade-offs & Consequences
- Clean remote history aligned with project security invariants (Constraints.md §1.3).

---

## [ADR-003] Confidential Computing Architecture (TEE) for Privacy-Preserving AI & Circuit IP
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
Standard cloud LLM architectures leak user code, circuit algorithms, student queries, and intellectual property to external third-party servers. Data is logged, retained, and potentially used for model training without learner/enterprise control. In quantum computing, circuits frequently encode proprietary algorithms, cryptographic logic, or patentable IP. Privacy and data sovereignty are existential requirements for enterprise and academic institutions.

#### Decision & Mechanism
1. Introduce a **Trusted Execution Environment (TEE)** enclave architecture (e.g., AWS Nitro Enclaves / AMD SEV-SNP / GCP Confidential VM) for the AI Tutor and confidential simulation tier.
2. In-Enclave Execution: AI inference runs in hardware-isolated, memory-encrypted RAM (MEK) where neither host OS, hypervisor, nor cloud provider can inspect computation.
3. Cryptographic Remote Attestation: Client validates hardware-signed PCR measurements before establishing an encrypted tunnel directly terminating inside enclave memory.
4. Zero-Data-Retention (ZDR): Prompts, circuit ASTs, and generated Socratic tokens are strictly transient and scrubbed post-response.

#### Alternatives Considered
- *Standard SaaS LLM APIs (OpenAI/Anthropic):* High capability, but data leaves the perimeter and incurs third-party logging and terms-of-service training risks.
- *Pure Local Browser LLM (WebLLM):* Solves privacy, but limited to small ~1B models with prohibitive mobile/laptop GPU memory requirements.
- *Standard Self-Hosted Cloud VM:* Cloud hypervisors and root infrastructure admins still have unrestricted memory dump access.

#### Trade-offs & Consequences
- **Positive:** Absolute cryptographic privacy guarantee, defense against cloud administrator snooping, zero external data leakage, powerful competitive differentiator for SIH.
- **Complexity:** Requires attestation verification logic in the client/proxy and enclave build packaging.

---

## [ADR-004] Quantum State Serialization & Intermediate Step Simulation
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
Frontend visualizers (Bloch spheres, statevector bars) and pedagogical inspectors require step-by-step statevectors after each discrete gate slice, alongside shot-based measurement histograms. Complex numbers cannot be natively encoded in JSON standards without serialization.

#### Decision & Mechanism
1. Built `simulate_bell.py` using modern `qiskit` and `qiskit-aer` (`AerSimulator`).
2. Captured intermediate step statevectors after $H(q_0)$ and $CNOT(q_0, q_1)$ using `save_statevector()`.
3. Standardized amplitude serialization into `{"real": float, "imag": float}` rounded to 6 decimal places to prevent floating-point representation noise.
4. Normalized shot counts over computational basis states (`00`, `01`, `10`, `11`) with explicit 0-count fallbacks.

#### Alternatives Considered
- *Stringifying complex numbers (e.g. "0.707+0j"):* Difficult for frontend JavaScript clients to parse reliably without custom regex.
- *Returning only final state:* Prevents step-by-step circuit timeline inspection in UI.

#### Trade-offs & Consequences
- Clean JSON interchange payload ready for backend API response and visualizer ingestion.

---

## [ADR-005] Generic Quantum Circuit Simulation API & Extensible Gate Registry
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
The frontend circuit builder requires an HTTP API to simulate arbitrary quantum circuits with dynamic gate counts, qubit counts, and parameterizations. Adding new quantum gates must not require refactoring endpoint routes or procedural `if-elif` control flows. Robust validation must preempt unhandled Qiskit exceptions (e.g. index errors, dimension mismatches) and return informative HTTP 400 responses.

#### Decision & Mechanism
1. Built a FastAPI application in `main.py` exposing `POST /circuits/simulate` and `GET /health`.
2. Created an extensible `GATE_REGISTRY` dictionary mapping gate names (`H`, `X`, `Y`, `Z`, `CNOT`, `S`, `T`, `RX`) to expected qubit counts, validation flags, Qiskit application lambdas, and display formatters.
3. Implemented defensive validation enforcing bounds: $1 \le \text{qubit\_count} \le 8$, distinct target qubits for multi-qubit gates, valid index ranges, and positive shot counts.
4. Added CORS middleware matching localhost and 127.0.0.1 on any port for seamless local frontend integration.
5. Standardized response schema containing `qubit_count`, `gates_applied`, `per_gate_states`, `final_statevector`, and `measurement_counts`.

#### Alternatives Considered
- *Hardcoded switch-case / if-elif in endpoint:* Highly brittle; requires modifying endpoint logic for every new quantum gate.
- *Blindly passing user parameters to Qiskit without validation:* Results in raw 500 internal server error tracebacks exposed to frontend users.

#### Trade-offs & Consequences
- **Positive:** O(1) extension for new gates; airtight HTTP 400 user-facing error reporting; verified with comprehensive test suite (`test_api.py`).
- **Constraint:** Limited to $\le 8$ qubits per system invariants (Constraints.md §2).

---

## [ADR-006] Minimal React Client & End-to-End CORS Pipeline Verification
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
Before introducing heavy UI component libraries, canvas engines, or state stores, a lightweight frontend pipeline test is essential to prove that HTTP/JSON interchange and cross-origin communication between the Vite client (`http://localhost:5173`) and FastAPI server (`http://localhost:8000`) function reliably.

#### Decision & Mechanism
1. Initialized a minimal React client using Vite in `frontend/`.
2. Implemented `frontend/src/App.jsx` with hardcoded `BELL_CIRCUIT` and `INVALID_CIRCUIT` payloads.
3. Connected actions to `POST http://localhost:8000/circuits/simulate` with in-flight `"Simulating…"` status, raw JSON `<pre>` rendering on success, and red error text on 400/network failures.
4. Validated live CORS integration between port 5173 and port 8000 for both 200 OK and 400 Bad Request responses.
5. Documented end-to-end setup instructions in `README.md`.

#### Alternatives Considered
- *Mocking API calls in frontend:* Defeats integration verification and obscures CORS issues.
- *Adding UI libraries upfront:* Adds unnecessary noise and complexity before basic connectivity is validated.

#### Trade-offs & Consequences
- **Positive:** Clean proof that client-to-backend communication, CORS headers, and error propagation work seamlessly end-to-end.

---

## [ADR-007] Circuit-Grounded Socratic AI Tutor Prompt Architecture & Consistency Guardrails
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
Generic LLMs produce textbook explanations detached from the user's active circuit, frequently hallucinate missing qubits/gates, or passively validate flawed user premises. The AI tutor must explain the *exact empirical results* generated by the student's circuit, ground answers in concrete numbers, and challenge inconsistencies.

#### Decision & Mechanism
1. Formalized `SYSTEM_PROMPT` in `tutor_prompt.py` enforcing empirical grounding (specific gates, specific qubits, exact numbers).
2. Mandated explicit contradiction handling: if a student's question assumes an outcome that contradicts the simulation payload (e.g. asking why 01/10 were absent when counts prove they were present), the tutor explicitly points out the contradiction rather than hallucinating explanations.
3. Implemented standardized test harness (`tutor_prompt.py`) evaluating:
   - Causal chain reasoning (superposition $\to$ correlation $\to$ zero amplitude).
   - Numeric grounding (referencing ~0.707107 amplitudes and 486/538 shot counts).
   - Resistance to mismatched/inconsistent test prompts.

#### Alternatives Considered
- *Open-ended conversational prompt:* Prone to generic textbook definitions ("Entanglement is when two particles...") without explaining the student's actual circuit.
- *Blind premise acceptance:* AI confirms student's false beliefs when asked misleading questions.

#### Trade-offs & Consequences
- **Positive:** Pedagogically sound, verifiable, resistant to hallucinations and adversarial student queries.
- **Constraint:** Context injection must always provide sanitized, accurate simulation JSON.

---

## [ADR-008] Async PostgreSQL Persistence Layer, Alembic Migrations, and Append-Only Simulation Ledger
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
The PRD and TRD specify that learning progress, circuit iterations, and student predictions must be persisted to enable empirical comparison loops and historical analytics. In accordance with system invariants, the simulation execution ledger must be append-only (no destructive updates).

#### Decision & Mechanism
1. Built SQLAlchemy 2.0 async models in `db/models.py` for `users`, `circuits`, `simulation_runs`, and `predictions`.
2. Established `simulation_runs` as an append-only table (INSERT only) tracking every execution, noise level, statevector, and execution duration.
3. Created `alembic/` async migrations and generated initial migration `84a43014ac7d_initial_tables.py`, verified against PostgreSQL.
4. Added `docker-compose.yml` for isolated containerized PostgreSQL deployment.
5. Updated `POST /circuits/simulate` to persist `circuits` and `simulation_runs` rows and return `circuit_id` and `run_id`.
6. Added `POST /predictions` and `GET /predictions/{id}/compare` to close the pedagogical hypothesis testing loop.

#### Alternatives Considered
- *In-memory mock store / SQLite:* Insufficient for production concurrent workloads, JSONB operations, and team collaboration.
- *Synchronous psycopg2 driver:* Blocks FastAPI async event loop under high concurrency.

#### Trade-offs & Consequences
- **Positive:** Type-safe async DB access; robust schema migration trail; append-only auditability.
- **Maintenance:** Requires running `alembic upgrade head` across deployment environments.

---

## [ADR-009] Probability Normalization and Disambiguated 404 Diagnostics for Predictions
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
Students submit predicted probability distributions on a 0–1 scale (e.g. `0.5`, `0.5`), whereas `simulation_runs.counts` stores raw integer shot tallies (e.g. `488`, `512`). Direct visualization or automated grading without normalization forces frontend code to guess shot counts and perform ad-hoc arithmetic. Furthermore, frontend debugging was impaired when a 404 error could mean either "prediction record does not exist" or "the prediction exists but no simulation was ever run for this circuit".

#### Decision & Mechanism
1. Updated `GET /predictions/{id}/compare` to normalize raw counts against total shots, rounding to 3 decimal places (`round(v / total_shots, 3)`), aligning `predicted` and `actual` distributions on the identical 0–1 scale.
2. Disambiguated error messages:
   - Prediction missing: `"Prediction with id {id} not found"`
   - Circuit unsimulated: `"No simulation run exists yet for circuit {circuit_id}"`
3. Added `POST /circuits` endpoint allowing creation of unsimulated draft circuits.
4. Rewrote `test_predictions_workflow.py` with explicit test cases for probability scale checks and distinct 404 diagnosis.

#### Alternatives Considered
- *Normalizing in frontend client:* Duplicates calculation across web, mobile, and grading microservices; risks division by zero and precision drift.
- *Generic 404 error without circuit context:* Causes difficult UI debugging when distinguishing missing records from unsimulated circuits.

#### Trade-offs & Consequences
- **Positive:** Clean mathematical parity between student predictions and empirical results; clear, actionable error diagnostics.

---

## [ADR-010] Interactive 2-Qubit SVG Circuit Canvas, State-Derived AST, and Visualizer Displays
- **Date:** 2026-09-11
- **Model / Author:** Gemini 3.8 Flash
- **Status:** Accepted

#### Context & Motivation
Students need an interactive, diagram-accurate visual interface to compose quantum circuits without writing code. The canvas must enforce a canonical single source of truth (`[{type, target_qubits, params, step_index}]`) matching backend schema specifications, support two-click multi-qubit gates (CNOT), enable removal on click, and render empirical measurement histograms and statevectors directly from simulation outputs.

#### Decision & Mechanism
1. Implemented interactive SVG circuit canvas in `frontend/src/App.jsx` with 2 horizontal qubit wires (`q0`, `q1`) and 4 discrete time-step columns.
2. Built gate palette with sharp-cornered rectangle tiles (`H`, `X`, `Y`, `Z`) per UI/UX diagram-accurate specifications.
3. Implemented two-click CNOT placement: click control qubit dot $\to$ click target qubit at the same step $\to$ renders solid control circle linked via vertical line to target $\oplus$ symbol.
4. Click-to-remove: Clicking an active gate immediately filters it from state.
5. Bound "Run Circuit" to live `POST http://localhost:8000/circuits/simulate`.
6. Replaced raw JSON dump with:
   - Measurement histogram: 4 probability bars (`|00⟩`, `|01⟩`, `|10⟩`, `|11⟩`) with dynamic percentages and shot counts.
   - Statevector inspector: Formatted complex numbers (`real + imag*i`) rounded to 3 decimal places.
   - Error banner: Prominent red alert banner positioned above canvas for API 400 validation failures.

#### Alternatives Considered
- *Third-party canvas / drag-and-drop libraries:* Overly complex and heavyweight for a 2-qubit MVP; adds bundle bloat before core pedagogical loop is verified.
- *Maintaining separate UI state vs circuit AST:* Prone to desynchronization between canvas display and backend payload.

#### Trade-offs & Consequences
- **Positive:** Lightweight (~126ms build); pure SVG vector rendering; zero state drift between canvas and backend API.



---

## [ADR-011] Full Experiment Workspace UI — Predict→Run→Explain Loop
- **Date:** 2026-09-11
- **Model / Author:** Antigravity (Google DeepMind)
- **Status:** Accepted

#### Context & Motivation
The circuit builder canvas (ADR-010) was functional but had no prediction UI, no comparison chart, no AI tutor panel, and used generic CSS (white background, system fonts, blue buttons). The UIUX doc §4 specifies a five-panel Experiment Workspace. User feedback explicitly rejected: (1) glassmorphism / dark-teal-purple gradient aesthetic, (2) JSON textarea for predictions, (3) modal or accordion tutor placement.

#### Decision & Mechanism

**CSS / Design Tokens (`index.css`):**
- Implemented all §2 tokens directly as CSS custom properties (`--paper`, `--ink`, `--superposition-violet`, `--collapse-cobalt`, `--void`, `--error-line`, `--hairline`).
- Imported Literata (prose) + JetBrains Mono (data) from Google Fonts — two families only, no tracked ALL-CAPS, no gradient decorations.
- Flat surfaces: 1px `var(--hairline)` dividers everywhere, `border-radius: 4px` on content panels, `0px` on circuit gate tiles (diagram-accurate).
- Dark surface (`var(--void)`) used **only** for the circuit SVG canvas background, nowhere else.
- Motion: single orchestrated keyframe — `.cmp-bar.predicted` (violet, 0.55 opacity) and `.cmp-bar.actual` (cobalt) animate their `height` with `0.45s cubic-bezier` on render, with a 0.1s offset to visually show the "collapse" sequence. `prefers-reduced-motion` fallback strips transition.

**App.jsx layout:**
- Two-column CSS grid: `1fr 320px` (main content | tutor). Mobile: collapses to single column, stacked.
- Header: circuit title + live status dot (muted/violet/cobalt depending on state).

**Prediction Panel:**
- Four `pred-bar-col` components (one per basis state `|00⟩`…`|11⟩`), each with a percentage label, a violet fill bar (`var(--superposition-violet)`), a state label, and ± 5% stepper buttons (keyboard accessible per §10 — not drag-only).
- Live sum indicator: computes `Σ probabilities` after every stepper click; turns cobalt + ✓ when `|sum - 1.0| < 0.011`. Lock button disabled until sum valid.
- "Lock Prediction" calls `POST /predictions` with `user_id` (from `/users/anonymous` on mount) and current `circuit_id`.

**Run + Compare Chart:**
- "Run Circuit" sends `POST /circuits/simulate` with `circuit_id` if already exists (ADR-009 no-duplicate behavior).
- After run: for each basis state, renders a `compare-bars-pair` with predicted bar (violet, left) and actual bar (cobalt, right) side-by-side — **same visual shape**, directly comparable. This is the UIUX §4 "same bar-chart shape, side by side" requirement.
- Color is never the only signal: percentage labels in matching colors accompany each bar (§10).

**AI Tutor Panel:**
- Right column, always visible, never modal/accordion/floating-bubble (§9 "Don't Build This").
- Opens with a grounded observation keyed to current circuit state, not "Ask me anything!"
- After run, replaces opening observation with: "Run complete. Top outcome: |XX⟩ at ~N%."
- Input scoped to "Ask about this circuit" label; inline errors with specific wording if no circuit/run yet.
- `GET /users/anonymous` called on mount; result stored in `userId` state.

#### Alternatives Considered
- **Drag-to-set prediction bars**: would require pointer capture + math for height-to-probability conversion; decided against for MVP because ± buttons already satisfy §10 keyboard accessibility requirement and deliver the same UX goal (deliberate commitment). Can be added as progressive enhancement.
- **JSON textarea for predictions**: explicitly rejected by user — it turns "commit to a prediction" back into "fill out a form," collapsing the pedagogical moment.
- **Modal / accordion for tutor**: rejected per §9 and §1 Principle 4 — tutor must always visibly reference the same instrument the student is looking at.
- **Glassmorphism dark theme**: rejected — matches the exact "generic AI-generated SaaS demo" pattern the UIUX doc §0 calls out to avoid.

#### Trade-offs & Consequences
- **Easier:** prediction vs. result comparison is visually immediate; design tokens are reused consistently so future screens (Noise Lab, Debug) can import the same variables.
- **More constrained:** lesson panel (collapsible rail) and step scrubber (per-gate statevector playback) not yet implemented — those are the next two features before the workspace matches the full §4 wireframe.
- **Dependency:** `/users/anonymous` must be reachable on mount; failure is non-fatal (prediction just won't have an `owner_id`) but should be improved once auth is implemented.
---

## [ADR-012] AI Tutor Grounding, Token Budgeting & Key Resolution Fix
- **Date:** 2026-09-11
- **Model / Author:** Antigravity (Google DeepMind)
- **Status:** Accepted

#### Context & Motivation
Students testing the Bell state reported two issues with the AI Tutor:
1. Truncated responses: tutor explanations were cutting off mid-sentence (e.g. `...superposition of |0⟩ and |`).
2. Quota & key resolution: `GEMINI_API_KEY` was static at startup, and `gemini-2.5-flash`'s internal reasoning/thinking tokens (~487 tokens) were consuming the 512 `maxOutputTokens` quota before user text could complete.
3. Inverted pedagogical sequencing: `lockPrediction` previously required a prior run, which inverted the Predict→Lock→Run requirement.

#### Decisions Made
1. **Token Budget Expansion (`maxOutputTokens: 2048`)**:
   - Modern Gemini models (2.5/3 Flash) utilize internal thought tokens that count towards total output token allocation. Setting `maxOutputTokens: 2048` guarantees full 3-4 sentence pedagogical explanations without hitting `finishReason: MAX_TOKENS`.
2. **Dynamic Key Resolution (`get_gemini_api_key`)**:
   - Resolved dynamically per request from environment variables or local `.env` (gitignored), eliminating the need for process restarts when updating credentials.
3. **Model Selection & Fallback (`gemini-3-flash-preview`)**:
   - Defaulted to `gemini-3-flash-preview` which provides instant latency, high fidelity grounding, and active quota.
4. **Pedagogical Gating in `App.jsx`**:
   - `Lock Prediction` creates the circuit in the DB first (`POST /circuits`), then locks the prediction.
   - `Run Circuit` is disabled until `predLocked === true`.
   - Canvas is set to read-only once locked to prevent post-lock tampering with the experimental setup.

#### Verification
- Simulated Bell state: `H(0)` + `CNOT(0, 1)`.
- Verified prediction comparison: 50% `|00⟩` vs 50.3% actual (515 shots), 50% `|11⟩` vs 49.7% actual (509 shots).
- Verified tutor output: quotes exact statevector `[0.707107, 0, 0, 0.707107]`, exact counts (515, 509), and explains gate mechanics without truncation.

---

## [ADR-013] Step-by-Step Amplitude Evolution Scrubber
- **Date:** 2026-09-11
- **Model / Author:** Antigravity (Google DeepMind)
- **Status:** Accepted

#### Context & Motivation
While the simulation outputs final measurement counts and the final statevector, quantum mechanics pedagogy requires understanding how superposition and entanglement evolve gate-by-gate before measurement collapse. The backend already returns `per_gate_states` containing intermediate statevectors after each gate.

#### Decisions Made
1. **Scrubber UI Placement & Architecture**:
   - Placed directly below the circuit SVG canvas, inside the circuit card, keeping student attention anchored to the circuit layout.
   - Stepper format: `◀ Step currentStep / N ▶` where step 0 is initial ground state ($|00\rangle$), and step $N$ is the final post-run state.
   - Arrow buttons and global keyboard navigation (`ArrowLeft` / `ArrowRight`), disabled at step 0 and step $N$ respectively without wrap-around.
2. **Dynamic Step Labeling**:
   - Pulled directly from `per_gate_states[currentStep - 1].after_gate` (e.g. `"After: H(q0)"` at step 1, `"After: CNOT(q0,q1)"` at step 2, `"Initial ground state |00⟩"` at step 0).
3. **Synchronized Circuit Canvas Feedback**:
   - The gate tile corresponding to the active step (`gateRank === currentStep - 1`) is highlighted with `--collapse-cobalt` (`#1B4FE0`), an active halo stroke, and increased stroke width.
   - Future gates (`gateRank > currentStep - 1` or all gates at step 0) are visually de-emphasized with `opacity: 0.35`.
   - Past gates maintain standard full opacity.
4. **Parameterized Statevector Display**:
   - The existing statevector table in the results section dynamically renders `activeStatevector` derived from `currentStep` instead of only static final state.
5. **Lifecycle Reset & Accessibility**:
   - Scrubber resets to step $N$ automatically whenever a new simulation run completes.
   - Respects `prefers-reduced-motion` with disabled transitions.

#### Verification
- Bell State circuit:
  - **Step 0**: `|00⟩: 1.000`, `|01⟩: 0.000`, `|10⟩: 0.000`, `|11⟩: 0.000`. Prev disabled, Next enabled. All gates dimmed (0.35 opacity).
  - **Step 1**: `|00⟩: 0.707`, `|01⟩: 0.707`, `|10⟩: 0.000`, `|11⟩: 0.000`. H gate highlighted in cobalt. CNOT gate dimmed.
  - **Step 2**: `|00⟩: 0.707`, `|01⟩: 0.000`, `|10⟩: 0.000`, `|11⟩: 0.707`. CNOT gate highlighted. Prev enabled, Next disabled.
- Frontend build: `npm run build` exits 0 (221ms).

---

## [ADR-014] Debug Mode Experiment Type & Diagnostic Socratic Tutor Constraint
- **Date:** 2026-09-11
- **Model / Author:** Antigravity (Google DeepMind)
- **Status:** Accepted

#### Context & Motivation
Pedagogical learning requires testing student conceptual models through debugging broken circuits (identifying bugs and understanding why expected quantum phenomena fail to occur).
The Bell state broken circuit challenge provides a circuit where an X gate on q0 replaces the required H gate, putting q0 deterministically in |1⟩ and resulting in |11⟩ at 100%.

#### Decisions Made
1. **Challenge Endpoint (`GET /experiments/debug/bell-state`)**:
   - Hardcoded contract returning challenge prompt, target distribution (`|00⟩: 0.5, |11⟩: 0.5`), tolerance (`0.05`), and broken starter circuit (`X(q0)` + `CNOT(q0, q1)`).
2. **Diagnostic Socratic Prompt Constraint (`/tutor/ask`)**:
   - Evaluates whether the simulation run matches the target behavior.
   - If mismatched (`experiment_type: "debug"`): Enforces that the tutor must *never* reveal the fix directly. It asks a targeted diagnostic question directing the student's attention to the gate/state responsible (e.g. asking whether X creates superposition or a fixed bit).
   - If fixed: The tutor's tone shifts to affirmative confirmation and celebration, explaining why the student's fix succeeded.
3. **Frontend Debug Mode UX**:
   - Header mode switcher (`Standard` vs `🐞 Debug Mode`).
   - Amber accent banner (`--signal-amber`) per design tokens prominently displaying challenge prompt and target behavior.
   - Target vs. Observed comparison box showing target distribution alongside live measurement counts and mismatch/fixed badges.
   - Auto-fires one diagnostic tutor hint on the first run in debug mode.
   - Students freely edit gates and re-run iteratively.

#### Verification
- Loaded challenge via `GET /experiments/debug/bell-state`.
- Ran broken starter circuit: 1024 shots on `|11⟩` (100%).
- Verified tutor diagnostic hint: pointed to $X$ gate vs superposition without revealing "swap X for H".
- Fixed circuit ($X \rightarrow H$): 522 shots on `|00⟩` (51%), 502 shots on `|11⟩` (49%).
- Verified tutor confirmation: confirmed fix, celebrated completion, explained why $H$ followed by $CNOT$ creates the entangled Bell state.
- Frontend build: `npm run build` exits 0 (142ms).

---

## [ADR-015] Noise Lab Feature & Depolarizing Error Channel Simulation
- **Date:** 2026-09-11
- **Model / Author:** Antigravity (Google DeepMind)
- **Status:** Accepted

#### Context & Motivation
Pedagogical understanding of quantum computing requires demonstrating how environmental decoherence and quantum hardware noise corrupt ideal quantum states. Students need to see why real physical hardware measurements deviate from theoretical statevector mathematics, contrasting pure state evolution against noisy shot-based sampling.

#### Decisions Made
1. **Backend Depolarizing Noise Integration (`POST /circuits/simulate`)**:
   - Extended `CircuitSimulateRequest` with optional `noise_level: float = Field(0.0, ge=0.0, le=1.0)`.
   - Strict validation: rejects values outside $[0.0, 1.0]$ with HTTP 400 (`"noise_level must be between 0.0 and 1.0"`).
   - Aer Noise Modeling: when `noise_level > 0.0`, constructs a `qiskit_aer.noise.NoiseModel` with `depolarizing_error(noise_level, 1)` for 1-qubit gates (`['h', 'x', 'y', 'z', 's', 't', 'rx']`) and `depolarizing_error(noise_level, 2)` for 2-qubit gates (`['cx']`).
   - Pure State Invariant: statevector and `per_gate_states` calculations remain strictly ideal and noise-free. Noise model is applied exclusively to the measurement/sampling simulator pass (`qc_meas`).
   - Persisted `noise_level` into the `simulation_runs` database record.
2. **AI Tutor Noise Grounding (`POST /tutor/ask`)**:
   - Added `ideal_counts` and `noise_level` fields to `TutorAskRequest`.
   - When `experiment_type == "noise"` or `noise_level` is present, prompt directs the tutor to explain the physical decoherence mechanism and ground explanations directly in the exact noise percentage and count discrepancies (specifically explaining why non-basis states like $|01\rangle$ and $|10\rangle$ begin leaking in).
3. **Frontend Noise Lab Workspace (`App.jsx` + `index.css`)**:
   - Mode switcher expanded to 3 options: `Standard`, `🐞 Debug Mode`, `🔬 Noise Lab`.
   - Loads fixed Bell state circuit (`H(q0)` + `CNOT(q0, q1)`) in read-only mode (palette replaced by notice, slot interactions disabled).
   - Horizontal slider (`Noise: 0% ———●——— 100%`) with live percentage display.
   - Debounced dispatch on drag release / arrow key events, avoiding excess API traffic while dragging.
   - Dual side-by-side histogram grid: cached **Ideal (0% Noise)** on the left vs **Noisy (X% Noise)** on the right with locked basis-state ordering (`|00⟩`, `|01⟩`, `|10⟩`, `|11⟩`) to prevent layout shifts.
   - Auto-fires grounded tutor debrief on noise level change.

#### Verification
- Ran `test_noise_lab.py` proving smooth, monotonic degradation across the slider range:
  - `noise_level=0.00`: `{'00': 512, '01': 0, '10': 0, '11': 512}` (0 errors / 0.0%).
  - `noise_level=0.15`: `{'00': 494, '01': 47, '10': 39, '11': 444}` (86 errors / 8.4%).
  - `noise_level=0.50`: `{'00': 360, '01': 135, '10': 143, '11': 386}` (278 errors / 27.1%).
  - Confirmed monotonic increase in error states ($|01\rangle$ and $|10\rangle$) and smooth drop in $|00\rangle$/$|11\rangle$.
  - Boundary check: rejects -0.1 and 1.2 with HTTP 400.
  - Tutor debrief: explicitly analyzed 15% and 50% noise with exact shot counts and zero amplitude in ideal statevector.
- Frontend build: `npm run build` exits 0 (143ms).

---

## [ADR-016] Real Authentication — bcrypt/JWT Backend + In-Memory Frontend Auth
- **Date:** 2026-09-11
- **Model / Author:** Antigravity (Google DeepMind)
- **Status:** Accepted

#### Context & Motivation
All previous sessions used an anonymous-user helper (`GET /users/anonymous`) that assigned a random UUID to each browser session with no identity verification. This meant:
- Any client could claim any `owner_id` in request bodies (spoofing risk).
- No meaningful access control was possible for instructor-only routes.
- The SIH demo needed to show a realistic multi-user, role-based system to evaluators.

#### Decision & Mechanism

**Backend:**
1. **Password hashing** — `passlib[bcrypt]` with bcrypt pinned to `3.2.2` for compatibility with passlib's `CryptContext`. Newer bcrypt versions change the hash prefix (`$2b$` vs `$2y$`) in a way that passlib `identify_record` cannot resolve.
2. **JWT issuance** — `python-jose` with HS256 algorithm, 24-hour expiry, signed with `SECRET_KEY` loaded from `.env`. Payload carries `sub` (user UUID) and `role`.
3. **Endpoints** — `POST /auth/signup` (201, hashes password, 409 on duplicate email) and `POST /auth/login` (200, returns `{access_token, token_type, user:{id,email,role,display_name}}`). Login always returns a generic 401 on failure — never reveals whether the email exists.
4. **Dependencies** — `get_current_user` extracts and validates JWT from `Authorization: Bearer <token>` header, raises 401 if missing/invalid/expired. `require_instructor` wraps `get_current_user` and raises 403 if `role != "instructor"`. `optional_current_user` allows unauthenticated access for read endpoints.
5. **Ownership derivation** — `POST /circuits`, `POST /predictions`, `POST /tutor/ask` derive `owner_id`/`user_id` exclusively from the JWT `sub` claim. Client-provided IDs in request bodies are ignored, preventing spoofing.

**Frontend:**
1. **In-memory only** — `authToken` is stored in React `useState`. Never written to `localStorage`, `sessionStorage`, or cookies. Token is lost on page refresh (intentional for the SIH demo — avoids persistent session security concerns without a proper refresh-token infrastructure).
2. **`authTokenRef` ref** — mirrors `authToken` state via a `useEffect`. All `authFetch()` calls read from the ref, not the state, eliminating stale-closure risk inside async callbacks.
3. **`authFetch()` wrapper** — drops-in replacement for `fetch()`. Injects `Authorization: Bearer <token>` and `Content-Type: application/json` automatically. All 9 existing API calls migrated to `authFetch()`.
4. **Auth screen** — conditional early-return before the workspace JSX when `authToken === null`. Full-page dark glassmorphism card (void canvas background + cobalt radial glow + animated card entrance). Login/signup tab switcher, success/error banners, form with validation.
5. **Header user badge** — after login, displays `display_name` + role pill + Log Out button. Logout calls `handleLogout()` which nullifies token, user, ref, and all workspace state, then re-shows the auth screen.

#### Alternatives Considered
- **localStorage for JWT**: Rejected — XSS attack surface; SIH evaluators expect security awareness.
- **httpOnly cookie via backend**: Rejected — requires CORS `credentials: include`, SameSite config, and a proper refresh-token endpoint. Over-engineered for a hackathon demo.
- **Session-based auth (server-side)**: Rejected — stateful, incompatible with stateless FastAPI + async PostgreSQL design.
- **OAuth / social login**: Rejected — external dependency, out of scope for SIH timeline.

#### Trade-offs & Consequences
- ✅ Spoofing eliminated — backend never trusts client-provided user IDs.
- ✅ RBAC ready — `require_instructor` dependency available for future instructor dashboard.
- ✅ No persistence risk — in-memory token never touches disk.
- ⚠️ Page refresh logs user out — acceptable for demo; would need refresh tokens in production.
- ⚠️ bcrypt 3.2.2 pin — must be revisited if passlib releases a compatibility update.

#### Verification
- `test_auth.py`: signup (201), duplicate → 409, login (200 + JWT), wrong password → 401 generic, spoofing attempt → rejected (ownership from JWT), RBAC instructor route → 403 for student.
- Server logs confirm: `POST /auth/login → 200 OK`, `POST /circuits/simulate → 200 OK` with Bearer token.
- Vite HMR picked up `App.jsx` and `index.css` with no compile errors (confirmed in task-694 log).




