# System Architecture (`Architecture.md`)
## Egreen-Quanta: Interactive Quantum Algorithm Learning Platform (SIH)

**Last Updated:** September 11, 2026  
**Status:** Initial Blueprint from PRD, TRD, UI/UX, & Backend Schema

---

## 1. High-Level Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Client (Web App)                                │
│ ┌──────────────────────┐ ┌────────────────────┐ ┌─────────────────────────┐ │
│ │ Circuit Canvas (DAG) │ │ Monaco Code Editor │ │ Visualizers             │ │
│ │ (Drag & Drop Gates)  │ │ (Qiskit / OpenQASM)│ │ (Bloch, Statevector,    │ │
│ └──────────┬───────────┘ └─────────┬──────────┘ │  Histograms, Unitary)   │ │
│            │                       │            └────────────▲────────────┘ │
│            └───────────┬───────────┘                         │              │
│                        ▼                                     │              │
│              Local Circuit AST & Parser                      │              │
│            ┌───────────┴───────────┐                         │              │
│ (≤ 4 qubits, instant)              │ (≥ 5 qubits or noise)   │              │
│            ▼                       ▼                         │              │
│   WebAssembly Client Sim      WebSocket / REST API           │              │
│   (Zero latency feedback)          │                         │              │
└────────────────────────────────────┼─────────────────────────┼──────────────┘
                                     │                         │
┌────────────────────────────────────▼─────────────────────────┴──────────────┐
│                            Backend Services (FastAPI)                       │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ API Gateway & Session Auth (JWT / Session Cookie)                       │ │
│ └───────┬──────────────┬──────────────┬──────────────┬─────────────┬──────┘ │
│         │              │              │              │             │        │
│   ┌─────▼────┐   ┌─────▼────┐   ┌─────▼────┐   ┌─────▼────┐  ┌─────▼────┐   │
│   │ Circuit  │   │Simulation│   │ AI Tutor │   │Progress  │  │Challenge │   │
│   │ Service  │   │Execution │   │ Service  │   │& Profile │  │& Grading │   │
│   │(Transpile│   │(Qiskit   │   │  Router  │   │(XP,      │  │(State &  │   │
│   │ AST/Sync)│   │ Aer/QPU) │   │          │   │ Streaks) │  │ Unitary) │   │
│   └─────┬────┘   └─────┬────┘   └─────┬────┘   └─────┬────┘  └─────┬────┘   │
│         │              │              │              │             │        │
│         └──────────────┴──────────────┼──────────────┴─────────────┘        │
│                                       │                                     │
│                        ┌──────────────▼──────────────┐                      │
│                        │  TRUSTED EXECUTION ENV (TEE)│                      │
│                        │  [Hardware-Isolated Enclave]│                      │
│                        │ ┌─────────────────────────┐ │                      │
│                        │ │ Remote Attestation Core │ │                      │
│                        │ │ (AMD SEV-SNP / Nitro)   │ │                      │
│                        │ ├─────────────────────────┤ │                      │
│                        │ │ Encrypted In-Memory LLM │ │                      │
│                        │ │ (vLLM / llama.cpp / ZDR)│ │                      │
│                        │ ├─────────────────────────┤ │                      │
│                        │ │ Private Circuit Sim &   │ │                      │
│                        │ │ Socratic Reasoning Core │ │                      │
│                        │ └─────────────────────────┘ │                      │
│                        │ Hardware Memory Encryption  │                      │
│                        │ Zero Host/Cloud Access      │                      │
│                        └──────────────┬──────────────┘                      │
│                                       ▼                                     │
│                        PostgreSQL Database (Prisma / SQL)                   │
│         (Users, Circuits, Curriculum Nodes, Challenge Attempts, Logs)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### 2.1 Frontend Subsystem
- **Circuit Canvas**: Interactive visual composer managing circuit depth, qubit register lines, gate placements, and parameter inputs. Maintains a canonical JSON AST.
- **Bi-directional Code Editor**: Monaco editor with syntax support for Python (Qiskit) and OpenQASM 2.0/3.0. Two-way sync keeps code and visual canvas coherent.
- **Visualizer Engine**:
  - **Bloch Sphere**: 3D Three.js/WebGL render for single-qubit pure state projections.
  - **Statevector Bar**: Amplitudes (magnitude + phase via color wheel).
  - **Measurement Histogram**: Probability distribution across computational basis states ($|00\dots\rangle$ to $|11\dots\rangle$).
  - **Step-by-Step Inspector**: State inspection slider after any discrete gate slice.

### 2.2 Simulation Engine
- **Tier 1 (Client-side / WebAssembly)**: Low-overhead JS/Wasm statevector simulator for $\le 4$ qubits. Provides instant ($\le 10$ms) feedback while dragging gates.
- **Tier 2 (Backend Aer Worker)**: Python-based Qiskit Aer backend for circuits up to 15 qubits, parameterized gates, shot noise sampling, and realistic noise models.
- **Tier 3 (Cloud Hardware / QPU)**: Optional asynchronous job queue dispatching to IBM Quantum / qBraid with result caching.

### 2.3 AI Tutor Service (Circuit-Aware)
- Unlike generic chatbots, the AI tutor receives a rich context payload on every query:
  - Current Circuit AST & QASM.
  - Execution statevector & measurement probabilities.
  - Expected vs. actual state comparison.
  - Active curriculum learning objective or challenge test condition.
- Guided Socratic prompt structure: hints before answers, conceptual grounding before syntax.

### 2.4 Persistence & Data Model (PostgreSQL)
- Built directly on the specifications in `SIH_Quantum_Platform_Backend_Schema.md`.
- Normalized entities for User Accounts, Courses, Modules, Lessons, Challenges, Submissions, Circuits, and Session Analytics.

### 2.5 Confidential Computing & TEE Subsystem (Hardware-Enforced Privacy)
- **The Core Problem with Standard AI Cloud Deployments:**
  - Student code, proprietary enterprise circuits, research IP, and conversational queries are transmitted to third-party endpoints.
  - Vulnerable to provider logging, model training ingestion, cloud operator snooping, and memory dumps.
- **TEE Hardware-Level Security:**
  - Deploys within a secure enclave (e.g., AWS Nitro Enclave, AMD SEV-SNP, Intel SGX, or GCP Confidential VM).
  - **Memory Encryption (MEK):** Hardware-generated AES keys encrypt volatile memory; neither the cloud provider, hypervisor root, nor rogue host processes can inspect enclave RAM.
  - **Remote Cryptographic Attestation:** Before the client transmits circuit definitions or prompts, the enclave produces an unforgeable hardware-signed attestation document (PCR measurements). The client validates that the binary running inside the enclave is the unaltered, official, zero-data-retention build.
  - **Zero-Data-Retention (ZDR):** Prompts, circuits, and responses exist only ephemerally in encrypted memory and are destroyed upon request completion. No external training logging is possible.

