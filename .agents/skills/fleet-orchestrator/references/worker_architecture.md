# Fleet-Orchestrator Worker Architecture & Concurrency

## 1. Tri-Fleet Credential Pooling
The fleet dynamically pools compute across three distinct provider layers configured via modular environment files:

### A. GitHub Copilot Fleet (`.env.fleet.copilot`)
- Up to 27 accounts pooled dynamically ($27 \times 200 = 5,400$ monthly credits).
- GitHub Fine-Grained PATs with "Copilot Requests" Read & Write permissions and 90-day expiry.
- Subprocess isolation with isolated `COPILOT_HOME` directories.

### B. Google AI Studio Gemini API Fleet (`.env.fleet.gemini`)
- Pooled Google AI Studio Gemini API keys with 2-tier cooldown (60s burst on 429, daily reset at 00:00 UTC).
- Keys created in separate Google Cloud Projects to achieve true multiplied throughput (15 RPM / 1,500 RPD per project).
- Transparent zero-drop failover across keys via `GeminiKeyRotator`.

### C. Google Antigravity (AGY) CLI Fleet (`.env.fleet.agy`)
- Headless `agy.exe -p` execution with mandatory `--dangerously-skip-permissions`.
- Sandbox isolation: each worker receives an isolated `AGY_WORKER_HOME` to prevent SQLite lock collisions on `conversation_summaries.db`.
- Structured JSON output parsing and bounded execution timeouts.

## 2. Worktree Sandboxing
- Workers isolate changes inside `.worktrees/<task_id>`.
- Multiple workers can execute concurrently without merge collisions or dirty working trees on `main`.
- On completion, the worker commits the worktree branch, updates `orchestrator-state/checkpoints/`, and tears down the worktree directory.
