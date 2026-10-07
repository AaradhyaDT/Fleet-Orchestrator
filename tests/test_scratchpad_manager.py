from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from server.core.scratchpad_manager import (
    ScratchpadError,
    ScratchpadManager,
    build_task_context,
)


@pytest.fixture
def temp_scratchpad_dir(tmp_path: Path) -> Path:
    scratch_dir = tmp_path / "scratchpads"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    return scratch_dir


def test_scratchpad_path_and_validation(temp_scratchpad_dir: Path):
    manager = ScratchpadManager(base_dir=temp_scratchpad_dir)
    valid_id = "job_123-abc.001"
    path = manager.path_for(valid_id)
    assert path.name == f"{valid_id}_scratchpad.md"
    assert path.parent == temp_scratchpad_dir

    with pytest.raises(ScratchpadError):
        manager.path_for("../invalid/job")

    with pytest.raises(ScratchpadError):
        manager.path_for("job!invalid@")


def test_scratchpad_ensure_and_read(temp_scratchpad_dir: Path):
    manager = ScratchpadManager(base_dir=temp_scratchpad_dir)
    job_id = "job_init_test"

    assert not manager.exists(job_id)
    assert manager.read(job_id) == ""

    p = manager.ensure(job_id)
    assert p.exists()
    assert manager.exists(job_id)

    content = manager.read(job_id)
    assert f"# Shared Scratchpad — {job_id}" in content
    assert "## 1. Architectural Plan & WBS Specs" in content
    assert "## 2. Worktree Diffs & Test Passes" in content
    assert "## 3. Adversarial QA Verdict" in content
    assert manager.read_section(job_id, 1) == ""


def test_scratchpad_write_and_read_section(temp_scratchpad_dir: Path):
    manager = ScratchpadManager(base_dir=temp_scratchpad_dir)
    job_id = "job_rw_test"

    manager.write_section(job_id, 1, "Plan content here.")
    assert manager.read_section(job_id, 1) == "Plan content here."
    assert manager.read_section(job_id, 2) == ""

    manager.write_section(job_id, 2, "Diffs and test pass logs.")
    assert manager.read_section(job_id, 2) == "Diffs and test pass logs."

    # Overwrite section 1
    manager.write_section(job_id, 1, "Updated plan.")
    assert manager.read_section(job_id, 1) == "Updated plan."

    # Invalid section raises ScratchpadError
    with pytest.raises(ScratchpadError):
        manager.write_section(job_id, 4, "Invalid")
    with pytest.raises(ScratchpadError):
        manager.read_section(job_id, 0)


def test_scratchpad_append_section(temp_scratchpad_dir: Path):
    manager = ScratchpadManager(base_dir=temp_scratchpad_dir)
    job_id = "job_append_test"

    manager.append_section(job_id, 3, "Review 1: REVISE")
    assert manager.read_section(job_id, 3) == "Review 1: REVISE"

    manager.append_section(job_id, 3, "Review 2: PASS")
    assert "Review 1: REVISE" in manager.read_section(job_id, 3)
    assert "Review 2: PASS" in manager.read_section(job_id, 3)


def test_scratchpad_render_context(temp_scratchpad_dir: Path):
    manager = ScratchpadManager(base_dir=temp_scratchpad_dir)
    job_id = "job_render_test"

    assert manager.render_context(job_id) == ""

    manager.write_section(job_id, 1, "Architecture details.")
    manager.write_section(job_id, 3, "QA verdict: PASS.")

    rendered = manager.render_context(job_id)
    assert "## 1. Architectural Plan & WBS Specs" in rendered
    assert "Architecture details." in rendered
    assert "Claude Architect" in rendered
    assert "## 3. Adversarial QA Verdict" in rendered
    assert "Claude Reviewer" in rendered

    # Exclude text match
    rendered_excluded = manager.render_context(job_id, exclude_text="Architecture details.")
    assert "Architecture details." not in rendered_excluded
    assert "## 3. Adversarial QA Verdict" in rendered_excluded

    # Truncation check
    rendered_truncated = manager.render_context(job_id, max_chars=30)
    assert "[scratchpad truncated]" in rendered_truncated


def test_build_task_context(temp_scratchpad_dir: Path):
    manager = ScratchpadManager(base_dir=temp_scratchpad_dir)
    assert build_task_context({}) == {}

    job_id = "job_ctx_test"
    manager.write_section(job_id, 1, "Spec draft")

    ctx = build_task_context({"job_id": job_id, "spec": "other"}, manager=manager)
    assert ctx["job_id"] == job_id
    assert "scratchpad" in ctx
    assert "Spec draft" in ctx["scratchpad"]


def test_concurrent_locks(temp_scratchpad_dir: Path):
    manager = ScratchpadManager(base_dir=temp_scratchpad_dir)
    job_id = "job_concurrency_test"

    errors = []

    def writer_worker(idx: int):
        try:
            for _ in range(5):
                manager.append_section(job_id, 2, f"Worker {idx} entry\n")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer_worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    sec2 = manager.read_section(job_id, 2)
    for i in range(4):
        assert f"Worker {i} entry" in sec2
