# Handoff: Fleet-Orchestrator Independent Engine & Multi-Account Copilot Pool

**Target Repository:** `F:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator`  
**Date:** 2026-10-08  
**Working Branch:** `main` (clean, synced with `origin/main`)  
**Companion Repos:** `Claude-Desktop` (`F:\Aaradhya-Dev-Tamrakar\Claude-Desktop`), `brainstorm` (`F:\Aaradhya-Dev-Tamrakar\brainstorm`)

---

## 1. System Context & Architecture Overview

`Fleet-Orchestrator` is an **independent, high-throughput batch execution engine and multi-account credential aggregator**. It manages 27 verified GitHub Copilot CLI accounts pooling **5,400 monthly AI credits** ($27 \times 200$), executing code implementation tasks autonomously with complete decoupling from Claude Desktop.

### Key Architectural Pillars:
- **Decoupled File-Watching Worker**: Lightweight, resilient background worker (`tools/copilot_queue_worker.py`) that monitors `orchestrator-state/tasks/` for `kind == "code"` and `status == "pending"`.
- **Atomic Claim Token Governance**: Employs kernel-level atomic `O_CREAT | O_EXCL` claim tokens coupled with `os.replace` atomic file swaps, ensuring zero duplicate claims or race conditions across concurrent OS processes.
- **Round-Robin Rotation with Cooldown Governance**: Automatically distributes code jobs across ready Copilot workers (`copilot-w1` through `copilot-w27`), dynamically bypassing accounts in active rate-limit or monthly quota cooldown.
- **Provider Auto-Routing Enforcement**: Strictly omits `--model` flags on Copilot Free accounts to prevent quota exhaustion errors and comply with GitHub's model routing constraints.
- **Automated Worktree Isolation**: Auto-provisions and tears down isolated Git worktrees (`.worktrees/task_<id>`) for zero file collisions between concurrent or sequential task executions.
- **Real-Time Quota Dashboard**: Live CLI and REST API visibility into monthly credit burn rates, pool capacity, and per-worker telemetry.
- **Standalone Batch Execution**: Autonomous task submission and batch runners (`python tools/copilot_fleet.py submit / batch`) running end-to-end without Claude Desktop dependencies.

---

## 2. Current State & Assets in `Fleet-Orchestrator`

1. **`tools/copilot_queue_worker.py`**:
   - Background daemon scanning `orchestrator-state/tasks/` with atomic claims, worktree isolation, usage parsing, and concurrency support (`--concurrency N`, `--worker-id`, `--task-id`).
   - Auto-provisions isolated Git worktrees (`git worktree add -b task/<task_id> <worktree_dir> HEAD`).
   - Auto-commits worktree diffs (`feat({task_id}): automated implementation`) and cleans up worktrees upon checkpoint submission or failure.
   - Parses `--usage-output-file` JSON from `copilot.exe` for `credits_used`, `tokens_used`, and quota exhaustion detection.
   - Persists telemetry (`credits_used`, `credits_remaining`, `monthly_credits`, `cooldown_until`) into `live-status/<worker_id>.json`.

2. **`tools/copilot_fleet.py`**:
   - `dashboard`: Real-time ASCII and JSON (`--json`) dashboard reporting fleet pool capacity (5,400 credits), consumed credits, monthly burn bar, and per-worker status.
   - `submit`: Enqueues individual or batch task specs directly into `orchestrator-state/tasks/`.
   - `batch`: Autonomous end-to-end batch execution pipeline (enqueues -> runs worker pool -> prints execution manifest).
   - `status` & `canary`: Verifies GitHub API PAT readiness and executes concurrent canary checks across all accounts.

3. **`tools/stress_test_concurrency.py`**:
   - High-load multi-worker stress testing harness verifying race-free task acquisition and 100% checkpoint generation.

4. **`launch_copilot_worker.bat`**:
   - One-click runner (~14 MB RAM) forwarding CLI arguments (`%*`) to `copilot_queue_worker.py`.

5. **`server/api/routes_workers.py`**:
   - REST API endpoint `GET /api/v1/workers/quota-dashboard` surfacing live fleet quota telemetry.

6. **Test Suite Status**:
   - **159 / 159 tests passing** (100% pass rate in `pytest` across unit, integration, stress, and API test suites).

---

## 3. Completed Objectives

1. **Multi-Process Concurrency Tuning & Stress Testing**:
   - Implemented kernel-level `O_CREAT | O_EXCL` atomic claim token in `claim_task()` to eliminate race conditions under heavy load.
   - Built standalone stress test harness (`tools/stress_test_concurrency.py`) and automated pytest suite (`tests/test_concurrency_stress.py`).
   - Verified 16 tasks across 4 concurrent workers under heavy contention: 100% completion, 0 double claims, perfectly balanced task distribution.

2. **Quota Tracking Dashboard**:
   - Implemented `get_fleet_quota_metrics()` in `tools/copilot_fleet.py`.
   - Added CLI dashboard command (`python tools/copilot_fleet.py dashboard [--json]`).
   - Exposed REST API endpoint `GET /api/v1/workers/quota-dashboard` in `server/api/routes_workers.py`.
   - Covered with unit tests in `tests/test_copilot_fleet_dashboard.py` and `tests/test_quota_dashboard_api.py`.

3. **Standalone Autonomous Execution**:
   - Implemented autonomous task submission (`python tools/copilot_fleet.py submit --spec "..."`).
   - Built autonomous batch executor (`python tools/copilot_fleet.py batch --specs "..." --concurrency 2`).
   - Verified dry-run and live batch task execution independent of Claude Desktop.

---

## 4. Operational Invariants & Rules

- **Zero Raw Git Commands**: Never run raw `git add`, `git commit`, or `git push`. Always run `.\sync.bat` (or `.\sync.ps1`).
- **Strictly No `--model` on Copilot Free**: Always allow GitHub's auto-routing to avoid `ModelNotAllowed` errors.
- **Verification Gate**: Ensure `pytest` passes 100% before committing or syncing changes.
