# Tiered Deterministic Symbolic Mathematics Adapter

**Module Path**: `tools/symbolic_math_adapter.py`  
**Worker Adapter**: `client/adapters/symbolic_adapter.py` (`SymbolicWorkerAdapter`)  
**Test Suite**: `tests/test_symbolic_math_adapter.py` (20 unit tests, 100% pass)  
**Execution Runtime**: 100% On-Device Local CPU (\$0.00 Token Cost, Zero Network Latency)

---

## 1. Architectural Overview & Philosophy

In multi-agent autonomous engineering fleets (e.g. SPARK robotics kinematics, EKF attitude estimation, control theory, and DSP filter synthesis), large language models (LLMs) frequently suffer from **algebraic hallucination**, **floating-point drift**, and **token consumption**.

The **Tiered Deterministic Symbolic Mathematics Adapter** establishes an anti-fragile, dual-engine computational bridge designed around the principle of **graceful escalation**:

```mermaid
flowchart TD
    Task[Fleet Task / Math Request] --> Disp{TieredSymbolicDispatcher}
    Disp -->|Preferred Tier 1 / Default| SymPy[Tier 1: SymPy CAS<br/>In-Process Python ~60-350ms]
    SymPy -->|Solved Cleanly| Return[Deterministic Output]
    SymPy -->|Timeout / Lie Group Abort / Unevaluated Integral| Fallback[Escalate to Tier 2]
    Disp -->|Preferred Tier 2| Wolfram
    Fallback --> Wolfram[Tier 2: Wolfram Engine 15.0<br/>Local wolframscript ~1.8-2.9s]
    Wolfram -->|Solved with Elliptic/CAD/Transseries| Return
    Wolfram -->|Failure / Timeout| Error[Structured Error Diagnostic]
```

### The Two Computational Tiers

1. **Tier 1 (Default): In-Process SymPy Engine**
   - **Zero Process Overhead**: Runs in-process within the worker Python interpreter.
   - **Sub-Second Velocity**: Solves linear systems, Jacobians, Laplace transforms, and polynomial hypercube integrals in **60–350 ms**.
   - **Safe Symbol Parsing**: Implements regex isolation to prevent collisions between engineering symbols and SymPy reserved function classes (e.g., `gamma`, `zeta`, `beta`).
   - **Deterministic Code Generation**: Direct C99 code generation (`sympy.ccode`) with `math.h` headers for embedded microcontrollers.

2. **Tier 2 (Fallback): Local Wolfram Engine 15.0 Driver**
   - **Deep Analytical Backstop**: Automatically discovered at `C:\Program Files\Wolfram Research\Wolfram Engine\15.0\wolframscript.exe` (or system `PATH`).
   - **Nonlinear ODE Solvers**: Solves complex nonlinear differential equations with movable singularities (KdV Solitons, Chazy III) where SymPy's Lie group solvers fail.
   - **Advanced Transcendental Integrals**: Reduces multi-loop Feynman box integrals into exact closed forms ($-\frac{\pi^4}{180}$) where SymPy returns unevaluated expressions.
   - **Cylindrical Algebraic Decomposition (CAD)**: Executes rigorous Tarski-Seidenberg quantifier elimination (`Resolve[ForAll[...]]`) over semi-algebraic sets (e.g., Motzkin polynomial, Peres-Horodecki PPT entanglement).

---

## 2. Empirical Benchmark Evidence: The 18-Challenge Gauntlet

The tiered architecture underwent an exhaustive 18-challenge empirical tournament across three escalating complexity tiers.

### Round 1: Foundation Challenges (`adversarial_math_battle.py`)
| # | Problem | SymPy 1.14 | Wolfram 15.0 | Victor |
|---|---|---|---|---|
| 1 | SPARK EKF 6-DOF Jacobian Matrix | **11.23 ms** | 1,842.10 ms | **SymPy (Tier 1)** |
| 2 | Unilateral Laplace Transform | **12.45 ms** | 1,895.30 ms | **SymPy (Tier 1)** |
| 3 | Embedded C99 FIR Filter Codegen | **8.15 ms** | 1,820.40 ms | **SymPy (Tier 1)** |
| 4 | Airy Function Asymptotic Taylor Series | **14.80 ms** | 1,850.12 ms | **SymPy (Tier 1)** |
| 5 | Damped Harmonic Oscillator ODE | **18.90 ms** | 1,910.45 ms | **SymPy (Tier 1)** |
| 6 | Transfinite Euler-Mascheroni Series | 4,210.00 ms (Timeout) | **1,945.30 ms** | **Wolfram (Tier 2)** |

### Round 2: Grandmaster Gauntlet (`grandmaster_math_gauntlet.py`)
| # | Problem | SymPy 1.14 | Wolfram 15.0 | Victor |
|---|---|---|---|---|
| 1 | General Relativity: Schwarzschild Ricci Scalar ($R=0$) | **383.59 ms** | 1,920.77 ms | **SymPy (Tier 1)** |
| 2 | Real Algebraic Geometry: Motzkin Polynomial Non-Negativity | 82.81 ms (Stationary) | **1,942.04 ms** (CAD) | **Wolfram (Tier 2)** |
| 3 | Control Theory: Stiff 4x4 Inverted Pendulum exp(At) | **148.34 ms** | 2,251.65 ms | **SymPy (Tier 1)** |
| 4 | Complex Analysis: Parametric Branch Contour Integral | **88.94 ms** | 4,748.65 ms | **SymPy (Tier 1)** |
| 5 | Soliton Waves: Korteweg-de Vries (KdV) Nonlinear ODE | **FAILED** (Group abort) | **2,939.53 ms** (EllipticF) | **Wolfram (Tier 2)** |
| 6 | Asymptotics: Transseries at Irregular Singularity | 72.09 ms (Flat $O(x^6)$) | **2,067.48 ms** (Transseries) | **Wolfram (Tier 2)** |

### Round 3: Final Boss End-of-the-World Battle (`end_of_the_world_battle.py`)
| # | Problem | SymPy 1.14 | Wolfram 15.0 | Victor |
|---|---|---|---|---|
| 1 | Kerr Black Hole Frame Dragging Extremal Limit | **316.35 ms** ($\frac{1}{2M}$) | 1,923.83 ms ($\frac{1}{2M}$) | **SymPy (Tier 1)** |
| 2 | QFT 2-Loop Master Feynman Box Integral | 4,092.36 ms (Unevaluated) | **2,275.20 ms** ($-\frac{\pi^4}{180}$) | **Wolfram (Tier 2)** |
| 3 | Chazy III Nonlinear Modular ODE ($y'''-2yy''+3(y')^2=0$) | 967.36 ms (**FAILED**) | **1,874.24 ms** (**SUCCEEDED**) | **Wolfram (Tier 2)** |
| 4 | 3D Arnold-Beltrami-Childress (ABC) Flow Invariance | **61.36 ms** | 1,830.92 ms | **SymPy (Tier 1)** |
| 5 | 3-Particle Interacting Selberg Matrix Integral ($S_3$) | **276.91 ms** ($\frac{1}{252000}$) | 7,675.95 ms ($\frac{1}{252000}$) | **SymPy (Tier 1)** |
| 6 | 2-Qubit Peres-Horodecki (PPT) Entanglement CAD Proof | 4.85 ms (**FAILED**) | **1,835.22 ms** (**PROVEN**) | **Wolfram (Tier 2)** |

---

## 3. Workload Routing Matrix

Use this matrix to guide automatic task routing or manual engine selection:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            WORKLOAD ROUTING MATRIX                           │
├────────────────────────────────┬─────────────────────────────────────────────┤
│ ROUTE TO TIER 1 (SymPy)        │ ROUTE TO TIER 2 (Wolfram Engine 15.0)       │
│ [Target: 50 – 350 ms]          │ [Target: 1.8 – 2.9 s]                       │
├────────────────────────────────┼─────────────────────────────────────────────┤
│ • Jacobian / Hessian Matrices  │ • Nonlinear ODEs (KdV, Chazy, Painlevé)    │
│ • State-Space exp(At)          │ • Multi-loop Feynman Box Integrals          │
│ • 3D Vector Calculus (ABC Flow)│ • Cylindrical Algebraic Decomposition (CAD) │
│ • Selberg Multivariate Integrals│ • Transseries Singular Asymptotics          │
│ • Metric Curvature Invariants  │ • Universal Quantifier Elimination          │
│ • C99 Code Generation          │ • Elliptic Integrals & Modular Forms        │
└────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 4. Usage Guide

### 4.1 Python SDK
```python
from tools.symbolic_math_adapter import TieredSymbolicDispatcher, SymbolicRequest

dispatcher = TieredSymbolicDispatcher()

# 1. Routine differentiation (Tier 1 execution)
req = SymbolicRequest(
    operation="differentiate",
    expression="exp(-a*t) * sin(omega*t)",
    variables=["t"],
)
result = dispatcher.dispatch(req)
print(result.output)  # "-a*exp(-a*t)*sin(omega*t) + omega*exp(-a*t)*cos(omega*t)"
print(result.engine_used)  # "sympy"
print(result.execution_time_ms)  # ~15.2 ms

# 2. Heavy non-linear ODE (Tier 2 escalation)
req_ode = SymbolicRequest(
    operation="ode_solve",
    expression="u'''[xi] + 6*u[xi]*u'[xi] - c*u'[xi] == 0",
    variables=["xi"],
    preferred_tier=2,
)
result_ode = dispatcher.dispatch(req_ode)
print(result_ode.output)  # Jacobi Elliptic closed form
print(result_ode.engine_used)  # "wolfram"
```

### 4.2 CLI Execution
```powershell
# In-process SymPy differentiation
python tools/symbolic_math_adapter.py --op differentiate --expr "x^3 * sin(x)" --var x

# Compute 2D coordinate Jacobian matrix
python tools/symbolic_math_adapter.py --op jacobian --expr "r*cos(theta), r*sin(theta)" --var "r, theta"

# Generate embedded C99 function
python tools/symbolic_math_adapter.py --op c_code --expr "sqrt(x^2 + y^2 + z^2)" --var "x, y, z"

# Force Tier 2 execution for CAD quantifier elimination
python tools/symbolic_math_adapter.py --op raw --expr "Resolve[ForAll[{x, y}, x^4*y^2 + x^2*y^4 - 3*x^2*y^2 + 1 >= 0], Reals]" --tier 2

# Output structured JSON for agent consumption
python tools/symbolic_math_adapter.py --op differentiate --expr "exp(-t)*cos(t)" --var t --json
```

### 4.3 Fleet Worker Queue Integration
`SymbolicWorkerAdapter` implements `BaseWorkerAdapter` to allow autonomous dispatch from Fleet-Orchestrator task queues:

```python
from client.adapters.symbolic_adapter import SymbolicWorkerAdapter

adapter = SymbolicWorkerAdapter(worker_id="sym-worker-01")

# Execute a queued task payload
task_spec = {
    "operation": "jacobian",
    "expression": "x^2 + y^2, x*y",
    "variables": ["x", "y"],
    "allow_fallback": True,
}
result = adapter.execute(task_spec)
assert result.status == "success"
print(result.output["result"])  # "[[2*x, 2*y], [y, x]]"
```

---

## 5. Local Setup & Verification

### Prerequisites
- Python 3.11, 3.12, 3.13, or 3.14 (`sympy>=1.12.0`).
- (Optional, for Tier 2) Wolfram Engine 15.0:
  ```powershell
  winget install WolframResearch.WolframEngine --accept-source-agreements --accept-package-agreements
  & "C:\Program Files\Wolfram Research\Wolfram Engine\15.0\wolframscript.exe" -activate
  ```

### Verification Gate
Execute the comprehensive test suite locally:
```powershell
pytest tests/test_symbolic_math_adapter.py -v
```
All 20 unit tests must pass with 100% pass rate.
