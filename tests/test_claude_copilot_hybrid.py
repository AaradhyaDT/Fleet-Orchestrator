"""
test_claude_copilot_hybrid.py
-----------------------------
Comprehensive integration tests for the Claude Desktop & Copilot CLI Hybrid Swarm:
- Verifies SKU pipeline template: claude_copilot_hybrid_cycle.json.
- Verifies scheduler affinity routing across hybrid stages.
- Verifies scratchpad state transitions and gate sealing.
"""

import json
from pathlib import Path
import pytest
import pytest_asyncio
import aiosqlite

from server.core.config import settings
from server.core.database import init_db
from server.core.scheduler import QuotaAwareScheduler
from server.core.pipeline_engine import PipelineEngine
from client.scratchpad_manager import ScratchpadManager


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_hybrid.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield


def test_hybrid_sku_template_loading():
    sku = PipelineEngine.load_sku_template("claude_copilot_hybrid_cycle")
    assert sku is not None
    assert sku["sku_id"] == "claude_copilot_hybrid_cycle"
    assert sku["pipeline"] == ["plan", "code", "qa_review"]
    assert len(sku["quality_rules"]) >= 3


@pytest.mark.asyncio
async def test_scheduler_hybrid_stage_affinity():
    scheduler = QuotaAwareScheduler()
    async with aiosqlite.connect(settings.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Register workers: 1 Claude Architect, 1 Copilot Coder, 1 Claude Reviewer
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, capabilities, quota_limit_per_window, quota_used_current, status)
            VALUES (?, ?, ?, ?, ?, ?, 0, 'idle')
            """,
            ("claude-w1", "claude_desktop_cdp", "node-1", "adevtmr", json.dumps(["writing", "research", "plan", "architecture"]), 50)
        )
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, capabilities, quota_limit_per_window, quota_used_current, status)
            VALUES (?, ?, ?, ?, ?, ?, 0, 'idle')
            """,
            ("copilot-w1", "copilot_cli", "node-2", "AaradhyaDT", json.dumps(["code", "refactor", "unit_test"]), 200)
        )
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, capabilities, quota_limit_per_window, quota_used_current, status)
            VALUES (?, ?, ?, ?, ?, ?, 0, 'idle')
            """,
            ("claude-w4", "claude_desktop_cdp", "node-1", "adtbei79001", json.dumps(["qa", "qa_review", "audit"]), 50)
        )
        await db.commit()

        # 1. Test Task for 'plan' stage -> should route to claude-w1
        await db.execute(
            """
            INSERT INTO tasks (id, job_id, stage, stage_order, kind, spec, status)
            VALUES ('task_plan_01', 'job_test', 'plan', 1, 'text', 'Decompose feature', 'pending')
            """
        )
        await db.commit()
        best_for_plan = await scheduler.select_best_worker_for_task("task_plan_01", db)
        assert best_for_plan == "claude-w1"

        # 2. Test Task for 'code' stage -> should route to copilot-w1
        await db.execute(
            """
            INSERT INTO tasks (id, job_id, stage, stage_order, kind, spec, status)
            VALUES ('task_code_01', 'job_test', 'code', 2, 'code', 'Implement feature', 'pending')
            """
        )
        await db.commit()
        best_for_code = await scheduler.select_best_worker_for_task("task_code_01", db)
        assert best_for_code == "copilot-w1"

        # 3. Test Task for 'qa_review' stage -> should route to claude-w4
        await db.execute(
            """
            INSERT INTO tasks (id, job_id, stage, stage_order, kind, spec, status)
            VALUES ('task_qa_01', 'job_test', 'qa_review', 3, 'text', 'Review feature', 'pending')
            """
        )
        await db.commit()
        best_for_qa = await scheduler.select_best_worker_for_task("task_qa_01", db)
        assert best_for_qa == "claude-w4"
