# Product Requirements Document
## Interactive Quantum Algorithm Learning Platform (SIH)

**Status:** Draft v1
**Owner:** Team [Team Name]
**Last updated:** September 11, 2026

---

## 1. Purpose

Build an AI-assisted, interactive platform that teaches quantum computing through **experimentation**, not passive content consumption. The product's core thesis:

> Students learn quantum concepts by predicting circuit behavior, building circuits, running them, comparing prediction vs. reality, and debugging discrepancies with an AI tutor that understands their actual circuit and simulation state — not by reading articles or chatting with a generic LLM.

This PRD translates the research/strategy document into buildable scope: what we're building, for whom, in what order, and how we'll know it worked.

---

## 2. Background & Competitive Context

The SIH problem statement requires: learning content, a visual + code circuit builder, simulation via Qiskit/PennyLane/Cirq/qBraid, visualization (circuit diagrams, histograms, statevectors, Bloch spheres), AI assistance, quizzes/challenges with auto-grading, progress tracking, instructor analytics, and cloud deployment.

Nearly every individual piece already exists in some competitor:

| Competitor | Owns | Gap we exploit |
|---|---|---|
| IBM Quantum Composer/Learning | Circuit builder, sim, visualization, deep courses | Development tool, not a guided learning *loop* |
| Microsoft Quantum Katas | Theory + coding + Copilot + progress | Tied to Q#/Microsoft stack |
| PennyLane | Tutorials, Codebook, coding challenges | Developer/research-oriented, not beginner-first |
| Quirk | Instant drag-drop simulation feedback | No curriculum, no assessment |
| Classiq | AI-assisted quantum development | Engineering tool, not pedagogy |

**Conclusion:** we cannot win on feature checklist. We win on making the *loop* — Learn → Predict → Build → Run → Observe → Explain → Debug → Challenge → Master — the product itself, with an AI tutor that is circuit-aware rather than a generic chatbot.

---

## 3. Goals

### Product goals
- G1: Make every core quantum concept teachable through a hands-on experiment, not a static lesson.
- G2: Make the AI tutor demonstrably grounded in the student's actual circuit/simulation state (no hallucinated generic answers).
- G3: Give instructors actionable insight into *where and why* students struggle, not just scores.
- G4: Ship a narrow, polished, end-to-end demo rather than a broad, shallow feature set.

### Non-goals (for MVP)
- Building a custom quantum simulator (use Qiskit Aer / PennyLane / Cirq).
- Supporting every quantum algorithm — depth over breadth.
- Enterprise-grade auth, multi-tenant admin, billing, etc.
- Full multi-backend parity across all four frameworks on day one.

---

## 4. Target Users

| Persona | Need |
|---|---|
| **Beginner student** (target user) | Wants to *understand* quantum concepts intuitively, not just pass a quiz. Little to no linear algebra background. |
| **Instructor / TA** | Wants to see where a cohort collectively struggles and intervene early. |
| **SIH judges** (evaluation persona) | Want to see a coherent, demo-able, technically credible product with a clear differentiator in under ~5 minutes. |

---

## 5. Core Product Loop

```
LEARN → PREDICT → BUILD → RUN → OBSERVE → EXPLAIN → DEBUG → CHALLENGE → MASTER
```

Worked example (Entanglement):
1. **Learn** — short explanation + micro-animation of what entanglement means.
2. **Predict** — student picks expected measurement distribution before running anything.
3. **Build** — student drags H + CNOT onto a 2-qubit circuit (or writes it in code).
4. **Run** — circuit executes on Qiskit Aer.
5. **Observe** — histogram, statevector, Bloch sphere rendered.
6. **Explain** — AI tutor explains the *actual* result, referencing the student's prediction and their specific circuit.
7. **Debug** — if prediction ≠ result, AI guides root-cause identification instead of just stating the answer.
8. **Challenge** — student is asked to modify the circuit to hit a new target distribution.
9. **Master** — concept-level mastery is updated in the student's knowledge graph.

---

## 6. Feature Requirements

Each feature below is tagged **[MVP]**, **[WOW]**, or **[STRETCH]**.

### 6.1 Learning Modules — [MVP]
- 3 beginner modules at launch: Qubits & Superposition, Gates, Entanglement.
- Each module ends by feeding directly into a Predict→Build→Run experiment (no dead-end reading pages).
- **Acceptance criteria:** a student can complete a module end-to-end without leaving the experiment loop.

### 6.2 Circuit Builder (visual) — [MVP]
- Drag-and-drop gates (H, X, Y, Z, CNOT, S, T, measurement) onto a qubit grid (start with ≤5 qubits).
- Real-time (or near-real-time) recompute on gate change — inspired by Quirk's instant feedback, not "press Run and wait."
- **Acceptance criteria:** adding/removing a gate updates the circuit diagram instantly; running requires an explicit action only when compute cost is non-trivial.

### 6.3 Code Editor — [MVP]
- Qiskit-syntax editor as the first-class code path, synced bidirectionally with the visual builder where feasible.
- **Acceptance criteria:** a circuit built visually can be viewed as generated Qiskit code, and vice versa for a supported gate subset.

### 6.4 Simulation Backend — [MVP]
- Qiskit Aer as the primary backend at launch.
- Backend adapter layer designed so PennyLane/Cirq/qBraid can be added without rewriting the learning layer (see §8 Architecture).
- **Acceptance criteria:** circuit → simulation → results round-trip completes in a demo-acceptable time (<2s for ≤5 qubits, ideal case).

### 6.5 Visualization — [MVP]
- Measurement histogram, statevector display, Bloch sphere (single-qubit and reduced-state views).
- **Acceptance criteria:** all three visualizations update consistently from a single simulation run — no stale/inconsistent state across views.

### 6.6 Prediction-Before-Run — [WOW, high priority]
- Before executing, student selects/estimates the expected outcome (multiple choice for MVP; freeform probability entry as a stretch).
- System stores prediction alongside actual result for later comparison and analytics.
- **Acceptance criteria:** every guided experiment requires a prediction before the Run button is enabled.

### 6.7 Circuit-Aware AI Tutor — [MVP core, WOW in depth]
- AI tutor's context window includes: current lesson, current circuit (visual + code form), latest simulation output, and the student's prediction/history for that experiment.
- Answers are grounded against a **verified quantum knowledge base** (curated course content + algorithm definitions + circuit metadata), not open-ended LLM recall — reduces hallucination risk on physics claims.
- **Acceptance criteria:** asking "why did I get this result?" produces an answer referencing the student's actual gates and actual output distribution, not a generic textbook answer.

### 6.8 "What Changed?" Before/After Explainer — [WOW]
- When a student edits a circuit, show side-by-side before/after state + probabilities, with an AI-generated causal explanation of the delta.
- **Acceptance criteria:** any single-gate edit triggers a before/after comparison view without requiring a manual "compare" action.

### 6.9 Step-Through State Evolution ("Amplitude Scrubber") — [WOW, new]
- A scrubber under the circuit lets the student step through gate-by-gate execution, watching the statevector/Bloch sphere update at each step rather than only at start/end.
- **Rationale:** stronger technical differentiator than a static before/after — ties math to visualization continuously.
- **Acceptance criteria:** scrubbing to gate *n* shows the exact intermediate state after gates 1..n.

### 6.10 Quantum Circuit Debugger — [WOW]
- Present intentionally broken circuits (or the student's own incorrect attempt) and guide root-cause diagnosis rather than revealing the fix directly.
- **Acceptance criteria:** the AI's first response to a broken circuit is a diagnostic question or hint, not the corrected circuit.

### 6.11 Noise Lab — [WOW]
- Slider for noise level; show ideal vs. noisy histograms side by side with an explanation of the divergence.
- **Acceptance criteria:** noise level changes are reflected in a re-run simulation within the same session without a page reload.

### 6.12 Classical vs. Quantum Lab — [STRETCH]
- Side-by-side classical vs. quantum (e.g., Grover) behavior as problem size scales, with a simple scaling visualization.
- **Acceptance criteria:** student can vary N and see both classical attempt count and quantum query count update.

### 6.13 Real-Hardware Run — [WOW, new, demo moment]
- One-click send of a completed circuit to a free-tier real QPU (IBM Quantum / qBraid), compared against noisy-sim and ideal-sim results.
- **Acceptance criteria:** at least one polished demo path shows ideal-sim vs. noisy-sim vs. real-hardware histograms for the same circuit. Must have a cached fallback in case of API/queue failure during a live demo.

### 6.14 Coding Challenges & Auto-Grading — [MVP]
- Small challenge set (start with ≤10) with automated pass/fail + partial credit via test-circuit comparison.
- **Acceptance criteria:** a submitted circuit/code is graded without manual intervention and gives specific feedback (not just pass/fail).

### 6.15 Progress Tracking (concept-level) — [MVP]
- Track mastery per concept (not just per module/quiz), feeding a lightweight knowledge graph (Qubit → Superposition → Gates → Multi-qubit → Entanglement → …).
- **Acceptance criteria:** dashboard shows per-concept mastery, not only aggregate scores.

### 6.16 Adaptive Recommendation — [STRETCH]
- Recommend next experiment/mini-lesson based on weak prerequisite concepts rather than a fixed sequence.
- **Acceptance criteria:** two students with different error patterns are shown different "next" recommendations.

### 6.17 Instructor Dashboard with Misconception Tagging — [WOW, elevated priority]
- Beyond scores: tag *why* an answer was wrong against a small taxonomy (e.g., "confuses superposition with classical probability," "ignores relative phase," "wrong qubit ordering").
- Surface most-failed concepts, most-common misconceptions, and students needing intervention.
- **Acceptance criteria:** instructor view shows at least one misconception category per commonly-missed exercise, not just an aggregate score.

### 6.18 Crowd-Sourced Debug Puzzles — [STRETCH, new]
- After fixing a broken circuit, students can optionally submit their bug as a puzzle for classmates (moderated/curated before publishing).
- **Acceptance criteria:** a submitted puzzle can be reviewed and published by an instructor and then attempted by other students.

### 6.19 Multi-Backend Comparison — [STRETCH / PS requirement]
- Common internal circuit representation executable through Qiskit, PennyLane, and Cirq adapters; compare execution characteristics.
- **Acceptance criteria:** the same internal circuit can be executed through at least two backend adapters and results compared side by side.

### 6.20 Auth & Roles — [MVP, kept minimal]
- Basic student/instructor login. No SSO, no multi-tenant org management for MVP.

---

## 7. Explicitly Out of Scope for SIH Timeline

- Custom quantum simulator built from scratch.
- Broad algorithm library (20+ algorithms) — prioritize Bell states, Grover, and one more (Deutsch–Jozsa or teleportation) done *well*.
- Generic chatbot UI disconnected from circuit state.
- Full 4-framework parity (Qiskit + PennyLane + Cirq + qBraid) at MVP — architecture should allow it, implementation should not block MVP on it.
- Elaborate dashboards without a clear pedagogical payoff.

---

## 8. Technical Architecture (proposed)

```
Learner
  ↓
Web Application (frontend)
  ↓
Circuit / Code Representation (shared internal format)
  ↓
Backend Adapter Layer  ──────────────► AI Tutor Service
  ↓                                         ↑
Qiskit Aer (MVP) / PennyLane / Cirq / qBraid │
  ↓                                         │
Simulation Results ─────────────────────────┘
  ↓
Visualization + Assessment + Progress Layer
```

Key architectural principles:
- **Single internal circuit representation** decoupled from any one framework, so multi-backend support is additive, not a rewrite.
- **AI tutor as a service with structured context injection** (lesson + circuit + sim output + history), grounded against a curated knowledge base rather than open-ended generation, to reduce hallucination on physics claims.
- **Real-time-feel simulation** for small qubit counts (≤5–6) so the "instant feedback" UX (a la Quirk) is preserved without heavy backend round trips.

---

## 9. Success Metrics (for SIH evaluation + internal validation)

| Metric | Target |
|---|---|
| Demo completion time | Full Learn→Master loop demoable in under 5 minutes |
| AI tutor groundedness | 100% of tutor responses in the demo path reference the actual circuit/output, not generic text |
| Prediction accuracy delta | Track whether student prediction accuracy improves session-over-session (internal validation, not required for judging) |
| Instructor dashboard usefulness | At least 1 misconception category surfaced per commonly-missed MVP exercise |
| Fallback reliability | Live demo has a working cached fallback for AI + real-hardware calls in case of network/API failure |

---

## 10. Milestones (suggested)

| Phase | Deliverable |
|---|---|
| Phase 0 | Finalize PS requirement checklist + validate pedagogy assumptions with Prof. Ashok |
| Phase 1 | MVP loop working end-to-end for 1 concept (Entanglement) with Qiskit Aer only |
| Phase 2 | Expand to 3 modules; add Prediction-Before-Run + circuit-aware AI tutor |
| Phase 3 | Add 2 WOW features (recommend: Amplitude Scrubber + Misconception-tagged Instructor Dashboard) |
| Phase 4 | Add Noise Lab + Circuit Debugger if timeline allows |
| Phase 5 | Polish single end-to-end demo path + cached fallback for live-demo risk; rehearse pitch |

---

## 11. Open Questions for Faculty Validation

- Are our explanations of qubits, superposition, measurement, and entanglement scientifically accurate at a beginner level?
- Which algorithms are appropriate for a beginner-first platform (confirm: Bell state, Grover, one more)?
- Is prediction-before-execution pedagogically sound, or could it reinforce incorrect intuitions if not handled carefully?
- What is the correct, simplified way to explain amplitude/phase without introducing misconceptions?
- What common student misconceptions should the AI tutor's taxonomy include?
- How should noise/real-hardware limitations be framed for a beginner audience?

---

## 12. Suggested Pitch Line

> "We turn quantum computing from something students read about into something they experiment with. Our platform combines interactive learning, circuit construction, simulation, visualization, and a circuit-aware AI tutor into a single loop: Learn → Predict → Build → Run → Observe → Explain → Debug → Challenge."

---

## 13. Sources / References

- IBM Quantum Composer docs — https://quantum.cloud.ibm.com/docs/en/guides/composer
- Microsoft Quantum Katas — https://learn.microsoft.com/en-us/azure/quantum/katas-qdk-learning
- Microsoft Quantum Computing Fundamentals — https://learn.microsoft.com/en-us/training/paths/quantum-computing-fundamentals/
- PennyLane Codebook — https://www.pennylane.ai/codebook
- PennyLane Challenges — https://pennylane.ai/challenges/
- Quirk — https://algassert.com/quirk
- Classiq Quantum AI — https://www.classiq.io/quantum-ai

*This PRD builds on the team's prior research/strategy document and should be revisited after faculty validation and after the first end-to-end MVP build.*
