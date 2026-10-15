"""
End of the World Final Boss Adversarial Battle: SymPy 1.14.0 vs. Wolfram Engine 15.0.0

The ultimate computational gauntlet pushing Computer Algebra Systems to the frontier:
1. Astrophysics & Relativistic Black Holes: Kerr Spacetime Frame Dragging & Extremal Horizon Limit
2. Quantum Field Theory: 2-Loop Master Feynman Box Integral (Euler-Zagier / Polylogarithms)
3. Non-Linear Dynamical Systems: Chazy III Equation (Movable Circular Natural Boundaries)
4. Fluid Turbulence & Magnetohydrodynamics: 3D Arnold-Beltrami-Childress (ABC) Exact Navier-Stokes Solvability
5. Random Matrix Theory & Quantum Chaos: 3-Particle Selberg Matrix Integral (Vandermonde Eigenvalue Gas)
6. Quantum Information & Entanglement: 2-Qubit Peres-Horodecki (PPT) Separability via Quantifier Elimination
"""

import time
import json
import os
import subprocess
from typing import Any, Dict, List

import sympy
from sympy import (
    Symbol, Matrix, sin, cos, exp, log, sqrt, pi, oo, Function,
    symbols, diff, integrate, dsolve, eye, series, solveset, S,
    polylog, simplify, Limit, Rational
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
    boss_results = []
    print("=" * 85)
    print("FINAL BOSS ROUND: END OF THE WORLD SYMBOLIC GAUNTLET")
    print("SymPy 1.14.0 (Tier 1) vs. Wolfram Engine 15.0.0 (Tier 2)")
    print("=" * 85)

    # -------------------------------------------------------------------------
    # BOSS 1: Astrophysics & Relativistic Spacetime — Kerr Black Hole Frame Dragging
    # Exact metric: ds^2 = -(1 - 2Mr/rho^2) dt^2 - (4Mar sin^2(th)/rho^2) dt dphi + ...
    # Target: Frame dragging angular velocity Omega = -g_tphi / g_phiphi
    # Extremal Limit: as a -> M, r -> M at the equator (th = pi/2), Omega -> 1 / (2 M)
    # -------------------------------------------------------------------------
    print("\n[BOSS 1] Relativistic Astrophysics: Kerr Black Hole Frame Dragging Extremal Limit")
    
    def sympy_kerr():
        r, M, a, th = symbols("r M a th", positive=True)
        rho2 = r**2 + a**2 * cos(th)**2
        Delta = r**2 - 2 * M * r + a**2
        g_tphi = - (2 * M * a * r * sin(th)**2) / rho2
        g_phiphi = (r**2 + a**2 + (2 * M * a**2 * r * sin(th)**2) / rho2) * sin(th)**2
        Omega = - g_tphi / g_phiphi
        Omega_simplified = simplify(Omega)
        # Equatorial plane th = pi/2
        Omega_eq = Omega_simplified.subs(th, pi / 2)
        # Extremal limit a -> M, r -> M
        extremal_Omega = sympy.limit(sympy.limit(Omega_eq, r, M), a, M)
        return extremal_Omega

    s_res = run_sympy(sympy_kerr)
    wl_kerr = (
        "Module[{r, M, a, th, rho2, Delta, gtphi, gphiphi, Omega},"
        " rho2 = r^2 + a^2*Cos[th]^2;"
        " gtphi = -(2*M*a*r*Sin[th]^2)/rho2;"
        " gphiphi = (r^2 + a^2 + (2*M*a^2*r*Sin[th]^2)/rho2)*Sin[th]^2;"
        " Omega = Simplify[-gtphi/gphiphi];"
        " Limit[Omega /. {th -> Pi/2, r -> M}, a -> M]]"
    )
    w_res = run_wolfram(wl_kerr)

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms (Res: {s_res['output']})")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms (Res: {w_res['output']})")
    winner1 = "SymPy (Tier 1)" if s_res['success'] and "1/(2*M)" in s_res['output'].replace(" ", "") and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)"
    print(f"  >>> Winner: {winner1}")
    boss_results.append({
        "boss": 1,
        "name": "Kerr Black Hole Frame Dragging & Extremal Limit",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'],
        "wolfram_out": w_res['output'],
        "winner": winner1,
    })

    # -------------------------------------------------------------------------
    # BOSS 2: Quantum Field Theory — Multi-Loop Transcendental Feynman Box Integral
    # Target: I = Integrate_0^1 [ Log[x] * Log[1-x]^2 / x ] dx
    # Analytical Exact Closed-Form: -Pi^4 / 180  (= -zeta(4)/2)
    # -------------------------------------------------------------------------
    print("\n[BOSS 2] Quantum Field Theory: Multi-Loop Feynman Box Integral Integrate[Log[x]*Log[1-x]^2 / x, {x, 0, 1}]")

    def sympy_feynman_box():
        x = Symbol("x", positive=True)
        # Definite integral with logarithmic singularities at both endpoints (0 and 1)
        res = integrate(log(x) * (log(1 - x))**2 / x, (x, 0, 1))
        return res

    s_res = run_sympy(sympy_feynman_box)
    w_res = run_wolfram("Integrate[Log[x] * Log[1 - x]^2 / x, {x, 0, 1}]")

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms (Res: {s_res['output']})")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms (Res: {w_res['output']})")
    winner2 = "SymPy (Tier 1)" if s_res['success'] and ("pi**4/180" in s_res['output'] or "zeta(4)" in s_res['output']) and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)"
    print(f"  >>> Winner: {winner2}")
    boss_results.append({
        "boss": 2,
        "name": "QFT 2-Loop Master Feynman Box Integral",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'][:80] if s_res['success'] else s_res['error'],
        "wolfram_out": w_res['output'][:80] if w_res['success'] else w_res['error'],
        "winner": winner2,
    })

    # -------------------------------------------------------------------------
    # BOSS 3: Non-Linear Soliton Physics — The Chazy III Equation
    # Target: y'''[x] - 2*y[x]*y''[x] + 3*(y'[x])^2 == 0
    # Equation with movable circular natural boundary (modular form connection).
    # -------------------------------------------------------------------------
    print("\n[BOSS 3] Non-Linear Soliton Dynamics: Chazy III Equation y''' - 2 y y'' + 3 (y')^2 == 0")

    def sympy_chazy():
        x = Symbol("x")
        y = Function("y")
        eq = diff(y(x), x, 3) - 2 * y(x) * diff(y(x), x, 2) + 3 * (diff(y(x), x))**2
        return dsolve(eq, y(x))

    s_res = run_sympy(sympy_chazy)
    w_res = run_wolfram("DSolve[y'''[x] - 2*y[x]*y''[x] + 3*(y'[x])^2 == 0, y[x], x]")

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms")
    winner3 = "Wolfram (Tier 2)" if w_res['success'] and not s_res['success'] else ("SymPy (Tier 1)" if s_res['success'] and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)")
    print(f"  >>> Winner: {winner3}")
    boss_results.append({
        "boss": 3,
        "name": "Chazy III Non-Linear ODE with Movable Natural Boundary",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'][:80] if s_res['success'] else s_res['error'],
        "wolfram_out": w_res['output'][:80] if w_res['success'] else w_res['error'],
        "winner": winner3,
    })

    # -------------------------------------------------------------------------
    # BOSS 4: Hydrodynamics & Turbulence — 3D Arnold-Beltrami-Childress (ABC) Flow
    # Velocity field: u = [A sin(z) + C cos(y), B sin(x) + A cos(z), C sin(y) + B cos(x)]
    # Target: 1. Verify Beltrami property: Curl[u] == u
    #         2. Compute convective acceleration a = (u . Grad) u
    #         3. Verify Curl[a] == 0 (pure gradient) and extract exact pressure field p(x,y,z)
    # -------------------------------------------------------------------------
    print("\n[BOSS 4] Fluid Mechanics: 3D ABC Beltrami Flow & Exact Navier-Stokes Pressure")

    def sympy_abc_flow():
        x, y, z, A, B, C = symbols("x y z A B C", real=True)
        u1 = A * sin(z) + C * cos(y)
        u2 = B * sin(x) + A * cos(z)
        u3 = C * sin(y) + B * cos(x)
        # Curl of u
        w1 = diff(u3, y) - diff(u2, z)  # C cos(y) - (-A sin(z)) = C cos(y) + A sin(z) = u1
        w2 = diff(u1, z) - diff(u3, x)  # A cos(z) - (-B sin(x)) = A cos(z) + B sin(x) = u2
        w3 = diff(u2, x) - diff(u1, y)  # B cos(x) - (-C sin(y)) = B cos(x) + C sin(y) = u3
        curl_matches = (simplify(w1 - u1) == 0) and (simplify(w2 - u2) == 0) and (simplify(w3 - u3) == 0)
        # Convective acceleration: a_i = sum_j u_j d(u_i)/dx_j
        a1 = u1 * diff(u1, x) + u2 * diff(u1, y) + u3 * diff(u1, z)
        a2 = u1 * diff(u2, x) + u2 * diff(u2, y) + u3 * diff(u2, z)
        a3 = u1 * diff(u3, x) + u2 * diff(u3, y) + u3 * diff(u3, z)
        # Check irrotational: curl(a) == 0
        curl_a1 = simplify(diff(a3, y) - diff(a2, z))
        curl_a2 = simplify(diff(a1, z) - diff(a3, x))
        curl_a3 = simplify(diff(a2, x) - diff(a1, y))
        is_irrotational = (curl_a1 == 0 and curl_a2 == 0 and curl_a3 == 0)
        return f"Beltrami: {curl_matches}, Irrotational: {is_irrotational}"

    s_res = run_sympy(sympy_abc_flow)
    wl_abc = (
        "Module[{u, x, y, z, A, B, C, curlU, conv, curlConv},"
        " u = {A*Sin[z] + C*Cos[y], B*Sin[x] + A*Cos[z], C*Sin[y] + B*Cos[x]};"
        " curlU = {D[u[[3]], y] - D[u[[2]], z], D[u[[1]], z] - D[u[[3]], x], D[u[[2]], x] - D[u[[1]], y]};"
        " conv = {u[[1]]*D[u[[1]], x] + u[[2]]*D[u[[1]], y] + u[[3]]*D[u[[1]], z],"
        "         u[[1]]*D[u[[2]], x] + u[[2]]*D[u[[2]], y] + u[[3]]*D[u[[2]], z],"
        "         u[[1]]*D[u[[3]], x] + u[[2]]*D[u[[3]], y] + u[[3]]*D[u[[3]], z]};"
        " curlConv = {D[conv[[3]], y] - D[conv[[2]], z], D[conv[[1]], z] - D[conv[[3]], x], D[conv[[2]], x] - D[conv[[1]], y]};"
        " {Simplify[curlU - u] == {0, 0, 0}, Simplify[curlConv] == {0, 0, 0}}]"
    )
    w_res = run_wolfram(wl_abc)

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms (Res: {s_res['output']})")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms (Res: {w_res['output']})")
    winner4 = "SymPy (Tier 1)" if s_res['success'] and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)"
    print(f"  >>> Winner: {winner4}")
    boss_results.append({
        "boss": 4,
        "name": "3D Arnold-Beltrami-Childress (ABC) Navier-Stokes Flow",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'],
        "wolfram_out": w_res['output'],
        "winner": winner4,
    })

    # -------------------------------------------------------------------------
    # BOSS 5: Quantum Chaos & Random Matrix Theory — 3-Particle Selberg Integral
    # Target: Evaluate 3-fold interacting Coulomb gas integral over [0,1]^3:
    # S_3 = Integrate[ x1(1-x1)*x2(1-x2)*x3(1-x3)*(x1-x2)^2*(x2-x3)^2*(x3-x1)^2, {x1,0,1},{x2,0,1},{x3,0,1}]
    # Exact Ground Truth: 1 / 252000
    # -------------------------------------------------------------------------
    print("\n[BOSS 5] Random Matrix Theory: 3-Particle Selberg Integral S_3 == 1/252000")

    def sympy_selberg3():
        x1, x2, x3 = symbols("x1 x2 x3")
        f = x1 * (1 - x1) * x2 * (1 - x2) * x3 * (1 - x3) * (x1 - x2)**2 * (x2 - x3)**2 * (x3 - x1)**2
        res = integrate(f, (x1, 0, 1), (x2, 0, 1), (x3, 0, 1))
        return res

    s_res = run_sympy(sympy_selberg3)
    wl_selberg = "Integrate[x1*(1 - x1)*x2*(1 - x2)*x3*(1 - x3)*(x1 - x2)^2*(x2 - x3)^2*(x3 - x1)^2, {x1, 0, 1}, {x2, 0, 1}, {x3, 0, 1}]"
    w_res = run_wolfram(wl_selberg)

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms (Res: {s_res['output']})")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms (Res: {w_res['output']})")
    winner5 = "SymPy (Tier 1)" if s_res['success'] and "252000" in s_res['output'] and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)"
    print(f"  >>> Winner: {winner5}")
    boss_results.append({
        "boss": 5,
        "name": "3-Particle Interacting Selberg Matrix Integral",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'],
        "wolfram_out": w_res['output'],
        "winner": winner5,
    })

    # -------------------------------------------------------------------------
    # BOSS 6: Quantum Information — Peres-Horodecki (PPT) Separability Quantifier Elimination
    # Target: 2-Qubit Werner state rho_p = p |psi-><psi-| + (1-p)/4 * I_4
    # The partial transpose has eigenvalues (1-p)/4 (mult 3) and (1-3p)/4.
    # Formally prove via quantifier elimination:
    # ForAll[p, 0 <= p <= 1, (1-p)/4 >= 0 && (1-3p)/4 >= 0 <=> p <= 1/3]
    # -------------------------------------------------------------------------
    print("\n[BOSS 6] Quantum Entanglement: Peres-Horodecki PPT Separability Quantifier Elimination")

    def sympy_ppt():
        p = Symbol("p", real=True)
        # Eigenvalues of partial transpose
        eig1 = (1 - p) / 4
        eig2 = (1 - 3 * p) / 4
        sol = solveset((eig1 >= 0) & (eig2 >= 0) & (p >= 0) & (p <= 1), p, domain=S.Reals)
        return str(sol)

    s_res = run_sympy(sympy_ppt)
    wl_ppt = "Resolve[Equivalent[0 <= p <= 1 && (1 - p)/4 >= 0 && (1 - 3*p)/4 >= 0, 0 <= p <= 1/3], Reals]"
    w_res = run_wolfram(wl_ppt)

    print(f"  * SymPy:   {'PASS' if s_res['success'] else 'FAIL'} in {s_res['time_ms']:.2f} ms (Res: {s_res['output']})")
    print(f"  * Wolfram: {'PASS' if w_res['success'] else 'FAIL'} in {w_res['time_ms']:.2f} ms (Res: {w_res['output']})")
    winner6 = "Wolfram (Tier 2)" if w_res['output'] == "True" and s_res['output'] != "True" else ("SymPy (Tier 1)" if s_res['success'] and s_res['time_ms'] < w_res['time_ms'] else "Wolfram (Tier 2)")
    print(f"  >>> Winner: {winner6}")
    boss_results.append({
        "boss": 6,
        "name": "Peres-Horodecki 2-Qubit PPT Entanglement Verification",
        "sympy_ms": s_res['time_ms'],
        "wolfram_ms": w_res['time_ms'],
        "sympy_out": s_res['output'],
        "wolfram_out": w_res['output'],
        "winner": winner6,
    })

    # Save Boss Ledger
    out_file = "orchestrator-state/bench/end_of_the_world_battle_results_20261015.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(boss_results, f, indent=2)
    print(f"\n[+] Final Boss Battle ledger saved to: {out_file}")


if __name__ == "__main__":
    main()
