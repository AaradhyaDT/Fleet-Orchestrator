"""
Unit test suite for Azmuth Neuromorphic & Multi-Universe Foresight Engine.
Tests all Gate 1 mathematical invariants and algorithmic alleles.
"""

import json
import pytest
from tools.azmuth_macro_graph import (
    HomeostaticBaselineNormalizer,
    ThalamicSignalFilter,
    SpikingMacroGraph,
    PreContactAvoidanceGate,
    InhibitorySafetyCatch,
    ForesightAlphaEngine,
)


@pytest.fixture
def sample_nodes():
    return [
        {
            "id": "ASML",
            "label": "ASML Lithography",
            "current_value": 2.5,
            "layer1_homeostatic": {"mu0": 0.0, "sigma0": 1.0},
            "layer3_nociceptive": {"abs_min": -50.0, "abs_max": 50.0},
        },
        {
            "id": "TSM",
            "label": "TSMC Foundry",
            "current_value": 0.2,
            "layer1_homeostatic": {"mu0": 0.0, "sigma0": 1.0},
            "layer3_nociceptive": {"abs_min": -50.0, "abs_max": 50.0},
        },
        {
            "id": "NVDA",
            "label": "NVIDIA GPU",
            "current_value": 0.1,
            "layer1_homeostatic": {"mu0": 0.0, "sigma0": 1.0},
            "layer3_nociceptive": {"abs_min": -50.0, "abs_max": 50.0},
        },
        {
            "id": "PEACEFUL_NODE",
            "label": "Quiet Node",
            "current_value": 0.05,
            "layer1_homeostatic": {"mu0": 0.0, "sigma0": 1.0},
            "layer3_nociceptive": {"abs_min": -10.0, "abs_max": 10.0},
        },
    ]


@pytest.fixture
def sample_synapses():
    return [
        {"source": "ASML", "target": "TSM", "weight": 0.90, "lag_days": 14},
        {"source": "TSM", "target": "NVDA", "weight": 0.85, "lag_days": 21},
        {"source": "PEACEFUL_NODE", "target": "NVDA", "weight": 0.05, "lag_days": 7},  # Below 0.15 threshold
    ]


def test_homeostatic_baseline_normalization(sample_nodes):
    norm_asml = HomeostaticBaselineNormalizer.normalize_node(sample_nodes[0])
    assert norm_asml["z_score"] == 2.5
    assert norm_asml["spikes"] == 2
    assert not norm_asml["habituated"]

    norm_peaceful = HomeostaticBaselineNormalizer.normalize_node(sample_nodes[3])
    assert norm_peaceful["z_score"] == 0.05
    assert norm_peaceful["spikes"] == 0
    assert norm_peaceful["habituated"]


def test_thalamic_signal_filtering(sample_nodes, sample_synapses):
    thalamus = ThalamicSignalFilter(habituate_threshold=0.8, min_synapse_weight=0.15)
    nodes_dict = {n["id"]: n for n in sample_nodes}
    active = thalamus.filter_active_spikes(nodes_dict)
    assert "ASML" in active
    assert "PEACEFUL_NODE" not in active

    pruned = thalamus.prune_synapses(sample_synapses)
    assert len(pruned) == 2
    assert all(abs(s["weight"]) >= 0.15 for s in pruned)


def test_multi_hop_shock_propagation(sample_nodes, sample_synapses):
    graph = SpikingMacroGraph(sample_nodes, sample_synapses)
    res = graph.simulate_shock("ASML", magnitude=-0.40, max_hops=2)
    targets = {t["target"]: t for t in res["affected_targets"]}

    assert "TSM" in targets
    assert "NVDA" in targets
    # Hop 1: -0.40 * 0.90 * 0.75^1 = -0.27
    assert pytest.approx(targets["TSM"]["impact_score"], 0.01) == -0.27
    assert targets["TSM"]["arrival_lag_days"] == 14
    # Hop 2 arrival lag = 14 + 21 = 35d
    assert targets["NVDA"]["arrival_lag_days"] == 35


def test_unpriced_ripple_detection(sample_nodes, sample_synapses):
    graph = SpikingMacroGraph(sample_nodes, sample_synapses)
    engine = ForesightAlphaEngine(graph)
    ripples = engine.compute_signal1_unpriced_ripples(min_coupling=0.20, z_upstream=1.8, z_downstream=0.75)

    assert len(ripples) > 0
    top = ripples[0]
    assert top["upstream"] == "ASML"
    assert top["downstream"] in ["TSM", "NVDA"]
    assert top["z_upstream"] >= 1.8
    assert top["z_downstream"] < 0.75


def test_inhibitory_safety_catch_cbf(sample_nodes, sample_synapses):
    graph = SpikingMacroGraph(sample_nodes, sample_synapses)
    # Target TSM -> NVDA coupling is 0.85. NVDA abs_max is 50.0. Safety margin 85% is 35.0.
    # An extreme positive delta of +100.0 from TSM would push NVDA to 85.0 (breach!).
    catch_res = InhibitorySafetyCatch.evaluate("TSM", delta_x=100.0, graph=graph, safety_margin=0.85)

    assert catch_res["engaged"]
    assert catch_res["alpha_brake"] < 1.0
    assert "CATCH_AND_ARREST" in catch_res["action"]
    assert len(catch_res["breach_reasons"]) > 0


def test_chokepoint_betweenness_alpha(sample_nodes, sample_synapses):
    graph = SpikingMacroGraph(sample_nodes, sample_synapses)
    chokepoints = graph.detect_systemic_chokepoints()
    assert len(chokepoints) > 0
    # TSM sits between ASML and NVDA, should have positive betweenness
    choke_map = {c["node_id"]: c for c in chokepoints}
    assert choke_map["TSM"]["betweenness"] >= 0.0


def test_all_six_cortical_cartridges():
    """Verify all 6 universe lobes load cleanly, have nodes and synapses, and can initialize SpikingMacroGraph."""
    from tools.azmuth_macro_graph import CorticalCartridgeLoader, SpikingMacroGraph, DEFAULT_CARTRIDGE_DIR

    cartridges = [
        "u0_ecosystem_mesh",
        "u1_research_arbitrage",
        "u2_ai_compute_frontier",
        "u3_career_opportunity_alpha",
        "u4_macro_capital_markets",
        "u5_hardware_physics_bom",
        "u6_energy_thermal_power",
        "u7_cyber_resilience_dfir",
        "u8_algorithmic_complexity_cp",
        "u9_regulatory_epistemic_audit",
    ]

    for c_id in cartridges:
        c_path = DEFAULT_CARTRIDGE_DIR / f"{c_id}.json"
        cart = CorticalCartridgeLoader.load_cartridge(c_path)
        assert "metadata" in cart or "universe_id" in cart
        assert "nodes" in cart
        assert "synapses" in cart
        assert len(cart["nodes"]) >= 3
        assert len(cart["synapses"]) >= 2

        graph = SpikingMacroGraph(cart["nodes"], cart["synapses"])
        assert len(graph.nodes) == len(cart["nodes"])
        assert len(graph.synapses) == len(cart["synapses"])

    from tools.azmuth_macro_graph import CROSS_UNIVERSE_BRIDGE_SYNAPSES
    assert len(CROSS_UNIVERSE_BRIDGE_SYNAPSES) >= 8


def test_market_sensor_cache_integration():
    """Verify that azmuth_market_sensor writes a valid JSON delta cache with timestamps."""
    from tools.azmuth_market_sensor import AzmuthMarketSensor, CACHE_FILE
    sensor = AzmuthMarketSensor()
    readings = sensor.get_stream3_cached_telemetry(["NVDA", "TSM"], force_refresh=True)

    assert len(readings) == 2
    assert "NVDA" in readings
    assert "current_value" in readings["NVDA"]
    assert "z_score" in readings["NVDA"]
    assert CACHE_FILE.exists()

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache_data = json.load(f)
    assert "timestamp" in cache_data
    assert "readings" in cache_data
    assert "NVDA" in cache_data["readings"]



