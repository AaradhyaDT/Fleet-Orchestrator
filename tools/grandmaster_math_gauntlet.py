"""
Grandmaster-Tier Adversarial Gauntlet: SymPy 1.14.0 vs. Wolfram Engine 15.0.0.

Pushes both computer algebra systems into Ph.D. / Theoretical Physics & Formal Geometry territory:
1. Differential Geometry: Schwarzschild Metric -> Exact Riemann, Ricci & Einstein Tensors
2. Real Algebraic Geometry: Motzkin Polynomial Non-Negativity (Hilbert's 17th Problem: ForAll[x, y, M(x,y) >= 0])
3. Symbolic Matrix Exponential: Stiff 4x4 State-Space Control System exp(A*t)
4. Parametric Complex Contour Integral with Multi-Branch Cuts: Integral_0^oo x^(a-1)/(1 + x^b) dx
5. Non-Linear Soliton PDE / Exact Traveling Wave Solutions (Korteweg-de Vries equation)
6. Asymptotic Transseries & High-Order Asymptotic Expansion around Irregular Singularities
"""

import time
import json
import os
import subprocess
from typing import Any, Dict, List

import sympy
from sympy import (
    Symbol, Matrix, sin, cos, exp, log, sqrt, pi, oo, Function,
    symbols, diff, integrate, dsolve, eye, series, solveset, S
)

WOLFRAM_PATH = r"C:\Program Files\Wolfram Research\Wolfram Engine\15.0\wolframscript.exe"


def run_wolfram(code: str, timeout: float = 60.0) -> Dict[str, Any]:
    t0 = time.perf_counter()
    cmd = [WOLFRAM_PATH, "-code", f"ToString[{code}, InputForm]"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        elapsed = (time.perf_counter() - t0) * 1000.0
        return {"success": True, "output": proc.stdout.strip(), "time_ms": elapsed, "error": None}
    except subprocess.TimeoutExpired:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return {"success": False, "output": "", "time_ms": elapsed, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return {"success": False, "output": "", "time_ms": elapsed, "error": str(e)}


def run_sympy(fn, timeout: float = 60.0) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        res = fn()
        elapsed = (time.perf_counter() - t0) * 1000.0
        return {"success": True, "output": str(res), "time_ms": elapsed, "error": None}
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return {"success": False, "output": "", "time_ms": elapsed, "error": str(e)}


def main():
    gauntlet_results = []
    print("=" * 85)
    print("GRANDMASTER ADVERSARIAL GAUNTLET: SymPy (Tier 1) vs. Wolfram Engine 15.0 (Tier 2)")
    print("=" * 85)

    # -------------------------------------------------------------------------
    # CHALLENGE 1: Differential Geometry & General Relativity (Schwarzschild Metric)
    # Target: Compute the Ricci Scalar R from the Schwarzschild metric:
    # ds^2 = -(1 - 2M/r) dt^2 + (1 - 2M/r)^(-1) dr^2 + r^2 dtheta^2 + r^2 sin^2(theta) dphi^2
    # Known Analytical Invariant: Vacuum solution, so Ricci Scalar R == 0 exactly!
    # -------------------------------------------------------------------------
    print("\n[CHALLENGE 1] General Relativity: Vacuum Schwarzschild Metric Ricci Scalar R == 0")
    
    def sympy_ricci_scalar():
        t, r, th, ph, M = symbols("t r theta phi M")
        coords = [t, r, th, ph]
        # Diagonal metric tensor
        g = Matrix([
            [-(1 - 2*M/r), 0, 0, 0],
            [0, 1/(1 - 2*M/r), 0, 0],
            [0, 0, r**2, 0],
            [0, 0, 0, r**2 * sin(th)**2]
        ])
        g_inv = g.inv()

        # Christoffel symbols of the second kind: Gamma^k_ij = 1/2 g^kl (d_i g_lj + d_j g_li - d_l g_ij)
        n = 4
        Gamma = [[[0 for _ in range(n)] for _ in range(n)] for _ in range(n)]
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    val = 0
                    for l in range(n):
                        term = diff(g[l, j], coords[i]) + diff(g[l, i], coords[j]) - diff(g[i, j], coords[l])
                        val += S(1)/2 * g_inv[k, l] * term
                    Gamma[k][i][j] = sympy.simplify(val)

        # Ricci tensor: R_ij = d_k Gamma^k_ij - d_j Gamma^k_ik + Gamma^k_kl Gamma^l_ij - Gamma^k_jl Gamma^l_ik
        R_tensor = Matrix.zeros(n, n)
        for i in range(n):
            for j in range(n):
                r_val = 0
                for k in range(n):
                    r_val += diff(Gamma[k][i][j], coords[k]) - diff(Gamma[k][i][k], coords[j])
                    for l in range(n):
                        r_val += Gamma[k][k][l] * Gamma[l][i][j] - Gamma[k][j][l] * Gamma[l][i][k]
                R_tensor[i, j] = sympy.simplify(r_val)

        # Ricci scalar R = g^ij R_ij
        R_scalar = 0
        for i in range(n):
            for j in range(n):
                R_scalar += g_inv[i, j] * R_tensor[i, j]
        return sympy.simplify(R_scalar)

    s_res = run_sympy(sympy_ricci_scalar)
    
    # Wolfram code for Christoffel / Ricci on Schwarzschild metric
    wl_gr = (
        "Module[{coord = {t, r, th, ph}, g, ginv, n = 4, Gamma, Rtensor, Rscalar},"
        "  g = DiagonalMatrix[{-(1 - 2*M/r), (1 - 2*M/r)^(-1), r^2, r^2*Sin[th]^2}];"
        "  ginv = Inverse[g];"
        "  Gamma = Table[1/2 * Sum[ginv[[k, l]] * (D[g[[l, j]], coord[[i]]] + D[g[[l, i]], coord[[j]]] - D[g[[i, j]], coord[[l]]]), {l, n}], {k, n}, {i, n}, {j, n}];"
        "  Rtensor = Table[Sum[D[Gamma[[k, i, j]], coord[[k]]] - D[Gamma[[k, i, k]], coord[[j]]], {k, n}] + "
        "                  Sum[Gamma[[k, k, l]]*Gamma[[l, i, j]] - Gamma[[k, j, l]]*Gamma[[l, i, k]], {k, n}, {l, n}], {i, n}, {j, n}];"
        "  Rscalar = Simplify[Sum[ginv[[i, j]] * Rtensor[[i, j]], {i, n}, {j, n}]];"
        "  Rscalar"
        "]"
    )
    w_res = run_wolfram(wl_gr)

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms (Scalar R = {s_res['output']})")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms (Scalar R = {w_res['output']})")
    winner1 = "SymPy (Tier 1)" if s_res['success'] and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)"
    print(f"  >>> Winner: {winner1}")
    gauntlet_results.append({
        "challenge": 1,
        "name": "General Relativity: Schwarzschild Ricci Invariant",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'],
        "wolfram_out": w_res['output'],
        "winner": winner1,
    })

    # -------------------------------------------------------------------------
    # CHALLENGE 2: Real Algebraic Geometry (The Motzkin Polynomial Proof)
    # Target: Prove for all real (x, y): M(x, y) = x^4*y^2 + x^2*y^4 - 3*x^2*y^2 + 1 >= 0
    # Note: Cannot be written as a sum of squares of polynomials (Hilbert's 17th Problem counterexample).
    # -------------------------------------------------------------------------
    print("\n[CHALLENGE 2] Real Algebraic Geometry: Motzkin Polynomial Non-Negativity ForAll[x, y, M(x,y)>=0]")
    
    def sympy_motzkin():
        # SymPy doesn't have a full multivariate CAD quantifier elimination module; test if solveset or intervals work
        x, y = symbols("x y", real=True)
        m = x**4 * y**2 + x**2 * y**4 - 3 * x**2 * y**2 + 1
        # Check if SymPy can verify global non-negativity
        # Using minimum search via stationary points
        grad = [diff(m, x), diff(m, y)]
        crit_pts = sympy.solve(grad, [x, y], dict=True)
        vals = [m.subs(p) for p in crit_pts]
        return min(vals) >= 0

    s_res = run_sympy(sympy_motzkin)
    w_res = run_wolfram("Resolve[ForAll[{x, y}, Element[{x, y}, Reals], x^4*y^2 + x^2*y^4 - 3*x^2*y^2 + 1 >= 0]]")

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms (Proven: {s_res['output']})")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms (Proven: {w_res['output']})")
    winner2 = "Wolfram (Tier 2)" if w_res['output'] == "True" else "SymPy (Tier 1)"
    print(f"  >>> Winner: {winner2}")
    gauntlet_results.append({
        "challenge": 2,
        "name": "Motzkin Polynomial Non-Negativity (Hilbert's 17th)",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'],
        "wolfram_out": w_res['output'],
        "winner": winner2,
    })

    # -------------------------------------------------------------------------
    # CHALLENGE 3: Stiff 4x4 State-Space Control System (Symbolic Matrix Exponential exp(A*t))
    # Target: Compute e^(A*t) for 4x4 coupled inverted pendulum on a cart system
    # -------------------------------------------------------------------------
    print("\n[CHALLENGE 3] Control Theory: Stiff 4x4 State-Space Symbolic Matrix Exponential exp(A*t)")
    
    def sympy_matrix_exp():
        t, M, m, l, g = symbols("t M m l g", positive=True)
        # Inverted pendulum linearized state-space matrix A
        A = Matrix([
            [0, 1, 0, 0],
            [0, 0, -m*g/M, 0],
            [0, 0, 0, 1],
            [0, 0, (M + m)*g/(M*l), 0]
        ])
        return (A * t).exp()

    s_res = run_sympy(sympy_matrix_exp)
    wl_matrix = "MatrixExp[{{0, 1, 0, 0}, {0, 0, -(m*g)/M, 0}, {0, 0, 0, 1}, {0, 0, (M + m)*g/(M*l), 0}} * t]"
    w_res = run_wolfram(f"Simplify[{wl_matrix}]")

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms")
    winner3 = "SymPy (Tier 1)" if s_res['success'] and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)"
    print(f"  >>> Winner: {winner3}")
    gauntlet_results.append({
        "challenge": 3,
        "name": "Stiff 4x4 Symbolic Matrix Exponential exp(A*t)",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'][:80] if s_res['success'] else s_res['error'],
        "wolfram_out": w_res['output'][:80] if w_res['success'] else w_res['error'],
        "winner": winner3,
    })

    # -------------------------------------------------------------------------
    # CHALLENGE 4: Parametric Complex Contour Integral with Multi-Branch Cuts
    # Target: Integrate_0^oo [ x^(a-1) / (1 + x^b) ] dx with convergence assumptions 0 < a < b
    # Exact Analytical Closed-Form: pi / (b * sin(a*pi / b))
    # -------------------------------------------------------------------------
    print("\n[CHALLENGE 4] Complex Contour Integration: Integrate[x^(a-1)/(1 + x^b), {x, 0, oo}]")
    
    def sympy_contour_integral():
        x = Symbol("x", positive=True)
        a = Symbol("a", positive=True)
        b = Symbol("b", positive=True)
        # Note: If evaluated with symbolic parameters, does SymPy return the clean reflection formula?
        res = integrate(x**(a - 1) / (1 + x**b), (x, 0, oo))
        return res

    s_res = run_sympy(sympy_contour_integral)
    w_res = run_wolfram("Assuming[0 < a < b, Integrate[x^(a - 1)/(1 + x^b), {x, 0, Infinity}]]")

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms (Res: {s_res['output'][:70]}...)")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms (Res: {w_res['output'][:70]}...)")
    # Did Wolfram reduce to Pi/(b*Sin[(a*Pi)/b])?
    winner4 = "Wolfram (Tier 2)" if "Sin" in w_res['output'] and "meijerg" in s_res['output'].lower() else ("SymPy (Tier 1)" if s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)")
    print(f"  >>> Winner: {winner4}")
    gauntlet_results.append({
        "challenge": 4,
        "name": "Parametric Multi-Branch Contour Integral",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'][:80] if s_res['success'] else s_res['error'],
        "wolfram_out": w_res['output'][:80] if w_res['success'] else w_res['error'],
        "winner": winner4,
    })

    # -------------------------------------------------------------------------
    # CHALLENGE 5: Soliton Wave Equation (Korteweg-de Vries Non-Linear PDE)
    # Target: Solve traveling wave ODE for KdV: -c*u' + 6*u*u' + u''' == 0
    # Exact Analytical 1-Soliton Solution: u(xi) = (c/2) * sech^2( sqrt(c)/2 * xi )
    # -------------------------------------------------------------------------
    print("\n[CHALLENGE 5] Soliton Non-Linear Wave: -c*u' + 6*u*u' + u''' == 0 with u(+-oo)==0")
    
    def sympy_kdv():
        xi, c = symbols("xi c", positive=True)
        u = Function("u")
        # u''' + 6 u u' - c u' = 0
        eq = diff(u(xi), xi, 3) + 6 * u(xi) * diff(u(xi), xi) - c * diff(u(xi), xi)
        return dsolve(eq, u(xi))

    s_res = run_sympy(sympy_kdv)
    w_res = run_wolfram("DSolve[u'''[xi] + 6*u[xi]*u'[xi] - c*u'[xi] == 0, u[xi], xi]")

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms")
    winner5 = "SymPy (Tier 1)" if s_res['success'] and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)"
    print(f"  >>> Winner: {winner5}")
    gauntlet_results.append({
        "challenge": 5,
        "name": "KdV Soliton Non-Linear Differential Equation",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'][:80] if s_res['success'] else s_res['error'],
        "wolfram_out": w_res['output'][:80] if w_res['success'] else w_res['error'],
        "winner": winner5,
    })

    # -------------------------------------------------------------------------
    # CHALLENGE 6: High-Order Asymptotic Transseries Around Irregular Singularity
    # Target: Asymptotic series of Exp[-1/x^2] * BesselK[0, 1/x] as x -> 0+ up to O(x^6)
    # -------------------------------------------------------------------------
    print("\n[CHALLENGE 6] Irregular Singularity: Series[Exp[-1/x^2] * BesselK[0, 1/x], {x, 0, 6}]")
    
    def sympy_asymptotic():
        x = Symbol("x", positive=True)
        from sympy import besselk
        expr = exp(-1/x**2) * besselk(0, 1/x)
        return series(expr, x, 0, n=6)

    s_res = run_sympy(sympy_asymptotic)
    w_res = run_wolfram("Series[Exp[-1/x^2] * BesselK[0, 1/x], {x, 0, 6}]")

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms")
    winner6 = "Wolfram (Tier 2)" if w_res['success'] and not s_res['success'] else ("SymPy (Tier 1)" if s_res['success'] and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)")
    print(f"  >>> Winner: {winner6}")
    gauntlet_results.append({
        "challenge": 6,
        "name": "Asymptotic Transseries at Irregular Singularity",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'][:80] if s_res['success'] else s_res['error'],
        "wolfram_out": w_res['output'][:80] if w_res['success'] else w_res['error'],
        "winner": winner6,
    })

    # Save Gauntlet Ledger
    out_file = "orchestrator-state/bench/grandmaster_gauntlet_results_20261015.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(gauntlet_results, f, indent=2)
    print(f"\n[+] Grandmaster Gauntlet ledger saved to: {out_file}")


if __name__ == "__main__":
    main()
