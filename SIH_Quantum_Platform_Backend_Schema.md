# Backend Schema Document
## Interactive Quantum Algorithm Learning Platform (SIH)

**Status:** Draft v1
**Companion to:** PRD, TRD, UI/UX Document
**Database:** PostgreSQL
**Last updated:** September 11, 2026

---

## 0. Purpose

This document defines the concrete database schema implementing the data models sketched in the TRD (§4). It specifies tables, columns, types, constraints, relationships, and indexes so the backend team can generate migrations directly from it. It also documents a few schema-level decisions (why JSONB is used where it is, why certain tables are split apart) so the reasoning survives beyond the initial build.

---

## 1. Entity-Relationship Overview

```
                    ┌───────────┐
                    │  users    │
                    └─────┬─────┘
                          │ 1
              ┌───────────┼─────────────────────┐
              │           │                      │
              │ N         │ N                    │ N
       ┌──────▼─────┐ ┌───▼──────────┐   ┌───────▼────────┐
       │ circuits   │ │ predictions  │   │ concept_mastery │
       └──────┬─────┘ └──────┬───────┘   └────────┬────────┘
              │ 1             │ N                   │ N
              │ N             │                     │
      ┌───────▼────────┐      │             ┌───────▼───────┐
      │ simulation_runs│◄─────┘             │   concepts    │
      └────────────────┘                    └───────┬───────┘
                                                     │ N
       ┌───────────┐        ┌──────────────┐  ┌─────▼──────┐
       │  modules  │──1───N─│ experiments  │  │ misconception│
       └───────────┘        └──────┬───────┘  │    _tags     │
                                    │ N        └──────┬───────┘
                             ┌──────▼────────┐        │ N
                             │  submissions  │        │
                             └───────────────┘  ┌─────▼────────────┐
                                                 │misconception_events│
       ┌──────────────────┐                     └────────────────────┘
       │ tutor_interactions│
       └──────────────────┘

       ┌──────────────┐        ┌───────────────┐
       │  cohorts     │──N───N─│ enrollments   │── users (students)
       └──────────────┘        └───────────────┘

       ┌────────────────────┐
       │ knowledge_base_entries │  (referenced by tutor_interactions.grounded_sources)
       └────────────────────┘
```

---

## 2. Table Definitions

### 2.1 `users`

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK, default `gen_random_uuid()` |
| `email` | `text` | UNIQUE, NOT NULL |
| `password_hash` | `text` | NOT NULL |
| `role` | `text` | NOT NULL, CHECK IN (`'student'`, `'instructor'`) |
| `display_name` | `text` | NOT NULL |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |
| `last_login_at` | `timestamptz` | NULL |

**Indexes:** unique index on `email`.

**Notes:** Single `role` column is sufficient for MVP (2 roles, no multi-role users). If admin/TA roles are added later, migrate to a `user_roles` join table rather than extending the CHECK constraint indefinitely.

---

### 2.2 `concepts`

The prerequisite knowledge graph referenced throughout the PRD (e.g., Qubit → Superposition → Gates → Entanglement).

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `name` | `text` | NOT NULL, UNIQUE |
| `description` | `text` | NOT NULL |

### 2.3 `concept_prerequisites`

Self-referencing many-to-many edge table for the knowledge graph.

| Column | Type | Constraints |
|---|---|---|
| `concept_id` | `uuid` | PK part, FK → `concepts.id` |
| `prerequisite_id` | `uuid` | PK part, FK → `concepts.id` |

**Constraint:** composite PK on (`concept_id`, `prerequisite_id`); CHECK `concept_id <> prerequisite_id`.

---

### 2.4 `modules`

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `title` | `text` | NOT NULL |
| `order_index` | `integer` | NOT NULL |
| `primary_concept_id` | `uuid` | FK → `concepts.id`, NOT NULL |

**Indexes:** index on `order_index` for ordered fetch.

### 2.5 `experiments`

An experiment is one guided unit inside a module: a "Learn → Predict → Build → Run" instance, a debug challenge, or a coding challenge.

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `module_id` | `uuid` | FK → `modules.id`, NOT NULL |
| `type` | `text` | NOT NULL, CHECK IN (`'guided'`, `'debug'`, `'challenge'`) |
| `prompt` | `text` | NOT NULL |
| `target_behavior` | `jsonb` | NOT NULL — e.g. `{"distribution": {"00": 0.5, "11": 0.5}, "tolerance": 0.05}` |
| `starter_circuit_id` | `uuid` | FK → `circuits.id`, NULL (debug/challenge experiments start from a given broken/incomplete circuit) |
| `order_index` | `integer` | NOT NULL |

**Indexes:** index on `module_id`.

**Notes:** `target_behavior` is JSONB rather than fixed columns because grading targets vary by experiment type (exact statevector fidelity for some, distribution tolerance for others, required-gate-presence for others). Validate its shape in application code against a per-`type` schema rather than in the database.

---

### 2.6 `circuits`

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `owner_id` | `uuid` | FK → `users.id`, NULL (NULL = system-authored, e.g. starter/broken circuits) |
| `experiment_id` | `uuid` | FK → `experiments.id`, NULL |
| `qubit_count` | `smallint` | NOT NULL, CHECK `qubit_count BETWEEN 1 AND 8` |
| `gates` | `jsonb` | NOT NULL — array of `{type, target_qubits, params, step_index}` |
| `code_form` | `text` | NULL — generated/edited Qiskit source |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` |

**Indexes:** index on `owner_id`; index on `experiment_id`.

**Notes:** `gates` is JSONB rather than a normalized `circuit_gates` table for MVP. This is a deliberate tradeoff: circuits are small (≤8 qubits, typically <20 gates), always read/written as a whole unit (never queried gate-by-gate), and the qubit cap keeps documents small — so JSONB avoids join overhead for the single most frequently hit table in the product. If cross-circuit gate analytics become a real requirement post-MVP (e.g. "which gate type most often precedes a wrong answer"), revisit with a normalized table at that point.

---

### 2.7 `simulation_runs`

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `circuit_id` | `uuid` | FK → `circuits.id`, NOT NULL |
| `backend` | `text` | NOT NULL, CHECK IN (`'aer'`, `'pennylane'`, `'cirq'`, `'real_ibm'`) |
| `noise_level` | `real` | NOT NULL, default `0`, CHECK `noise_level BETWEEN 0 AND 1` |
| `counts` | `jsonb` | NOT NULL — e.g. `{"00": 512, "11": 488}` |
| `statevector` | `jsonb` | NULL — final statevector, list of `{real, imag}` |
| `per_gate_states` | `jsonb` | NULL — array of statevectors, one per gate step, for the amplitude scrubber |
| `duration_ms` | `integer` | NOT NULL |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |

**Indexes:** index on `circuit_id`; index on (`circuit_id`, `backend`, `created_at` DESC) to fetch the latest run per circuit/backend quickly.

**Notes:** rows are immutable once written (append-only), per TRD §11 data-integrity requirement — never update a `simulation_runs` row; a re-run creates a new row. This keeps prediction-vs-actual comparisons and grading disputes auditable.

---

### 2.8 `predictions`

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `user_id` | `uuid` | FK → `users.id`, NOT NULL |
| `experiment_id` | `uuid` | FK → `experiments.id`, NOT NULL |
| `circuit_id` | `uuid` | FK → `circuits.id`, NOT NULL |
| `predicted_distribution` | `jsonb` | NOT NULL — e.g. `{"00": 0.5, "11": 0.5, "01": 0, "10": 0}` |
| `actual_run_id` | `uuid` | FK → `simulation_runs.id`, NULL until the student runs the circuit |
| `locked_at` | `timestamptz` | NOT NULL, default `now()` |

**Indexes:** index on (`user_id`, `experiment_id`).

**Notes:** `locked_at` exists (rather than relying on `created_at`) to make explicit that this timestamp represents the UI's "Lock Prediction" moment (per UI/UX §4) — the prediction is immutable after this point by product rule, enforced at the application layer.

---

### 2.9 `submissions`

Coding-challenge / auto-graded attempts, kept separate from `circuits` because a submission carries grading metadata a plain circuit doesn't.

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `user_id` | `uuid` | FK → `users.id`, NOT NULL |
| `experiment_id` | `uuid` | FK → `experiments.id`, NOT NULL |
| `circuit_id` | `uuid` | FK → `circuits.id`, NOT NULL |
| `run_id` | `uuid` | FK → `simulation_runs.id`, NOT NULL |
| `score` | `real` | NOT NULL, CHECK `score BETWEEN 0 AND 1` |
| `feedback` | `text` | NOT NULL — structured, human-readable grading feedback |
| `passed` | `boolean` | NOT NULL |
| `attempt_number` | `integer` | NOT NULL |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |

**Indexes:** index on (`user_id`, `experiment_id`, `attempt_number`).

---

### 2.10 `concept_mastery`

| Column | Type | Constraints |
|---|---|---|
| `user_id` | `uuid` | PK part, FK → `users.id` |
| `concept_id` | `uuid` | PK part, FK → `concepts.id` |
| `mastery_score` | `real` | NOT NULL, default `0`, CHECK `mastery_score BETWEEN 0 AND 1` |
| `attempts` | `integer` | NOT NULL, default `0` |
| `last_updated` | `timestamptz` | NOT NULL, default `now()` |

**Constraint:** composite PK on (`user_id`, `concept_id`).

**Notes:** updated by application logic after each graded submission/experiment completion, not recomputed from scratch on every read — this table is the materialized, fast-read source for the progress screen and adaptive-recommendation logic (PRD §6.16), avoiding an expensive aggregation query on every dashboard load.

---

### 2.11 `misconception_tags`

Fixed taxonomy (curated, faculty-reviewed per PRD §11), not freeform.

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `name` | `text` | NOT NULL, UNIQUE — e.g. `"superposition_as_classical_probability"` |
| `display_label` | `text` | NOT NULL — e.g. `"Confuses superposition with classical probability"` |
| `concept_id` | `uuid` | FK → `concepts.id`, NOT NULL |

### 2.12 `misconception_events`

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `user_id` | `uuid` | FK → `users.id`, NOT NULL |
| `experiment_id` | `uuid` | FK → `experiments.id`, NOT NULL |
| `tag_id` | `uuid` | FK → `misconception_tags.id`, NOT NULL |
| `source` | `text` | NOT NULL, CHECK IN (`'rule_based'`, `'ai_classified'`) |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |

**Indexes:** index on `tag_id` (for instructor dashboard's "most common misconception" aggregation); index on `user_id`.

---

### 2.13 `tutor_interactions`

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `user_id` | `uuid` | FK → `users.id`, NOT NULL |
| `experiment_id` | `uuid` | FK → `experiments.id`, NULL |
| `context_snapshot` | `jsonb` | NOT NULL — circuit, code, sim result ref, prediction ref, lesson id, history summary at time of asking |
| `question` | `text` | NOT NULL |
| `response` | `text` | NOT NULL |
| `grounded_sources` | `jsonb` | NOT NULL — array of `knowledge_base_entries.id` used to ground the response |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |

**Indexes:** index on `user_id`; index on `experiment_id`.

**Notes:** this table is append-only and exists primarily for auditability of the AI tutor (TRD §7.4) — it should be queryable by the team when reviewing whether the tutor stayed grounded, not just a debug log.

---

### 2.14 `knowledge_base_entries`

The curated, faculty-reviewed content the AI tutor is grounded against (TRD §7.2).

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `concept_id` | `uuid` | FK → `concepts.id`, NOT NULL |
| `title` | `text` | NOT NULL |
| `content` | `text` | NOT NULL |
| `reviewed_by` | `text` | NULL — faculty reviewer name, for provenance |
| `reviewed_at` | `timestamptz` | NULL |

**Indexes:** index on `concept_id`.

**Notes:** for MVP, retrieval can be a simple keyword/concept match (`WHERE concept_id = :current_concept`) rather than a vector-search pipeline — the content set is small and curated, so exact retrieval is both simpler and more auditable than embedding-based similarity search. Revisit only if the knowledge base grows large enough that concept tagging alone stops being precise.

---

### 2.15 `cohorts`

| Column | Type | Constraints |
|---|---|---|
| `id` | `uuid` | PK |
| `name` | `text` | NOT NULL |
| `instructor_id` | `uuid` | FK → `users.id`, NOT NULL |

### 2.16 `enrollments`

| Column | Type | Constraints |
|---|---|---|
| `cohort_id` | `uuid` | PK part, FK → `cohorts.id` |
| `student_id` | `uuid` | PK part, FK → `users.id` |
| `enrolled_at` | `timestamptz` | NOT NULL, default `now()` |

**Constraint:** composite PK on (`cohort_id`, `student_id`).

---

## 3. Enum Reference

Represented as `CHECK` constraints on `text` columns rather than native Postgres `ENUM` types, so new values (e.g. adding a `qbraid` backend, or a new experiment `type`) don't require an `ALTER TYPE` migration — just a constraint update.

| Field | Allowed values |
|---|---|
| `users.role` | `student`, `instructor` |
| `experiments.type` | `guided`, `debug`, `challenge` |
| `simulation_runs.backend` | `aer`, `pennylane`, `cirq`, `real_ibm` |
| `misconception_events.source` | `rule_based`, `ai_classified` |

---

## 4. Indexing Strategy Summary

| Table | Index | Reason |
|---|---|---|
| `users` | unique(`email`) | login lookup |
| `circuits` | (`owner_id`), (`experiment_id`) | "my circuits" and "starter circuit" lookups |
| `simulation_runs` | (`circuit_id`, `backend`, `created_at` DESC) | fetch latest run per circuit/backend without a full scan |
| `predictions` | (`user_id`, `experiment_id`) | prediction-vs-actual comparison on the Experiment Workspace |
| `submissions` | (`user_id`, `experiment_id`, `attempt_number`) | grading history and attempt-count checks |
| `misconception_events` | (`tag_id`), (`user_id`) | instructor dashboard aggregation, student drill-down |
| `tutor_interactions` | (`user_id`), (`experiment_id`) | audit/debug queries |
| `knowledge_base_entries` | (`concept_id`) | grounding retrieval |

---

## 5. Migration & Seeding Notes

- Migrations should be managed with a standard tool (e.g. Alembic for a FastAPI/Python backend) — one migration per schema change, checked into version control alongside the backend code.
- Seed data required before any demo: `concepts` + `concept_prerequisites` (the knowledge graph), 3 `modules` (Qubits/Superposition, Gates, Entanglement), their `experiments`, and at least one `misconception_tags` row per concept so the instructor dashboard has something real to show, not an empty state, during a demo.
- `knowledge_base_entries` must be populated and faculty-reviewed **before** the AI tutor is demoed — an empty knowledge base means the tutor has nothing to ground against, defeating the entire "circuit-aware, non-hallucinating tutor" pitch (PRD §6.7).

---

## 6. Deliberate Non-Decisions (left for implementation team)

- Whether `jsonb` columns (`gates`, `counts`, `statevector`) get GIN indexes depends on whether any feature actually needs to *query inside* them (e.g. "find all circuits containing a CNOT gate," relevant to the crowd-sourced puzzle feature, PRD §6.18/STRETCH). Don't add the index speculatively — add it if/when that feature is built.
- Soft-delete vs. hard-delete for `circuits`/`submissions` is left open; given the audit requirement on `simulation_runs`/`tutor_interactions`, the safer default is soft-delete (an `deleted_at` column) everywhere student work is involved, but this can be finalized alongside auth/privacy requirements.

---

*This schema implements the data models introduced in TRD §4. If feature scope changes in the PRD, update this document and the TRD together — they should never drift out of sync.*
