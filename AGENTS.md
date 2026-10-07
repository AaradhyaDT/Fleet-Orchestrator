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
- **Major Features / Architectural Changes**:
  ```powershell
  .\sync.bat -m "feat(scope): detailed commit summary"
  ```
- **Safe Pull Only**:
  ```powershell
  .\sync.bat -PullOnly
  ```

---

## 2. Verification Gates & Reality Layer

Before finalizing changes or committing:
1. **Pytest Verification**:
   ```powershell
   pytest tests/
   ```
   Ensure all unit tests pass with 100% pass rate.
2. **Adapter Verification**:
   ```powershell
   pytest tests/test_copilot_cli_adapter.py -v
   pytest tests/test_copilot_headless.py -v
   ```

---

## 3. Security & Invariants

- **Zero Credential Commits**: Never commit `.env`, `.env.fleet`, `*.db`, session files, cookies, or raw tokens.
- **Process Isolation**: Each worker subprocess driving `copilot.exe` must receive its own isolated `COPILOT_GITHUB_TOKEN` and `COPILOT_HOME` directory.
