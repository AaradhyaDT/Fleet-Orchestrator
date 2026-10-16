#!/usr/bin/env python3
"""tests/test_ultimatrix_splicer.py
---------------------------------
Unit tests for the Azmuth Ultimatrix DNA Splicer (Zero-Boilerplate C++ Synthesizer).
"""

import pytest
from tools.ultimatrix_splicer import (
    load_all_genes,
    resolve_genes_from_query,
    resolve_genes_for_task,
    splice_dna,
)


def test_load_all_genes():
    from tools.ultimatrix_splicer import CODON_STREAM
    genes = load_all_genes()
    if CODON_STREAM.exists():
        assert len(genes) >= 100, f"Expected >= 100 sequenced genes in codon_stream, found {len(genes)}"
    else:
        assert len(genes) >= 50, f"Expected >= 50 fallback genes in CI environment, found {len(genes)}"
    assert "DISJOINT_SET_UNION" in genes
    assert "FAST_IO_STREAM_UNTIE" in genes
    assert "DIJKSTRA_SHORTEST_PATH" in genes


def test_resolve_genes_from_query():
    genes = resolve_genes_from_query("Find shortest path on graph using dijkstra and segment tree")
    assert "FAST_IO_STREAM_UNTIE" in genes
    assert "DIJKSTRA_SHORTEST_PATH" in genes
    assert "SEGMENT_TREE_RANGE_QUERY" in genes


def test_splice_dna_compilation_ready():
    spliced_cpp = splice_dna(
        ["FAST_IO_STREAM_UNTIE", "DISJOINT_SET_UNION", "DIJKSTRA_SHORTEST_PATH"],
        task_title="Test Splicing Task",
    )
    assert "#include <iostream>" in spliced_cpp
    assert "struct DSU" in spliced_cpp
    assert "struct Dijkstra" in spliced_cpp
    assert "ios_base::sync_with_stdio(false)" in spliced_cpp
    assert "void solve()" in spliced_cpp
    assert "int main()" in spliced_cpp
    # Redundant header guard should not be present in body
    assert "#pragma once" not in spliced_cpp
