# Agent Rules & Workflow Guidelines — Fleet-Orchestrator

Welcome, Agent. This repository (`Fleet-Orchestrator`) serves as the **Autonomous Multi-Model Agent Fleet Orchestration Engine** for Aaradhya's developer ecosystem.

To preserve repository integrity, avoid merge collisions, and enforce zero-drift deterministic verification, you **MUST** strictly adhere to the following operating principles.

---

## 1. Git Workflow & Ecosystem Automation (CRITICAL — STRICT ENFORCEMENT)

To avoid breaking branch tracking and prevent wasteful multi-step Git commands, **NEVER run individual `git add`, `git commit`, `git push`, or `git pull` commands directly.**

**ALWAYS execute `.\sync.bat` (or `.\sync.ps1`) for repository synchronization and version control.**
*(Note: `.\sync.bat` is the zero-friction execution wrapper that automatically bypasses PowerShell ExecutionPolicy restrictions).*

### Core Commands

- **Routine Sync**:
  ```powershell
  .\sync.bat                              # or .\sync.ps1
  ```
- **Dry-Run Preview (Simulate without modifying Git)**:
  ```powershell
  .\sync.bat -WhatIf                      # or .\sync.ps1 -WhatIf
  ```
- **Major Features / Architectural Changes**:
  ```powershell
  .\sync.bat -m "feat(scope): detailed commit summary"
  ```
- **Safe Pull Only**:
  ```powershell
  .\sync.bat -PullOnly
  ```
- **GitHub CLI Workflow Engine (`.\gh.bat` / `.\gh.ps1`)**:
  Use `.\gh.bat` (or `.\gh.ps1`) for issue creation, checklist task toggling, GraphQL sub-issue linking, SHA-verified issue closing, and automatic `--body` to `--body-file` UTF-8 protection (`INV-GH-BODY-FILE`):
  ```powershell
  .\gh.bat --gh-help
  .\gh.bat issue-create --title "[Feature] Summary" --assignee AaradhyaDT --label enhancement --type Feature --body "## Overview..."
  .\gh.bat task --issue <id> --list
  .\gh.bat close-verified <id> --comment "All verification gates passed."
  ```

---

## 2. Verification Gates & Reality Layer

Before finalizing changes or executing `.\sync.bat`:
1. **Linting & Code Hygiene Gate** (Mandatory — Zero Errors):
   ```powershell
   ruff check .
   ```
2. **Secret Leakage & Schema Validation**:
   ```powershell
   python tools/ci_secret_scanner.py --all
   python tools/validate_schemas.py --all
   ```
3. **Skill Mirror Audit & Synchronization**:
   ```powershell
   python tools/mirror_skills.py --fix    # or --sync (copies SSOT adaptive-workflow to global & brainstorm mirrors)
   ```
4. **Pytest Verification**:
   ```powershell
   pytest tests/                          # 100% pass rate required
   pytest -k "azmuth" -v                  # Prefer -k keyword selection over literal quoted globs on Windows
   ```
5. **Adapter Verification**:
   ```powershell
   pytest tests/test_copilot_cli_adapter.py -v
   pytest tests/test_copilot_headless.py -v
   ```

---

## 3. Canonical Repository Layout & Invariants

- **Linter Configuration**: `ruff.toml` (do NOT look for `pyproject.toml` or `.ruff.toml`).
- **Test Configuration**: `pytest.ini`.
- **CI/CD Workflow**: `.github/workflows/ci.yml` (do NOT look for `ci-cd.yml`).
- **Google Drive Sync**: `scripts/sync_drive.py` (located in `scripts/`, not `tools/`).
- **Scratch & Test Isolation**: Store ephemeral runner scripts in `<appDataDir>\brain\<conversation-id>/scratch/`. Repository `scratch/` is strictly git-ignored and never committed to Git.
- **Zero Credential Commits**: Never commit `.env`, `.env.fleet`, `*.db`, session files, cookies, or raw tokens.
- **Zero Idle Compute Burn & Unconditional Teardown Invariant (`INV-COLAB-UNASSIGN-MANDATORY`)**:
  - In ALL batch, training, data processing, transcoding, or headless Google Colab notebooks, `runtime.unassign()` is **MANDATORY, UNCONDITIONAL, AND STRICTLY ENFORCED**.
  - **Zero Conditional Teardown Guards**: NEVER gate container teardown behind `if AUTO_UNASSIGN:`, environment variables, or boolean checks that can silently default to `False`. The terminal cell MUST unconditionally flush storage (`drive.flush_and_unmount()`) and invoke `runtime.unassign()` to destroy the VM.
  - Leaving a billable GPU/TPU VM running idle after batch execution is a severe operational violation. For interactive server instances (e.g. `llama-server`), explicit manual stop commands (`colab stop -s <name>`) or client-side idle timeouts must be actively enforced.
- **Process Isolation**: Each worker subprocess driving `copilot.exe` must receive its own isolated `COPILOT_GITHUB_TOKEN` and `COPILOT_HOME` directory.
- **Background Task & Subprocess Governance (`background-task-governance`)**:
  - Automatically enforce the [`background-task-governance`](file:///C:/Users/Aaradhya/.gemini/config/skills/background-task-governance/SKILL.md) skill across all orchestrator and worker executions.
  - **Zero Interactive CLIs Headlessly**: Never invoke CLI utilities that prompt for unattached stdin or confirmation without non-interactive flags (e.g., `diskpart`, interactive WSL commands, unflagged package managers).
  - **Zero Elevated UAC Headlessly**: Commands requiring administrator elevation must never be dispatched headlessly; instruct the user to run them in an external elevated terminal.
  - **PowerShell Script-File First**: Never pass multi-pipe expressions or complex PowerShell blocks via inline `-Command "..."` strings. Write to a `.ps1` in the scratch directory and invoke with `-ExecutionPolicy Bypass -File`.
  - **Proactive Watchdog**: If any background task produces no output or progress for >60s, inspect process CPU/IO immediately and kill deadlocked tasks.

---

## 4. Token Density & Anti-Degradation Invariants

To prevent softmax attention dispersion, multi-byte tokenizer fragmentation, and KV cache pollution:
- **Zero Decorative Emojis**: Strictly ban decorative symbols (lightning, sparkles, rocket, brain, lightbulb, fire, pushpin, target) from technical documentation, prompt templates, commit messages, and agent instructions.
- **Thinking Trace Isolation**: All multi-turn agent dispatchers must strip internal thinking traces (`<think>` blocks) prior to appending assistant responses back into conversation history.
- **Stdout Truncation**: Terminal tool outputs injected into agent contexts must never exceed 30 lines (top 10 lines, truncation ellipsis, bottom 20 lines) to preserve token Signal-to-Noise Ratio (SNR).
- **Automated Screening**: Run `python tools/screen_token_degradation.py --all` to audit documentation and prompts before finalizing releases.


