"""Tests for Multi-scale SDE Horizon Simulator."""

from pathlib import Path
import numpy as np
from tools.azmuth_multiscale_sde import AzmuthMultiScaleSDESimulator


def test_simulate_stratified_horizons(tmp_path: Path):
    sim = AzmuthMultiScaleSDESimulator(state_dir=tmp_path, seed=123)
    nodes = [
        {"id": "node_1", "z_score": 0.1},
        {"id": "node_2", "z_score": -0.2},
        {"id": "node_3", "z_score": 0.5},
    ]
    adj = np.eye(3) * 0.05
    telemetry = sim.simulate_stratified_horizons(nodes, adj, num_trials=500)

    assert telemetry["num_nodes"] == 3
    assert len(telemetry["projections"]) == 4

    labels = [p["horizon_label"] for p in telemetry["projections"]]
    assert labels == ["7D_OPERATIONAL", "30D_TACTICAL", "90D_QUARTERLY", "365D_STRATEGIC"]

    for p in telemetry["projections"]:
        assert 0.0 <= p["survival_probability_pct"] <= 100.0
        assert p["asymptotic_status"] in ["ULTRA_ROBUST", "HOMEOPATHIC_RESILIENT", "ELEVATED_RISK", "CRITICAL_DRIFT"]
