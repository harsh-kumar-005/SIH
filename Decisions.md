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
