from argparse import Namespace
from tools.azmuth_cli import handle_break, handle_dump, handle_resume


def test_cognitive_barrier_break_cycle(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.azmuth_cli.STATE_DIR", tmp_path)

    # 1. Initiate Break
    res_b = handle_break(Namespace(minutes=15))
    assert res_b == 0
    assert (tmp_path / "cognitive_telemetry.json").exists()

    # 2. Dump Thought without raising error
    res_d = handle_dump(Namespace(thought=["Map", "ITU", "AI", "timeline"]))
    assert res_d == 0
    assert (tmp_path / "cognitive_vault.jsonl").exists()

    # 3. Resume Session
    res_r = handle_resume(Namespace())
    assert res_r == 0


def test_incubator_worker_dry_run(tmp_path, monkeypatch):
    from tools.incubator_gemini_worker import main_async
    import asyncio

    monkeypatch.setattr("tools.incubator_gemini_worker.INCUBATOR_DIR", tmp_path / "incubator")
    monkeypatch.setattr("tools.incubator_gemini_worker.VAULT_PATH", tmp_path / "cognitive_vault.jsonl")

    # Run with --no-issue to verify Gemini Fleet generation without hitting remote GitHub API
    rc = asyncio.run(main_async("Test Kalman filter integration", create_issue=False))
    assert rc == 0
    rfcs = list((tmp_path / "incubator").glob("*.md"))
    assert len(rfcs) == 1
    content = rfcs[0].read_text(encoding="utf-8")
    assert "Test Kalman filter integration" in content
    assert len(content) > 100
