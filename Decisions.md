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



