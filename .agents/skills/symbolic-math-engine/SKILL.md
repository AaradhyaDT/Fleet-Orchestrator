---
name: symbolic-math-engine
description: This skill should be used when the user asks to "compute symbolic derivative", "evaluate analytical integral", "solve differential equation", "compute EKF Jacobian matrix", "calculate matrix exponential exp(At)", "derive transfer function", "generate C99 code for math expression", "eliminate quantifiers via CAD", "prove polynomial non-negativity", "solve nonlinear ODE", "derive kinematics symbolically", or mentions using SymPy, Wolfram Engine, or the Tiered Symbolic Mathematics Adapter in Fleet-Orchestrator.
version: 1.0.0
---

# Tiered Deterministic Symbolic Math Engine (`symbolic-math-engine`)

This skill equips agents with the **Tiered Deterministic Symbolic Mathematics Adapter** (`tools/symbolic_math_adapter.py` and `client/adapters/symbolic_adapter.py`), eliminating LLM algebraic hallucinations, floating-point inaccuracies, and token burn by executing 100% on-device CPU symbolic algebra.

---

## 1. Operating Principles & Anti-Fragile Escalation

Agents must NEVER manually approximate or hallucinate complex calculus, Jacobian matrices, or nonlinear ODE solutions when exact symbolic CAS engines are available.

```
                    Mathematical Query / Analytical Derivation
                                        │
                                        ▼
             ┌────────────────────────────────────────────────────────┐
             │  TIER 1: Air-Gapped Zero-Dependency Core (Default)     │
             │  - Engine: In-Process Python SymPy 1.14                │
             │  - Latency: ~60 – 350 ms                               │
             │  - Scope: Routine calculus, EKF Jacobians, DSP,        │
             │           linear state-space exp(At), C99 codegen      │
             └──────────────────────────┬─────────────────────────────┘
                                        │
                         Fails / Times out (>5s) / Unevaluated
                                        │
                                        ▼
             ┌────────────────────────────────────────────────────────┐
             │  TIER 2: Heavy-Duty Symbolic Engine (Local Fallback)   │
             │  - Engine: Local Wolfram Engine 15.0 (wolframscript)   │
             │  - Latency: ~1.8 – 2.9 s                               │
             │  - Scope: Non-linear coupled ODEs (KdV, Chazy),        │
             │           Feynman box integrals, CAD quantifier proofs │
             └────────────────────────────────────────────────────────┘
```

---

## 2. Workload Routing Rules

Before selecting an engine or formulating a request, apply the **Workload Routing Matrix**:

| Workload Domain | Recommended Tier | Typical Latency | Why |
|---|---|---|---|
| **Jacobian / Hessian Matrices** | **Tier 1 (SymPy)** | 10 – 50 ms | Fast analytical differentiation with zero process launch latency. |
| **State-Space Matrix Exponential $e^{At}$** | **Tier 1 (SymPy)** | 100 – 200 ms | 15x faster than Wolfram subprocess for $4\times 4$ matrices. |
| **3D Vector Calculus (ABC Flow, Vorticity)** | **Tier 1 (SymPy)** | 50 – 100 ms | 30x faster for differential vector identities. |
| **Multivariate Monomial Integrals (Selberg)** | **Tier 1 (SymPy)** | 200 – 350 ms | 27x faster on hypercube polynomial integration. |
| **Embedded C99 Code Generation** | **Tier 1 (SymPy)** | 10 – 30 ms | Emits ISO C99 headers (`math.h`) ready for microcontrollers. |
| **Nonlinear ODEs (KdV Soliton, Chazy III)** | **Tier 2 (Wolfram)** | 1.8 – 2.9 s | Resolves Lie group failures using elliptic integrals. |
| **Transcendental Multi-Loop Integrals** | **Tier 2 (Wolfram)** | 2.0 – 2.5 s | Computes exact polylogarithmic identities ($-\frac{\pi^4}{180}$). |
| **Cylindrical Algebraic Decomposition (CAD)** | **Tier 2 (Wolfram)** | 1.8 – 2.2 s | Tarski-Seidenberg quantifier elimination over $\mathbb{R}^n$. |

---

## 3. Direct Execution Patterns

### Pattern A: CLI Execution
```powershell
# 1. Differentiation (Tier 1 default)
python tools/symbolic_math_adapter.py --op differentiate --expr "exp(-a*t) * sin(omega*t)" --var t

# 2. 2D Coordinate Jacobian Matrix (EKF)
python tools/symbolic_math_adapter.py --op jacobian --expr "r*cos(theta), r*sin(theta)" --var "r, theta"

# 3. Definite Integral
python tools/symbolic_math_adapter.py --op integrate --expr "x^2 * exp(-x)" --var x --limits "0, oo"

# 4. Embedded C99 Firmware Codegen
python tools/symbolic_math_adapter.py --op c_code --expr "sqrt(x^2 + y^2 + z^2)" --var "x, y, z"

# 5. Escalate to Wolfram Engine for CAD Proof
python tools/symbolic_math_adapter.py --op raw --expr "Resolve[ForAll[{x, y}, x^4*y^2 + x^2*y^4 - 3*x^2*y^2 + 1 >= 0], Reals]" --tier 2

# 6. Structured JSON output for downstream agents
python tools/symbolic_math_adapter.py --op differentiate --expr "x^3 * log(x)" --var x --json
```

### Pattern B: In-Process Python SDK
```python
from tools.symbolic_math_adapter import TieredSymbolicDispatcher, SymbolicRequest

dispatcher = TieredSymbolicDispatcher()

# Execute with automatic fallback
request = SymbolicRequest(
    operation="jacobian",
    expression="x^2 + y^2, x*y",
    variables=["x", "y"],
    allow_fallback=True,
)
result = dispatcher.dispatch(request)
assert result.success
print("Output:", result.output)
print("Engine Used:", result.engine_used)
print("Time (ms):", result.execution_time_ms)
```

### Pattern C: Fleet Worker Adapter Integration
```python
from client.adapters.symbolic_adapter import SymbolicWorkerAdapter

adapter = SymbolicWorkerAdapter(worker_id="sym-worker-01")

task_spec = {
    "operation": "laplace",
    "expression": "t^3 * exp(-2*t)",
    "variables": ["t"],
    "allow_fallback": True,
}
result = adapter.execute(task_spec)
# result.output contains {"result": "6/(s + 2)**4", "engine": "sympy", ...}
```

---

## 4. Engineering Safety Invariants

1. **Greek Symbol Safety**: Words like `zeta`, `gamma`, and `beta` are isolated via regex to ensure they are created as formal `Symbol` instances, never invoking SymPy special function classes.
2. **Zero Network / Air-Gapped Invariant**: Neither SymPy nor local Wolfram Engine open external cloud sockets during symbolic execution. All computations run on local CPU cores.
3. **Deterministic Output Guarantee**: All results are strictly deterministic algebraic expressions; no stochastic sampling, floating-point rounding errors, or LLM token expenses occur.
