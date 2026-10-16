"""tests/test_ultimatrix_arena.py
------------------------------
Unit tests for the Ultimatrix Evolutionary Arena.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from tools.ultimatrix_arena import (
    calculate_analytical_fitness,
    benchmark_allele,
    race_gene_alleles,
    run_arena_tournament,
)


def test_calculate_analytical_fitness():
    """Verify analytical cycle and memory complexity budgeting."""
    rt_cubic, ram_cubic = calculate_analytical_fitness("O(N^3)", "O(N^2)", n_val=1000)
    rt_simd, ram_simd = calculate_analytical_fitness("O(N^3 / 64)", "O(N^2 / 64)", n_val=1000)

    # SIMD bit-parallel must be significantly faster and more compact
    assert rt_simd < rt_cubic
    assert ram_simd < ram_cubic


def test_race_gene_alleles_promotes_fastest(tmp_path: Path):
    """Verify that racing alleles in a gene promotes the fastest allele to PRIMARY."""
    test_gene = tmp_path / "test_gene.json"
    data = {
        "gene_id": "TEST_COMPLEXITY_GENE",
        "tier": 3,
        "category": "dimensional_collapse",
        "description": "Test gene racing",
        "alleles": [
            {
                "allele_id": "naive_cubic",
                "dominance": "PRIMARY",
                "complexity_time": "O(N^3)",
                "complexity_space": "O(N^2)",
                "environmental_triggers": ["N <= 400"],
                "code_template": "void solve() {}",
            },
            {
                "allele_id": "bitset_simd",
                "dominance": "RECESSIVE",
                "complexity_time": "O(N^3 / 64)",
                "complexity_space": "O(N^2 / 64)",
                "environmental_triggers": ["N <= 5000"],
                "code_template": "void solve_simd() {}",
            },
        ],
    }
    test_gene.write_text(json.dumps(data, indent=2), encoding="utf-8")

    res = race_gene_alleles(test_gene)
    assert res["status"] == "SUCCESS"
    assert res["dominant_allele"] == "bitset_simd"

    # Verify persisted gene file has updated dominance
    updated = json.loads(test_gene.read_text(encoding="utf-8"))
    assert updated["alleles"][0]["allele_id"] == "bitset_simd"
    assert updated["alleles"][0]["dominance"] == "PRIMARY"
    assert updated["alleles"][1]["allele_id"] == "naive_cubic"
    assert updated["alleles"][1]["dominance"] == "RECESSIVE"
