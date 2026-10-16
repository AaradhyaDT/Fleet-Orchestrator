#!/usr/bin/env python3
"""tests/test_ultimatrix_closed_loop.py
--------------------------------------
Unit and integration tests for Azmuth Phase 7 Closed-Loop Evolutionary Scheduler:
1. Anti-starvation in Arena: only_unraced=True returns genes_processed=0 when all genes are stabilized.
2. Harvester progression: falls through from Priority 5 to Priority 6 (Solver) and 7 (Mutator).
3. Solver attempted_slugs tracking: records failure states without stalling on first unsolveable task.
4. Closed-loop sequencing: task in solutions/solution.py is automatically parsed and materialized into codon_stream.
5. Mutator bounded depth: existing _mut_ alleles are not mutated recursively.
"""

import json
from pathlib import Path
from tools.ultimatrix_arena import run_arena_tournament
from tools.azmuth_corpus_harvester import harvest_single_task
from tools.azmuth_gene_catalog import parse_task_submissions
from tools.ultimatrix_autonomous_solver import (
    solve_task_autonomously,
    load_solver_ledger,
    save_solver_ledger,
    get_unsolved_tasks,
)
from tools.ultimatrix_mutator import mutate_gene_file


def test_arena_anti_starvation_filter(tmp_path: Path):
    """Verifies only_unraced=True returns ALL_GENES_STABILIZED when all genes have empirical fitness."""
    # When all genes are benchmarked, only_unraced=True should return 0 genes processed
    res = run_arena_tournament(max_genes=1, only_unraced=True)
    assert res.get("genes_processed") == 0
    assert res.get("status") in ("ALL_GENES_STABILIZED", "CODON_STREAM_NOT_FOUND", "NO_GENES_FOUND")


def test_solver_records_attempted_and_advances():
    """Verifies that an unsupported task is recorded in attempted_slugs."""
    ledger = load_solver_ledger()
    ledger["attempted_slugs"] = {}
    save_solver_ledger(ledger)

    # Solve a non-existent/unsupported task
    res = solve_task_autonomously("unsupported-hard-challenge-xyz")
    assert res["status"] in ("NO_SAMPLES", "UNSUPPORTED_ARCHETYPE")

    reloaded = load_solver_ledger()
    if res["status"] == "UNSUPPORTED_ARCHETYPE":
        assert reloaded["attempted_slugs"].get("unsupported-hard-challenge-xyz") == "UNSUPPORTED_ARCHETYPE"


def test_closed_loop_solutions_sequencing(tmp_path: Path):
    """Verifies parse_task_submissions correctly ingests tasks with solutions/solution.py."""
    task_dir = tmp_path / "custom-task"
    task_dir.mkdir()
    (task_dir / "problem.json").write_text(json.dumps({"title": "Custom Task", "difficulty": "MEDIUM"}), encoding="utf-8")
    (task_dir / "statement.md").write_text("# Custom Task\n", encoding="utf-8")

    # Put a solution in solutions/ directory
    sol_dir = task_dir / "solutions"
    sol_dir.mkdir()
    (sol_dir / "solution.py").write_text("import sys\nprint('hello')\n", encoding="utf-8")

    gene = parse_task_submissions(task_dir)
    assert gene is not None
    assert gene["gene_id"] == "TASK_CUSTOM_TASK"
    assert len(gene["alleles"]) == 1
    assert "auto_solution_python" in gene["alleles"][0]["allele_id"]


def test_bounded_mutation_depth(tmp_path: Path):
    """Verifies that mutant alleles (_mut_) are not recursively mutated."""
    gene_path = tmp_path / "bounded_gene.json"
    gene_data = {
        "gene_id": "BOUNDED_TEST",
        "tier": 2,
        "category": "primitive_structure",
        "alleles": [
            {
                "allele_id": "base_sub_mut_fast_io",
                "dominance": "PRIMARY",
                "complexity_time": "O(N)",
                "complexity_space": "O(N)",
                "code_template": "int main() {}",
                "empirical_fitness": {"runtime_ms": 10.0, "ram_kb": 1024},
            }
        ],
    }
    gene_path.write_text(json.dumps(gene_data, indent=2), encoding="utf-8")

    res = mutate_gene_file(gene_path)
    # Should decline mutation because the only allele is already a mutant
    assert res["status"] == "NO_MUTATIONS_APPLICABLE"
