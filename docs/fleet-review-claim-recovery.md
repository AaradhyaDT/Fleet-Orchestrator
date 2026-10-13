# Claim-recovery review

## Result

The copied candidate had three reproducible filesystem/recovery defects:

- A claimed task's untrusted `id` was interpolated into its lock-file path. A stale task with `id: "../../escaped-lock"` created a lock file outside `tasks/`. Lock filenames now use a SHA-256 digest of the ID.
- A non-finite legacy `timeout` such as `"Infinity"` yielded an infinite recovery grace and stranded stale claims. Non-finite and unconvertible timeouts now use the 600-second default.
- `FileLock` followed a pre-existing symlink at the lock path; a dangling link caused a file to be created at its target. Task locking now refuses a symlinked lock path.

## Files reviewed

Copied from the main checkout into this isolated worktree: `tools/copilot_queue_worker.py`, `tests/test_copilot_queue_worker.py`, `tests/test_background_task_handoff.py`, and `tests/test_concurrency_stress.py`. Surgical changes were limited to `tools/copilot_queue_worker.py` and `tests/test_copilot_queue_worker.py`; this receipt is `docs/fleet-review-claim-recovery.md`. The main checkout was not edited.

## Verification

- Before fixes, the three added regressions failed: traversal created an escaped lock file; `"Infinity"` prevented reclaim; a symlinked lock was followed and its target created.
- After fixes: `python -m pytest -q` — **348 passed**, with one unrelated `google.genai` deprecation warning.
- `python -m ruff check tools/copilot_queue_worker.py tests/test_copilot_queue_worker.py tests/test_background_task_handoff.py tests/test_concurrency_stress.py` — passed.
- `git diff --check` on the four Python files — passed.
- The suite includes a separate-process OS-lock contention test, stale/missing-PID recovery, and fencing of late completion and failure updates.

## Limitations

Provider authentication, live credit harvesting, and external heartbeat integrations were not contacted; tests use local temporary state and mocked process identities where needed. The symlink regression covers a pre-existing link at lock acquisition; it does not claim protection against a concurrent filesystem attacker racing the link check.
