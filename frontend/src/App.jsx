import { useState } from 'react';

// Hardcoded valid Bell-state circuit matching POST /circuits/simulate schema
const BELL_CIRCUIT = {
  qubit_count: 2,
  gates: [
    { type: "H", target_qubits: [0], params: null, step_index: 0 },
    { type: "CNOT", target_qubits: [0, 1], params: null, step_index: 1 }
  ],
  shots: 1024
};

// Hardcoded deliberately broken circuit (CNOT with only 1 qubit) to verify 400 error handling
const INVALID_CIRCUIT = {
  qubit_count: 2,
  gates: [
    { type: "CNOT", target_qubits: [0], params: null, step_index: 0 }
  ],
  shots: 1024
};

const API_ENDPOINT = 'http://localhost:8000/circuits/simulate';

export default function App() {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

  async function executeSimulation(circuitPayload) {
    setLoading(true);
    setResponse(null);
    setError(null);

    try {
      const res = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(circuitPayload)
      });

      const data = await res.json();

      if (!res.ok) {
        // Capture specific error message returned by FastAPI validation (e.g. detail field)
        const errorMessage = data?.detail || `HTTP Error ${res.status}: ${JSON.stringify(data)}`;
        setError(errorMessage);
      } else {
        setResponse(data);
      }
    } catch (err) {
      // Network or connection failure
      setError(`Network error: Could not connect to ${API_ENDPOINT}. Ensure backend is running.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>Quantum Circuit Simulator - Pipeline Test</h1>
      <div style={{ marginBottom: '16px' }}>
        <button
          onClick={() => executeSimulation(BELL_CIRCUIT)}
          disabled={loading}
          style={{ marginRight: '10px' }}
        >
          Run Circuit
        </button>
        <button
          onClick={() => executeSimulation(INVALID_CIRCUIT)}
          disabled={loading}
        >
          Run Invalid Circuit
        </button>
      </div>

      {loading && <p>Simulating…</p>}

      {error && (
        <div style={{ color: 'red', marginTop: '16px' }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {response && (
        <div style={{ marginTop: '16px' }}>
          <h3>Simulation Result:</h3>
          <pre>{JSON.stringify(response, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
