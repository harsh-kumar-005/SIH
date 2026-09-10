# System Constraints & Invariants (`Constraints.md`)
## Egreen-Quanta: Boundary Rules for AI & Human Collaborators

**Last Updated:** September 11, 2026  
**Status:** Active Non-Negotiables

---

## 1. What AI Must NEVER Do Without Explicit Confirmation

1. **Never mutate or delete existing database migrations:**
   - Once a migration is committed and applied, create a new forward migration (`V2__...`). Never alter old migration files in-place.
2. **Never execute arbitrary, unsandboxed Python code on the backend:**
   - Client code submitted to the backend must be strictly parsed into an AST, validated against an allowlist of quantum primitives, or executed inside an isolated, unprivileged runner with resource caps (CPU/memory/timeout limits).
3. **Never hardcode secrets, API keys, or tokens:**
   - AI service keys (Anthropic, OpenAI, Gemini), DB credentials, and QPU credentials (IBM Quantum, qBraid) must reside exclusively in environment variables and `.env.example` placeholders.
4. **Never bypass the Auto-Grading Oracle:**
   - Challenges must be graded on mathematical / unitary equivalence and statevector trace distance, never by fuzzy LLM string matching or subjective output checking.
5. **Never leak solution circuits directly in AI Tutor responses:**
   - The AI Tutor system prompt must enforce pedagogical Socratic scaffolding (nudges, counter-questions, bug localization) rather than emitting full circuit solutions.

---

## 2. Resource & Performance Constraints

| Constraint | Limit | Rationale |
|---|---|---|
| **Client-Side Simulation** | Max $\le 5$ qubits ($2^5 = 32$ state floats) | Protects browser UI thread from freezing during drag-and-drop. |
| **Server-Side Aer Sim (Sync)** | Max $\le 12$ qubits ($2^{12} = 4096$ floats), timeout 2s | Keeps API responsive under concurrent student load. |
| **Server-Side Aer Sim (Async/Jobs)** | Max $\le 16$ qubits, timeout 30s | Memory consumption scales as $2^N \times 16$ bytes per state vector. |
| **Max Circuit Depth** | 100 gate layers | Prevents infinite loop AST spam and canvas buffer overflow. |
| **AI Tutor Latency** | Streaming response within 1.5s TTFT | High conversational responsiveness for learning flow. |

---

## 3. Quantum Semantics Invariants

- **Qubit Indexing Convention:**
  - Standardize on little-endian vs big-endian across the entire stack.
  - Qiskit uses $|q_{n-1} q_{n-2} \dots q_0\rangle$ (little-endian: qubit 0 is the least significant bit).
  - The UI Canvas and Statevector Visualizer must document and maintain this exact bit-ordering convention consistently to avoid phase/basis inversion bugs.
- **Normalization:**
  - All statevectors must satisfy $\sum |\alpha_i|^2 = 1.0 \pm 10^{-6}$.
  - Any unitary matrix checked in challenges must verify $U^\dagger U = I$.
