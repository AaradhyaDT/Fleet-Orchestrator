#!/usr/bin/env python3
"""tests/test_ultimatrix_cross_language.py
-----------------------------------------
Unit tests for Azmuth Phase 6: Cross-Language Gene Translation & Dual C++/Python Arena:
1. C++ to Python algorithmic gene transliteration (DSU, Fenwick, SegTree, Dijkstra, Sliding Window)
2. Python DNA strand splicing (splice_python_dna)
3. Dual-language allele benchmarking in Ultimatrix Arena with VM overhead normalization
"""

import json
from pathlib import Path
from tools.ultimatrix_splicer import (
    translate_cpp_gene_to_python,
    splice_python_dna,
)
from tools.ultimatrix_arena import (
    calculate_analytical_fitness,
    benchmark_allele,
    race_gene_alleles,
)


def test_translate_dsu_to_python():
    """Verifies DSU transliteration produces valid Python class."""
    py_code = translate_cpp_gene_to_python("DISJOINT_SET_UNION", "// C++ DSU")
    assert "class DSU:" in py_code
    assert "def find(self, v: int)" in py_code
    assert "def unite(self, a: int, b: int)" in py_code


def test_translate_fenwick_and_segtree_to_python():
    """Verifies Fenwick Tree and Segment Tree transliterations."""
    fenwick_py = translate_cpp_gene_to_python("FENWICK_BINARY_INDEXED_TREE", "")
    assert "class Fenwick:" in fenwick_py
    assert "self.bit" in fenwick_py

    segtree_py = translate_cpp_gene_to_python("SEGMENT_TREE_RANGE_QUERY", "")
    assert "class SegTree:" in segtree_py
    assert "def query(self, l: int, r: int)" in segtree_py


def test_translate_dijkstra_to_python():
    """Verifies Dijkstra shortest path transliteration with heapq."""
    dijkstra_py = translate_cpp_gene_to_python("DIJKSTRA_SHORTEST_PATH", "")
    assert "class Dijkstra:" in dijkstra_py
    assert "heapq.heappop" in dijkstra_py


def test_splice_python_dna():
    """Verifies complete Python solution generation with standard libraries."""
    gene_ids = ["DISJOINT_SET_UNION", "FENWICK_BINARY_INDEXED_TREE"]
    spliced = splice_python_dna(gene_ids, task_title="Test Dual Splicing")
    assert "ULTIMATRIX SYNTHESIZED PYTHON DNA STREAM" in spliced
    assert "sys.setrecursionlimit" in spliced
    assert "class DSU:" in spliced
    assert "class Fenwick:" in spliced
    assert "def solve():" in spliced


def test_dual_language_arena_benchmarking():
    """Verifies Python alleles receive VM compensation factor relative to C++ alleles."""
    cpp_rt, cpp_ram = calculate_analytical_fitness("O(N log N)", "O(N)", n_val=2000, language="cpp")
    py_rt, py_ram = calculate_analytical_fitness("O(N log N)", "O(N)", n_val=2000, language="python")

    assert py_rt > cpp_rt
    assert py_ram > cpp_ram

    cpp_allele = {
        "allele_id": "dsu_cpp",
        "complexity_time": "O(N)",
        "complexity_space": "O(N)",
        "environmental_triggers": ["cpp20"],
    }
    py_allele = {
        "allele_id": "dsu_py",
        "complexity_time": "O(N)",
        "complexity_space": "O(N)",
        "environmental_triggers": ["python3"],
    }

    fit_cpp = benchmark_allele(cpp_allele)
    fit_py = benchmark_allele(py_allele)

    assert fit_cpp["runtime_ms"] < fit_py["runtime_ms"]
    assert fit_cpp["ram_kb"] < fit_py["ram_kb"]


def test_dual_language_gene_race(tmp_path: Path):
    """Verifies racing multi-language alleles produces correct dominance assignment."""
    gene_file = tmp_path / "dual_lang_gene.json"
    gene_data = {
        "gene_id": "DUAL_LANG_BENCHMARK",
        "tier": 2,
        "category": "primitive_structure",
        "description": "Multi-language benchmark gene",
        "alleles": [
            {
                "allele_id": "py_sub_1",
                "dominance": "ALTERNATIVE",
                "complexity_time": "O(N)",
                "complexity_space": "O(N)",
                "environmental_triggers": ["python"],
                "code_template": "pass",
            },
            {
                "allele_id": "cpp_sub_1",
                "dominance": "ALTERNATIVE",
                "complexity_time": "O(N)",
                "complexity_space": "O(N)",
                "environmental_triggers": ["c++20"],
                "code_template": "int main() {}",
            },
        ],
    }
    gene_file.write_text(json.dumps(gene_data, indent=2), encoding="utf-8")

    result = race_gene_alleles(gene_file)
    assert result["status"] == "SUCCESS"
    assert result["dominant_allele"] == "cpp_sub_1"
