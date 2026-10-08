"""
test_scratchpad_manager.py
--------------------------
Unit tests for ScratchpadManager:
- Lifecycle: init, read, append, stage context formatting, sealing.
- Concurrency: race safety across parallel append operations.
"""

import asyncio
from pathlib import Path
import pytest
import pytest_asyncio

from client.scratchpad_manager import ScratchpadManager


@pytest.fixture
def scratchpad(tmp_path: Path) -> ScratchpadManager:
    return ScratchpadManager(base_dir=tmp_path / "scratchpads")


@pytest.mark.asyncio
async def test_scratchpad_lifecycle(scratchpad: ScratchpadManager):
    job_id = "job_test_001"
    path = await scratchpad.init_scratchpad(job_id, "Build Levenshtein Util", "Implement Levenshtein function")
    assert path.exists()

    content = await scratchpad.read_scratchpad(job_id)
    assert "Build Levenshtein Util" in content
    assert "Implement Levenshtein function" in content
    assert "INITIALIZED" in content

    # Append Stage 1 Plan (Section 2)
    await scratchpad.append_section(
        job_id,
        2,
        "WBS Task 1: Create levenshtein.py with DP table.\nWBS Task 2: Create test_levenshtein.py.",
        actor="claude-w1-adevtmr",
    )
    content2 = await scratchpad.read_scratchpad(job_id)
    assert "WBS Task 1" in content2
    assert "claude-w1-adevtmr" in content2

    # Append Stage 2 Implementation (Section 3)
    await scratchpad.append_section(
        job_id,
        3,
        "Implemented levenshtein(a, b). Local pytest passed: 10/10.",
        actor="copilot-w1",
    )
    content3 = await scratchpad.read_scratchpad(job_id)
    assert "Local pytest passed: 10/10" in content3
    assert "copilot-w1" in content3

    # Append Stage 3 QA Verdict (Section 4)
    await scratchpad.append_section(
        job_id,
        4,
        "QA_VERDICT: PASS\nAll edge cases (empty strings, unicode) handled cleanly.",
        actor="claude-w4-adtbei79001",
    )
    content4 = await scratchpad.read_scratchpad(job_id)
    assert "QA_VERDICT: PASS" in content4
    assert "claude-w4-adtbei79001" in content4

    # Seal scratchpad
    sealed_path = await scratchpad.seal_scratchpad(job_id, "COMPLETED", "All acceptance criteria verified.")
    assert sealed_path.exists()
    final_content = await scratchpad.read_scratchpad(job_id)
    assert "COMPLETED" in final_content
    assert "All acceptance criteria verified" in final_content


@pytest.mark.asyncio
async def test_scratchpad_concurrent_appends(scratchpad: ScratchpadManager):
    job_id = "job_concurrent_002"
    await scratchpad.init_scratchpad(job_id, "Concurrent Append Test", "Test parallel writers")

    async def _worker_append(worker_idx: int):
        await scratchpad.append_section(
            job_id,
            3,
            f"Worker {worker_idx} completed diff block {worker_idx}.",
            actor=f"copilot-w{worker_idx}",
        )

    # 10 workers appending concurrently
    await asyncio.gather(*[_worker_append(i) for i in range(1, 11)])

    final_content = await scratchpad.read_scratchpad(job_id)
    for i in range(1, 11):
        assert f"Worker {i} completed diff block {i}" in final_content
        assert f"copilot-w{i}" in final_content
