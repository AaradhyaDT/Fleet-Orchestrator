"""Multi-scale Continuous-Time SDE Horizon Projections.

Extends the Azmuth Neuromorphic Engine to simulate Euler-Maruyama stochastic
differential trajectories across four stratified time scales:
- 7-Day: Operational execution / sprint volatility
- 30-Day: Tactical roadmap & task convergence
- 90-Day: Quarterly milestone / research publication cycle
- 365-Day: Annual strategic paradigm & career alpha

Evaluates mean trajectory, standard deviation, Value-at-Risk (VaR 95%),
and asymptotic survival probability: P(h(x) >= 0 over horizon).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
import numpy as np


@dataclass
class HorizonProjection:
    horizon_days: int
    horizon_label: str
    steps_evaluated: int
    mean_drift: float
    volatility: float
    var_95: float
    survival_probability_pct: float
    asymptotic_status: str


class AzmuthMultiScaleSDESimulator:
    """Stratified multi-horizon stochastic risk and survival engine."""

    HORIZONS = [
        (7, "7D_OPERATIONAL"),
        (30, "30D_TACTICAL"),
        (90, "90D_QUARTERLY"),
        (365, "365D_STRATEGIC"),
    ]

    def __init__(self, state_dir: Path | None = None, seed: int = 42):
        self.state_dir = state_dir or Path("orchestrator-state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.state_dir / "azmuth_multiscale_sde.json"
        self.seed = seed

    def simulate_stratified_horizons(
        self,
        nodes: List[Dict[str, Any]],
        adjacency_matrix: np.ndarray,
        num_trials: int = 5000,
    ) -> Dict[str, Any]:
        """Simulate SDE trajectories across all four horizons for the network."""
        np.random.seed(self.seed)
        n_nodes = len(nodes)
        if n_nodes == 0:
            return {"error": "Empty node list"}

        # Initial states and base drifts from Z-scores
        z_scores = np.array([float(n.get("z_score", 0.0)) for n in nodes])
        results: List[HorizonProjection] = []

        # Mean-reverting Ornstein-Uhlenbeck parameters
        theta = 0.15  # mean-reversion rate
        sigma_base = 0.25  # diffusion volatility

        for days, label in self.HORIZONS:
            # dt is scaled so that each horizon has ~50 discrete integration steps
            n_steps = min(days * 2, 100)
            dt = days / float(n_steps)

            # Paths tensor: [num_trials, n_nodes]
            paths = np.tile(z_scores, (num_trials, 1))
            survival_flags = np.ones(num_trials, dtype=bool)

            for _ in range(n_steps):
                # Network coupling drift: A @ x
                coupling = paths @ adjacency_matrix.T
                # OU drift: -theta * paths + coupling * 0.05
                drift = -theta * paths + 0.05 * coupling
                # Diffusion shock
                shock = sigma_base * np.sqrt(dt) * np.random.randn(num_trials, n_nodes)

                paths = paths + drift * dt + shock

                # Check safety barrier: |Z| < 3.0 (i.e. h(x) >= 0)
                unsafe = np.any(np.abs(paths) >= 3.0, axis=1)
                survival_flags = survival_flags & (~unsafe)

            final_means = np.mean(paths, axis=1)
            mean_drift = float(np.mean(final_means))
            vol = float(np.std(final_means))
            var_95 = float(np.percentile(final_means, 5.0))
            survival_pct = float(np.mean(survival_flags) * 100.0)

            if survival_pct >= 90.0:
                status = "ULTRA_ROBUST"
            elif survival_pct >= 75.0:
                status = "HOMEOPATHIC_RESILIENT"
            elif survival_pct >= 50.0:
                status = "ELEVATED_RISK"
            else:
                status = "CRITICAL_DRIFT"

            results.append(
                HorizonProjection(
                    horizon_days=days,
                    horizon_label=label,
                    steps_evaluated=n_steps,
                    mean_drift=round(mean_drift, 4),
                    volatility=round(vol, 4),
                    var_95=round(var_95, 4),
                    survival_probability_pct=round(survival_pct, 2),
                    asymptotic_status=status,
                )
            )

        telemetry = {
            "num_nodes": n_nodes,
            "trials_per_horizon": num_trials,
            "projections": [asdict(r) for r in results],
        }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(telemetry, f, indent=2)

        return telemetry


def run_multiscale_cli() -> None:
    """CLI to run multi-scale SDE simulation on current macro graph."""
    from tools.azmuth_macro_graph import CorticalCartridgeLoader, DEFAULT_CARTRIDGE_DIR

    cartridges = CorticalCartridgeLoader.list_available_cartridges(DEFAULT_CARTRIDGE_DIR)

    nodes_list = []
    for c in cartridges:
        try:
            c_data = CorticalCartridgeLoader.load_cartridge(c["path"])
            u_id = c_data.get("universe_id", c["id"])
            for n in c_data.get("nodes", []):
                n_id = n.get("id", "unknown")
                nodes_list.append({"id": f"{u_id}::{n_id}", "z_score": float(n.get("z_score", 0.0))})
        except Exception:
            pass

    n = len(nodes_list)
    # Fast identity/sparse adjacency mock for local testing
    adj = np.eye(n) * 0.02 if n > 0 else np.zeros((1, 1))

    sim = AzmuthMultiScaleSDESimulator()
    telemetry = sim.simulate_stratified_horizons(nodes_list, adj, num_trials=2000)

    print("=" * 80)
    print("  AZMUTH MULTI-SCALE SDE HORIZON PROJECTIONS")
    print("=" * 80)
    print(f"- Total Nodes: {telemetry['num_nodes']}")
    print(f"- Trials/Horizon: {telemetry['trials_per_horizon']}")
    print("-" * 80)
    for p in telemetry["projections"]:
        print(f"[{p['horizon_label']}] {p['horizon_days']} Days:")
        print(f"  - Survival: {p['survival_probability_pct']}% ({p['asymptotic_status']})")
        print(f"  - Mean Drift: {p['mean_drift']} | Volatility: {p['volatility']} | VaR(95%): {p['var_95']}")
    print("=" * 80)


if __name__ == "__main__":
    run_multiscale_cli()
