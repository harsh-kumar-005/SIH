# Execution & Data Flow (`Flow.md`)
## Egreen-Quanta: End-to-End Traces

**Last Updated:** September 11, 2026  
**Status:** Canonical Flow Specifications

---

## 1. Flow 1: Circuit Drag-and-Drop & Instant Statevector Simulation

```
[User drags gate (e.g. H) onto Qubit 0]
                 │
                 ▼
1. Canvas Component (React / SVG Canvas)
   - Dispatches `PLACE_GATE` action with `{ gate: 'H', target: 0, step: 2 }`
                 │
                 ▼
2. Circuit State Store (Zustand / Redux)
   - Validates placement against qubit count and depth limit
   - Updates Canonical Circuit DAG / AST
                 │
                 ▼
3. Local Simulation Worker (WebAssembly / JS Engine)
   - Checks if qubit_count <= 4
   - Executes matrix multiplication across statevector tensor
   - Emits: `{ statevector: [...], probabilities: [...], bloch_vectors: [...] }`
                 │
                 ▼
4. Visualizer Dispatcher
   - Bloch Sphere: Updates 3D vector arrow $(x, y, z)$ on Qubit 0 sphere
   - Statevector Bar: Animates amplitude bars and phase colors ($|0\rangle \to \frac{1}{\sqrt{2}}|0\rangle + \frac{1}{\sqrt{2}}|1\rangle$)
   - Measurement Histogram: Renders 50/50 bars for $|0\rangle$ and $|1\rangle$
```

---

## 2. Flow 2: Guided Pedagogical Loop (Learn → Predict → Run → AI Explain)

```
1. Lesson Step Display: Shows prompt: "Predict outcome of Bell State circuit (H on Q0, CNOT on Q0->Q1)"
2. Student Input: Selects prediction on interactive probability slider (e.g., 50% |00>, 50% |11>)
3. Student builds & clicks "Run Circuit"
4. Discrepancy Engine:
   - Compares Student Prediction Vector vs. Simulated Output Vector
   - Detects delta (e.g., Student forgot H gate, got 100% |00>)
5. AI Tutor Request:
   - Assembles Context:
     * Current Circuit AST & QASM string
     * Simulation Output Statevector
     * Student Prediction & Discrepancy Note
     * Current Lesson Learning Objective
   - API Call to AI Tutor Service (`/api/v1/tutor/explain`)
6. AI Tutor Response:
   - Streams Socratic feedback: "Notice what happened to Qubit 0 before the CNOT. Is it in a superposition state?"
```

---

## 3. Flow 3: Code Editor <-> Visual Canvas Bi-directional Synchronization

```
[User edits Python Qiskit code in Monaco Editor]
                 │
                 ▼
1. Debounced AST Parser (250ms delay)
                 │
                 ▼
2. Python Qiskit AST Analyzer
   - Extracts circuit statements: `qc.h(0)`, `qc.cx(0, 1)`
   - Detects syntax errors or unsupported commands
                 │
                 ▼
3. Canonical Circuit AST Converter
   - Translates parsed operations into visual grid coordinate matrix
                 │
                 ▼
4. Canvas Re-render
   - Updates SVG grid lines and gate nodes smoothly without losing viewport zoom/pan
```

---

## 4. Flow 4: Cryptographically Attested TEE AI Tutor Flow (Zero-Leakage Inference)

```
[User submits question about proprietary/exercise circuit]
                         │
                         ▼
1. Client-Side Attestation Handshake
   - Client requests `/api/v1/tee/attestation`
   - Enclave generates Hardware Attestation Document with PCR hashes
   - Client verifies enclave signature against AMD / AWS root CA cert
                         │
                         ▼
2. Ephemeral Session Key Exchange (ECDH inside Enclave)
   - TLS tunnel terminates directly inside enclave memory
   - Host OS / cloud hypervisor cannot decrypt payload
                         │
                         ▼
3. Enclave Ingestion & Context Assembly
   - Decrypts circuit AST, student question, and execution vectors
   - Loads into encrypted RAM space (MEK - Memory Encryption Key)
                         │
                         ▼
4. Hardware-Isolated LLM Inference (vLLM / llama.cpp)
   - Runs model entirely within enclave memory bounds
   - Generates Socratic guidance without external API round-trips
   - Zero-Data-Retention: Context discarded immediately after generation
                         │
                         ▼
5. Encrypted Stream Delivery
   - Streams Socratic explanation back through secure channel to Client UI
   - No prompts or circuit logic logged to disk, database, or external servers
```

