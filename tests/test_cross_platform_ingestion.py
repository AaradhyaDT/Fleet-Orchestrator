#!/usr/bin/env python3
"""tests/test_cross_platform_ingestion.py
---------------------------------------
Unit and integration tests for Azmuth Phase 5 Cross-Platform Ingestion:
1. Codeforces submission parsing and schema validation
2. AtCoder submission parsing and schema validation
3. ICPC regional submission parsing and schema validation
4. Expanded autonomous solver archetypes (Sliding window, Prefix sums, Coordinate compression)
5. Problem index multi-platform expansion
"""

import json
from pathlib import Path
from tools.azmuth_gene_catalog import (
    parse_codeforces_task_submissions,
    parse_atcoder_task_submissions,
    parse_icpc_task_submissions,
)
from tools.ultimatrix_autonomous_solver import (
    synthesize_python_solution,
    run_solution_verification,
)


def test_parse_codeforces_task_submissions(tmp_path: Path):
    """Verifies Codeforces task structure maps cleanly to a valid multi-allele gene."""
    task_dir = tmp_path / "4A-watermelon"
    task_dir.mkdir()
    
    prob_file = task_dir / "problem.json"
    prob_file.write_text(json.dumps({
        "name": "Watermelon",
        "rating": 800,
        "tags": ["brute force", "math"],
        "time_limit": "1000 ms",
    }), encoding="utf-8")
    
    sub_dir = task_dir / "submissions"
    sub_dir.mkdir()
    (sub_dir / "sub_1001.py").write_text("w = int(input())\nprint('YES' if w > 2 and w % 2 == 0 else 'NO')", encoding="utf-8")
    (sub_dir / "sub_1002.cpp").write_text("#include <iostream>\nint main() { int w; std::cin >> w; std::cout << (w > 2 && w % 2 == 0 ? \"YES\" : \"NO\"); }", encoding="utf-8")

    gene = parse_codeforces_task_submissions(task_dir)
    assert gene is not None
    assert gene["gene_id"] == "CF_4A_WATERMELON"
    assert gene["tier"] == 2
    assert gene["category"] == "primitive_structure"
    assert len(gene["alleles"]) == 2
    
    allele_ids = [a["allele_id"] for a in gene["alleles"]]
    assert "cf_sub_sub_1001" in allele_ids
    assert "cf_sub_sub_1002" in allele_ids


def test_parse_atcoder_task_submissions(tmp_path: Path):
    """Verifies AtCoder task structure maps cleanly to a valid multi-allele gene."""
    task_dir = tmp_path / "abc300_a"
    task_dir.mkdir()

    prob_file = task_dir / "problem.json"
    prob_file.write_text(json.dumps({
        "title": "A. N-choice question",
        "contest_id": "abc300",
        "problem_index": "A",
    }), encoding="utf-8")

    sub_dir = task_dir / "submissions"
    sub_dir.mkdir()
    (sub_dir / "solution.py").write_text("n, a, b = map(int, input().split())\nc = list(map(int, input().split()))\nprint(c.index(a + b) + 1)", encoding="utf-8")

    gene = parse_atcoder_task_submissions(task_dir)
    assert gene is not None
    assert gene["gene_id"] == "ATCODER_ABC300_A"
    assert gene["tier"] == 2
    assert len(gene["alleles"]) == 1
    assert "contest_abc300" in gene["alleles"][0]["environmental_triggers"]


def test_parse_icpc_task_submissions(tmp_path: Path):
    """Verifies ICPC/IEEEXtreme task structure maps cleanly to Tier 3 gene."""
    task_dir = tmp_path / "icpc_regional_flow"
    task_dir.mkdir()

    prob_file = task_dir / "problem.json"
    prob_file.write_text(json.dumps({
        "name": "Regional Flow Network",
        "difficulty": "HARD",
    }), encoding="utf-8")

    sub_dir = task_dir / "submissions"
    sub_dir.mkdir()
    (sub_dir / "sol_dinic.cpp").write_text("#include <bits/stdc++.h>\n// Dinic Max Flow Implementation\nint main() {}", encoding="utf-8")

    gene = parse_icpc_task_submissions(task_dir)
    assert gene is not None
    assert gene["gene_id"] == "ICPC_ICPC_REGIONAL_FLOW"
    assert gene["tier"] == 3
    assert gene["category"] == "dimensional_collapse"
    assert len(gene["alleles"]) == 1


def test_expanded_archetype_sliding_window():
    """Verifies TWO_POINTER_SLIDING_WINDOW solution synthesis and verification."""
    task_info = {
        "slug": "subarray_sum_equals_k",
        "candidate_genes": ["TWO_POINTER_SLIDING_WINDOW"],
    }
    code = synthesize_python_solution(task_info)
    assert code is not None
    assert "left = 0" in code
    
    # 5 elements, target 7: array [1, 2, 4, 3, 5] -> subarrays [1, 2, 4] and [4, 3] both sum to 7 -> total 2
    samples = [("5 7\n1 2 4 3 5", "2")]
    passed = run_solution_verification(code, samples)
    assert passed is True


def test_expanded_archetype_prefix_sums():
    """Verifies PREFIX_SUM_2D_INCLUSION / 1D range sum query solver."""
    task_info = {
        "slug": "static_range_sum_queries",
        "candidate_genes": ["PREFIX_SUM_2D_INCLUSION"],
    }
    code = synthesize_python_solution(task_info)
    assert code is not None
    assert "pref = [0]" in code
    
    # n=4, q=2, arr=[10, 20, 30, 40], query [1, 2] -> 30, query [2, 4] -> 90
    samples = [("4 2\n10 20 30 40\n1 2\n2 4", "30\n90")]
    passed = run_solution_verification(code, samples)
    assert passed is True


def test_expanded_archetype_coordinate_compression():
    """Verifies COORDINATE_COMPRESSOR rank transformation solver."""
    task_info = {
        "slug": "coordinate_compression_1d",
        "candidate_genes": [],
    }
    code = synthesize_python_solution(task_info)
    assert code is not None
    assert "unique_sorted" in code
    
    # n=5, arr=[100, 20, 50, 20, 100] -> unique: 20(1), 50(2), 100(3) -> "3 1 2 1 3"
    samples = [("5\n100 20 50 20 100", "3 1 2 1 3")]
    passed = run_solution_verification(code, samples)
    assert passed is True
