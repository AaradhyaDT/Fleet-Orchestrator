from __future__ import annotations

import json
import pytest
import pytest_asyncio
import aiosqlite
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from server.core.database import init_db
from server.core.config import settings
from server.core.pipeline_engine import pipeline_engine
from server.main import app

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path: Path, monkeypatch):
    test_db_path = tmp_path / "test_qa_gating.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db_path)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

async def test_checkpoint_does_not_advance_qa_stage():
    """
    Priority 0 Test A:
    A task in 'qa', 'review', or 'qa_review' stage must NOT advance the pipeline
    upon /checkpoint submission alone. It requires explicit /qa-review PASS.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register worker
        await client.post("/api/v1/workers/register", json={
            "id": "worker_gating_01",
            "provider": "copilot_cli",
            "node_id": "test-node",
            "nickname": "Gating Worker",
            "capabilities": ["code", "qa", "qa_review"],
            "quota_limit_per_window": 100,
            "cooldown_window_minutes": 300,
        })

        # Create job with pipeline ["code", "qa", "deploy"]
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            await db.execute(
                """
                INSERT INTO jobs (id, sku, client, input_uri, status, pipeline, quality_rules)
                VALUES ('job_qa_gated', 'test_sku', 'Internal', 'data/in.csv', 'running', ?, '[]')
                """,
                (json.dumps(["code", "qa", "deploy"]),)
            )
            # Create QA stage task (stage_order=2)
            await db.execute(
                """
                INSERT INTO tasks (id, job_id, stage, stage_order, kind, spec, status, priority)
                VALUES ('task_qa_stage_01', 'job_qa_gated', 'qa', 2, 'text', 'Review code deliverable', 'pending', 5)
                """
            )
            await db.commit()

        # Claim the QA task
        claim_res = await client.post("/api/v1/tasks/task_qa_stage_01/claim", json={
            "worker_id": "worker_gating_01",
            "lease_seconds": 300,
        })
        assert claim_res.status_code == 200
        claim_token = claim_res.json()["claim_token"]

        # Worker mistakenly calls /checkpoint instead of /qa-review
        cp_res = await client.post("/api/v1/tasks/task_qa_stage_01/checkpoint", json={
            "task_id": "task_qa_stage_01",
            "kind": "text",
            "summary": "Attempted QA bypass via checkpoint",
            "result_text": "Candidate QA notes",
            "submitted_by": "worker_gating_01",
            "claim_token": claim_token,
        })
        assert cp_res.status_code == 201

        # Verify: 'deploy' stage was NOT auto-created because 'qa' stage is verification-gated
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            deploy_task = await (await db.execute("SELECT * FROM tasks WHERE stage = 'deploy'")).fetchone()
            assert deploy_task is None, "QA stage must not advance to downstream deploy stage without QA review approval"

async def test_qa_rejection_reopens_parent_and_purges_pending_children():
    """
    Priority 0 Test B:
    If QA review returns 'revision_needed' or 'fail', the parent task deliverable
    under review is reopened for revision, and any pending child tasks are purged.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/workers/register", json={
            "id": "qa_reviewer_worker",
            "provider": "claude_desktop_cdp",
            "node_id": "test-node",
            "nickname": "Adversarial Reviewer",
            "capabilities": ["qa", "review"],
            "quota_limit_per_window": 100,
            "cooldown_window_minutes": 300,
        })

        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            await db.execute(
                """
                INSERT INTO jobs (id, sku, client, input_uri, status, pipeline, quality_rules)
                VALUES ('job_rev_test', 'test_sku', 'Client', 'data/in.csv', 'running', ?, '[]')
                """,
                (json.dumps(["draft", "qa", "publish"]),)
            )
            # Parent draft task
            await db.execute(
                """
                INSERT INTO tasks (id, job_id, stage, stage_order, kind, spec, status, priority)
                VALUES ('task_draft_01', 'job_rev_test', 'draft', 1, 'text', 'Draft body', 'done', 5)
                """
            )
            # QA task attached with parent_id
            await db.execute(
                """
                INSERT INTO tasks (id, job_id, parent_id, stage, stage_order, kind, spec, status, priority, owner_worker_id, claim_token, lease_expires_at)
                VALUES ('task_qa_01', 'job_rev_test', 'task_draft_01', 'qa', 2, 'text', 'Review draft', 'claimed', 5, 'qa_reviewer_worker', 'token_qa_123', datetime('now', '+300 seconds'))
                """
            )
            # Downstream child prematurely created or pending
            await db.execute(
                """
                INSERT INTO tasks (id, job_id, parent_id, stage, stage_order, kind, spec, status, priority)
                VALUES ('task_publish_pending', 'job_rev_test', 'task_qa_01', 'publish', 3, 'text', 'Publish draft', 'pending', 5)
                """
            )
            await db.commit()

        # Submit QA review with revision_needed
        qa_res = await client.post("/api/v1/tasks/task_qa_01/qa-review", json={
            "task_id": "task_qa_01",
            "reviewer_worker_id": "qa_reviewer_worker",
            "claim_token": "token_qa_123",
            "verdict": "revision_needed",
            "rejection_reason": "Tone too promotional, lacks technical rigor",
            "checks_passed": {"technical_rigor": False},
        })
        assert qa_res.status_code == 201

        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            # 1. Parent draft task reopened to pending
            parent_task = await (await db.execute("SELECT status FROM tasks WHERE id = 'task_draft_01'")).fetchone()
            assert parent_task["status"] == "pending", "Parent task must be reopened to pending upon QA revision"

            # 2. QA task reset to pending
            qa_task = await (await db.execute("SELECT status, owner_worker_id FROM tasks WHERE id = 'task_qa_01'")).fetchone()
            assert qa_task["status"] == "pending"
            assert qa_task["owner_worker_id"] is None

            # 3. Downstream pending publish task was purged
            downstream = await (await db.execute("SELECT * FROM tasks WHERE id = 'task_publish_pending'")).fetchone()
            assert downstream is None, "Downstream unverified tasks must be purged upon QA rejection"

async def test_idempotent_advance_stage_does_not_duplicate_or_overwrite():
    """
    Priority 0 Test C:
    Calling advance_task_to_next_stage multiple times for the same task
    returns the existing child task ID without recreating or wiping state.
    """
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO jobs (id, sku, client, input_uri, status, pipeline, quality_rules)
            VALUES ('job_idem_01', 'test_sku', 'Client', 'in.csv', 'running', ?, '[]')
            """,
            (json.dumps(["stage_a", "stage_b"]),)
        )
        await db.execute(
            """
            INSERT INTO tasks (id, job_id, stage, stage_order, kind, spec, status, priority)
            VALUES ('task_a_01', 'job_idem_01', 'stage_a', 1, 'text', 'Stage A work', 'done', 5)
            """
        )
        await db.execute(
            """
            INSERT INTO checkpoints (task_id, job_id, kind, summary, result_text, submitted_by)
            VALUES ('task_a_01', 'job_idem_01', 'text', 'Stage A done', 'Output A', 'w1')
            """
        )
        await db.commit()

        # First advance
        first_id = await pipeline_engine.advance_task_to_next_stage("task_a_01", db)
        assert first_id is not None

        # Simulate claiming first_id and setting it to claimed
        await db.execute("UPDATE tasks SET status = 'claimed', owner_worker_id = 'w2' WHERE id = ?", (first_id,))
        await db.commit()

        # Second advance call (re-entrant / replay)
        second_id = await pipeline_engine.advance_task_to_next_stage("task_a_01", db)
        assert second_id == first_id

        # Verify worker w2 ownership was NOT wiped out by INSERT OR REPLACE
        row = await (await db.execute("SELECT status, owner_worker_id FROM tasks WHERE id = ?", (first_id,))).fetchone()
        assert row["status"] == "claimed"
        assert row["owner_worker_id"] == "w2"
