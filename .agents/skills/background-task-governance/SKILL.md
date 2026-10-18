---
name: background-task-governance
description: Prevents background tasks and CLI commands from hanging, freezing, or blocking execution in Antigravity/agent sessions on Windows. Enforces non-interactive execution guards, elevated UAC command bans, PowerShell escaping rules, wait timeout calibration, and proactive watchdog monitoring.
version: 1.0.0
---

# Background Task & CLI Execution Governance (Anti-Hang & Anti-Freeze)

This skill provides deterministic rules and execution guardrails to prevent agent background commands and asynchronous tasks from hanging, deadlocking, or remaining stuck on Windows systems.

---

## 1. Root Causes of Hanging Background Tasks

When an AI agent runs shell commands on Windows via `run_command` or background tasks, hangs almost always stem from five root failure modes:

| Failure Mode | Trigger / Symptom | Why It Freezes | Prevention / Fix |
| :--- | :--- | :--- | :--- |
| **Interactive CLI Prompts** | `diskpart`, `wsl --set-sparse`, `ftp`, `ssh`, `format`, `choice`, `pause` | The CLI expects interactive standard input (`stdin`) or confirmation (`[Y/n]`). Headless subprocess stdin remains unattached, causing the process to block indefinitely. | **Never run interactive CLIs headlessly.** Use non-interactive flags (e.g., `-y`, `--yes`, `--force`) or equivalent non-interactive APIs (PowerShell cmdlets, WMI/CIM, direct filesystem operations). |
| **Silent UAC / Elevation Requirement** | `diskpart`, `net stop/start`, `bcdedit`, `reagentc` | The process requires administrator privileges. In a standard user shell without interactive UAC approval, the process deadlocks or aborts without emitting stdout. | **Never invoke commands requiring elevated UAC in background subprocesses.** Guide the user to run elevated commands in an external Administrator terminal. |
| **PowerShell Quote & Pipeline Parsing Mangling** | Nested double quotes, unescaped `|`, `$`, or `{}` in `powershell -Command "..."` | Windows CMD / ProcessStartInfo strips or misparses `"` and `|`, causing PowerShell to treat parameters as missing or wait for stdin input lines. | **Use `.ps1` scratch script files** in `<appDataDir>\brain\<conversation-id>\scratch\` executed with `-ExecutionPolicy Bypass -File`, OR use standard `cmd.exe /c` with clean syntax. |
| **Unbounded Output Buffering / Streaming Deadlocks** | Recursive commands scanning millions of files without pagination (`Get-ChildItem -Recurse`) | Output buffer pipe fills up faster than the stream reader, or stdout waits indefinitely on file locks. | Use targeted filters, `-ErrorAction SilentlyContinue`, and avoid unbounded recursive pipe sweeps when targeted path lookups suffice. |
| **Inappropriate `WaitMsBeforeAsync` Configuration** | Setting `WaitMsBeforeAsync: 10000` on commands that naturally take 15 seconds, spawning unnecessary background task handles. | Task is prematurely sent to the background or left with default timeouts. | Calibrate `WaitMsBeforeAsync` appropriately (use synchronous execution up to 10s for quick audits, or explicit script tasks for long operations). |

---

## 2. Mandatory Pre-Flight Checklist Before Running Any Command

Before proposing or executing any CLI command, verify:

- [ ] **Is the command non-interactive?** Does it have any prompt asking `Are you sure (Y/N)?` If yes, pass `--force`, `-Force`, `-y`, or `/q`.
- [ ] **Does the utility require Administrator privileges?** If it requires UAC (like `diskpart` or editing system volumes), **do not run it**.
- [ ] **Does the command contain complex PowerShell pipelines?** If it exceeds 1 pipe or has custom object construction (`[PSCustomObject]`), write it into a `.ps1` script file and execute via `powershell -ExecutionPolicy Bypass -File <script.ps1>`.
- [ ] **Are long-running file deletions handled natively?**
  - For directories: use `cmd.exe /c "rd /s /q <path>"` (substantially faster than PowerShell `Remove-Item -Recurse`).
  - For file batches: use `cmd.exe /c "del /f /q <path>\*"` (bypasses PowerShell pipeline memory allocation).

---

## 3. Safe Command Substitution Patterns

### A. Disk & Partition Actions
- ❌ **Forbidden**: `diskpart /s script.txt` (Hangs without elevation and blocks on subcommands).
- ✅ **Safe Alternative**:
  - Query volume info: `powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Volume -DriveLetter <Letter>"`
  - Query disk sizes: `Get-PSDrive <Letter>` or `Get-CimInstance Win32_LogicalDisk`

### B. WSL Management
- ❌ **Forbidden**: `wsl --manage <distro> --set-sparse true` (Aborts with `E_INVALIDARG` or requires user prompt).
- ✅ **Safe Alternative**: Run `wsl -l -v` or `wsl --shutdown` (safe, non-blocking).

### C. Large Directory & Cache Removal
- ❌ **Inefficient / Prone to Hangs**: `Remove-Item -Path $dir -Recurse -Force` across 200,000 files in a single PowerShell pipeline (runs into file-lock timeouts and high memory usage).
- ✅ **Safe Alternative**:
  ```cmd
  cmd.exe /c "rd /s /q <DirectoryPath>"
  ```
  Or for specific file types:
  ```cmd
  cmd.exe /c "del /f /q <DirectoryPath>\*.tmp"
  ```

### D. Package Cache Management
- For `uv`:
  ```cmd
  uv cache clean
  ```
- For `npm`:
  ```cmd
  npm cache clean --force
  ```
- For `pip`:
  ```powershell
  python -m pip cache purge
  ```

---

## 4. Active Background Task Watchdog & Recovery Protocol

If a task was launched into the background:

1. **Verify Progress Proactively**:
   - Check `manage_task` with `Action: 'status'` after launching.
   - Inspect the task log file (`logUri`) to verify active disk write or CPU activity.

2. **Detect Deadlocks Early**:
   - If a background task emits zero stdout/stderr for **> 60 seconds** on a command that shouldn't take that long (e.g., `diskpart`, interactive utilities), inspect the process via:
     ```powershell
     Get-Process -Name <process> -ErrorAction SilentlyContinue
     ```
   - If CPU usage is `0.0` or process is waiting on unattached stdin, **immediately terminate** via `manage_task` with `Action: 'kill'`.

3. **Never Chain Commands Behind a Suspected Hang**:
   - Always verify or terminate a blocked task before initiating subsequent file operations on the same partition or directory.
