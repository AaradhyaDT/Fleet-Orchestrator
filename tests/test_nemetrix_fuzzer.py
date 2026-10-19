"""tests/test_nemetrix_fuzzer.py
------------------------------
Unit tests and verification harness for the Nemetrix Adversarial Predatory Fuzzing Engine.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.nemetrix_fuzzer import (
    CrabdozerPredator,
    HypnotickPredator,
    MucilatorPredator,
    NemetrixFuzzer,
    OmnivoraciousPredator,
    SlamwormPredator,
    TerroranchulaPredator,
    VicetopusPredator,
)


def test_omnivoracious_anti_quicksort_middle():
    """Verify Omnivoracious degrades quicksort (middle pivot) to quadratic comparisons."""
    n = 100
    killer_arr = OmnivoraciousPredator.generate_killer_middle_pivot(n)
    assert len(killer_arr) == n

    audit = OmnivoraciousPredator.simulate_quicksort_comparisons(killer_arr, "middle")
    theoretical_max = n * (n - 1) // 2

    # Must achieve at least 85% of theoretical quadratic maximum
    assert audit["comparisons"] >= 0.85 * theoretical_max
    assert audit["quadratic_ratio"] >= 0.85
    assert audit["is_quadratic_degradation"] is True


def test_omnivoracious_anti_quicksort_median3():
    """Verify Omnivoracious degrades quicksort with median-of-3 pivot."""
    n = 100
    killer_arr = OmnivoraciousPredator.generate_killer_median3_pivot(n)
    assert len(killer_arr) == n

    audit = OmnivoraciousPredator.simulate_quicksort_comparisons(killer_arr, "median3")
    assert audit["comparisons"] > 1000  # Significantly above O(N log2 N) ~ 664
    assert audit["quadratic_ratio"] > 0.20


def test_vicetopus_hash_collision_flooding():
    """Verify Vicetopus forces 100% bucket clustering in power-of-two hash tables."""
    count = 80
    bucket_size = 1024
    keys = VicetopusPredator.generate_bucket_collision_integers(count, bucket_size)
    assert len(keys) == count

    audit = VicetopusPredator.measure_hash_clustering(keys, bucket_count=bucket_size)
    assert audit["total_keys"] == count
    assert audit["max_chain_depth"] == count
    assert audit["occupied_buckets"] == 1
    assert audit["clustering_severity"] == "CRITICAL"

    # Test polynomial hash collision block generation
    str_collisions = VicetopusPredator.generate_polynomial_hash_collisions(pair_count=3)
    assert len(str_collisions) == 8


def test_hypnotick_graph_cycles():
    """Verify Hypnotick generates cyclic traps and figure-eight loops."""
    # Direct cycle
    direct = HypnotickPredator.generate_direct_cycle(15)
    assert len(direct) == 15
    audit_direct = HypnotickPredator.test_cycle_trap_steps(direct, start_node=0, step_limit=100)
    assert audit_direct["detected_cycle"] is True
    assert audit_direct["is_infinite_loop_vulnerable"] is True

    # Figure eight
    fig8 = HypnotickPredator.generate_figure_eight_trap(petal_size=12)
    assert len(fig8) == 24
    assert 0 in fig8
    assert len(fig8[0]) == 2  # Hub splits into both petals


def test_slamworm_deep_recursion_and_bst():
    """Verify Slamworm constructs linear recursion chains and degenerate BSTs."""
    depth = 1200
    dag = SlamwormPredator.generate_linear_recursion_dag(depth)
    assert len(dag) == depth + 1
    assert dag[0] == [1]
    assert dag[depth] == []

    # Degenerate BST
    seq = SlamwormPredator.generate_degenerate_bst_sequence(500)
    assert seq == list(range(1, 501))
    rev_seq = SlamwormPredator.generate_degenerate_bst_sequence(500, reverse=True)
    assert rev_seq == list(range(500, 0, -1))


def test_terroranchula_exponential_backtracking():
    """Verify Terroranchula generates 2^K exponential path DAGs."""
    k_stages = 10
    ladder = TerroranchulaPredator.generate_diamond_ladder_dag(stages=k_stages)

    # 3 nodes per stage + 1 sink
    assert len(ladder) == 3 * k_stages + 1
    sink = 3 * k_stages
    path_count = TerroranchulaPredator.count_paths_dag(ladder, source=0, sink=sink)
    assert path_count == 2**k_stages
    assert path_count == 1024

    # Catastrophic regex string
    pattern, evil = TerroranchulaPredator.generate_catastrophic_regex_input(20)
    assert evil.endswith("!")
    assert evil.count("a") == 20
    assert pattern == r"^(a+)+$"


def test_crabdozer_sparse_memory_spike():
    """Verify Crabdozer computes petabyte dense allocations from sparse coordinates."""
    coords = CrabdozerPredator.generate_sparse_coordinate_spike(max_coord=10_000_000)
    assert len(coords) == 2

    audit = CrabdozerPredator.compute_dense_vs_sparse_footprint(coords)
    assert audit["dense_elements"] > 10**14
    assert audit["dense_ram_gb"] > 100_000
    assert audit["sparse_ram_kb"] < 1.0


def test_mucilator_heap_percolate_degenerator():
    """Verify Mucilator forces 100% maximal percolation swaps on min-heap insertions."""
    n = 200
    desc_arr = MucilatorPredator.generate_worst_case_min_heap_input(n)
    assert len(desc_arr) == n

    audit = MucilatorPredator.simulate_min_heap_swaps(desc_arr)
    assert audit["adversarial_efficiency"] == 1.0
    assert audit["is_maximal_percolation"] is True
    assert audit["total_swaps"] == audit["max_theoretical_swaps"]


def test_nemetrix_fuzzer_coordinator():
    """Verify Master Nemetrix coordinator, listing, and individual predator dispatch."""
    catalog = NemetrixFuzzer.list_predators()
    assert len(catalog) == 7

    names = {p["name"].lower() for p in catalog}
    assert "omnivoracious" in names
    assert "vicetopus" in names
    assert "hypnotick" in names
    assert "slamworm" in names
    assert "terroranchula" in names
    assert "crabdozer" in names
    assert "mucilator" in names

    # Individual execution dispatch
    payload = NemetrixFuzzer.run_predator("omnivoracious", size=50)
    assert len(payload) == 50

    coords = NemetrixFuzzer.run_predator("crabdozer", max_coord=5000)
    assert len(coords) == 2


def test_nemetrix_full_gauntlet_subsecond():
    """Verify full gauntlet executes in under 200 milliseconds with all passing."""
    report = NemetrixFuzzer.execute_full_gauntlet(test_scale=200)
    assert report["predators_executed"] == 7
    assert report["verdict"] == "VULNERABILITIES_UNMASKED"
    assert report["gauntlet_elapsed_ms"] < 200.0

    # Ensure all 7 predators returned PASS status
    for _, res in report["results"].items():
        assert res["status"] == "PASS"


def test_nemetrix_report_serialization(tmp_path: Path):
    """Verify JSON report generation and schema consistency."""
    report = NemetrixFuzzer.execute_full_gauntlet(test_scale=50)
    out_file = tmp_path / "nemetrix_test_report.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["predators_executed"] == 7
    assert "omnivoracious" in loaded["results"]
