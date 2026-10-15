## Summary

Closes #172.

Implements the **Tiered Deterministic Symbolic Mathematics Adapter** for Fleet-Orchestrator worker queues, Sentinel DAG planners, and engineering simulation workflows (e.g. SPARK kinematics, control systems, and DSP filter synthesis).

This adapter eliminates LLM token burn and algebraic hallucination by establishing an anti-fragile, tiered compute bridge:
- **Tier 1 (Default)**: Air-gapped local Python `SymPy` engine running 100% offline with zero token cost.
- **Tier 2 (Fallback)**: Local `Wolfram Engine` (`wolframscript` / WSTP) driver with automatic escalation when Tier 1 times out ($\le 5\text{s}$) or encounters complex unevaluated expressions.
- **Worker Adapter**: `SymbolicWorkerAdapter` implementing `BaseWorkerAdapter` for direct fleet worker dispatch.

---

## Changes

1. **`tools/symbolic_math_adapter.py`**:
   - `SymbolicRequest` & `SymbolicResult` Pydantic schemas.
   - `SymPyEngine` with safe symbol parsing (preventing collisions with special functions like `zeta`, `gamma`, `beta`), calculus, matrix Jacobian, Laplace transforms, and C99 code generation.
   - `WolframEngineDriver` with path discovery and subprocess execution.
   - `TieredSymbolicDispatcher` orchestrating automatic failover and priority execution.
   - Full CLI entrypoint supporting both human-readable and structured `--json` outputs.
2. **`client/adapters/symbolic_adapter.py`**:
   - `SymbolicWorkerAdapter(BaseWorkerAdapter)` providing fleet worker integration.
   - Exported in `client/adapters/__init__.py`.
3. **`requirements.txt`**: Added `sympy>=1.12.0`.
4. **`tests/test_symbolic_math_adapter.py`**:
   - 19 comprehensive unit tests covering differentiation, definite/indefinite integration, systems of linear equations, 2D coordinate Jacobian matrices, unilateral Laplace transforms, C99 code generation, Greek letter safety, Wolfram mocking, fallback triggers, and worker adapter task execution.

---

## Verification & Test Proof

```
======================== 19 passed, 1 warning in 2.03s ========================
pytest tests/test_symbolic_math_adapter.py -v (100% pass)
pytest tests/test_copilot_cli_adapter.py tests/test_copilot_headless.py -v (32 passed, 0 regressions)
```

1. **Deterministic Speed**: SymPy differentiation completed in 46.68ms; Jacobian in 11.11ms; definite integral in 84.70ms.
2. **Zero-Token Runtime**: 100% offline execution on local CPU.
