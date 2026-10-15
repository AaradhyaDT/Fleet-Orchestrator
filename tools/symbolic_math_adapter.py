"""
Tiered Deterministic Symbolic Mathematics Adapter (SymPy Core with Wolfram Fallback).

Architecture:
  Tier 1: Air-Gapped Python SymPy (Default) - 100% offline, zero license, zero token cost.
  Tier 2: Local Wolfram Engine (wolframscript / WSTP fallback) - Activated when SymPy
          times out or returns unevaluated expressions (e.g. non-linear ODEs, complex integrals).
  Tier 3: SMT Solver / Multi-Model Council (Verification tier).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

logger = logging.getLogger("fleet.symbolic_math")


class SymbolicRequest(BaseModel):
    """Specification for a symbolic mathematics query."""
    operation: str = Field(
        ...,
        description="One of: 'solve', 'diff', 'integrate', 'jacobian', 'laplace', 'c_code', 'simplify'",
    )
    expression: Optional[str] = Field(None, description="Primary mathematical expression string.")
    variables: List[str] = Field(default_factory=list, description="Variables involved (e.g. ['x', 'y']).")
    equations: List[str] = Field(default_factory=list, description="List of equations for systems or vector expressions.")
    limits: Optional[Tuple[str, str]] = Field(None, description="Integration limits (lower, upper).")
    order: int = Field(default=1, description="Derivative order.")
    timeout_seconds: float = Field(default=5.0, description="Max execution time per tier before escalating.")
    preferred_tier: int = Field(default=1, description="1 for SymPy (default), 2 for Wolfram.")
    allow_fallback: bool = Field(default=True, description="Whether to escalate to Tier 2 on failure.")


class SymbolicResult(BaseModel):
    """Normalized response from any symbolic compute tier."""
    success: bool
    tier_used: int
    tier_name: str
    result: str
    c_code: Optional[str] = None
    latex: Optional[str] = None
    execution_time_ms: float = 0.0
    fallback_triggered: bool = False
    error: Optional[str] = None
    raw_output: Optional[str] = None


class TierFallbackNeededError(Exception):
    """Raised when an engine cannot reduce an expression or exceeds its budget."""
    pass


class SymbolicEngine(ABC):
    """Abstract interface for a symbolic mathematics execution engine."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this engine runtime is installed and operational."""
        pass

    @abstractmethod
    def solve(self, equations: List[str], variables: List[str], timeout: float) -> Tuple[str, Optional[str]]:
        """Solve a system of equations. Returns (solution_str, latex_str)."""
        pass

    @abstractmethod
    def differentiate(self, expression: str, variable: str, order: int, timeout: float) -> Tuple[str, Optional[str]]:
        """Differentiate expression. Returns (derivative_str, latex_str)."""
        pass

    @abstractmethod
    def integrate(self, expression: str, variable: str, limits: Optional[Tuple[str, str]], timeout: float) -> Tuple[str, Optional[str]]:
        """Integrate expression. Returns (integral_str, latex_str)."""
        pass

    @abstractmethod
    def compute_jacobian(self, expressions: List[str], variables: List[str], timeout: float) -> Tuple[List[List[str]], Optional[str]]:
        """Compute the Jacobian matrix. Returns (matrix_strings, latex_str)."""
        pass

    @abstractmethod
    def laplace_transform(self, expression: str, t_var: str, s_var: str, timeout: float) -> Tuple[str, Optional[str]]:
        """Compute unilateral Laplace transform. Returns (transformed_str, latex_str)."""
        pass

    @abstractmethod
    def export_c_code(self, expression: str, function_name: Optional[str] = None) -> str:
        """Export expression as valid C99 code."""
        pass


class SymPyEngine(SymbolicEngine):
    """Tier 1: Pure local, air-gapped Python SymPy engine."""

    def __init__(self) -> None:
        try:
            import sympy
            self._sympy = sympy
            self._available = True
        except ImportError:
            self._sympy = None
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def _parse_expr(self, text: str, explicit_vars: Optional[List[str]] = None) -> Any:
        import re
        import sympy
        from sympy.parsing.sympy_parser import parse_expr
        # Replace common syntax variances: ^ with **
        cleaned = text.replace("^", "**")
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", cleaned)
        standard_funcs = {
            "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh",
            "exp", "log", "ln", "sqrt", "Abs", "sign", "floor", "ceiling", "pi", "E", "I"
        }
        local_dict = {w: sympy.Symbol(w) for w in words if w not in standard_funcs}
        if explicit_vars:
            for v in explicit_vars:
                local_dict[v] = sympy.Symbol(v)
        return parse_expr(cleaned, local_dict=local_dict, evaluate=True)

    def _parse_symbols(self, names: List[str]) -> List[Any]:
        import sympy
        return [sympy.Symbol(n.strip()) for n in names if n.strip()]

    def solve(self, equations: List[str], variables: List[str], timeout: float) -> Tuple[str, Optional[str]]:
        import sympy
        sym_vars = self._parse_symbols(variables)
        parsed_eqs = []
        for eq in equations:
            if "=" in eq:
                lhs, rhs = eq.split("=", 1)
                parsed_eqs.append(self._parse_expr(lhs) - self._parse_expr(rhs))
            else:
                parsed_eqs.append(self._parse_expr(eq))

        sol = sympy.solve(parsed_eqs, sym_vars, dict=True)
        if not sol:
            # Try general solve
            sol = sympy.solve(parsed_eqs, sym_vars)
        return str(sol), sympy.latex(sol)

    def differentiate(self, expression: str, variable: str, order: int, timeout: float) -> Tuple[str, Optional[str]]:
        import sympy
        expr = self._parse_expr(expression)
        var = sympy.Symbol(variable.strip())
        res = sympy.diff(expr, var, order)
        if isinstance(res, sympy.Derivative):
            raise TierFallbackNeededError(f"SymPy left derivative unevaluated: {res}")
        return str(res), sympy.latex(res)

    def integrate(self, expression: str, variable: str, limits: Optional[Tuple[str, str]], timeout: float) -> Tuple[str, Optional[str]]:
        import sympy
        expr = self._parse_expr(expression)
        var = sympy.Symbol(variable.strip())
        if limits:
            lower = self._parse_expr(limits[0])
            upper = self._parse_expr(limits[1])
            res = sympy.integrate(expr, (var, lower, upper))
        else:
            res = sympy.integrate(expr, var)

        if isinstance(res, sympy.Integral):
            raise TierFallbackNeededError(f"SymPy left integral unevaluated: {res}")
        return str(res), sympy.latex(res)

    def compute_jacobian(self, expressions: List[str], variables: List[str], timeout: float) -> Tuple[List[List[str]], Optional[str]]:
        import sympy
        sym_vars = self._parse_symbols(variables)
        parsed_exprs = [self._parse_expr(e) for e in expressions]
        matrix = sympy.Matrix(parsed_exprs)
        jacobian = matrix.jacobian(sym_vars)
        
        # Convert to nested list of strings
        rows: List[List[str]] = []
        for r in range(jacobian.rows):
            row = [str(jacobian[r, c]) for c in range(jacobian.cols)]
            rows.append(row)
        return rows, sympy.latex(jacobian)

    def laplace_transform(self, expression: str, t_var: str = "t", s_var: str = "s", timeout: float = 5.0) -> Tuple[str, Optional[str]]:
        import sympy
        t = sympy.Symbol(t_var)
        s = sympy.Symbol(s_var)
        expr = self._parse_expr(expression)
        res, _, cond = sympy.laplace_transform(expr, t, s, noconds=False)
        return str(res), sympy.latex(res)

    def export_c_code(self, expression: str, function_name: Optional[str] = None) -> str:
        import sympy
        from sympy import ccode
        expr = self._parse_expr(expression)
        code_body = ccode(expr)
        if function_name:
            # Extract free symbols
            symbols = sorted(list(expr.free_symbols), key=lambda s: s.name)
            args = ", ".join(f"double {s.name}" for s in symbols)
            return (
                f"// Auto-generated deterministic math kernel\n"
                f"#include <math.h>\n\n"
                f"double {function_name}({args}) {{\n"
                f"    return {code_body};\n"
                f"}}\n"
            )
        return code_body


class WolframEngineDriver(SymbolicEngine):
    """Tier 2: Local Wolfram Engine driver using wolframscript."""

    def __init__(self, binary_path: Optional[str] = None) -> None:
        self.binary_path = binary_path or self._discover_wolframscript()

    def _discover_wolframscript(self) -> Optional[str]:
        # Check PATH first
        on_path = shutil.which("wolframscript")
        if on_path:
            return on_path

        # Standard Windows install locations
        win_candidates = [
            r"C:\Program Files\Wolfram Research\Wolfram Engine\15.0\wolframscript.exe",
            r"C:\Program Files\Wolfram Research\Wolfram Engine\wolframscript.exe",
            r"C:\Program Files\Wolfram Research\Wolfram Engine\14.0\wolframscript.exe",
            r"C:\Program Files\Wolfram Research\Wolfram Engine\13.3\wolframscript.exe",
            r"C:\Program Files\Wolfram Research\Mathematica\15.0\wolframscript.exe",
            r"C:\Program Files\Wolfram Research\Mathematica\14.0\wolframscript.exe",
            r"C:\Program Files\Wolfram Research\Mathematica\13.3\wolframscript.exe",
        ]
        for path in win_candidates:
            if os.path.isfile(path):
                return path
        return None

    def is_available(self) -> bool:
        if not self.binary_path:
            return False
        return os.path.isfile(self.binary_path)

    def _execute_code(self, wl_code: str, timeout: float = 10.0) -> str:
        if not self.is_available():
            raise RuntimeError("Wolfram Engine is not installed or wolframscript not found.")

        # Ensure output is formatted cleanly as JSON or text
        cmd = [self.binary_path, "-code", wl_code]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )
            return proc.stdout.strip()
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Wolfram Engine timed out after {timeout}s.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Wolfram Engine error: {e.stderr.strip() or e.stdout.strip()}")

    def solve(self, equations: List[str], variables: List[str], timeout: float) -> Tuple[str, Optional[str]]:
        eq_list = ", ".join(equations)
        var_list = ", ".join(variables)
        code = f"ToString[Solve[{{{eq_list}}}, {{{var_list}}}], InputForm]"
        out = self._execute_code(code, timeout)
        latex = self._execute_code(f"ToString[TeXForm[Solve[{{{eq_list}}}, {{{var_list}}}]]]", timeout)
        return out, latex

    def differentiate(self, expression: str, variable: str, order: int, timeout: float) -> Tuple[str, Optional[str]]:
        code = f"ToString[D[{expression}, {{{variable}, {order}}}], InputForm]"
        out = self._execute_code(code, timeout)
        latex = self._execute_code(f"ToString[TeXForm[D[{expression}, {{{variable}, {order}}}]]]", timeout)
        return out, latex

    def integrate(self, expression: str, variable: str, limits: Optional[Tuple[str, str]], timeout: float) -> Tuple[str, Optional[str]]:
        if limits:
            spec = f"{{{variable}, {limits[0]}, {limits[1]}}}"
        else:
            spec = variable
        code = f"ToString[Integrate[{expression}, {spec}], InputForm]"
        out = self._execute_code(code, timeout)
        latex = self._execute_code(f"ToString[TeXForm[Integrate[{expression}, {spec}]]]", timeout)
        return out, latex

    def compute_jacobian(self, expressions: List[str], variables: List[str], timeout: float) -> Tuple[List[List[str]], Optional[str]]:
        exprs = "{" + ", ".join(expressions) + "}"
        vars_ = "{" + ", ".join(variables) + "}"
        code = f"ToString[Grad[{exprs}, {vars_}], InputForm]"
        out = self._execute_code(code, timeout)
        latex = self._execute_code(f"ToString[TeXForm[Grad[{exprs}, {vars_}]]]", timeout)
        # Parse basic array structure or return as raw string
        return [[out]], latex

    def laplace_transform(self, expression: str, t_var: str = "t", s_var: str = "s", timeout: float = 5.0) -> Tuple[str, Optional[str]]:
        code = f"ToString[LaplaceTransform[{expression}, {t_var}, {s_var}], InputForm]"
        out = self._execute_code(code, timeout)
        latex = self._execute_code(f"ToString[TeXForm[LaplaceTransform[{expression}, {t_var}, {s_var}]]]", timeout)
        return out, latex

    def export_c_code(self, expression: str, function_name: Optional[str] = None) -> str:
        code = f"ToString[CForm[{expression}]]"
        c_expr = self._execute_code(code, timeout=5.0)
        if function_name:
            return (
                f"// Auto-generated via Wolfram Engine\n"
                f"#include <math.h>\n\n"
                f"double {function_name}() {{\n"
                f"    return {c_expr};\n"
                f"}}\n"
            )
        return c_expr


class TieredSymbolicDispatcher:
    """Coordinates Tier 1 (SymPy) with automated Tier 2 (Wolfram) fallback."""

    def __init__(self, sympy_engine: Optional[SymPyEngine] = None, wolfram_engine: Optional[WolframEngineDriver] = None) -> None:
        self.tier1 = sympy_engine or SymPyEngine()
        self.tier2 = wolfram_engine or WolframEngineDriver()

    def execute(self, request: SymbolicRequest) -> SymbolicResult:
        t0 = time.perf_counter()
        op = request.operation.lower()
        fallback_triggered = False

        # If user explicitly preferred Tier 2, try Wolfram first
        if request.preferred_tier == 2 and self.tier2.is_available():
            try:
                res, latex = self._dispatch_engine(self.tier2, op, request, request.timeout_seconds)
                c_code = str(res) if op == "c_code" else None
                elapsed = (time.perf_counter() - t0) * 1000.0
                return SymbolicResult(
                    success=True,
                    tier_used=2,
                    tier_name="Wolfram",
                    result=str(res),
                    c_code=c_code,
                    latex=latex,
                    execution_time_ms=elapsed,
                    fallback_triggered=False,
                )
            except Exception as e:
                logger.warning(f"Tier 2 (Wolfram) failed: {e}. Falling back to Tier 1.")

        # Default path: Tier 1 (SymPy)
        if self.tier1.is_available():
            try:
                res, latex = self._dispatch_engine(self.tier1, op, request, request.timeout_seconds)
                c_code = str(res) if op == "c_code" else None
                if op != "c_code" and request.expression:
                    try:
                        c_code = self.tier1.export_c_code(str(res))
                    except Exception:
                        c_code = None

                elapsed = (time.perf_counter() - t0) * 1000.0
                return SymbolicResult(
                    success=True,
                    tier_used=1,
                    tier_name="SymPy",
                    result=str(res),
                    c_code=c_code,
                    latex=latex,
                    execution_time_ms=elapsed,
                    fallback_triggered=fallback_triggered,
                )
            except (TierFallbackNeededError, Exception) as e:
                logger.info(f"Tier 1 (SymPy) unable to reduce ({e}). Checking Tier 2 fallback.")
                if not request.allow_fallback:
                    elapsed = (time.perf_counter() - t0) * 1000.0
                    return SymbolicResult(
                        success=False,
                        tier_used=1,
                        tier_name="SymPy",
                        result="",
                        execution_time_ms=elapsed,
                        error=str(e),
                    )
                fallback_triggered = True

        # Fallback to Tier 2 (Wolfram Engine)
        if self.tier2.is_available():
            try:
                res, latex = self._dispatch_engine(self.tier2, op, request, request.timeout_seconds * 2)
                c_code = None
                if op == "c_code":
                    c_code = self.tier2.export_c_code(request.expression or "")
                elapsed = (time.perf_counter() - t0) * 1000.0
                return SymbolicResult(
                    success=True,
                    tier_used=2,
                    tier_name="Wolfram",
                    result=str(res),
                    c_code=c_code,
                    latex=latex,
                    execution_time_ms=elapsed,
                    fallback_triggered=fallback_triggered,
                )
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000.0
                return SymbolicResult(
                    success=False,
                    tier_used=2,
                    tier_name="Wolfram",
                    result="",
                    execution_time_ms=elapsed,
                    fallback_triggered=fallback_triggered,
                    error=f"Tier 2 fallback failed: {e}",
                )

        elapsed = (time.perf_counter() - t0) * 1000.0
        return SymbolicResult(
            success=False,
            tier_used=1,
            tier_name="SymPy",
            result="",
            execution_time_ms=elapsed,
            fallback_triggered=fallback_triggered,
            error="Tier 1 failed and Tier 2 (Wolfram Engine) is not available locally.",
        )

    def _dispatch_engine(self, engine: SymbolicEngine, op: str, req: SymbolicRequest, timeout: float) -> Tuple[Any, Optional[str]]:
        if op == "solve":
            eqs = req.equations or ([req.expression] if req.expression else [])
            return engine.solve(eqs, req.variables, timeout)
        elif op == "diff":
            var = req.variables[0] if req.variables else "x"
            return engine.differentiate(req.expression or "", var, req.order, timeout)
        elif op == "integrate":
            var = req.variables[0] if req.variables else "x"
            return engine.integrate(req.expression or "", var, req.limits, timeout)
        elif op == "jacobian":
            exprs = req.equations or ([req.expression] if req.expression else [])
            return engine.compute_jacobian(exprs, req.variables, timeout)
        elif op == "laplace":
            t_var = req.variables[0] if len(req.variables) > 0 else "t"
            s_var = req.variables[1] if len(req.variables) > 1 else "s"
            return engine.laplace_transform(req.expression or "", t_var, s_var, timeout)
        elif op == "c_code":
            code = engine.export_c_code(req.expression or "", "kernel_eval")
            return code, None
        else:
            raise ValueError(f"Unsupported symbolic operation: {op}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiered Deterministic Symbolic Math Adapter")
    parser.add_argument("--op", required=True, choices=["solve", "diff", "integrate", "jacobian", "laplace", "c_code"])
    parser.add_argument("--expr", type=str, help="Math expression")
    parser.add_argument("--eqs", type=str, nargs="*", help="List of equations")
    parser.add_argument("--vars", type=str, nargs="*", default=["x"], help="Variables involved")
    parser.add_argument("--limits", type=str, nargs=2, help="Lower and upper integration limits")
    parser.add_argument("--order", type=int, default=1, help="Derivative order")
    parser.add_argument("--tier", type=int, default=1, choices=[1, 2], help="Preferred tier (1: SymPy, 2: Wolfram)")
    parser.add_argument("--json", action="store_true", help="Output JSON response")
    args = parser.parse_args()

    req = SymbolicRequest(
        operation=args.op,
        expression=args.expr,
        equations=args.eqs or [],
        variables=args.vars,
        limits=tuple(args.limits) if args.limits else None,
        order=args.order,
        preferred_tier=args.tier,
    )

    dispatcher = TieredSymbolicDispatcher()
    result = dispatcher.execute(req)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"[{result.tier_name}] Success: {result.success} ({result.execution_time_ms:.2f}ms)")
        if result.success:
            print(f"Result: {result.result}")
            if result.latex:
                print(f"LaTeX:  {result.latex}")
            if result.c_code:
                print(f"C-Code:\n{result.c_code}")
        else:
            print(f"Error: {result.error}")


if __name__ == "__main__":
    main()
