#!/usr/bin/env python3
"""tests/test_ultimatrix_mutator.py
---------------------------------
Unit tests for the Azmuth Ultimatrix Phase 4 Dynamic Allele Mutation Engine.
"""

import json
from pathlib import Path
from unittest.mock import patch

from tools.ultimatrix_mutator import (
    load_mutation_ledger,
    save_mutation_ledger,
    apply_fast_io_mutation,
    apply_pragma_tuning_mutation,
    apply_static_memory_mutation,
    mutate_allele,
    mutate_gene_file,
)


def test_mutation_ledger_roundtrip(tmp_path: Path):
    test_ledger = tmp_path / "test_mut_ledger.json"
    with patch("tools.ultimatrix_mutator.MUTATION_LEDGER", test_ledger):
        ledger = load_mutation_ledger()
        assert ledger["version"] == 1
        ledger["mutations_applied"] += 2
        ledger["promotions_won"] += 1
        save_mutation_ledger(ledger)

        reloaded = load_mutation_ledger()
        assert reloaded["mutations_applied"] == 2
        assert reloaded["promotions_won"] == 1


def test_apply_pragma_tuning_cpp():
    raw_cpp = "int main() { return 0; }"
    mutated, applied = apply_pragma_tuning_mutation(raw_cpp, lang="cpp")
    assert applied is True
    assert "#pragma GCC optimize" in mutated
    assert "avx2" in mutated


def test_apply_fast_io_cpp():
    raw_cpp = "int main() {\n    int x;\n    return 0;\n}"
    mutated, applied = apply_fast_io_mutation(raw_cpp, lang="cpp")
    assert applied is True
    assert "std::ios_base::sync_with_stdio(false)" in mutated


def test_mutate_allele_boosts_fitness():
    allele = {
        "allele_id": "naive_dsu",
        "dominance": "PRIMARY",
        "code_template": "struct DSU { int n; };",
        "environmental_triggers": ["cpp20"],
        "empirical_fitness": {"runtime_ms": 100.0, "ram_kb": 2048},
    }
    mutant = mutate_allele(allele, "pragma_tuning")
    assert mutant is not None
    assert mutant["allele_id"] == "naive_dsu_mut_pragma_tuning"
    assert mutant["empirical_fitness"]["runtime_ms"] < 100.0
    assert "#pragma GCC" in mutant["code_template"]


def test_mutate_gene_file(tmp_path: Path):
    gene_file = tmp_path / "test_gene.json"
    data = {
        "gene_id": "TEST_MUT_GENE",
        "tier": 2,
        "category": "primitive_structure",
        "alleles": [
            {
                "allele_id": "orig_impl",
                "dominance": "PRIMARY",
                "code_template": "int main() { return 0; }",
                "empirical_fitness": {"runtime_ms": 80.0, "ram_kb": 1024},
            }
        ],
    }
    gene_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    res = mutate_gene_file(gene_file)
    assert res["status"] == "SUCCESS"
    assert res["mutants_created"] >= 1
    assert "orig_impl_mut_" in res["dominant_allele"]
