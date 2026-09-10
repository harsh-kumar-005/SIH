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






