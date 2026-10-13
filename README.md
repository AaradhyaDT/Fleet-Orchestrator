# Fleet-Orchestrator: Autonomous Multi-Model Agent Fleet & Swarm Engine

A production-grade, distributed multi-agent task execution and coordination platform designed to pool heterogeneous AI compute models (GitHub Copilot CLI, Claude Desktop CDP, Google Gemini Free, Groq, and Ollama) into a unified, high-concurrency autonomous swarm.

---

## 1. Architectural Highlights

CLI account enrollment, isolated Codex/OpenCode pools, AGY limitations, and Windows diagnostics: [CLI account pools](docs/CLI_ACCOUNT_POOLS.md).

- **Multi-Provider Adapter Mesh (`client/adapters/`)**:
  - **GitHub Copilot CLI (`CopilotCLIAdapter`)**: Drives local `copilot.exe` in non-interactive `--autopilot` mode with sub-process environment isolation (`COPILOT_GITHUB_TOKEN`, `COPILOT_HOME`), workspace sandboxing (`--worktree`), and per-task credit budgeting (`--max-ai-credits`).
  - **GitHub Copilot Headless (`CopilotHeadlessAdapter`)**: Pure asynchronous HTTP client with an OpenAI-compatible autonomous tool-calling loop (`read_file`, `write_file`, `run_command`) executing at **$\sim 10\text{--}15\text{ MB RAM}$** per worker.
  - **Claude Desktop CDP Bridge (`ClaudeDesktopProxy`)**: Heavy reasoning, architecture drafting, and adversarial QA review tier running against local Chromium CDP debug ports.
  - **Gemini Free-Tier (`GeminiFreeAdapter`)**: High-rate API execution for large-context summarization and extraction.
  - **Groq, LM Studio Local & Ollama**: Zero-latency local/cloud open weights for lightweight formatting, routing, extraction, and offline code generation. Local inference runs primarily on LM Studio (`localhost:1234/v1`) using Intel Arc iGPU / Vulkan acceleration.

- **Multi-Account Credit Pooling ($N \times 200$) & Persistent Circular Round-Robin**:
  - Dynamically pools $N$ independent worker profiles into a shared execution mesh (e.g. 27 worker accounts = 5,400 monthly credits).
  - *Governance & Terms-Compliance Invariant*: Production deployments must use authorized organizational machine accounts, dedicated enterprise service principals, or documented provider API keys. Sharing personal consumer tokens to circumvent plan rate limits is prohibited by terms of service.
  - Eliminates browser 2FA challenges and Windows Credential Manager collisions via subprocess environment token injection.
  - Enforces persistent cross-process circular round-robin rotation (`w1 → w2 → ... → w27 → w1`) backed by atomic OS file locks (`FileLock`), preventing single-worker credit concentration across CLI commands.

- **FastAPI Coordination Backend (`server/`)**:
  - SQLite WAL (Write-Ahead Logging) database with cryptographic atomic lease tokens (`claim_token`) preventing task collisions.
  - Quota-aware scheduler with stage affinity bonuses (`+0.20` for code/draft/refactor on Copilot CLI).
  - Heartbeat watchdog and automatic lease revocation for ungracefully terminated workers.
  - Hosted Streamable HTTP/SSE Remote MCP server (23 tools) for Antigravity and external agent orchestration.

- **Declarative SKU Pipeline DAGs (`sku-templates/`)**:
  - Expands multi-step batch jobs into dependency-ordered Directed Acyclic Graphs with automated handoffs, validation gates, and checkpoint persistence.

---

## 2. Directory Layout

```
Fleet-Orchestrator/
├── server/                        # FastAPI coordination backend & MCP remote
│   ├── main.py                    # Application entrypoint & background lifecycle
│   ├── mcp_remote.py              # Hosted Remote MCP Server (23 tools)
│   ├── requirements.txt           # Backend dependencies
│   ├── Dockerfile                 # Container packaging definition
│   ├── docker-compose.yml         # Container stack
│   ├── api/                       # REST routes (jobs, tasks, workers, live status)
│   ├── core/                      # Engine core (scheduler, watchdog, db, models)
│   └── data/                      # Local SQLite WAL storage (.gitkeep)
│
├── client/                        # Autonomous worker daemons & adapter mesh
│   ├── worker_daemon.py           # Polling daemon: registers worker, claims tasks
│   ├── fleet_supervisor.py        # Supervises concurrent worker fleet pools
│   ├── local_llm.py               # Lightweight stdlib client for LM Studio / local LLMs
│   └── adapters/                  # Provider adapters
│       ├── base_adapter.py        # Abstract worker interface
│       ├── agy_adapter.py         # Google Antigravity headless CLI adapter
│       ├── codex_cli_adapter.py   # OpenAI Codex exec JSONL adapter
│       ├── opencode_cli_adapter.py# OpenCode run JSON-event adapter
│       ├── copilot_cli_adapter.py # GitHub Copilot CLI subprocess adapter
│       ├── copilot_headless.py    # Asynchronous Copilot REST + tool loop
│       ├── claude_desktop_proxy.py# Claude Desktop UI/CDP bridge
│       ├── gemini_api_adapter.py  # Modern google-genai v2.25.0 adapter (Gemini 3.8 Flash)
│       ├── gemini_free_adapter.py # Backward-compatible Gemini adapter
│       ├── groq_adapter.py        # Groq LLM adapter
│       ├── lmstudio_local_adapter.py# LM Studio local models adapter (fleet-master-3b/7b)
│       └── ollama_local_adapter.py# Ollama local models adapter
│
├── .agents/skills/fleet-orchestrator/ # Specialized Antigravity skill for swarm control
├── sku-templates/                 # Declarative DAG job expansion templates (including iv_ii_course_study_pack.json)
├── orchestrator-state/            # Schemas, worker roles, and live status
├── worker-prompts/                # Specialized role system prompts (lead, scout, coder, qa)
├── tools/                         # CLI controllers and dashboards
│   ├── models.ps1 / models.bat    # Local model lifecycle manager (status, up, heavy, down, bench)
│   ├── bench_local_router.py      # Quantitative local router benchmark
│   ├── ci_secret_scanner.py       # Standalone secret leakage audit tool
│   ├── ci_self_healing_runner.py  # Self-healing test runner with flaky retries
│   ├── credit_ledger.py           # Leaf credit ledger engine with OS locking & session harvesting
│   ├── fleet_commander.py         # Context-firebreak batch orchestrator (<=300 word manifest)
│   ├── copilot_fleet.py           # Multi-account Copilot fleet controller (status, canary, reconcile, dashboard)
│   ├── fast_intent_router.py      # Sub-50ms local intent router with LM Studio integration & fallback
│   ├── fleet_cli.py               # General fleet inspection and management CLI
│   └── fleet_gui.py               # Modern Fleet-Orchestrator Control Center v2.0 (Tkinter High-DPI GUI)
│
├── .github/workflows/             # GitHub Actions CI/CD workflows
│   ├── ci.yml                     # Dynamic matrix CI/CD & container verification
│   ├── self-healing-watchdog.yml  # Autonomous scheduled health sentinel
│   └── sync-drive.yml             # Continuous Google Drive & NotebookLM documentation sync
│
├── scripts/                       # Hybrid benchmarks & orchestration tests
│   ├── dispatch_iv_ii_tasks.py    # Autonomous task dispatcher for IV-II study packs
│   ├── sync_drive.py              # Zero-dependency Google Drive doc sync engine
│   ├── upload_large_model_to_drive.py # Resumable chunked upload for binary ML models
│   └── test_hybrid_copilot_fleet.py # Multi-tier concurrent pipeline benchmark
│
├── tests/                         # Full automated pytest test suite (332 tests across 55 suites)
├── requirements.txt               # Unified project dependencies
├── requirements-dev.txt           # CI/CD and linting dependencies
├── ruff.toml                      # Linter configuration
├── .env.fleet.example             # Multi-account token template (safe example)
├── drive-manifest.json            # Google Drive & NotebookLM live sync manifest
├── launch_copilot_fleet.bat       # One-click Windows fleet launcher
├── launch_fleet_gui.bat           # Direct one-click launcher for Fleet Control Center GUI v2.0
├── sync.ps1                       # Ecosystem synchronization with pre-commit gates & selective CI
├── sync.bat                       # Zero-friction execution wrapper (-SkipCI / -NoCI)
├── AGENTS.md                      # Operational rules & epistemic invariants
├── GEMINI.md                      # Antigravity IDE agent pointer
└── README.md                      # Repository documentation
```

---

## 2.1 Selective Synchronization & CI/CD Controls

To guarantee that day-to-day work (updating task queues, logging scratchpads, syncing memory, writing docs) is completely friction-free without triggering expensive CI builds:

- **Strict Code Path Filtering (`.github/workflows/ci.yml`)**:
  GitHub Actions CI only executes when files in `client/`, `server/`, `tools/`, or `tests/` are modified. Operational state (`orchestrator-state/`), logs, and documentation (`*.md`) never trigger CI runs.
- **Selective CI Bypass (`-SkipCI` / `-NoCI`)**:
  ```powershell
  .\sync.bat -SkipCI                        # Rapid sync bypassing remote CI
  .\sync.bat -m "feat(wip): draft" -NoCI    # Custom commit with [skip ci]
  ```
- **Automated Non-Code Detection**:
  `sync.ps1` automatically detects when staged changes are strictly non-code and appends `[skip ci]` to the commit message.

---

## 3. Quick Start: Copilot Multi-Account Fleet

### Step 1: The 9-Step Account Activation Playbook
To register and activate any GitHub account in the fleet:
1. Sign out of all GitHub accounts in the browser.
2. Sign in to the target GitHub account.
3. Navigate to: `https://github.com/settings/copilot/features`.
4. Click **Start using Copilot Free** (enables Copilot entitlement on GitHub's API gateway).
5. Navigate to: `https://github.com/settings/personal-access-tokens/new`.
6. Select Token Name: `Fleet-Orchestrator` | Expiration: Custom or No expiration.
7. Under **Permissions**, switch to the **Account** tab (leave Repository permissions at *None*).
8. Under **Account permissions**, select:
   - **`Copilot Requests`**: `Read and write`
   - *(Optional)* `Copilot Chat`, `Copilot Editor Context`
9. Click **Generate token** and paste the token string into `.env.fleet`.

### Step 2: Check Fleet Status
```powershell
python tools/copilot_fleet.py status
```
*Current Fleet: 27 registered accounts, 27 verified active & passing canary (5,400 AI credits / month).*

### Step 3: Run Concurrent Canary Ping
```powershell
python tools/copilot_fleet.py canary
```
*Runs concurrent non-interactive headless smoke tasks across all active accounts, updating the ledger post-run.*

### Step 4: Reconcile Quota Telemetry & View Live Dashboard
```powershell
python tools/copilot_fleet.py reconcile   # Harvests authentic sessions into per-worker sidecars (~26.92 credits)
python tools/copilot_fleet.py dashboard   # Real-time quota burn rate & worker topology
```

### Step 5: Execute Autonomous Tasks with Fleet Commander
```powershell
python tools/fleet_commander.py --specs "Implement feature A" "Refactor module B" --concurrency 2
```
*Enforces Context Firebreak Invariant (`INV-CTX-FIREBREAK`), isolates child logs, checks fleet health ratio $H$, and emits a structured $\le 300$-word manifest.*

### Step 6: Antigravity 2.0 Background Task Handoff
Dispatch one-shot tasks directly from the Antigravity IDE to the fleet, with live milestone streaming in the Background Tasks pane:
```powershell
.\fleet.bat run-task --spec "Add docstrings to tools/credit_ledger.py" --auto-tier balance
.\fleet.bat run-task --spec "Refactor pipeline" --auto-tier intelligence --model gemini-3.8-flash
.\fleet.bat run-task --spec "Quick lint fix" --auto-tier efficiency
.\fleet.bat run-task --spec "Implement validator" --target-repo "F:\Aaradhya-Dev-Tamrakar\SPARK"
.\fleet.bat run-task --spec "Scaffold module" --dry-run
```

**Auto-Tier Timeout Floors**: The SLM router computes dynamic `timeout_ceiling_s` from prompt semantics. The CLI enforces minimum floors per tier to prevent premature kills:

| `--auto-tier` | Timeout Floor | Model Class |
|:---|:---|:---|
| `efficiency` | 120s | GPT-4o-mini / Haiku |
| `balance` | 300s | Default balanced |
| `intelligence` | 600s | Frontier reasoning |

### CLI workers in `active_fleet.json`

The supervisor accepts `Provider` values `agy_cli` (or `agy`), `codex_cli`, and
`opencode_cli`. Set
`Workspace` or `Worktree` to the task's isolated checkout. AGY workers can set
`AgyPath`, `AgyHome`, `PreferredModel`, `Effort`, `Timeout`, and
`DangerouslySkipPermissions`. Codex workers can set `CodexPath`, `CodexHome`,
`PreferredModel`, `ReasoningEffort`, `Timeout`, `Sandbox`, and `ApprovalPolicy`.
Use a separate, pre-authenticated home per concurrent worker (`AgyHome` or
`CodexHome`) when profile isolation is needed. Codex defaults to the
`workspace-write` sandbox; AGY permission skipping is configurable and defaults
to enabled for unattended task execution.

OpenCode workers can set `OpenCodePath` (or `OPENCODE_CLI_BINARY`),
`OpenCodeModel` (`provider/model`),
`OpenCodeVariant`, `Timeout`, and `OpenCodeAuto` (defaults to `true`). OpenCode
uses its own saved provider sign-in; Fleet does not read or copy credentials.
Auto mode approves permission requests unless explicitly denied, so configure
OpenCode permission rules and use an isolated worktree. `--dir` selects the
working directory; it is not an operating-system sandbox. See the
[CLI provider compatibility map](docs/CLI_PROVIDER_COMPATIBILITY.md) for
account fit and other candidates from the supplied research notes.

```json
[
  {
    "Account": "codex-w1",
    "Nickname": "Codex Worker",
    "Role": "writer",
    "Provider": "codex_cli",
    "Workspace": "C:/worktrees/task-001",
    "CodexHome": "C:/fleet/codex/w1",
    "Timeout": 600
  },
  {
    "Account": "agy-w1",
    "Nickname": "AGY Worker",
    "Role": "researcher",
    "Provider": "agy_cli",
    "Workspace": "C:/worktrees/task-002",
    "AgyHome": "C:/fleet/agy/w1",
    "Timeout": 300
  },
  {
    "Account": "opencode-w1",
    "Nickname": "OpenCode Worker",
    "Role": "writer",
    "Provider": "opencode_cli",
    "Workspace": "C:/worktrees/task-003",
    "OpenCodeModel": "openai/gpt-5",
    "OpenCodeVariant": "high",
    "OpenCodeAuto": true,
    "Timeout": 600
  }
]
```

---

## 4. Verification & Testing

Fleet-Orchestrator enforces continuous deterministic verification across 332 test cases (100% pass rate across 55 test suites):
```powershell
pytest tests/test_schema_validation.py -v
pytest tests/test_quota_reconciliation.py -v
pytest tests/test_copilot_cli_adapter.py -v
pytest tests/test_copilot_headless.py -v
pytest tests/
```

---

## 5. Living Documentation & NotebookLM Knowledge Base

Fleet-Orchestrator maintains a continuous, bidirectional documentation pipeline that synchronizes living repository documents into Google Drive and anchors them into a dedicated Google NotebookLM knowledge base:

- **Google Drive Folder**: [`Fleet-Orchestrator`](https://drive.google.com/drive/folders/1wGq53okV7ZaFGSw2fWilEfxL4FEIVeIF) (`1wGq53okV7ZaFGSw2fWilEfxL4FEIVeIF`)
  - Subfolder of parent **Super-NLM** (`1wn330GxoGoMf956xClHxULnsJQWxohxx`) at `My Drive > Share to Aaradhya > Super-NLM`.
  - Automatically converts markdown files (`README.md`, `HANDOFF_FLEET_ORCHESTRATOR.md`, `team-context.md`, `team-memory.md`) into native Google Docs while preserving permanent file IDs.

- **Cloud-Archived GGUF Model Weights & Resumable Downloads**:
  The fine-tuned model weights reside in the Google Drive ecosystem folder and can be pulled locally using `gdown`:

  | Model | Params | Quant | Size | Drive ID | Retrieval Command |
  | :--- | :--- | :--- | :--- | :--- | :--- |
  | **`qwen_intent_router`** | 494M | `Q4_K_M` | 398 MB | [`1bjXQ4K6hTtOevmG6XFih-AVGP0UlXGEK`](https://drive.google.com/file/d/1bjXQ4K6hTtOevmG6XFih-AVGP0UlXGEK/view) | `python -m gdown --continue "https://drive.google.com/uc?id=1bjXQ4K6hTtOevmG6XFih-AVGP0UlXGEK" -O "models/qwen_intent_router_q4_k_m.gguf"` |
  | **`fleet_master_brain_3b`** | 3.1B | `Q4_K_M` | 1.93 GB | [`1kZ7hIAeVM6T0AVDwU1bruWRtIaNMLTzR`](https://drive.google.com/file/d/1kZ7hIAeVM6T0AVDwU1bruWRtIaNMLTzR/view) | `python -m gdown --continue "https://drive.google.com/uc?id=1kZ7hIAeVM6T0AVDwU1bruWRtIaNMLTzR" -O "models/fleet_master_brain_3b_q4km.gguf"` |
  | **`fleet_master_brain_7b`** | 7.6B | `Q4_K_M` | 4.68 GB | [`1XnqLXF6F7-ibDrJdcZzw-XGRneVQ02Rd`](https://drive.google.com/file/d/1XnqLXF6F7-ibDrJdcZzw-XGRneVQ02Rd/view) | `python -m gdown --continue "https://drive.google.com/uc?id=1XnqLXF6F7-ibDrJdcZzw-XGRneVQ02Rd" -O "models/fleet_master_brain_7b_q4km.gguf"` |

- **Dedicated Google NotebookLM**: [`Fleet-Orchestrator`](https://notebook.google.com/notebook/6a37d992-6ceb-4d72-a909-e10e9cca32b6) (`6a37d992-6ceb-4d72-a909-e10e9cca32b6`)
  - Grounded directly on the Google Drive live sources.
  - Enables instant semantic search, multi-turn technical Q&A, and cross-repo synthesis across all Fleet-Orchestrator architecture and operations.
- **Automated Sync Engine (`scripts/sync_drive.py` & `.github/workflows/sync-drive.yml`)**:
  - Triggers on every push to `main` touching repository documentation or manifests.
  - Zero third-party dependencies (pure standard library `urllib` with exponential backoff and jitter).
  - Tracked via [`drive-manifest.json`](drive-manifest.json) using SHA-256 change detection.

---

## 6. License

MIT License. Developed by Aaradhya Dev Tamrakar.
