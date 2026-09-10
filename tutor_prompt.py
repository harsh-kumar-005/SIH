"""
tutor_prompt.py
===============
Circuit-Aware AI Tutor Prompt Template & Context Injection Harness.

This module encapsulates the Socratic AI Tutor persona, formats prompt payloads
with active circuit ASTs and simulation statevectors, and provides validation
test cases to ensure explanations remain strictly grounded in empirical data.
"""

from typing import Dict, Any, List, Optional
import json

# -----------------------------------------------------------------------------
# 1. System Prompt (The "Tutor Persona")
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a quantum computing tutor embedded in a learning platform. "
    "You will be given: (1) the circuit a student built, (2) the actual simulation results from running that circuit, "
    "and (3) the student's question. Your explanations must be grounded strictly in the provided circuit and results — "
    "reference specific gates, specific qubits, and specific numbers from the data given. "
    "Do not give a generic textbook explanation of quantum concepts; explain this specific result. "
    "If the student's question can't be answered from the given data, or if the question contradicts the provided "
    "simulation data (e.g., asking why an outcome didn't happen when the data shows it did, or asking about numbers that do not match), "
    "point out the discrepancy explicitly rather than guessing or justifying false premises. "
    "Keep explanations to 3-4 sentences, beginner-friendly, no unexplained jargon."
)


# -----------------------------------------------------------------------------
# 2. Context Injection Payload Formatter
# -----------------------------------------------------------------------------
def format_tutor_user_message(
    gates_applied: List[str],
    statevector: List[float],
    measurement_counts: Dict[str, int],
    student_question: str,
    basis_order: str = "00, 01, 10, 11"
) -> str:
    """Formats student question and circuit execution context into a grounded prompt."""
    counts_str = json.dumps(measurement_counts)
    sv_str = json.dumps([round(x, 6) for x in statevector])
    gates_str = ", ".join(gates_applied) if gates_applied else "None (ground state)"

    return (
        f"Circuit:\n"
        f"Gates applied: {gates_str}\n\n"
        f"Simulation result:\n"
        f"Final statevector: {sv_str} (basis order: {basis_order})\n"
        f"Measurement counts (1024 shots): {counts_str}\n\n"
        f'Student\'s question: "{student_question}"'
    )


# -----------------------------------------------------------------------------
# 3. Canonical Test Case Scenarios & Model Reference Outputs
# -----------------------------------------------------------------------------
SAMPLE_TEST_CASES = {
    "case_1_bell_state_grounded": {
        "description": "Standard Bell State Entanglement Explanation",
        "input": {
            "gates_applied": ["H(q0)", "CNOT(q0,q1)"],
            "statevector": [0.707107, 0.0, 0.0, 0.707107],
            "measurement_counts": {"00": 486, "01": 0, "10": 0, "11": 538},
            "student_question": "Why did I only get 00 and 11, and not 01 or 10?"
        },
        "target_reference_response": (
            "When you applied the H gate to qubit 0, it placed q0 into an equal superposition of 0 and 1. "
            "The CNOT gate then used q0 as the control to flip q1 only when q0 is 1, which perfectly correlates the two qubits so q1 always matches q0. "
            "This left non-zero amplitudes (~0.707107) exclusively for states |00> and |11>, while the amplitudes for |01> and |10> are exactly 0. "
            "Because those probabilities are zero, your 1024 measurement shots yielded 486 counts for '00' and 538 counts for '11', with 0 counts for '01' or '10'."
        ),
        "validation_rubric": [
            "References actual gates: H(q0) and CNOT(q0,q1)",
            "References actual numbers: ~0.707107 and 486/538 counts",
            "Explains causal chain: H superposes q0 -> CNOT correlates q1 -> 01/10 have 0 amplitude",
            "No invented qubits or gates (strictly 2 qubits)",
            "Concise: 3-4 sentences, beginner-friendly"
        ]
    },
    "case_2_mismatched_inconsistency": {
        "description": "Contradiction / Data Inconsistency Test (Student asks why 01/10 didn't occur, but data shows non-entangled state with all outcomes)",
        "input": {
            "gates_applied": ["H(q0)", "H(q1)"],
            "statevector": [0.5, 0.5, 0.5, 0.5],
            "measurement_counts": {"00": 260, "01": 255, "10": 250, "11": 259},
            "student_question": "Why did I only get 00 and 11, and not 01 or 10?"
        },
        "target_reference_response": (
            "Looking at your simulation data, there is a discrepancy with your question: you actually did receive '01' (255 shots) and '10' (250 shots), not just '00' (260) and '11' (259). "
            "Because you applied H gates to both q0 and q1 without an entangling CNOT, each qubit is in an independent 50/50 superposition. "
            "This gives all four basis states an equal amplitude of 0.5, which is why your 1024 shots were split roughly evenly across all four outcomes rather than restricted to 00 and 11."
        ),
        "validation_rubric": [
            "Flags the factual contradiction between the question premise and the actual simulation data",
            "Cites the actual counts (255 for '01', 250 for '10')",
            "Explains the actual circuit applied: H on both qubits with no entangling CNOT",
            "Refuses to hallucinate a false reason why 01/10 were absent when the data clearly proves they were present"
        ]
    }
}


if __name__ == "__main__":
    print("===================================================================")
    print("AI TUTOR PROMPT SPECIFICATION & VALIDATION HARNESS")
    print("===================================================================\n")
    print("--- SYSTEM PROMPT ---")
    print(SYSTEM_PROMPT)
    print("\n-------------------------------------------------------------------")
    
    for key, case in SAMPLE_TEST_CASES.items():
        print(f"\n[SCENARIO: {case['description']}]")
        formatted = format_tutor_user_message(**case["input"])
        print("\nFormed User Message:\n" + formatted)
        print("\nExpected Model Grounded Response:\n" + case["target_reference_response"])
        print("\nValidation Rubric Checkpoints:")
        for r in case["validation_rubric"]:
            print(f"  [x] {r}")
        print("-" * 65)
