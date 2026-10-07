# Fleet-Orchestrator: Autonomous Multi-Model Agent Fleet & Swarm Engine

A production-grade, distributed multi-agent task execution and coordination platform designed to pool heterogeneous AI compute models (GitHub Copilot CLI, Claude Desktop CDP, Google Gemini Free, Groq, and Ollama) into a unified, high-concurrency autonomous swarm.

---

## 1. Architectural Highlights

- **Multi-Provider Adapter Mesh (`client/adapters/`)**:
  - **GitHub Copilot CLI (`CopilotCLIAdapter`)**: Drives local `copilot.exe` in non-interactive `--autopilot` mode with sub-process environment isolation (`COPILOT_GITHUB_TOKEN`, `COPILOT_HOME`), workspace sandboxing (`--worktree`), and per-task credit budgeting (`--max-ai-credits`).
  - **GitHub Copilot Headless (`CopilotHeadlessAdapter`)**: Pure asynchronous HTTP client with an OpenAI-compatible autonomous tool-calling loop (`read_file`, `write_file`, `run_command`) executing at **$\sim 10\text{--}15\text{ MB RAM}$** per worker.
  - **Claude Desktop CDP Bridge (`ClaudeDesktopProxy`)**: Heavy reasoning, architecture drafting, and adversarial QA review tier running against local Chromium CDP debug ports.
  - **Gemini Free-Tier (`GeminiFreeAdapter`)**: High-rate API execution for large-context summarization and extraction.
  - **Groq & Local Ollama**: Zero-latency local/cloud open weights for lightweight formatting and classification.

- **Multi-Account Credit Pooling ($N \times 200$)**:
  - Dynamically pools $N$ independent GitHub accounts into a shared quota pool (e.g. 5 accounts = 1,000 monthly credits).
  - Eliminates browser 2FA challenges and Windows Credential Manager collisions via subprocess environment token injection.

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
│   └── adapters/                  # Provider adapters
│       ├── base_adapter.py        # Abstract worker interface
│       ├── copilot_cli_adapter.py # GitHub Copilot CLI subprocess adapter
│       ├── copilot_headless.py    # Asynchronous Copilot REST + tool loop
│       ├── claude_desktop_proxy.py# Claude Desktop UI/CDP bridge
│       ├── gemini_free_adapter.py # Gemini Free-tier adapter
│       ├── groq_adapter.py        # Groq LLM adapter
│       └── ollama_local_adapter.py# Ollama local models adapter
│
├── sku-templates/                 # Declarative DAG job expansion templates
├── orchestrator-state/            # Schemas, worker roles, and live status
├── worker-prompts/                # Specialized role system prompts (lead, scout, coder, qa)
├── tools/                         # CLI controllers and dashboards
│   ├── copilot_fleet.py           # Multi-account Copilot fleet controller
│   ├── fleet_cli.py               # General fleet inspection and management CLI
│   └── fleet_gui.py               # Tkinter desktop control panel
│
├── scripts/                       # Hybrid benchmarks & orchestration tests
│   └── test_hybrid_copilot_fleet.py # Multi-tier concurrent pipeline benchmark
│
├── tests/                         # Full automated pytest test suite (110+ tests)
├── .env.fleet.example             # Multi-account token template (safe example)
├── launch_copilot_fleet.bat       # One-click Windows fleet launcher
├── sync.ps1                       # Ecosystem synchronization with pre-commit gates
├── sync.bat                       # Zero-friction execution wrapper
├── AGENTS.md                      # Operational rules & epistemic invariants
├── GEMINI.md                      # Antigravity IDE agent pointer
└── README.md                      # Repository documentation
```

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
*Current Fleet: 27 registered accounts, 24 verified active & passing canary (4,800 AI credits / month).*

### Step 3: Run Concurrent Canary Ping
```powershell
python tools/copilot_fleet.py canary
```
*Runs concurrent non-interactive headless smoke tasks across all active accounts with zero credit overruns.*

### Step 4: Run End-to-End Task Dispatch Smoke Test
```powershell
python tools/e2e_dispatch_smoke.py
```
*Validates the full autonomous task lifecycle (REGISTER -> CLAIM LEASE -> EXECUTE -> CHECKPOINT -> DONE).*

---

## 4. Verification & Testing

Fleet-Orchestrator enforces continuous deterministic verification:
```powershell
pytest tests/test_copilot_cli_adapter.py -v
pytest tests/test_copilot_headless.py -v
pytest tests/
```

---

## 5. License

MIT License. Developed by Aaradhya Dev Tamrakar.
