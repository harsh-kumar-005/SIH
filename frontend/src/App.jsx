/**
 * App.jsx
 * =======
 * Experiment Workspace — 2-qubit circuit builder.
 *
 * Layout (§4 of UIUX doc):
 *   Left  column: circuit canvas + gate palette + prediction panel + run + results
 *   Right column: AI Tutor panel (always visible, never modal)
 *
 * Color semantics (§2.1):
 *   violet (#6E5AD6) = superposition / predicted / uncertain
 *   cobalt (#1B4FE0) = measured / actual / confirmed
 *
 * Prediction UX (§3 Principle 3 + §4):
 *   Four bar-steppers — one per basis state |00⟩…|11⟩ — styled identically to
 *   the result bars so the visual comparison is immediate. Sum indicator live-
 *   updates; Lock button disabled until total = 1.0 (±0.001 float tolerance).
 *
 * Motion (§2.4):
 *   The one orchestrated moment: violet prediction bars animate into cobalt
 *   result bars in-place after simulation. Respects prefers-reduced-motion.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

// ─── API Endpoints ────────────────────────────────────────────────────────────
const BASE = 'http://localhost:8000';
const API = {
  simulate:       `${BASE}/circuits/simulate`,
  predict:        `${BASE}/predictions`,
  compare:        (id) => `${BASE}/predictions/${id}/compare`,
  tutor:          `${BASE}/tutor/ask`,
  debugBellState: `${BASE}/experiments/debug/bell-state`,
  signup:         `${BASE}/auth/signup`,
  login:          `${BASE}/auth/login`,
};

// ─── Circuit Constants ────────────────────────────────────────────────────────
const PALETTE_GATES = ['H', 'X', 'Y', 'Z', 'CNOT'];
const TIME_STEPS    = [0, 1, 2, 3];
const QUBITS        = [0, 1];
const BASIS_STATES  = ['00', '01', '10', '11'];

// SVG layout coordinates — void canvas (#0D0F14)
const SVG_W    = 480;
const SVG_H    = 180;
const STEP_X   = [130, 215, 300, 385];
const QUBIT_Y  = [62, 132];
const WIRE_X0  = 82;
const WIRE_X1  = 450;

// Stepper step size for prediction bars (5% per click)
const STEP_SIZE = 0.05;

// ─── Helpers ─────────────────────────────────────────────────────────────────
function formatComplex(amp) {
  if (!amp) return '0.000 + 0.000i';
  const r  = (amp.real  || 0).toFixed(3);
  const im = Math.abs(amp.imag || 0).toFixed(3);
  const sg = (amp.imag  || 0) >= 0 ? '+' : '−';
  return `${r} ${sg} ${im}i`;
}

function roundTo2(n) { return Math.round(n * 100) / 100; }

function predSum(dist) {
  return roundTo2(Object.values(dist).reduce((a, b) => a + b, 0));
}

// ─── Component ───────────────────────────────────────────────────────────────
export default function App() {
  // ── Circuit state ──────────────────────────────────────────────────────────
  // [{type, target_qubits, params:null, step_index}] — matches backend GateRequest shape
  const [gates,              setGates]              = useState([]);
  const [selectedGate,       setSelectedGate]       = useState('H');
  const [cnotControl,        setCnotControl]        = useState(null); // {qubit, step}

  // ── IDs ───────────────────────────────────────────────────────────────────
  const [userId,             setUserId]             = useState(null);
  const [circuitId,          setCircuitId]          = useState(null); // from last simulate
  const [runId,              setRunId]              = useState(null);
  const [predictionId,       setPredictionId]       = useState(null);

  // ── Simulation ────────────────────────────────────────────────────────────
  const [simLoading,         setSimLoading]         = useState(false);
  const [simResult,          setSimResult]          = useState(null);
  const [simError,           setSimError]           = useState(null);

  // ── Experiment Mode (Standard vs Debug vs Noise Lab) ───────────────────────
  const [experimentMode,     setExperimentMode]     = useState('standard'); // 'standard' | 'debug' | 'noise'
  const [debugChallenge,     setDebugChallenge]     = useState(null);
  const [debugHasRunOnce,    setDebugHasRunOnce]    = useState(false);

  // ── Noise Lab ─────────────────────────────────────────────────────────────
  const [noiseLevel,         setNoiseLevel]         = useState(0.0);
  const [noiseSliderVal,     setNoiseSliderVal]     = useState(0.0);
  const [idealSimResult,     setIdealSimResult]     = useState(null);
  const [noisySimResult,     setNoisySimResult]     = useState(null);
  const [noiseSimLoading,    setNoiseSimLoading]    = useState(false);
  const noiseDebounceTimer                          = useRef(null);

  // ── Auth — JWT stored in memory only, never localStorage ─────────────────
  const [authToken,   setAuthToken]   = useState(null);
  const [authUser,    setAuthUser]    = useState(null); // {id, email, role, display_name}
  const [authView,    setAuthView]    = useState('login'); // 'login' | 'signup'
  const [authForm,    setAuthForm]    = useState({ email: '', password: '', display_name: '', role: 'student' });
  const [authLoading, setAuthLoading] = useState(false);
  const [authError,   setAuthError]   = useState(null);
  // Ref mirrors token so callbacks don't close over a stale value
  const authTokenRef = useRef(null);
  useEffect(() => { authTokenRef.current = authToken; }, [authToken]);
  // Sync userId from auth user so existing ownership logic keeps working
  useEffect(() => { if (authUser?.id) setUserId(String(authUser.id)); }, [authUser]);

  // ── Scrubber ──────────────────────────────────────────────────────────────
  const [currentStep,        setCurrentStep]        = useState(0);

  // ── Prediction ───────────────────────────────────────────────────────────
  // Distribution: {state: probability 0..1} — student's guess
  const [predDist,           setPredDist]           = useState({ '00': 0.25, '01': 0.25, '10': 0.25, '11': 0.25 });
  const [predLocked,         setPredLocked]         = useState(false);
  const [predLoading,        setPredLoading]        = useState(false);
  const [predError,          setPredError]          = useState(null);

  // ── Compare ───────────────────────────────────────────────────────────────
  const [compareData,        setCompareData]        = useState(null); // {predicted, actual}
  const [compareError,       setCompareError]       = useState(null);

  // ── Tutor ─────────────────────────────────────────────────────────────────
  const [tutorMessages,      setTutorMessages]      = useState([
    // Grounded opening observation — never generic "Ask me anything!"
    {
      id: 0,
      type: 'grounded-observation',
      text: 'Build a circuit, set your prediction, then run it — I\'ll explain what happened and why.',
    },
  ]);
  const [tutorQuestion,      setTutorQuestion]      = useState('');
  const [tutorLoading,       setTutorLoading]       = useState(false);
  const [tutorError,         setTutorError]         = useState(null);
  const tutorBottomRef = useRef(null);
  const msgIdRef       = useRef(1);

  // ─── Scrubber & Statevector Evolution Derived State ────────────────────────
  const sortedGates = useMemo(() => {
    return [...gates].sort((a, b) => a.step_index - b.step_index);
  }, [gates]);

  const totalSteps = simResult?.per_gate_states?.length || 0;

  const activeStatevector = useMemo(() => {
    if (!simResult) return null;
    if (currentStep === 0) {
      // Step 0: Initial ground state |00⟩
      return [
        { real: 1.0, imag: 0.0 },
        { real: 0.0, imag: 0.0 },
        { real: 0.0, imag: 0.0 },
        { real: 0.0, imag: 0.0 },
      ];
    }
    if (simResult.per_gate_states && simResult.per_gate_states[currentStep - 1]) {
      return simResult.per_gate_states[currentStep - 1].statevector;
    }
    return simResult.final_statevector;
  }, [simResult, currentStep]);

  const stepLabel = useMemo(() => {
    if (!simResult) return '';
    if (currentStep === 0) return 'Initial ground state |00⟩ (before gates)';
    const gateState = simResult.per_gate_states?.[currentStep - 1];
    return gateState ? `After: ${gateState.after_gate}` : `Step ${currentStep}`;
  }, [simResult, currentStep]);

  // Global ArrowLeft / ArrowRight support for scrubber when simulation has completed
  useEffect(() => {
    if (!simResult || !simResult.per_gate_states) return;
    const maxStep = simResult.per_gate_states.length;
    function handleKeyDown(e) {
      if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        setCurrentStep((s) => Math.max(0, s - 1));
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        setCurrentStep((s) => Math.min(maxStep, s + 1));
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [simResult]);

  // ─── detailMsg — normalise FastAPI error detail to a plain string ───────────
  // FastAPI validation errors (422) return detail as an array of Pydantic error
  // objects: [{type, loc, msg, input, ctx}, …]. Setting that array directly in
  // state and rendering it as {authError} crashes React with "Objects are not
  // valid as a React child". This helper always returns a string.
  function detailMsg(data, fallback) {
    const d = data?.detail;
    if (!d) return fallback;
    if (typeof d === 'string') return d;
    if (Array.isArray(d)) return d.map((e) => e.msg || JSON.stringify(e)).join(' · ');
    return fallback;
  }

  // ─── authFetch — injects Authorization header from in-memory token ──────────
  // Uses a ref so the function identity is stable across renders and can safely
  // be called inside async callbacks without a stale-closure risk.
  function authFetch(url, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (authTokenRef.current) {
      headers['Authorization'] = `Bearer ${authTokenRef.current}`;
    }
    return fetch(url, { ...options, headers });
  }

  // ─── Auth handlers ────────────────────────────────────────────────────────
  async function handleLogin(e) {
    e?.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res  = await fetch(API.login, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authForm.email, password: authForm.password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAuthError(detailMsg(data, 'Invalid email or password.'));
        return;
      }
      // Store token and user in memory — never write to localStorage
      setAuthToken(data.access_token);
      setAuthUser(data.user);
    } catch {
      setAuthError('Network error — could not reach server.');
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleSignup(e) {
    e?.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res  = await fetch(API.signup, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email:        authForm.email,
          password:     authForm.password,
          display_name: authForm.display_name,
          role:         authForm.role,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAuthError(detailMsg(data, `Signup failed (${res.status})`));
        return;
      }
      // After signup, switch to login with a success hint
      setAuthView('login');
      setAuthError('Account created! Please log in.');
      setAuthForm((f) => ({ ...f, password: '' }));
    } catch {
      setAuthError('Network error — could not reach server.');
    } finally {
      setAuthLoading(false);
    }
  }

  function handleLogout() {
    // Wipe all in-memory auth state — session ends here
    setAuthToken(null);
    setAuthUser(null);
    setUserId(null);
    authTokenRef.current = null;
    clearAll();
    setAuthView('login');
    setAuthError(null);
    setAuthForm({ email: '', password: '', display_name: '', role: 'student' });
  }

  // ─── Auto-scroll tutor to latest message ─────────────────────────────────
  useEffect(() => {
    tutorBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [tutorMessages]);

  // ─── Derived: tutor context line ─────────────────────────────────────────
  // Shows current sequencing state so the tutor panel is never misleading
  const tutorContextLine = runId
    ? `Circuit ${circuitId?.slice(0, 8)}… · run completed`
    : predLocked
    ? `Circuit ${circuitId?.slice(0, 8)}… · prediction locked, not yet run`
    : 'Build a circuit and lock your prediction first';

  // ─── Gate interaction ──────────────────────────────────────────────────────

  function findGateAt(qubit, step) {
    return gates.find(
      (g) =>
        g.step_index === step &&
        (g.target_qubits.includes(qubit) ||
          (g.type === 'CNOT' && (g.target_qubits[0] === qubit || g.target_qubits[1] === qubit)))
    );
  }

  function handleSlotClick(qubit, step) {
    // Read-only in Noise Lab
    if (experimentMode === 'noise') return;

    // Circuit is frozen once prediction is locked — prevent silent post-lock edits
    // that would make the prediction meaningless. Student must Clear to start over.
    if (predLocked) return;

    setSimError(null);

    // Remove gate if already placed here
    const existing = findGateAt(qubit, step);
    if (existing) {
      setGates(gates.filter((g) => g !== existing));
      setCnotControl(null);
      return;
    }

    if (selectedGate === 'CNOT') {
      if (!cnotControl) {
        setCnotControl({ qubit, step });
      } else if (cnotControl.step === step && cnotControl.qubit !== qubit) {
        setGates([
          ...gates,
          { type: 'CNOT', target_qubits: [cnotControl.qubit, qubit], params: null, step_index: step },
        ]);
        setCnotControl(null);
      } else if (cnotControl.step !== step) {
        setCnotControl({ qubit, step });
      } else {
        setCnotControl(null); // same qubit → cancel
      }
      return;
    }

    setCnotControl(null);
    setGates([
      ...gates,
      { type: selectedGate, target_qubits: [qubit], params: null, step_index: step },
    ]);
  }

  // ─── Run Simulation ────────────────────────────────────────────────────────
  async function runCircuit() {
    setSimLoading(true);
    setSimError(null);
    setSimResult(null);
    setCompareData(null);
    setCompareError(null);
    setRunId(null);

    try {
      const res = await authFetch(API.simulate, {
        method: 'POST',
        body: JSON.stringify({
          qubit_count: 2,
          gates,
          shots: 1024,
          // Reuse existing circuit if already created so no duplicate rows
          circuit_id: circuitId || undefined,
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        setSimError(data?.detail || `Simulation failed (${res.status})`);
        return;
      }

      setSimResult(data);
      setCircuitId(data.circuit_id);
      setRunId(data.run_id);
      // Auto-reset scrubber to the final step N when run completes
      setCurrentStep(data.per_gate_states?.length || 0);

      const counts = data.measurement_counts || {};
      const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;

      // In Debug Mode:
      if (experimentMode === 'debug') {
        const p00 = (counts['00'] || 0) / total;
        const p11 = (counts['11'] || 0) / total;
        const isFixed = Math.abs(p00 - 0.5) <= 0.08 && Math.abs(p11 - 0.5) <= 0.08;

        if (isFixed) {
          addTutorMessage('grounded-observation',
            `Run complete! Target achieved: |00⟩ at ${(p00 * 100).toFixed(0)}%, |11⟩ at ${(p11 * 100).toFixed(0)}%. You fixed the bug!`
          );
        } else {
          const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
          addTutorMessage('grounded-observation',
            `Run complete: observed |${top?.[0]}⟩ at ~${((top?.[1] / total) * 100).toFixed(0)}%. Target was equal 50/50 |00⟩ and |11⟩.`
          );
        }

        // Auto-fire diagnostic tutor question on first run in debug mode
        if (!debugHasRunOnce) {
          setDebugHasRunOnce(true);
          autoAskDebugTutor(data.circuit_id, data.run_id);
        }
      } else {
        // Standard mode observation
        const topState = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
        const pct = topState ? ((topState[1] / 1024) * 100).toFixed(0) : '?';
        addTutorMessage('grounded-observation',
          `Run complete. Top outcome: |${topState?.[0] ?? '?'}⟩ at ~${pct}%. Ask me why.`
        );

        // Auto-fetch compare if prediction already locked
        if (predictionId) {
          fetchCompare(predictionId);
        }
      }
    } catch (err) {
      setSimError(`Network error — could not reach ${API.simulate}`);
    } finally {
      setSimLoading(false);
    }
  }

  // ─── Lock Prediction ───────────────────────────────────────────────────────
  // SEQUENCING: Lock creates the circuit record in DB first (POST /circuits),
  // then posts the prediction against that circuit_id. This enforces the
  // correct pedagogical order: build → predict → lock → THEN run.
  // Run Circuit is disabled until predLocked = true (see btn-run below).
  async function lockPrediction() {
    if (!authToken) {
      setPredError('Please log in before locking a prediction.');
      return;
    }
    if (gates.length === 0) {
      setPredError('Place at least one gate on the canvas before locking a prediction.');
      return;
    }

    setPredLoading(true);
    setPredError(null);

    try {
      // Step 1: Persist the circuit definition to DB so prediction has a valid circuit_id.
      // We do NOT simulate yet — that comes after the student commits their prediction.
      // owner_id is derived from JWT on the backend; no need to send it from the client.
      const circRes = await authFetch(`${BASE}/circuits`, {
        method: 'POST',
        body: JSON.stringify({ qubit_count: 2, gates }),
      });
      const circData = await circRes.json();
      if (!circRes.ok) {
        setPredError(circData?.detail || `Circuit creation failed (${circRes.status})`);
        return;
      }
      const newCircuitId = circData.id;
      setCircuitId(newCircuitId);

      // Step 2: Lock the student's prediction against that circuit.
      const predRes = await authFetch(API.predict, {
        method: 'POST',
        body: JSON.stringify({
          circuit_id:             newCircuitId,
          predicted_distribution: predDist,
        }),
      });
      const predData = await predRes.json();
      if (!predRes.ok) {
        setPredError(predData?.detail || `Prediction failed (${predRes.status})`);
        return;
      }

      setPredictionId(predData.id);
      setPredLocked(true);
      addTutorMessage('grounded-observation',
        `Prediction locked. You\'ve committed to that distribution — now run the circuit and see how close you were.`
      );
    } catch {
      setPredError(`Network error — could not lock prediction.`);
    } finally {
      setPredLoading(false);
    }
  }

  // ─── Fetch Compare ────────────────────────────────────────────────────────
  async function fetchCompare(pid) {
    setCompareError(null);
    try {
      const res  = await authFetch(API.compare(pid));
      const data = await res.json();
      if (!res.ok) {
        setCompareError(data?.detail || `Compare failed (${res.status})`);
        return;
      }
      setCompareData(data);
    } catch {
      setCompareError('Network error — could not fetch comparison.');
    }
  }

  // ─── Debug Challenge Handlers ─────────────────────────────────────────────
  async function enterDebugMode() {
    setSimLoading(true);
    setSimError(null);
    try {
      const res = await authFetch(API.debugBellState);
      const data = await res.json();
      if (!res.ok) {
        setSimError('Failed to load debug challenge.');
        return;
      }
      setExperimentMode('debug');
      setDebugChallenge(data);
      setGates(data.starter_circuit?.gates || []);
      setCnotControl(null);
      setSimResult(null);
      setCircuitId(null);
      setRunId(null);
      setPredLocked(false);
      setPredictionId(null);
      setCompareData(null);
      setDebugHasRunOnce(false);
      setCurrentStep(0);
      addTutorMessage('grounded-observation',
        `Debug Mode active: ${data.prompt} The broken starter circuit is on the canvas. Run it to see the bug, or ask for a hint.`
      );
    } catch {
      setSimError('Network error — could not load debug challenge.');
    } finally {
      setSimLoading(false);
    }
  }

  function exitDebugMode() {
    setExperimentMode('standard');
    setDebugChallenge(null);
    setDebugHasRunOnce(false);
    clearAll();
  }

  function exitSpecialModes() {
    setExperimentMode('standard');
    setDebugChallenge(null);
    setDebugHasRunOnce(false);
    setIdealSimResult(null);
    setNoisySimResult(null);
    setNoiseLevel(0.0);
    setNoiseSliderVal(0.0);
    clearAll();
  }

  // ─── Noise Lab Handlers ───────────────────────────────────────────────────
  const NOISE_BELL_GATES = [
    { type: 'H', target_qubits: [0], params: null, step_index: 0 },
    { type: 'CNOT', target_qubits: [0, 1], params: null, step_index: 1 },
  ];

  async function enterNoiseLab() {
    setExperimentMode('noise');
    setDebugChallenge(null);
    setDebugHasRunOnce(false);
    setGates(NOISE_BELL_GATES);
    setSelectedGate(null);
    setCnotControl(null);
    setPredLocked(false);
    setPredictionId(null);
    setCompareData(null);
    setNoiseLevel(0.0);
    setNoiseSliderVal(0.0);
    setNoiseSimLoading(true);
    setSimError(null);

    try {
      const res = await authFetch(API.simulate, {
        method: 'POST',
        body: JSON.stringify({
          qubit_count: 2,
          gates: NOISE_BELL_GATES,
          shots: 1024,
          noise_level: 0.0,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSimError(data?.detail || 'Simulation failed');
        return;
      }
      setIdealSimResult(data);
      setNoisySimResult(data);
      setSimResult(data);
      setCircuitId(data.circuit_id);
      setRunId(data.run_id);
      setCurrentStep(data.per_gate_states?.length || 0);

      addTutorMessage('grounded-observation',
        'Noise Lab active. Baseline ideal circuit loaded (0% noise: |00⟩ ≈ 50%, |11⟩ ≈ 50%). Move the slider to apply depolarizing noise and observe decoherence.'
      );
    } catch {
      setSimError('Network error loading Noise Lab baseline.');
    } finally {
      setNoiseSimLoading(false);
    }
  }

  async function handleNoiseChange(newNoiseVal) {
    setNoiseLevel(newNoiseVal);
    setNoiseSimLoading(true);
    setSimError(null);

    try {
      const res = await authFetch(API.simulate, {
        method: 'POST',
        body: JSON.stringify({
          qubit_count: 2,
          gates: NOISE_BELL_GATES,
          shots: 1024,
          noise_level: newNoiseVal,
          circuit_id: circuitId || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSimError(data?.detail || 'Noisy simulation failed');
        return;
      }
      setNoisySimResult(data);
      setSimResult(data);
      setRunId(data.run_id);
      setCurrentStep(data.per_gate_states?.length || 0);

      // Auto-fire tutor call with exact noise percentage and count framing
      autoAskNoiseTutor(data.circuit_id, data.run_id, newNoiseVal, data.measurement_counts);
    } catch {
      setSimError('Network error simulating with noise.');
    } finally {
      setNoiseSimLoading(false);
    }
  }

  function debouncedNoiseChange(val) {
    if (noiseDebounceTimer.current) {
      clearTimeout(noiseDebounceTimer.current);
    }
    noiseDebounceTimer.current = setTimeout(() => {
      handleNoiseChange(val);
    }, 500);
  }

  function handleSliderRelease() {
    if (noiseDebounceTimer.current) {
      clearTimeout(noiseDebounceTimer.current);
    }
    if (noiseSliderVal !== noiseLevel) {
      handleNoiseChange(noiseSliderVal);
    }
  }

  async function autoAskNoiseTutor(cId, rId, nLevel, noisyCounts) {
    setTutorLoading(true);
    setTutorError(null);
    const noisePct = Math.round(nLevel * 100);
    const idealCounts = idealSimResult?.measurement_counts || { '00': 512, '01': 0, '10': 0, '11': 512 };
    try {
      const res = await authFetch(API.tutor, {
        method: 'POST',
        body: JSON.stringify({
          circuit_id: cId,
          run_id: rId,
          question: `Can you explain the difference between the ideal Bell state and what we observed with ${noisePct}% depolarizing noise?`,
          experiment_type: 'noise',
          noise_level: nLevel,
          ideal_counts: idealCounts,
        }),
      });
      const data = await res.json();
      if (res.ok && data.response) {
        addTutorMessage('response', data.response);
      }
    } catch {
      // non-blocking
    } finally {
      setTutorLoading(false);
    }
  }

  async function autoAskDebugTutor(cId, rId) {
    setTutorLoading(true);
    setTutorError(null);
    try {
      const res = await authFetch(API.tutor, {
        method: 'POST',
        body: JSON.stringify({
          circuit_id: cId,
          run_id: rId,
          question: "Why didn't this circuit produce the target Bell state?",
          experiment_type: "debug",
        }),
      });
      const data = await res.json();
      if (res.ok && data.response) {
        addTutorMessage('response', data.response);
      }
    } catch {
      // non-blocking
    } finally {
      setTutorLoading(false);
    }
  }

  // ─── Ask Tutor ────────────────────────────────────────────────────────────
  async function askTutor() {
    const q = tutorQuestion.trim();
    if (!q) return;
    if (!circuitId) {
      setTutorError('Build and run a circuit first so I have something specific to explain.');
      return;
    }
    if (!runId) {
      setTutorError('Run the circuit first — I need the actual results to reference.');
      return;
    }

    setTutorError(null);
    setTutorLoading(true);

    // Show student question immediately
    addTutorMessage('question', q);
    setTutorQuestion('');

    try {
      const res = await authFetch(API.tutor, {
        method: 'POST',
        body: JSON.stringify({
          circuit_id: circuitId,
          run_id: runId,
          question: q,
          experiment_type: experimentMode === 'debug' ? 'debug' : experimentMode === 'noise' ? 'noise' : undefined,
          noise_level: experimentMode === 'noise' ? noiseLevel : undefined,
          ideal_counts: experimentMode === 'noise' ? (idealSimResult?.measurement_counts || undefined) : undefined,
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        addTutorMessage('error', data?.detail || `Tutor error (${res.status})`);
        return;
      }

      addTutorMessage('response', data.response);
    } catch {
      addTutorMessage('error', 'Network error — could not reach tutor endpoint.');
    } finally {
      setTutorLoading(false);
    }
  }

  function addTutorMessage(type, text) {
    const id = msgIdRef.current++;
    setTutorMessages((prev) => {
      // Replace grounded-observation with new one; append everything else
      if (type === 'grounded-observation') {
        return [
          ...prev.filter((m) => m.type !== 'grounded-observation'),
          { id, type, text },
        ];
      }
      return [...prev, { id, type, text }];
    });
  }

  // ─── Prediction stepper helpers ───────────────────────────────────────────
  function adjustPred(state, delta) {
    setPredDist((prev) => {
      const next = { ...prev, [state]: roundTo2(Math.max(0, Math.min(1, (prev[state] || 0) + delta))) };
      return next;
    });
  }

  const sum   = predSum(predDist);
  const sumOk = Math.abs(sum - 1.0) < 0.011; // float tolerance

  // ─── Histogram helper ─────────────────────────────────────────────────────
  function getActualProb(state) {
    if (!simResult?.measurement_counts) return 0;
    return (simResult.measurement_counts[state] || 0) / 1024;
  }

  // ─── Clear everything ─────────────────────────────────────────────────────
  function clearAll() {
    setGates([]);
    setCnotControl(null);
    setSimResult(null);
    setSimError(null);
    setCircuitId(null);
    setRunId(null);
    setPredDist({ '00': 0.25, '01': 0.25, '10': 0.25, '11': 0.25 });
    setPredLocked(false);
    setPredictionId(null);
    setCompareData(null);
    setCompareError(null);
    setPredError(null);
    setCurrentStep(0);
    setTutorMessages([{
      id: msgIdRef.current++,
      type: 'grounded-observation',
      text: 'Build a circuit, set your prediction, then run it — I\'ll explain what happened and why.',
    }]);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // AUTH SCREEN — shown when no JWT is held in memory
  // ─────────────────────────────────────────────────────────────────────────
  if (!authToken) {
    const isLogin  = authView === 'login';
    const isSuccess = isLogin && authError?.startsWith('Account created');
    return (
      <div className="auth-screen">
        <div className="auth-card">
          {/* Wordmark */}
          <div className="auth-brand">
            <span className="auth-brand-mark">⟨ψ|</span>
            <span className="auth-brand-name">Egreen Quanta</span>
          </div>
          <p className="auth-tagline">Explore quantum circuits. Build intuition. Learn by doing.</p>

          {/* Tab switcher */}
          <div className="auth-tab-row">
            <button
              type="button"
              className={`auth-tab${isLogin ? ' active' : ''}`}
              onClick={() => { setAuthView('login'); setAuthError(null); }}
            >Log In</button>
            <button
              type="button"
              className={`auth-tab${!isLogin ? ' active' : ''}`}
              onClick={() => { setAuthView('signup'); setAuthError(null); }}
            >Sign Up</button>
          </div>

          {/* Feedback banner */}
          {authError && (
            <div className={`auth-banner${isSuccess ? ' success' : ' error'}`} role="alert">
              {authError}
            </div>
          )}

          <form
            className="auth-form"
            onSubmit={isLogin ? handleLogin : handleSignup}
            noValidate
          >
            <label className="auth-label">
              Email
              <input
                id="auth-email"
                type="email"
                className="auth-input"
                placeholder="you@example.com"
                autoComplete="email"
                value={authForm.email}
                onChange={(e) => setAuthForm((f) => ({ ...f, email: e.target.value }))}
                required
                disabled={authLoading}
              />
            </label>

            {!isLogin && (
              <label className="auth-label">
                Display Name
                <input
                  id="auth-display-name"
                  type="text"
                  className="auth-input"
                  placeholder="Ada Lovelace"
                  autoComplete="name"
                  value={authForm.display_name}
                  onChange={(e) => setAuthForm((f) => ({ ...f, display_name: e.target.value }))}
                  required
                  disabled={authLoading}
                />
              </label>
            )}

            <label className="auth-label">
              Password
              <input
                id="auth-password"
                type="password"
                className="auth-input"
                placeholder={isLogin ? '••••••••' : 'Min. 8 characters'}
                autoComplete={isLogin ? 'current-password' : 'new-password'}
                value={authForm.password}
                onChange={(e) => setAuthForm((f) => ({ ...f, password: e.target.value }))}
                required
                disabled={authLoading}
              />
            </label>

            {!isLogin && (
              <label className="auth-label">
                Role
                <select
                  id="auth-role"
                  className="auth-input auth-select"
                  value={authForm.role}
                  onChange={(e) => setAuthForm((f) => ({ ...f, role: e.target.value }))}
                  disabled={authLoading}
                >
                  <option value="student">Student</option>
                  <option value="instructor">Instructor</option>
                </select>
              </label>
            )}

            <button
              id={isLogin ? 'btn-login' : 'btn-signup'}
              type="submit"
              className="auth-submit"
              disabled={authLoading}
            >
              {authLoading ? 'Please wait…' : isLogin ? 'Log In →' : 'Create Account →'}
            </button>
          </form>

          <p className="auth-footer-note">
            Session is kept in memory only — your token is never stored on disk.
          </p>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="workspace">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="workspace-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1>Entanglement · Bell State</h1>
          <div className="mode-toggle-group">
            <button
              type="button"
              className={`mode-toggle-btn${experimentMode === 'standard' ? ' active' : ''}`}
              onClick={exitSpecialModes}
            >
              Standard
            </button>
            <button
              type="button"
              id="btn-debug-mode"
              className={`mode-toggle-btn debug${experimentMode === 'debug' ? ' active' : ''}`}
              onClick={enterDebugMode}
            >
              🐞 Debug Mode
            </button>
            <button
              type="button"
              id="btn-noise-lab"
              className={`mode-toggle-btn noise${experimentMode === 'noise' ? ' active' : ''}`}
              onClick={enterNoiseLab}
            >
              🔬 Noise Lab
            </button>
          </div>
        </div>
        <div className="header-right-group">
          <div className="header-status">
            <span
              className={`status-dot ${predLocked ? 'locked' : ''} ${runId ? 'run' : ''}`}
            />
            {experimentMode === 'noise'
              ? `Noise Lab · ${Math.round(noiseLevel * 100)}% Noise`
              : experimentMode === 'debug'
              ? 'Debug Challenge active'
              : predLocked && runId
              ? 'Prediction locked · Run complete'
              : predLocked
              ? 'Prediction locked'
              : runId
              ? 'Run complete'
              : 'Building'}
          </div>
          {authUser && (
            <div className="auth-user-badge">
              <span className="auth-user-name">{authUser.display_name}</span>
              <span className="auth-user-role">{authUser.role}</span>
              <button
                type="button"
                id="btn-logout"
                className="auth-logout-btn"
                onClick={handleLogout}
              >
                Log Out
              </button>
            </div>
          )}
        </div>
      </header>

      {/* ══ LEFT COLUMN — circuit + prediction + results ═══════════════════════ */}
      <main className="workspace-main">

        {/* ── Debug Mode Banner (Amber Accent) ────────────────────────────────── */}
        {experimentMode === 'debug' && debugChallenge && (
          <div className="debug-banner" role="region" aria-label="Debug Challenge">
            <span className="debug-badge">Debug Challenge · Broken Bell State</span>
            <p className="debug-prompt-text">{debugChallenge.prompt}</p>
            <div className="debug-target-row">
              <span className="debug-target-pill">
                Target: <strong>|00⟩ ≈ 50%, |11⟩ ≈ 50%</strong> (tolerance ±5%)
              </span>
              <span className="palette-hint" style={{ margin: 0 }}>
                Edit gates on canvas, then Run Circuit to test your fix.
              </span>
            </div>
          </div>
        )}

        {/* ── Noise Lab Banner ────────────────────────────────────────────────── */}
        {experimentMode === 'noise' && (
          <div className="noise-banner" role="region" aria-label="Noise Lab Banner">
            <span className="noise-badge">Noise Lab · Depolarizing Error Channel</span>
            <p className="debug-prompt-text">
              Examine how physical hardware noise degrades quantum states. The mathematical statevector remains ideal, while physical measurement samples suffer depolarizing errors.
            </p>
          </div>
        )}

        {/* ── Gate Palette ─────────────────────────────────────────────────── */}
        {experimentMode === 'noise' ? (
          <section aria-label="Gate palette">
            <div className="section-label">circuit mode · fixed bell state</div>
            <div className="palette-readonly-notice">
              Circuit is locked to <strong>Bell State [H(q0), CNOT(q0, q1)]</strong> for noise and decoherence analysis.
            </div>
          </section>
        ) : (
          <section aria-label="Gate palette">
            <div className="section-label">gate palette</div>
            <div className="palette">
              {PALETTE_GATES.map((g) => (
                <button
                  key={g}
                  type="button"
                  id={`gate-btn-${g}`}
                  className={`palette-btn${selectedGate === g ? ' selected' : ''}`}
                  onClick={() => { setSelectedGate(g); setCnotControl(null); }}
                  aria-pressed={selectedGate === g}
                >
                  {g}
                </button>
              ))}
              {selectedGate === 'CNOT' && (
                <span className="palette-hint">
                  {cnotControl
                    ? `Control set on q${cnotControl.qubit} · step ${cnotControl.step} — click target qubit at same step`
                    : 'CNOT: click control qubit, then target qubit at the same step'}
                </span>
              )}
            </div>
          </section>
        )}

        {/* ── Circuit Canvas (void surface) ─────────────────────────────────── */}
        <section aria-label="Circuit canvas">
          <div className="section-label">circuit · 2 qubits · 4 steps</div>

          {simError && (
            <div className="inline-error" role="alert">
              {simError}
            </div>
          )}

          <div className="circuit-canvas-wrap">
            <svg
              width={SVG_W}
              height={SVG_H}
              style={{ display: 'block', width: '100%', height: 'auto' }}
              role="img"
              aria-label="2-qubit quantum circuit diagram"
            >
              {/* Step column headers */}
              {TIME_STEPS.map((step) => (
                <text
                  key={`hdr-${step}`}
                  x={STEP_X[step]}
                  y={20}
                  textAnchor="middle"
                  fontSize={11}
                  fill="#8890A0"
                  fontFamily="'JetBrains Mono', monospace"
                >
                  step {step}
                </text>
              ))}

              {/* Qubit wires + labels */}
              {QUBITS.map((q) => {
                const y = QUBIT_Y[q];
                return (
                  <g key={`wire-${q}`}>
                    <text
                      x={10} y={y + 5}
                      fontSize={13} fontWeight={600}
                      fill="#EEF0F4"
                      fontFamily="'JetBrains Mono', monospace"
                    >
                      q{q}
                    </text>
                    <text
                      x={36} y={y + 5}
                      fontSize={12}
                      fill="#8890A0"
                      fontFamily="'JetBrains Mono', monospace"
                    >
                      |0⟩
                    </text>
                    {/* Qubit wire */}
                    <line
                      x1={WIRE_X0} y1={y}
                      x2={WIRE_X1} y2={y}
                      stroke="#8890A0" strokeWidth={1.5}
                    />
                  </g>
                );
              })}

              {/* Clickable slot targets (invisible hit areas + dashed empty markers) */}
              {QUBITS.map((q) =>
                TIME_STEPS.map((step) => {
                  const x   = STEP_X[step];
                  const y   = QUBIT_Y[q];
                  const occ = findGateAt(q, step);
                  const isPendingControl =
                    cnotControl && cnotControl.qubit === q && cnotControl.step === step;
                  const isReadOnly = predLocked || experimentMode === 'noise';

                  return (
                    <g
                      key={`slot-${q}-${step}`}
                      id={`slot-q${q}-s${step}`}
                      role={isReadOnly ? undefined : 'button'}
                      aria-label={isReadOnly ? undefined : `Qubit ${q} step ${step}`}
                      tabIndex={isReadOnly ? -1 : 0}
                      onClick={() => handleSlotClick(q, step)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSlotClick(q, step)}
                      style={{ cursor: isReadOnly ? 'default' : 'pointer' }}
                    >
                      {/* Broad invisible click target */}
                      <rect x={x - 24} y={y - 24} width={48} height={48} fill="transparent" />
                      {/* Dashed empty slot indicator — hidden after lock or in Noise Lab */}
                      {!occ && !isPendingControl && !isReadOnly && (
                        <rect
                          x={x - 18} y={y - 18} width={36} height={36}
                          fill="none"
                          stroke="#2A2E3A"
                          strokeDasharray="3,2"
                          rx={0}
                        />
                      )}
                      {/* Pending CNOT control indicator */}
                      {isPendingControl && (
                        <circle
                          cx={x} cy={y} r={7}
                          fill={`none`}
                          stroke="#6E5AD6"
                          strokeWidth={2}
                          strokeDasharray="3,2"
                        />
                      )}
                    </g>
                  );
                })
              )}

              {/* Render placed gates with active step highlight & future gate opacity */}
              {gates.map((gate, idx) => {
                const step = gate.step_index;
                const x    = STEP_X[step];
                const gateRank = sortedGates.findIndex((g) => g === gate);
                const isCurrentStepGate = simResult && currentStep > 0 && gateRank === currentStep - 1;
                const isFutureGate = simResult && (currentStep === 0 || gateRank > currentStep - 1);
                const gateOpacity = isFutureGate ? 0.35 : 1.0;

                if (gate.type === 'CNOT') {
                  const yCtrl = QUBIT_Y[gate.target_qubits[0]];
                  const yTgt  = QUBIT_Y[gate.target_qubits[1]];
                  const cnotStroke = isCurrentStepGate ? 'var(--collapse-cobalt)' : '#EEF0F4';
                  return (
                    <g
                      key={`gate-${idx}`}
                      id={`placed-gate-${idx}`}
                      onClick={predLocked ? undefined : () => setGates(gates.filter((_, i) => i !== idx))}
                      style={{
                        cursor: predLocked ? 'default' : 'pointer',
                        opacity: gateOpacity,
                        transition: 'opacity 0.18s ease',
                      }}
                      role={predLocked ? undefined : "button"}
                      aria-label={predLocked ? undefined : `Remove CNOT gate at step ${step}`}
                    >
                      {/* Vertical connecting line */}
                      <line
                        x1={x} y1={yCtrl} x2={x} y2={yTgt}
                        stroke={cnotStroke} strokeWidth={isCurrentStepGate ? 3 : 2}
                      />
                      {/* Control: filled solid dot */}
                      <circle cx={x} cy={yCtrl} r={isCurrentStepGate ? 7 : 6} fill={cnotStroke} />
                      {/* Target: ⊕ — open circle + crosshair */}
                      <circle
                        cx={x} cy={yTgt} r={13}
                        fill="#0D0F14" stroke={cnotStroke} strokeWidth={isCurrentStepGate ? 2.5 : 2}
                      />
                      <line
                        x1={x - 13} y1={yTgt} x2={x + 13} y2={yTgt}
                        stroke={cnotStroke} strokeWidth={isCurrentStepGate ? 2 : 1.5}
                      />
                      <line
                        x1={x} y1={yTgt - 13} x2={x} y2={yTgt + 13}
                        stroke={cnotStroke} strokeWidth={isCurrentStepGate ? 2 : 1.5}
                      />
                    </g>
                  );
                }

                // Single-qubit gate: sharp-cornered rectangle tile (rx=0 per spec §2.3)
                const q = gate.target_qubits[0];
                const y = QUBIT_Y[q];
                const tileStroke = isCurrentStepGate ? 'var(--collapse-cobalt)' : '#EEF0F4';
                return (
                  <g
                    key={`gate-${idx}`}
                    id={`placed-gate-${idx}`}
                    onClick={predLocked ? undefined : () => setGates(gates.filter((_, i) => i !== idx))}
                    style={{
                      cursor: predLocked ? 'default' : 'pointer',
                      opacity: gateOpacity,
                      transition: 'opacity 0.18s ease',
                    }}
                    role={predLocked ? undefined : "button"}
                    aria-label={predLocked ? undefined : `Remove ${gate.type} gate at qubit ${q} step ${step}`}
                  >
                    {isCurrentStepGate && (
                      <rect
                        x={x - 23} y={y - 23} width={46} height={46}
                        fill="none"
                        stroke="var(--collapse-cobalt)"
                        strokeWidth={1.5}
                        strokeDasharray="3,2"
                      />
                    )}
                    <rect
                      x={x - 19} y={y - 19} width={38} height={38}
                      fill="#1A1E28" stroke={tileStroke} strokeWidth={isCurrentStepGate ? 2.5 : 1.5}
                      rx={0} ry={0}
                    />
                    <text
                      x={x} y={y + 5}
                      textAnchor="middle"
                      fontWeight={600}
                      fontSize={13}
                      fill={isCurrentStepGate ? '#5B8CFF' : '#EEF0F4'}
                      fontFamily="'JetBrains Mono', monospace"
                    >
                      {gate.type}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          <div style={{ marginTop: 8 }}>
            <span className="section-label">
              {gates.length} gate{gates.length !== 1 ? 's' : ''} — click a placed gate to remove it
            </span>
          </div>

          {/* ── Amplitude Evolution Scrubber (directly below circuit canvas) ── */}
          {simResult && totalSteps > 0 && (
            <div
              className="scrubber-panel"
              role="region"
              aria-label="Amplitude evolution scrubber"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'ArrowLeft') {
                  e.preventDefault();
                  setCurrentStep((s) => Math.max(0, s - 1));
                } else if (e.key === 'ArrowRight') {
                  e.preventDefault();
                  setCurrentStep((s) => Math.min(totalSteps, s + 1));
                }
              }}
            >
              <div className="scrubber-controls">
                <div className="scrubber-step-info">
                  <span className="section-label" style={{ marginBottom: 0 }}>Evolution</span>
                  <span className="scrubber-counter" id="scrubber-step-counter">
                    ◀ Step {currentStep} / {totalSteps} ▶
                  </span>
                  <span className="scrubber-badge">
                    {currentStep === 0 ? 'Ground' : currentStep === totalSteps ? 'Final' : 'Active'}
                  </span>
                </div>

                <div className="scrubber-btn-group">
                  <button
                    type="button"
                    className="scrubber-btn"
                    id="btn-scrubber-prev"
                    onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}
                    disabled={currentStep === 0}
                    aria-label="Previous evolution step"
                    title="Previous step (ArrowLeft)"
                  >
                    ◀
                  </button>
                  <button
                    type="button"
                    className="scrubber-btn"
                    id="btn-scrubber-next"
                    onClick={() => setCurrentStep((s) => Math.min(totalSteps, s + 1))}
                    disabled={currentStep === totalSteps}
                    aria-label="Next evolution step"
                    title="Next step (ArrowRight)"
                  >
                    ▶
                  </button>
                </div>
              </div>

              <div className="scrubber-desc" id="scrubber-step-label">
                <span>{stepLabel}</span>
                <span className="scrubber-hint">(keyboard: ◀ / ▶)</span>
              </div>
            </div>
          )}
        </section>

        {/* ── Prediction Panel (Standard mode only) ────────────────────────── */}
        {experimentMode === 'standard' && (
          <section aria-label="Prediction panel">
            <div className="prediction-panel">
              <div className="section-label">
                {predLocked ? 'prediction locked ●' : 'your prediction — set before running'}
              </div>

              {/* Four bar-steppers: identical visual shape to result bars (§3 Principle 3) */}
              <div className="pred-bars">
                {BASIS_STATES.map((state) => {
                  const val = predDist[state] || 0;
                  const pct = (val * 100).toFixed(0);
                  return (
                    <div key={state} className="pred-bar-col">
                      <span className="pred-bar-pct">{pct}%</span>
                      <div className="pred-bar-track">
                        <div
                          className="pred-bar-fill"
                          style={{ height: `${pct}%` }}
                        />
                      </div>
                      <span className="pred-bar-label">|{state}⟩</span>

                      {/* Stepper buttons: ±5% steps */}
                      {!predLocked && (
                        <div className="pred-steppers">
                          <button
                            type="button"
                            className="pred-step-btn"
                            onClick={() => adjustPred(state, 0.05)}
                            aria-label={`Increase |${state}⟩ by 5%`}
                          >
                            +
                          </button>
                          <button
                            type="button"
                            className="pred-step-btn"
                            onClick={() => adjustPred(state, -0.05)}
                            aria-label={`Decrease |${state}⟩ by 5%`}
                            disabled={val <= 0}
                          >
                            -
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Sum indicator + Lock button — live validation */}
              <div className="pred-footer">
                {predLocked ? (
                  <div className="pred-locked-notice">
                    <span className="pred-locked-dot" />
                    <span>prediction locked — run circuit to see results</span>
                  </div>
                ) : (
                  <>
                    <span
                      className={`pred-sum-indicator${sumOk && gates.length > 0 ? ' valid' : ' invalid'}`}
                      aria-live="polite"
                    >
                      {!sumOk
                        ? `Prediction must sum to 1.0 — currently ${sum.toFixed(2)}`
                        : gates.length === 0
                        ? `Sum = 1.00 ✓ — place gates on circuit above to enable locking`
                        : `Sum = 1.00 ✓`}
                    </span>
                    <button
                      type="button"
                      id="btn-lock-prediction"
                      className="btn-lock"
                      disabled={!sumOk || predLoading || gates.length === 0}
                      onClick={lockPrediction}
                      title={gates.length === 0 ? 'Place at least one gate on the canvas above before locking' : !sumOk ? 'Probabilities must sum to 1.0' : 'Lock prediction'}
                    >
                      {predLoading ? 'Locking…' : gates.length === 0 ? 'Place Gates First' : 'Lock Prediction'}
                    </button>
                  </>
                )}
              </div>

              {predError && (
                <p className="inline-error" role="alert">{predError}</p>
              )}
            </div>
          </section>
        )}

        {/* ── Action Bar ───────────────────────────────────────────────────── */}
        <section aria-label="Run controls">
          <div className="action-bar">
            {experimentMode === 'noise' ? (
              <button
                type="button"
                id="btn-run-circuit"
                className="btn-run"
                onClick={() => handleNoiseChange(noiseSliderVal)}
                disabled={noiseSimLoading}
              >
                {noiseSimLoading ? 'Simulating…' : `Re-run with ${Math.round(noiseSliderVal * 100)}% Noise`}
              </button>
            ) : (
              <button
                type="button"
                id="btn-run-circuit"
                className="btn-run"
                onClick={runCircuit}
                disabled={simLoading || (experimentMode === 'standard' && !predLocked) || gates.length === 0}
                title={experimentMode === 'standard' && !predLocked ? 'Lock your prediction first — then Run Circuit' : undefined}
              >
                {simLoading ? 'Simulating…' : 'Run Circuit'}
              </button>
            )}

            <button
              type="button"
              id="btn-clear"
              className="btn-secondary"
              onClick={experimentMode === 'noise' ? enterNoiseLab : clearAll}
              disabled={simLoading || noiseSimLoading}
            >
              {experimentMode === 'noise' ? 'Reset (0% Noise)' : 'Clear'}
            </button>

            {simLoading && (
              <span className="action-hint">Running on Aer simulator…</span>
            )}
            {experimentMode === 'standard' && !predLocked && !simLoading && (
              <span className="action-hint">
                {gates.length === 0
                  ? 'Place gates on the circuit, then lock your prediction to enable Run'
                  : 'Lock your prediction to enable Run Circuit'}
              </span>
            )}
            {experimentMode === 'debug' && !simLoading && (
              <span className="action-hint" style={{ color: 'var(--signal-amber)' }}>
                Debug Mode: edit circuit freely, then Run Circuit to test your fix
              </span>
            )}
            {experimentMode === 'noise' && !noiseSimLoading && (
              <span className="action-hint" style={{ color: 'var(--collapse-cobalt)' }}>
                Noise Lab: adjust slider to simulate depolarizing errors on physical hardware
              </span>
            )}
          </div>
          {simError && (
            <p className="inline-error" role="alert" style={{ marginTop: 8 }}>{simError}</p>
          )}
        </section>

        {/* ── Results Panel: Compare + Statevector ─────────────────────────── */}
        {(simResult || compareData || noisySimResult || idealSimResult) && (
          <section aria-label="Results">
            <div className="results-panel">
              <div className="section-label">
                {experimentMode === 'noise'
                  ? 'noise lab results · ideal math vs. noisy sampling'
                  : experimentMode === 'debug'
                  ? 'debug results · target vs. observed'
                  : compareData
                  ? 'prediction vs. result'
                  : 'measurement result'}
              </div>

              {/* Debug Mode: Target vs Observed Comparison Banner */}
              {experimentMode === 'debug' && simResult?.measurement_counts && (() => {
                const counts = simResult.measurement_counts;
                const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
                const p00 = ((counts['00'] || 0) / total * 100).toFixed(0);
                const p11 = ((counts['11'] || 0) / total * 100).toFixed(0);
                const isFixed = Math.abs(p00 - 50) <= 8 && Math.abs(p11 - 50) <= 8;
                return (
                  <div className={`debug-comparison-box${isFixed ? ' fixed' : ''}`}>
                    <div>
                      <span><strong>Target:</strong> |00⟩ ≈ 50%, |11⟩ ≈ 50%</span>
                      <span style={{ margin: '0 8px', color: 'var(--hairline)' }}>|</span>
                      <span><strong>Observed:</strong> {Object.entries(counts).filter(([, v]) => v > 0).map(([k, v]) => `|${k}⟩: ${((v / total) * 100).toFixed(0)}%`).join(', ') || 'none'}</span>
                    </div>
                    <span className={`debug-status-badge ${isFixed ? 'fixed' : 'mismatch'}`}>
                      {isFixed ? '✓ Bell State Fixed!' : '⚠️ Bug Present — Mismatch'}
                    </span>
                  </div>
                );
              })()}

              {compareError && (
                <p className="inline-error" role="alert">{compareError}</p>
              )}

              {/* ── Side-by-side bar chart: violet (predicted) + cobalt (actual) ── */}
              {experimentMode === 'noise' ? (
                <div className="dual-histogram-grid">
                  {/* Left Column: Ideal (0% Noise) */}
                  <div className="dual-hist-col">
                    <div className="dual-hist-header">
                      <span className="dual-hist-title">Ideal (0% Noise)</span>
                      <span className="dual-hist-subtitle">Theoretical Bell state sampling (cached)</span>
                    </div>
                    <div className="compare-bars noise-hist-bars" aria-label="Ideal distribution">
                      {BASIS_STATES.map((state) => {
                        const count = idealSimResult?.measurement_counts?.[state] ?? 0;
                        const total = Object.values(idealSimResult?.measurement_counts || {}).reduce((a, b) => a + b, 0) || 1024;
                        const prob = count / total;
                        const pct = Math.max(2, prob * 100);
                        return (
                          <div key={`ideal-${state}`} className="compare-group">
                            <div className="compare-bars-pair">
                              <div
                                className="cmp-bar ideal"
                                style={{ height: `${pct}%` }}
                                title={`Ideal |${state}⟩: ${(prob * 100).toFixed(1)}% (${count} shots)`}
                              />
                            </div>
                            <div className="cmp-pct-row">
                              <span className="cmp-pct actual">{(prob * 100).toFixed(1)}%</span>
                            </div>
                            <span className="compare-group-label">|{state}⟩</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Right Column: Noisy (X% Noise) */}
                  <div className="dual-hist-col">
                    <div className="dual-hist-header">
                      <span className="dual-hist-title">Noisy ({Math.round(noiseLevel * 100)}% Noise)</span>
                      <span className="dual-hist-subtitle">Depolarizing error channel</span>
                    </div>
                    <div className="compare-bars noise-hist-bars" aria-label={`Noisy distribution at ${Math.round(noiseLevel * 100)}% noise`}>
                      {BASIS_STATES.map((state) => {
                        const count = noisySimResult?.measurement_counts?.[state] ?? 0;
                        const total = Object.values(noisySimResult?.measurement_counts || {}).reduce((a, b) => a + b, 0) || 1024;
                        const prob = count / total;
                        const pct = Math.max(2, prob * 100);
                        return (
                          <div key={`noisy-${state}`} className="compare-group">
                            <div className="compare-bars-pair">
                              <div
                                className="cmp-bar noisy"
                                style={{ height: `${pct}%` }}
                                title={`Noisy |${state}⟩: ${(prob * 100).toFixed(1)}% (${count} shots)`}
                              />
                            </div>
                            <div className="cmp-pct-row">
                              <span className="cmp-pct noisy">{(prob * 100).toFixed(1)}%</span>
                            </div>
                            <span className="compare-group-label">|{state}⟩</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : (
                <div
                  className="compare-bars"
                  aria-label={compareData ? 'Comparison chart: predicted vs actual probabilities' : 'Measurement histogram'}
                >
                  {BASIS_STATES.map((state) => {
                    const actualProb    = getActualProb(state);
                    const predictedProb = compareData?.predicted?.[state] ?? predDist[state] ?? 0;
                    const showPredicted = !!compareData || predLocked;

                    const actualPct    = Math.max(2, actualProb    * 100);
                    const predictedPct = Math.max(2, predictedProb * 100);

                    return (
                      <div key={state} className="compare-group">
                        {/* Bars pair: predicted (violet, left) + actual (cobalt, right) */}
                        <div className="compare-bars-pair">
                          {showPredicted && (
                            <div
                              className="cmp-bar predicted"
                              style={{ height: `${predictedPct}%` }}
                              title={`Predicted |${state}⟩: ${(predictedProb * 100).toFixed(1)}%`}
                            />
                          )}
                          <div
                            className="cmp-bar actual"
                            style={{ height: `${actualPct}%` }}
                            title={`Actual |${state}⟩: ${(actualProb * 100).toFixed(1)}%`}
                          />
                        </div>

                        {/* Percentage labels — numbers are content, not decoration (§1.5) */}
                        <div className="cmp-pct-row">
                          {showPredicted && (
                            <span className="cmp-pct predicted">
                              {(predictedProb * 100).toFixed(0)}%
                            </span>
                          )}
                          <span className="cmp-pct actual">
                            {(actualProb * 100).toFixed(1)}%
                          </span>
                        </div>

                        <span className="compare-group-label">|{state}⟩</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Legend — color is never the only signal (§10 accessibility) */}
              <div className="compare-legend">
                {experimentMode === 'noise' ? (
                  <>
                    <div className="legend-item">
                      <div className="legend-swatch" style={{ background: 'var(--collapse-cobalt)' }} />
                      ideal (0% noise)
                    </div>
                    <div className="legend-item">
                      <div className="legend-swatch" style={{ background: '#D97706' }} />
                      noisy ({Math.round(noiseLevel * 100)}% depolarizing)
                    </div>
                  </>
                ) : (
                  <>
                    {(compareData || predLocked) && (
                      <div className="legend-item">
                        <div className="legend-swatch" style={{ background: 'var(--superposition-violet)', opacity: 0.55 }} />
                        predicted
                      </div>
                    )}
                    <div className="legend-item">
                      <div className="legend-swatch" style={{ background: 'var(--collapse-cobalt)' }} />
                      measured (1024 shots)
                    </div>
                  </>
                )}
              </div>

              {/* ── Statevector ─────────────────────────────────────────────── */}
              {activeStatevector && (
                <div className="statevector-table" aria-label={`Statevector at step ${currentStep}`}>
                  <div className="section-label" style={{ marginBottom: 6 }}>
                    {currentStep === totalSteps
                      ? 'final statevector'
                      : `statevector at step ${currentStep} (${stepLabel})`}
                  </div>
                  {BASIS_STATES.map((state, idx) => {
                    const amp      = activeStatevector[idx];
                    const nonZero  = amp && (Math.abs(amp.real) > 0.001 || Math.abs(amp.imag) > 0.001);
                    return (
                      <div key={state} className="sv-row">
                        <span className="sv-label">|{state}⟩</span>
                        <span className={`sv-value${nonZero ? '' : ' zero'}`}>
                          {formatComplex(amp)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        )}

      </main>

      {/* ══ RIGHT COLUMN — AI Tutor (always visible, never modal) ═══════════════ */}
      <aside className="tutor-panel" aria-label="AI Tutor">

        <div className="tutor-header">
          <div className="section-label">ai tutor</div>
          <div className="tutor-context-line">{tutorContextLine}</div>
        </div>

        {/* Message thread */}
        <div className="tutor-messages" role="log" aria-live="polite">
          {tutorMessages.map((msg) => {
            if (msg.type === 'grounded-observation') {
              return (
                <div key={msg.id} className="tutor-message grounded-observation">
                  {msg.text}
                </div>
              );
            }
            if (msg.type === 'question') {
              return (
                <div
                  key={msg.id}
                  className="tutor-message"
                  style={{
                    fontFamily: 'var(--font-data)',
                    fontSize: 12,
                    color: 'var(--ink-secondary)',
                    borderLeft: '2px solid var(--hairline)',
                    paddingLeft: 10,
                  }}
                >
                  {msg.text}
                </div>
              );
            }
            if (msg.type === 'error') {
              return (
                <div key={msg.id} className="inline-error">
                  {msg.text}
                </div>
              );
            }
            // type === 'response'
            return (
              <div key={msg.id} className="tutor-message response">
                {msg.text}
              </div>
            );
          })}

          {tutorLoading && (
            <div className="tutor-loading">thinking about your circuit…</div>
          )}

          <div ref={tutorBottomRef} />
        </div>

        {/* Input footer */}
        <div className="tutor-footer">
          <div className="tutor-scope-label">Ask about this circuit:</div>
          {tutorError && (
            <p className="inline-error" role="alert">{tutorError}</p>
          )}
          <div className="tutor-input-row">
            <textarea
              id="tutor-question-input"
              className="tutor-input"
              rows={2}
              placeholder="Why is |11⟩ at ~50%?"
              value={tutorQuestion}
              onChange={(e) => setTutorQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  askTutor();
                }
              }}
              disabled={tutorLoading}
              aria-label="Question for AI tutor"
            />
          </div>
          <button
            type="button"
            id="btn-ask-tutor"
            className="btn-ask"
            onClick={askTutor}
            disabled={tutorLoading || !tutorQuestion.trim()}
          >
            Ask ↵
          </button>
        </div>

      </aside>

    </div>
  );
}
