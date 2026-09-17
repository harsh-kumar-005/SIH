# UI/UX Design Document
## Interactive Quantum Algorithm Learning Platform (SIH)

**Status:** Draft v1
**Companion to:** PRD, TRD
**Last updated:** September 11, 2026

---

## 0. Why this document exists

Most student projects in this space end up looking like a generic SaaS dashboard with a quantum logo pasted on — rounded cards, a hero gradient, an "AI Chat" bubble in the corner. That reads as templated, and judges have seen it a hundred times.

This document grounds every design decision in the actual subject matter: **circuits, waves, amplitudes, measurement, and experimentation** — not "dashboard #47 with a science theme." Every screen below is designed around what the *content* actually looks like (a circuit is a timeline of operations on parallel lines; a quantum state is a set of amplitudes with magnitude and phase; a measurement is a probability distribution), not around a generic component library.

---

## 1. Design Principles (specific to this product, not generic UX advice)

1. **The circuit is the interface, not a form.** Students should feel like they're manipulating a real physical diagram, not filling out fields. Gate placement should feel like arranging objects on a timeline, not selecting from a dropdown.
2. **State, not status.** Most apps show you "success/error." This app shows you *a quantum state* — amplitudes, probabilities, phase. Never flatten that into a generic green-checkmark pattern. A correct answer isn't just "✓ Correct" — it's the state converging to what was predicted.
3. **Prediction is a real commitment, not a formality.** The UI must make selecting a prediction feel deliberate (a genuine "lock in your answer" moment), or the pedagogy collapses into "click through to see the answer."
4. **The AI tutor is a lab partner reading the same instrument, not a chat window bolted on.** It should always visibly reference the specific circuit/result it's looking at — never float as a detached chatbot in a corner.
5. **Numbers are content, not decoration.** Probabilities, amplitudes, and phase values are the actual subject matter of this app. Typography and layout should treat them with the same care as headline text — not small grey mono text shoved into a corner.

---

## 2. Design Tokens

### 2.1 Color

Grounded in the subject: **superposition = two things blended; measurement = collapse to one.** The palette should visually distinguish "possibility" (soft, blended, uncertain) from "measured result" (defined, saturated, certain) — this maps directly onto real product moments (prediction state vs. result state).

| Token | Hex | Role |
|---|---|---|
| `paper` | `#EEF0F4` | Base background — cool light grey-blue, not cream (avoids the templated warm-cream tell) |
| `ink` | `#161A22` | Primary text — near-black with a blue undertone, not pure `#000` or `#111` |
| `superposition-violet` | `#6E5AD6` | Amplitude / "possibility" states, prediction UI, in-progress/uncertain moments |
| `collapse-cobalt` | `#1B4FE0` | Measured/actual results, "Run" action, confirmed states |
| `signal-amber` | `#E0982B` | Discrepancy / "what changed" / debug attention — used sparingly, never as a default accent |
| `void` | `#0D0F14` | Circuit canvas background only (the one place a dark surface is earned — it's literally where "empty qubit register" lives, like a blank stave) |
| `error-line` | `#C23B3B` | Broken circuit / failed test only |

Two colors carry real semantic weight: **violet = predicted/possible, cobalt = measured/actual.** This pairing should recur everywhere (histograms, statevector bars, prediction vs. result comparisons) so students learn to read it instinctively — it becomes part of the pedagogy, not just styling.

Avoid: warm terracotta/clay accents, all-black-with-one-neon-accent themes, rounded pastel SaaS cards, gradient washes as decoration.

### 2.2 Typography

- **Display/body:** *Literata* (serif) — used for lesson content, explanations, AI tutor prose. Serif improves long-form reading comfort (per typographic guidance) and visually separates "things you read" from "things you operate."
- **Data/code/labels:** *JetBrains Mono* — used for gate labels, qubit indices, amplitude values, code editor, probabilities. This is a genuine functional choice, not decoration: monospace keeps columns of numbers (probabilities, amplitudes) vertically aligned and scannable, which matters when comparing prediction vs. actual.
- Two families only. No tracked-out ALL-CAPS eyebrows, no middle-dot-joined meta strings, no arrow glyphs appended to buttons.
- Line length for lesson text: ~70 characters max, generous line-height (serif body).

### 2.3 Shape & Surface

- **Circuit builder canvas:** sharp rectangular gate tiles on horizontal qubit lines — this mirrors how circuits are actually drawn in every textbook and paper. No rounded "chip" gates; rounding here would misrepresent the subject.
- **Content surfaces (lesson cards, dashboard panels):** minimal, mostly-flat, thin 1px hairline dividers instead of drop-shadow cards. Reserve any elevation/shadow for the one surface that's genuinely floating above the canvas (e.g., the AI tutor panel when it's actively responding).
- Not everything gets the same corner radius. Circuit elements: 0px (sharp, diagram-accurate). Content panels: a single small radius (4px), used consistently, not as decoration on every div.

### 2.4 Motion

- One orchestrated moment: when a circuit runs, the state visibly "collapses" — amplitude bars (violet, uncertain) animate into measured probability bars (cobalt, defined). This is the single most important animation in the product because it *is* the concept being taught (superposition → measurement). Spend the animation budget here.
- Gate placement/removal: instant, no entrance animation — this needs to feel like direct manipulation, not a "reveal."
- No hover-lift on every card, no fade-slide-up on scroll. Motion only where it shows what changed.

---

## 3. Information Architecture

```
Landing / Login
  │
  ├── Student Home
  │     ├── Continue (last experiment)
  │     ├── Modules (Qubits → Gates → Entanglement → ...)
  │     └── Progress (concept mastery map)
  │
  ├── Experiment Workspace  ← core screen, most time spent here
  │     ├── Lesson panel (collapsible)
  │     ├── Circuit canvas
  │     ├── Prediction panel
  │     ├── Results panel (histogram / statevector / Bloch sphere / scrubber)
  │     ├── AI Tutor panel
  │     └── Challenge/Debug prompt (contextual)
  │
  ├── Noise Lab (variant of Experiment Workspace with a noise control)
  │
  └── Instructor Dashboard
        ├── Cohort overview
        ├── Misconception breakdown
        └── Student drill-down
```

The **Experiment Workspace is the product.** Everything else exists to get students into it faster or to report on what happened there. Don't over-invest in the home/landing screen — it's a launcher, not a destination.

---

## 4. Core Screen: Experiment Workspace

This is the screen judges will watch for 90% of the demo. It needs to hold five things at once without feeling cluttered: lesson context, the circuit, the prediction, the result, and the tutor.

```
┌──────────────────────────────────────────────────────────────────────┐
│ ≡ Entanglement · Bell State            [Predict locked ●]   ⚙ profile │
├───────────────────┬──────────────────────────────┬────────────────────┤
│ LESSON (collapsed  │  CIRCUIT                      │  AI TUTOR          │
│ to a thin rail     │                                │                    │
│ once student is    │  q0 ──[H]──●───────            │  "You predicted    │
│ mid-experiment —   │             │                  │   00/11 at 50%     │
│ tap to re-expand)  │  q1 ────────X───────            │   each — your      │
│                    │                                │   actual result    │
│  Two qubits can    │  gate palette:                 │   matches. The H   │
│  become            │  [H] [X] [Y] [Z] [●CNOT]       │   gate put q0 into │
│  correlated...     │                                │   superposition,   │
│                    │  ◀ step scrubber ▶  step 2/2    │   then CNOT        │
│                    │                                │   correlated q1."  │
├───────────────────┴──────────────────────────────┤                    │
│ PREDICTION (before run)      →      RESULT (after run)│  Ask about this   │
│                                                     │  circuit:          │
│  ░░ 00: 50%   ░░ 11: 50%    ██ 00: 51%  ██ 11: 49% │  [________] ↵      │
│  ░░ 01: 0%    ░░ 10: 0%     ░░ 01: 0%   ░░ 10: 0%  │                    │
│  (your guess, violet)       (measured, cobalt)      │                    │
│                                                     │                    │
│  [Run Circuit]              statevector · Bloch ▾   │                    │
└──────────────────────────────────────────────────────────────────────┘
```

### Key interaction details

- **Prediction lock:** the student must select a predicted distribution before "Run Circuit" becomes active. This isn't a dropdown — it's a set of bars the student drags/sets to a rough height, styled identically to the eventual result bars (violet vs. cobalt) so the visual comparison is immediate and legible, not a separate quiz widget bolted onto a simulator.
- **Prediction vs. result are shown in the same bar-chart shape, side by side** — never as two different chart types. The whole point is direct visual comparison.
- **The AI tutor panel is never empty and never generic.** On entry it shows a one-line grounded observation about the current circuit state (not "Ask me anything!"). The input is scoped to "Ask about this circuit," reinforcing that it isn't a general chatbot.
- **The scrubber (`◀ step scrubber ▶`)** lets a student step through the circuit gate-by-gate; the statevector/Bloch panel updates per step. This replaces a static "before/after" pair with a continuous read of the amplitude evolution — closer to how a physicist actually reasons about a circuit.
- **Lesson panel collapses to a thin vertical rail once the student starts building** — reading and doing shouldn't compete for the same screen space; the rail keeps context one tap away without stealing room from the circuit.

### Mobile / narrow viewport

Stack vertically in this order: Circuit → Prediction/Result → AI Tutor → Lesson rail (collapsed by default). The circuit and result comparison are the non-negotiable above-the-fold content; the tutor and lesson are reachable by scroll, not hidden behind a hamburger that hides the point of the screen.

---

## 5. Screen: Debug / Broken Circuit

Visually distinct from the normal build flow — signal-amber accent appears here and nowhere else in the default flow, so its presence itself communicates "something's wrong" before the student reads any text.

```
┌──────────────────────────────────────────────────────┐
│ ⚠ Debug: This circuit should create a Bell state       │
├──────────────────────────────────────────────────────┤
│  q0 ──[X]──●──                                          │
│             │                                           │
│  q1 ────────X──                                          │
│                                                          │
│  Expected: 00 ≈50% · 11 ≈50%                             │
│  Observed: 01 ≈50% · 10 ≈50%                             │
│                                                          │
│  AI Tutor: "Look at q0 before the entangling gate —      │
│  what state is it in, and is that what you wanted?"     │
│  [I want a hint]   [I think I found it]                 │
└──────────────────────────────────────────────────────┘
```

- The tutor's first move is **always a diagnostic question**, never the fix — the UI enforces this by only offering "I want a hint" (reveals a smaller nudge) vs. "I think I found it" (lets the student submit a corrected circuit), never a "Show me the answer" button.
- Expected vs. observed is text-first here (not a full chart) — at the debug stage the discrepancy itself is the content, so it should read fast, in one line, before the student dives back into the circuit.

---

## 6. Screen: Noise Lab

```
┌──────────────────────────────────────────────────────┐
│ Noise Lab                                              │
│                                                        │
│  Noise    ○──────●────────────────────  15%            │
│           0%                        100%               │
│                                                          │
│   IDEAL                    NOISY (15%)                  │
│   ██ 00: 50%                ██ 00: 42%                  │
│   ██ 11: 50%                ██ 11: 35%                  │
│   ░░ 01: 0%                 ░░ 01: 13%                  │
│   ░░ 10: 0%                 ░░ 10: 10%                  │
│                                                          │
│  "Real quantum hardware isn't perfect — as noise         │
│   increases, outcomes that should be impossible start   │
│   to appear. This is why error correction matters."     │
└──────────────────────────────────────────────────────┘
```

- The slider re-runs on release, not on every pixel of drag (avoids hammering the simulation service; per TRD §8 pattern of debounced recompute).
- Ideal and noisy results stay in fixed left/right positions as noise increases — bars should *degrade in place*, not reshuffle, so the eye can track the specific outcome that's drifting.

---

## 7. Screen: Instructor Dashboard

The thing that makes this useful is specificity — not another "average score: 78%" tile.

```
┌──────────────────────────────────────────────────────────┐
│ Cohort: Quantum 101 — Section A            42 students     │
├──────────────────────────────────────────────────────────┤
│ Most missed concept        Most common misconception       │
│ Entanglement (61% miss)    "Superposition = qubit is        │
│                             literally 0 and 1 at once"       │
│                             — 18 students                    │
├──────────────────────────────────────────────────────────┤
│ Needs intervention (3+ attempts, no progress)                │
│  • Aditi R.  — stuck on CNOT placement, 4 attempts            │
│  • Rohan K.  — confuses measurement with collapse, 3 attempts │
│  [message]     [assign review experiment]                     │
└──────────────────────────────────────────────────────────┘
```

- Every row is actionable (message, assign) — a dashboard that only displays numbers with no next action isn't worth building for the MVP.
- Misconceptions are shown as the actual tagged phrase (from the taxonomy in the TRD), not a numeric code — instructors shouldn't have to memorize a legend.

---

## 8. Content & Voice Guidance

- **AI tutor voice:** precise, a little dry, always specific to the circuit in front of it. Never "Great question!" or "I'd be happy to help!" — a lab partner doesn't open with enthusiasm, it opens with observation. E.g. *"Your q0 is in the |1⟩ state before the CNOT — that's probably not what you intended for a Bell state."*
- **Buttons say the actual action, matched to the resulting state:** `Run Circuit` → result panel populates. `Lock Prediction` → prediction bars freeze and Run becomes available. Never generic `Submit` / `Continue`.
- **Empty states are instructions, not apologies:** an unbuilt circuit canvas says *"Drag a gate onto q0 to begin"* — not "No circuit yet 😔."
- **Errors are specific:** *"CNOT needs a control and a target qubit — you've only set one."* Never a generic "Something went wrong."

---

## 9. Explicit "Don't Build This" List

To keep the team from drifting into templated territory under time pressure:

- ❌ A floating chat bubble icon in the corner that opens a generic chat window — the tutor lives in-panel, always visibly attached to the current circuit.
- ❌ Rounded pastel cards with drop shadows for every panel — reserve elevation for the one surface that's genuinely active (tutor mid-response).
- ❌ A hero landing page with a big gradient headline before the product — students should reach the Experiment Workspace in one click from login.
- ❌ ALL-CAPS section labels, middle-dot metadata strings, arrow glyphs on buttons.
- ❌ Green-checkmark/red-X as the only feedback language — this product's feedback language is *amplitude bars converging or diverging*, use that everywhere it fits.

---

## 10. Accessibility Baseline

- Color is never the only signal: violet (predicted) vs. cobalt (actual) bars are also labeled with text values, not color alone — same for noisy/ideal comparisons.
- Circuit builder: every gate placement reachable via keyboard (tab to a qubit/step position, enter to open gate picker, arrow keys to choose) — not just drag-and-drop, since drag-only interfaces exclude keyboard and some motor-impaired users.
- Visible focus states on all interactive elements (gate palette, tutor input, scrubber).
- Respect `prefers-reduced-motion`: the state-collapse animation (§2.4) should have an instant-transition fallback.

---

*This document should be read alongside the PRD (feature scope) and TRD (technical architecture). Wireframes here are intentionally low-fidelity — the goal is to lock interaction logic and content hierarchy before anyone opens Figma, so early visual exploration builds on real product decisions instead of generic component defaults.*
