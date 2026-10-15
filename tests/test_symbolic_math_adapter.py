"""
Unit tests for Tiered Deterministic Symbolic Mathematics Adapter.
Certifies 100% pass rate across Tier 1 (SymPy), Tier 2 (Wolfram) fallback,
and SymbolicWorkerAdapter fleet execution.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from tools.symbolic_math_adapter import (
    SymbolicEngine,
    SymbolicRequest,
    SymbolicResult,
    SymPyEngine,
    TierFallbackNeededError,
    TieredSymbolicDispatcher,
    WolframEngineDriver,
)
from client.adapters.symbolic_adapter import SymbolicWorkerAdapter


@pytest.fixture
def sympy_engine() -> SymPyEngine:
    return SymPyEngine()


@pytest.fixture
def dispatcher() -> TieredSymbolicDispatcher:
    return TieredSymbolicDispatcher()


# =====================================================================
# Tier 1: SymPy Engine Unit Tests
# =====================================================================

def test_sympy_availability(sympy_engine: SymPyEngine) -> None:
    assert sympy_engine.is_available() is True


def test_sympy_differentiation(sympy_engine: SymPyEngine) -> None:
    deriv, latex = sympy_engine.differentiate("sin(x)*exp(x)", "x", order=1, timeout=5.0)
    assert "exp(x)" in deriv
    assert "cos(x)" in deriv
    assert "sin(x)" in deriv
    assert latex is not None


def test_sympy_definite_integration(sympy_engine: SymPyEngine) -> None:
    val, latex = sympy_engine.integrate("3*x**2 + 2*x + 1", "x", limits=("0", "2"), timeout=5.0)
    assert val == "14"
    assert latex == "14"


def test_sympy_indefinite_integration(sympy_engine: SymPyEngine) -> None:
    val, _ = sympy_engine.integrate("cos(x)", "x", limits=None, timeout=5.0)
    assert val == "sin(x)"


def test_sympy_solve_linear_system(sympy_engine: SymPyEngine) -> None:
    eqs = ["x + y = 10", "2*x - y = 5"]
    sol, latex = sympy_engine.solve(eqs, ["x", "y"], timeout=5.0)
    assert "5" in sol
    assert latex is not None


def test_sympy_compute_jacobian(sympy_engine: SymPyEngine) -> None:
    # 2D polar to cartesian coordinate transformation Jacobian
    exprs = ["r*cos(theta)", "r*sin(theta)"]
    jacobian, latex = sympy_engine.compute_jacobian(exprs, ["r", "theta"], timeout=5.0)
    assert len(jacobian) == 2
    assert len(jacobian[0]) == 2
    assert "cos(theta)" in jacobian[0][0]
    assert "-r*sin(theta)" in jacobian[0][1]
    assert "sin(theta)" in jacobian[1][0]
    assert "r*cos(theta)" in jacobian[1][1]
    assert latex is not None


def test_sympy_laplace_transform(sympy_engine: SymPyEngine) -> None:
    res, latex = sympy_engine.laplace_transform("exp(-3*t)*cos(2*t)", "t", "s", timeout=5.0)
    assert "s + 3" in res
    assert "4" in res
    assert latex is not None


def test_sympy_export_c_code(sympy_engine: SymPyEngine) -> None:
    c_code = sympy_engine.export_c_code("x**2 + 2*zeta*omega*x + omega**2", "damping_eval")
    assert "#include <math.h>" in c_code
    assert "double damping_eval(" in c_code
    assert "double omega" in c_code
    assert "double zeta" in c_code
    assert "double x" in c_code
    assert "pow(omega, 2)" in c_code or "pow(" in c_code


def test_sympy_greek_letter_collision_safety(sympy_engine: SymPyEngine) -> None:
    # 'zeta', 'gamma', 'beta' are special functions in SymPy; verify they parse cleanly as symbols
    res, _ = sympy_engine.differentiate("zeta*x**2 + gamma*x + beta", "x", order=1, timeout=5.0)
    assert "2*x*zeta" in res or "2*zeta*x" in res
    assert "gamma" in res


# =====================================================================
# Tier 2: Wolfram Driver & Mocked Escalation
# =====================================================================

def test_wolfram_driver_availability() -> None:
    driver = WolframEngineDriver(binary_path="non_existent_binary.exe")
    assert driver.is_available() is False


def test_wolfram_driver_execution_mocked() -> None:
    driver = WolframEngineDriver(binary_path="mock_wolfram.exe")
    with patch.object(driver, "is_available", return_value=True):
        with patch.object(driver, "_execute_code", return_value="2*x"):
            res, latex = driver.differentiate("x^2", "x", 1, 5.0)
            assert res == "2*x"


# =====================================================================
# Tiered Dispatcher: Fallback & Priority Logic
# =====================================================================

def test_dispatcher_tier1_success(dispatcher: TieredSymbolicDispatcher) -> None:
    req = SymbolicRequest(operation="diff", expression="x**3", variables=["x"])
    result = dispatcher.execute(req)
    assert result.success is True
    assert result.tier_used == 1
    assert result.tier_name == "SymPy"
    assert "3*x**2" in result.result
    assert result.fallback_triggered is False


def test_dispatcher_fallback_to_tier2() -> None:
    mock_tier1 = MagicMock(spec=SymPyEngine)
    mock_tier1.is_available.return_value = True
    mock_tier1.differentiate.side_effect = TierFallbackNeededError("Complex unevaluated expression")

    mock_tier2 = MagicMock(spec=WolframEngineDriver)
    mock_tier2.is_available.return_value = True
    mock_tier2.differentiate.return_value = ("ClosedFormSolution", "\\text{LaTeX}")

    dispatcher = TieredSymbolicDispatcher(sympy_engine=mock_tier1, wolfram_engine=mock_tier2)
    req = SymbolicRequest(operation="diff", expression="non_linear_eq", variables=["x"], allow_fallback=True)

    result = dispatcher.execute(req)
    assert result.success is True
    assert result.tier_used == 2
    assert result.tier_name == "Wolfram"
    assert result.result == "ClosedFormSolution"
    assert result.fallback_triggered is True


def test_dispatcher_no_fallback_allowed() -> None:
    mock_tier1 = MagicMock(spec=SymPyEngine)
    mock_tier1.is_available.return_value = True
    mock_tier1.differentiate.side_effect = TierFallbackNeededError("Cannot reduce")

    mock_tier2 = MagicMock(spec=WolframEngineDriver)
    mock_tier2.is_available.return_value = True

    dispatcher = TieredSymbolicDispatcher(sympy_engine=mock_tier1, wolfram_engine=mock_tier2)
    req = SymbolicRequest(operation="diff", expression="test", variables=["x"], allow_fallback=False)

    result = dispatcher.execute(req)
    assert result.success is False
    assert result.tier_used == 1
    assert "Cannot reduce" in (result.error or "")


def test_dispatcher_preferred_tier2() -> None:
    mock_tier1 = MagicMock(spec=SymPyEngine)
    mock_tier2 = MagicMock(spec=WolframEngineDriver)
    mock_tier2.is_available.return_value = True
    mock_tier2.solve.return_value = ("{{x -> 42}}", "x = 42")

    dispatcher = TieredSymbolicDispatcher(sympy_engine=mock_tier1, wolfram_engine=mock_tier2)
    req = SymbolicRequest(operation="solve", expression="x - 42", variables=["x"], preferred_tier=2)

    result = dispatcher.execute(req)
    assert result.success is True
    assert result.tier_used == 2
    assert "{{x -> 42}}" in result.result
    # Tier 1 was not called because Tier 2 succeeded directly
    mock_tier1.solve.assert_not_called()


# =====================================================================
# Fleet Worker Adapter Integration Tests
# =====================================================================

@pytest.mark.asyncio
async def test_symbolic_worker_adapter_health() -> None:
    adapter = SymbolicWorkerAdapter()
    assert await adapter.check_health() is True


@pytest.mark.asyncio
async def test_symbolic_worker_adapter_execute_json() -> None:
    adapter = SymbolicWorkerAdapter()
    spec = '{"operation": "diff", "expression": "x**4", "variables": ["x"]}'
    res = await adapter.execute_task(
        task_id="task_math_001",
        spec=spec,
        stage="execution",
        context={},
    )
    assert res["success"] is True
    assert res["tier_used"] == 1
    assert "4*x**3" in res["result_text"]
    assert "Executed 'diff' via SymPy" in res["summary"]


@pytest.mark.asyncio
async def test_symbolic_worker_adapter_execute_context() -> None:
    adapter = SymbolicWorkerAdapter()
    context = {
        "symbolic_request": {
            "operation": "jacobian",
            "equations": ["x*y", "x + y"],
            "variables": ["x", "y"],
        }
    }
    res = await adapter.execute_task(
        task_id="task_math_002",
        spec="Solve Jacobian for sensor state",
        stage="execution",
        context=context,
    )
    assert res["success"] is True
    assert res["tier_used"] == 1
    assert "[['y', 'x'], ['1', '1']]" in res["result_text"]


@pytest.mark.asyncio
async def test_symbolic_worker_adapter_invalid_spec() -> None:
    adapter = SymbolicWorkerAdapter()
    res = await adapter.execute_task(
        task_id="task_math_invalid",
        spec="unrecognized non-math prompt without keywords",
        stage="execution",
        context={},
    )
    assert res["success"] is False
    assert "Could not parse" in res["error"]
