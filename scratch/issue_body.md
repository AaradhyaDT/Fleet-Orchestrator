## Overview

Implement a **Tiered Deterministic Symbolic Mathematics Adapter** for Fleet-Orchestrator worker agents and engineering simulation pipelines (e.g. SPARK kinematics, control systems, DSP filter synthesis, and formal proofs). 

In multi-model agent fleets, LLM workers are prone to algebraic slips, sign mistakes, and hallucinated mathematical derivations. This adapter provides an anti-fragile, layered compute bridge that guarantees 100% offline-first execution via `SymPy` as the default engine, while dynamically promoting hard non-linear or unreduced expressions to a local `Wolfram Engine` (or Wolfram MCP) fallback.

---

## Architectural Specification: Tiered Fallback Pipeline

```
              Agent / Worker Math Query (Calculus, ODE, EKF Jacobian, Laplace)
                                        │
                                        ▼
             ┌────────────────────────────────────────────────────────┐
             │  TIER 1: Air-Gapped Zero-Dependency Core (Default)     │
             │  - Engine: Python SymPy inside active virtualenv       │
             │  - Network: 100% air-gapped / zero telemetry           │
             │  - Scope: Routine calculus, EKF Jacobians, DSP,        │
             │           linear transfer functions, C-code export     │
             └──────────────────────────┬─────────────────────────────┘
                                        │
                         Fails / Times out (>5s) / Unevaluated
                                        │
                                        ▼
             ┌────────────────────────────────────────────────────────┐
             │  TIER 2: Heavy-Duty Symbolic Engine (Local Fallback)   │
             │  - Engine: Local Wolfram Engine (wolframscript / WSTP) │
             │  - Network: Localhost only (firewall-contained)        │
             │  - Scope: Non-linear coupled ODEs, high-degree roots,  │
             │           transcendental integrals, CForm export       │
             └──────────────────────────┬─────────────────────────────┘
                                        │
                         Extreme Edge Case / SMT Verification
                                        │
                                        ▼
             ┌────────────────────────────────────────────────────────┐
             │  TIER 3: Multi-Model Cognitive Council / Z3 SMT        │
             │  - SMT Solver: Z3 (audit.bat invariant certification)  │
             │  - Remote Fallback: Wolfram Cloud / Colab GPU          │
             └────────────────────────────────────────────────────────┘
```

---

## Scope & Non-Goals

### In Scope
- Lightweight Python wrapper (`src/fleet/tools/symbolic_math_adapter.py`) providing a unified solver interface (`solve_equation`, `compute_jacobian`, `export_c_code`, `laplace_transform`).
- Zero-dependency execution using `SymPy` as primary.
- Dynamic fallback trigger: if `SymPy` exceeds execution timeout ($\le 5\text{s}$) or returns unevaluated expressions (e.g. `Integral`, `Derivative`), failover cleanly to local `wolframscript`.
- Uniform C-code generation contract (`sympy.printing.c.c_code` vs. Wolfram `CForm`) to support bare-metal firmware embedding (e.g., ESP32-S3 firmware headers for SPARK).
- Unit test suite covering tier execution, fallback switching, and code emission parity.

### Out of Scope
- Running machine learning or neural net inference inside Wolfram (handled by PyTorch / TFLite Micro).
- Hard runtime dependencies on cloud Wolfram APIs (must remain functional 100% offline).

---

## Tasks & Acceptance Criteria

- [x] **Task 1: Core Solver Interface Specification**: Define `SymbolicSolver` abstract base class with unified request/response schemas in `src/fleet/tools/symbolic_math_adapter.py`.
- [x] **Task 2: Tier 1 SymPy Implementation**: Implement `SymPyEngine` with timeout protection, Jacobian extraction, and C99 code formatting.
- [x] **Task 3: Tier 2 Wolfram Engine Driver**: Implement `WolframEngineDriver` invoking local `wolframscript` CLI / WSTP subprocess with localhost firewall containment.
- [x] **Task 4: Tiered Fallback Dispatcher**: Build `TieredSymbolicDispatcher` orchestrating Tier 1 $\to$ Tier 2 escalation on timeout or unevaluated outputs.
- [x] **Task 5: Worker Fleet Integration & Unit Testing**: Register the symbolic solver as a callable tool in Fleet-Orchestrator worker runtime; add pytest suite in `tests/test_symbolic_math_adapter.py` certifying 100% pass rate.

---

## Verification Gate

1. `pytest tests/test_symbolic_math_adapter.py -v` passes with 100% clean exit.
2. Verified offline execution (zero external HTTP/HTTPS sockets opened during test runs).
3. C-code printer output validated for C99 syntax compliance.
