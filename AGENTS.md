# Engineering Protocol & AI Operating Rules

These principles govern all AI-assisted engineering and development sessions in this repository. Every model, subagent, and human collaborator must strictly uphold them.

---

### Core Tenets

1. **Handover files (`Handover.md`)**
   - Write context incrementally during work, not just at the end.
   - The next session must never start from zero context.

2. **Decisions log (`Decisions.md`)**
   - Log the *why* behind every AI decision, architectural choice, and structural pivot, not just the *what*.
   - Include rationale, trade-offs evaluated, and alternatives rejected.

3. **Explicit comments**
   - Make execution flow, domain invariants, and mathematical/quantum logic legible, not merely functional.
   - Code explains the mechanism; comments explain the intention and quantum semantics.

4. **Execution Flow tracing (`Flow.md`)**
   - Trace precisely how execution moves across files, components, and services (e.g., UI Canvas → Circuit AST → Backend Adapter → Qiskit Aer / WebAssembly Worker → Visualizer / Statevector).

5. **Bug.md / Feature.md Work Logs**
   - Maintain a reproducible, start-to-finish trail that anyone can pick up cold.
   - State problem / specification, root cause / design, exact files changed, validation steps, and edge cases.

6. **System Architecture Map (`Architecture.md`)**
   - Keep the system topology updated so no component or file is touched blind.

7. **System Constraints & Boundaries (`Constraints.md`)**
   - Explicitly list non-negotiables, forbidden patterns, security boundaries, and files AI must never touch without explicit clearance.

8. **Test Checklists**
   - Provide concrete proof that features work (commands, test output, visual verification, AST validation), never just an unverified claim.

9. **Rollback Plans**
   - Always formulate a clean exit/rollback strategy before executing non-trivial or high-risk modifications.

10. **Read Every Diff. Every Time.**
    - Inspect full unified diffs before and after writing code. Catch unexpected side effects or regressions early.

11. **Ask "Why" Before "What"**
    - Interrogate assumptions and catch flawed reasoning before generating 200 lines of code.

12. **One Change Per Request**
    - Keep iterations focused, small, traceable, and reviewable. Avoid sweeping multi-system rewrites in a single turn.

13. **End of Session Handoff Notes**
    - Dedicate 30 seconds to summarize state, uncommitted changes, blockers, and next steps in `Handover.md`.

14. **Version Pin Your Context**
    - Record which model made which architectural or implementation call in `Decisions.md` and session logs.

15. **Own the Mental Model**
    - Documentation supports active understanding; it does not substitute for deep comprehension of the quantum algorithms, circuit semantics, and system architecture.
