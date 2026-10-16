#!/usr/bin/env python3
"""tests/test_copilot_muscle_bridge.py
--------------------------------------
Unit test suite for Phase 1: Copilot Muscle Bridge & Multi-Model Quota Defense.

Validates:
1. Multi-model cascade on 429 quota exhaustion (gemini-3.8-flash -> gemini-2.5-flash -> gemini-2.5-flash-lite).
2. Circuit breaker cooldown bypass routing directly to Copilot/Local fallback.
3. Copilot Headless Adapter delegation when Gemini API is unavailable or exhausted.
4. Allele mutation throttling to PRIMARY/ALTERNATIVE base alleles only (no daughter thrashing).
5. Heuristic keyword protection against false-positive sum/addition matches.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.ultimatrix_autonomous_solver import (
    query_llm_with_resilient_fallback,
    synthesize_python_solution,
)
from tools.ultimatrix_mutator import mutate_gene_file


def test_heuristic_keyword_protection():
    """Verifies that naive 'sum' substring matching does not trigger addition template."""
    # 0-sum-array or sum-of-powers should NOT match simple addition
    task_complex_sum = {"slug": "0-sum-array", "candidate_genes": []}
    code = synthesize_python_solution(task_complex_sum)
    assert code is None or "a + b" not in code

    task_powers_sum = {"slug": "sum-of-powers", "candidate_genes": []}
    code2 = synthesize_python_solution(task_powers_sum)
    assert code2 is None or "a + b" not in code2

    # Exact 'addition' or 'a-plus-b' SHOULD match
    task_addition = {"slug": "addition", "candidate_genes": []}
    code_add = synthesize_python_solution(task_addition)
    assert code_add is not None
    assert "a + b" in code_add


def test_multi_model_cascade_on_429():
    """Verifies that query_llm_with_resilient_fallback falls back from 3.8-flash to 2.5-flash on 429."""
    call_log = []

    def mock_generate_content(model: str, contents: str, config=None):
        call_log.append(model)
        if model == "gemini-3.8-flash":
            raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded, retryDelay: '60s'")
        mock_resp = MagicMock()
        mock_resp.text = "```python\nprint('FALLBACK_MODEL_SUCCESS')\n```"
        return mock_resp

    with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_test_key"}), \
         patch("google.genai.Client") as mock_client_cls, \
         patch("tools.ultimatrix_autonomous_solver.load_solver_ledger", return_value={}):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = mock_generate_content
        mock_client_cls.return_value = mock_client

        res = query_llm_with_resilient_fallback("Solve problem X", task_slug="test-task")
        assert res == "print('FALLBACK_MODEL_SUCCESS')"
        assert call_log == ["gemini-3.8-flash", "gemini-2.5-flash"]


def test_circuit_breaker_bypasses_gemini(tmp_path: Path):
    """Verifies that when circuit breaker is active, Gemini is bypassed and Copilot/Local fallback is used."""
    future_time = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
    mock_ledger = {"gemini_circuit_breaker_until": future_time}

    with patch("tools.ultimatrix_autonomous_solver.load_solver_ledger", return_value=mock_ledger), \
         patch("tools.ultimatrix_autonomous_solver.query_copilot_or_local_fallback", return_value="print('COPILOT_FALLBACK_RESULT')") as mock_copilot:

        res = query_llm_with_resilient_fallback("Solve problem Y", task_slug="test-cb")
        assert res == "print('COPILOT_FALLBACK_RESULT')"
        mock_copilot.assert_called_once()


def test_copilot_headless_fallback_integration():
    """Verifies query_copilot_or_local_fallback invokes CopilotHeadlessAdapter with pooled account token."""
    from tools.ultimatrix_autonomous_solver import query_copilot_or_local_fallback

    mock_accounts = [{
        "worker_id": "copilot-w1",
        "name": "tester",
        "token": "ghp_mock_token_123",
        "has_token": True,
    }]

    mock_exec_result = {
        "success": True,
        "result_text": "```python\ndef solve():\n    print(42)\n```",
    }

    with patch("tools.copilot_fleet.load_env_fleet", return_value={}), \
         patch("tools.copilot_fleet.discover_accounts", return_value=mock_accounts), \
         patch("client.adapters.copilot_headless.CopilotHeadlessAdapter.execute_task", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_exec_result

        out = query_copilot_or_local_fallback("Solve task Z", task_slug="test-z")
        assert out is not None
        assert "print(42)" in out


def test_mutator_allele_throttling(tmp_path: Path):
    """Verifies mutator only mutates PRIMARY or ALTERNATIVE alleles, skipping daughters or RECESSIVE alleles."""
    gene_data = {
        "gene_id": "TASK_SAMPLE_MUTATION",
        "alleles": [
            {
                "allele_id": "allele_primary",
                "dominance": "PRIMARY",
                "code_template": "int main() { return 0; }",
            },
            {
                "allele_id": "allele_daughter_mut_fast_io",
                "dominance": "ALTERNATIVE",
                "code_template": "int main() { cin.tie(NULL); return 0; }",
            },
            {
                "allele_id": "allele_recessive",
                "dominance": "RECESSIVE",
                "code_template": "int main() { cout << 1; return 0; }",
            },
        ],
    }
    gene_file = tmp_path / "sample_gene.json"
    gene_file.write_text(json.dumps(gene_data, indent=2), encoding="utf-8")

    with patch("tools.ultimatrix_arena.race_gene_alleles", return_value={"dominant_allele": "allele_primary_mut_fast_io", "promotions": 1}), \
         patch("tools.ultimatrix_mutator.load_mutation_ledger", return_value={"history": []}), \
         patch("tools.ultimatrix_mutator.save_mutation_ledger"):

        res = mutate_gene_file(gene_file)
        assert res["status"] == "SUCCESS"
        assert res["mutants_created"] == 1

        updated_data = json.loads(gene_file.read_text(encoding="utf-8"))
        allele_ids = [a["allele_id"] for a in updated_data["alleles"]]
        # Should create mutant for allele_primary
        assert "allele_primary_mut_fast_io" in allele_ids
        # Should NOT create mutant for daughter or recessive
        assert not any("allele_daughter_mut_fast_io_mut_" in aid for aid in allele_ids)
        assert not any("allele_recessive_mut_" in aid for aid in allele_ids)
