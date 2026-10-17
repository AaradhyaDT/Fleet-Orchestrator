#!/usr/bin/env python3
"""tests/test_azmuth_language_and_escalation.py
----------------------------------------------
Unit and integration tests for:
1. Global Programming Language Reference Harvester (tools/azmuth_language_harvester.py)
2. Expanded Python 3.12+ DNA Splicer (tools/ultimatrix_splicer.py)
3. Structural Genetic Mutator Operators (tools/ultimatrix_mutator.py)
4. Problem-Dissector Contract Integration (tools/azmuth_corpus_harvester.py)
5. Autonomous Solver Escalation Ladder & Statement Sanitizer (tools/ultimatrix_autonomous_solver.py)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.azmuth_corpus_harvester import compute_dissection_contract_and_genes
from tools.azmuth_language_harvester import (
    GLOBAL_LANGUAGE_MANIFEST,
    get_language_reference_invariants,
    harvest_language_reference_step,
)
from tools.ultimatrix_autonomous_solver import (
    _clean_statement_text,
    solve_task_autonomously,
    synthesize_python_solution,
)
from tools.ultimatrix_mutator import (
    apply_bitwise_unrolling_mutation,
    apply_python_stdlib_accel_mutation,
)
from tools.ultimatrix_splicer import translate_cpp_gene_to_python


def test_global_language_harvester_offline_materialization(tmp_path: Path):
    """Verifies language harvester creates JSON/MD reference cards and Tier-1 genes."""
    mock_refs = tmp_path / "global_references"
    mock_tier1 = tmp_path / "tier1_language"
    mock_ledger = tmp_path / "azmuth_language_ledger.json"

    with patch("tools.azmuth_language_harvester.GLOBAL_REFS_DIR", mock_refs), \
         patch("tools.azmuth_language_harvester.TIER1_LANG_DIR", mock_tier1), \
         patch("tools.azmuth_language_harvester.LANGUAGE_LEDGER", mock_ledger):

        res = harvest_language_reference_step(batch_size=3, fetch_live=False)
        assert res["status"] == "SUCCESS"
        assert res["topics_harvested"] == 3
        assert res["genes_created"] == 3

        # Verify ledger and output files
        ledger_data = json.loads(mock_ledger.read_text(encoding="utf-8"))
        assert ledger_data["harvested_count"] == 3

        py_deque_json = mock_refs / "python" / "collections.json"
        py_deque_md = mock_refs / "python" / "collections.md"
        py_deque_gene = mock_tier1 / "lang_python_collections_deque.json"

        assert py_deque_json.exists()
        assert py_deque_md.exists()
        assert py_deque_gene.exists()

        gene_obj = json.loads(py_deque_gene.read_text(encoding="utf-8"))
        assert gene_obj["gene_id"] == "LANG_PYTHON_COLLECTIONS_DEQUE"
        assert gene_obj["tier"] == 1
        assert gene_obj["category"] == "language_runtime"
        assert len(gene_obj["alleles"]) == 1


def test_language_reference_invariants_retrieval():
    """Verifies distilled Python and C++ invariants are returned for prompt grounding."""
    py_invs = get_language_reference_invariants("python")
    cpp_invs = get_language_reference_invariants("cpp")
    assert len(py_invs) >= 4
    assert len(cpp_invs) >= 4
    assert any("deque" in x or "heapq" in x for x in py_invs)


def test_all_python_gene_translations_compile():
    """Verifies all 18+ expanded Python gene translations in ultimatrix_splicer parse as valid Python AST."""
    gene_ids = [
        "DISJOINT_SET_UNION",
        "FENWICK_BINARY_INDEXED_TREE",
        "SEGMENT_TREE_RANGE_QUERY",
        "DIJKSTRA_SHORTEST_PATH",
        "TWO_POINTER_SLIDING_WINDOW",
        "BINARY_LIFTING_LCA",
        "TARJAN_STRONGLY_CONNECTED_COMPONENTS",
        "KMP_PREFIX_AUTOMATON",
        "COMPACT_PREFIX_TRIE",
        "SPARSE_TABLE_RMQ_O1",
        "MONOTONIC_DEQUE_SLIDING_WINDOW",
        "LINEAR_SIEVE_PRIME_FACTORIZATION",
        "FAST_MODULAR_EXPONENTIATION",
        "EXTENDED_EUCLIDEAN_GCD",
        "MATRIX_EXPONENTIATION",
        "MONOTONE_CHAIN_CONVEX_HULL",
        "DINIC_MAX_FLOW",
        "PREFIX_SUM_2D_INCLUSION",
        "COORDINATE_COMPRESSOR",
    ]
    for gid in gene_ids:
        py_src = translate_cpp_gene_to_python(gid, "// C++ stub")
        assert not py_src.startswith("# Transliterated"), f"{gid} fell back to comment stub!"
        tree = ast.parse(py_src)
        assert tree is not None


def test_structural_mutation_operators():
    """Verifies bitwise_unrolling and python_stdlib_accel mutation operators."""
    cpp_code = "int mid = (l + r) / 2;\nif (x % 2 == 1) return mid;"
    mut_cpp, applied_cpp = apply_bitwise_unrolling_mutation(cpp_code, lang="cpp")
    assert applied_cpp
    assert ">> 1" in mut_cpp
    assert "& 1" in mut_cpp

    py_code = "def solve():\n    q = [1, 2, 3]\n    u = q.pop(0)\n"
    mut_py, applied_py = apply_python_stdlib_accel_mutation(py_code, lang="python")
    assert applied_py
    assert "popleft()" in mut_py


def test_problem_dissector_contract_integration():
    """Verifies compute_dissection_contract_and_genes maps statement constraints to candidate genes."""
    stmt = (
        "# Shortest Path on Tree\n"
        "You are given a tree with $N$ vertices and $Q$ queries finding the Lowest Common Ancestor.\n"
        "### Constraints\n$1 \\le N, Q \\le 10^5$\n"
    )
    genes, contract = compute_dissection_contract_and_genes(
        slug="tree-lca-queries",
        title="Tree LCA Queries",
        statement_text=stmt,
    )
    assert "FAST_IO_STREAM_UNTIE" in genes
    assert "DISJOINT_SET_UNION" in genes or "BINARY_LIFTING_LCA" in genes


def test_statement_sanitizer_strips_ace_css():
    """Verifies _clean_statement_text strips embedded Ace editor CSS dumps."""
    noisy = (
        "# Shifted Diagonal Sum\nFind max diagonal.\n"
        ".ace-tm .ace_gutter { background: #f0f0f0; } /*# sourceURL=ace/css/ace-tm */\n"
        "\ufffdXXXXXXXXXXXXXXXXXXXX\nReal explanation."
    )
    cleaned = _clean_statement_text(noisy)
    assert ".ace-tm" not in cleaned
    assert "XXXXXX" not in cleaned
    assert "Real explanation." in cleaned


def test_substring_heuristics_do_not_hijack_complex_tasks():
    """Verifies complex palindrome/gcd tasks are not hijacked by naive 5-line templates."""
    assert synthesize_python_solution({"slug": "101-palindromes", "candidate_genes": []}) is None
    assert synthesize_python_solution({"slug": "gcd-on-a-circle", "candidate_genes": []}) is None
    assert synthesize_python_solution({"slug": "powered-addition", "candidate_genes": []}) is None


def test_escalation_ladder_from_heuristic_to_llm(tmp_path: Path):
    """Verifies that if a fast-path heuristic fails verification and repair, solver escalates to Spliced-DNA LLM."""
    slug = "mock-escalated-task"
    samples = [("5", "25")]

    failing_heuristic = "import sys\ndef solve():\n    print(0)\nif __name__ == '__main__':\n    solve()\n"
    winning_llm_code = (
        "import sys\ndef solve():\n    n = int(sys.stdin.read().strip())\n"
        "    print(n * n)\nif __name__ == '__main__':\n    solve()\n"
    )
    tmp_ledger = tmp_path / "solver_ledger.json"

    with patch("tools.ultimatrix_solver.get_task_samples", return_value=samples), \
         patch("tools.ultimatrix_autonomous_solver.synthesize_python_solution", return_value=failing_heuristic), \
         patch("tools.ultimatrix_autonomous_solver.self_heal_solution", return_value=None), \
         patch("tools.ultimatrix_autonomous_solver.synthesize_with_spliced_dna_and_llm", return_value=winning_llm_code), \
         patch("tools.ultimatrix_autonomous_solver.SOLVER_LEDGER", tmp_ledger), \
         patch("tools.ultimatrix_autonomous_solver.CSACADEMY_TASKS", tmp_path):

        res = solve_task_autonomously(slug)
        assert res["status"] == "SUCCESS"
        assert res["samples_passed"] == 1


def test_all_30_language_modules_manifest_and_schema():
    """Verifies all 30 language modules in GLOBAL_LANGUAGE_MANIFEST are valid across all 3 tiers."""
    assert len(GLOBAL_LANGUAGE_MANIFEST) == 30
    valid_tiers = {"tier_a_ecosystem", "tier_b_learning", "tier_c_strategic"}

    tier_counts = {t: 0 for t in valid_tiers}
    for e in GLOBAL_LANGUAGE_MANIFEST:
        tier = e.get("tier_category")
        assert tier in valid_tiers, f"{e['id']} has invalid tier {tier}"
        tier_counts[tier] += 1
        assert e["id"] and e["gene_id"].startswith("LANG_")
        assert len(e["primitives"]) >= 2
        assert len(e["pitfalls"]) >= 1
        assert len(e["code_template"].strip()) > 10

    assert tier_counts["tier_a_ecosystem"] == 22
    assert tier_counts["tier_b_learning"] == 5
    assert tier_counts["tier_c_strategic"] == 3


def test_query_language_reference_fast_lookup():
    """Verifies zero-token query_language_reference function filters by keyword and tier."""
    from tools.azmuth_language_harvester import query_language_reference

    # Test keyword lookup
    res_async = query_language_reference("asyncio")
    assert len(res_async) >= 1
    assert res_async[0]["id"] == "python_asyncio_httpx_concurrency"

    # Test tier filtering
    res_tier_c = query_language_reference("concurrency", tier="tier_c_strategic")
    assert len(res_tier_c) >= 1
    assert any(r["language"] == "go" for r in res_tier_c)

    # Test SMT formal verification lookup
    res_z3 = query_language_reference("formal_proofs")
    assert len(res_z3) == 1
    assert res_z3[0]["gene_id"] == "LANG_Z3_SMT_FORMAL_PROOFS"


def test_master_index_generation(tmp_path: Path):
    """Verifies generate_master_index produces a markdown table linking all 30 modules."""
    from tools.azmuth_language_harvester import generate_master_index

    with patch("tools.azmuth_language_harvester.GLOBAL_REFS_DIR", tmp_path):
        idx_file = generate_master_index()
        assert idx_file.exists()
        content = idx_file.read_text(encoding="utf-8")
        assert "Total Canonical Modules**: `30`" in content
        assert "Tier A: Active Ecosystem Stack" in content
        assert "Tier B: Active Learning & Fellowship" in content
        assert "Tier C: Strategic Next Runtimes" in content
        assert "LANG_Z3_SMT_FORMAL_PROOFS" in content
        assert "LANG_PYTHON_ASYNCIO_HTTPX" in content


def test_check_and_reload_tool_modules():
    """Verifies daemon hot-reload guard checks mtimes without error."""
    from tools.azmuth_daemon import check_and_reload_tool_modules
    reloaded = check_and_reload_tool_modules()
    assert isinstance(reloaded, list)

