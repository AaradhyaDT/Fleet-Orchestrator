from argparse import Namespace
from tools.azmuth_cli import handle_break, handle_dump, handle_resume


def test_cognitive_barrier_break_cycle(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.azmuth_cli.STATE_DIR", tmp_path)

    # 1. Initiate Break
    res_b = handle_break(Namespace(minutes=15))
    assert res_b == 0
    assert (tmp_path / "cognitive_telemetry.json").exists()

    # 2. Dump Thought
    res_d = handle_dump(Namespace(thought=["Map", "ITU", "AI", "timeline"]))
    assert res_d == 0
    assert (tmp_path / "cognitive_vault.jsonl").exists()

    # 3. Resume Session
    res_r = handle_resume(Namespace())
    assert res_r == 0
