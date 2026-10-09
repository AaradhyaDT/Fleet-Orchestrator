import json
import pytest
from pathlib import Path
from tools.harvest_agent_trajectories import sanitize_text, is_error_output, export_splits


def test_sanitize_text():
    dummy_token = "ghp_" + ("1" * 36)
    raw = f"Error in C:\\Users\\Aaradhya\\.gemini\\antigravity\\brain\\foo with {dummy_token}"
    sanitized = sanitize_text(raw)
    assert "Aaradhya" not in sanitized
    assert "ghp_REDACTED_TOKEN" in sanitized
    assert "~/.antigravity" in sanitized


def test_is_error_output():
    assert is_error_output("Command exited with code 1") is True
    assert is_error_output("Traceback (most recent call last):") is True
    assert is_error_output("SyntaxError: invalid syntax") is True
    assert is_error_output("All 10 tests passed successfully") is False


def test_export_splits(tmp_path: Path):
    samples = [{"prompt": f"test_{i}", "val": i} for i in range(10)]
    train_n, eval_n = export_splits(samples, "test_prefix", tmp_path, eval_ratio=0.20, seed=42)
    assert train_n == 8
    assert eval_n == 2
    assert (tmp_path / "test_prefix_train.jsonl").exists()
    assert (tmp_path / "test_prefix_eval.jsonl").exists()
