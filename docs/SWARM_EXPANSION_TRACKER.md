# Fleet-Orchestrator Swarm Expansion Tracker

> **Living Architectural Tracker & Ground Truth State**  
> *Initialized: 2026-10-16*  
> *Primary Specification:* [`docs/RFC-001-tri-modal-swarm-mesh.md`](RFC-001-tri-modal-swarm-mesh.md) | [GitHub Issue #26](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/26)  
> *Invariant:* `INV-EXT-STATE` — System state lives in the repository, immune to chat context truncation.

---

## 1. Executive Summary & Fleet Capacity Ledger

This tracker records the phase-by-phase evolution of Fleet-Orchestrator into a **31-node homogeneous tri-modal swarm mesh** operating in symbiosis with the **Azmuth Ultimatrix Genomic Engine** and the wider 28-tool ecosystem.

### Current vs. Target Swarm Capacity

| Resource / Modality | Current Situ (Baseline) | Target 31×31 Mesh (RFC-001) | Multiplier / Gain |
|:---|:---|:---|:---|
| **Active Copilot PATs** | 27 accounts (`copilot-w1` ... `copilot-w27`) | 31 accounts (`copilot-w1` ... `copilot-w31`) | **+14.8% accounts** |
| **Pooled Copilot AI Credits** | **5,117 / 5,400 monthly credits** (94.8% intact) | **6,200 monthly credits** | **+800 credits/mo** |
| **Coding Tasks / Month** | ~1,000 – 2,500 tasks | **~2,000 – 3,100 tasks** | **~70 – 100 tasks/day** |
| **Google AI Studio Keys** | 1 unbilled key (single GCP project) | **31 keys** (across 31 independent GCP projects) | **31× keys** |
| **Gemini Burst Rate Limit** | 15 RPM | **465 RPM** (7.7 requests/sec) | **31× burst rate** |
| **Gemini Daily Request Limit** | 1,500 RPD (or 20/day on flash-3.8 free tier) | **46,500 RPD** | **31× to 2,325× daily quota** |
| **Gemini Multi-Model Fallback** | Single model (`gemini-3.8-flash`) | 3 models (`3.8-flash` → `2.5-flash` → `2.5-flash-lite`) | **93 quota buckets** (139.5k req/day) |
| **Antigravity CLI Cortexes** | 1 interactive session | **31 isolated sandboxes** (`~/.agy-workers/worker_N`) | **31 parallel cortexes** |
| **Local Hardware Acceleration** | Intel Core Ultra 7 155H (11 TOPS NPU + Arc iGPU) | Same physical hardware | $0.00 marginal cost |
| **Safe Concurrency Limit** | 4 – 6 active subprocesses (`INV-HW-THROTTLE`) | 4 – 6 active subprocesses (`INV-HW-THROTTLE`) | Thermal/RAM preservation |

---

## 2. Multi-Model & Multi-Provider Cascading Fallback Contract

To eliminate single-provider quota starvation (e.g. Gemini 429 exhaustion), all autonomous solvers, code generators, and workers must adhere to this exact 4-tier cascade:

```
[Incoming Task / Synthesis Request]
                 │
                 ▼
  ┌────────────────────────────────────────────────────────┐
  │ Tier 1: Within-Key Model Cascade (Key K_i)             │
  │   1. gemini-3.8-flash (Primary high-agency model)      │
  │   2. gemini-2.5-flash (Secondary independent bucket)   │
  │   3. gemini-2.5-flash-lite (Tertiary fast-path bucket) │
  └───────────────────────────────┬────────────────────────┘
                 │ (If all 3 models return 429 on Key K_i)
                 ▼
  ┌────────────────────────────────────────────────────────┐
  │ Tier 2: 31-Key GCP Project Rotation                    │
  │   Rotate circular pointer to Key K_{i+1}               │
  │   Record retryDelay cooldown in ledger per key/model   │
  └───────────────────────────────┬────────────────────────┘
                 │ (If all 31 Gemini keys are in active cooldown)
                 ▼
  ┌────────────────────────────────────────────────────────┐
  │ Tier 3: 31-Account Copilot Swarm Mesh (6,200 Credits)   │
  │   CopilotHeadlessAdapter (circular worker rotation)    │
  │   Model fallback: claude-3.7-sonnet → gpt-4o → o3-mini │
  └───────────────────────────────┬────────────────────────┘
                 │ (If offline or zero network reachability)
                 ▼
  ┌────────────────────────────────────────────────────────┐
  │ Tier 4: Local On-Device Zero-Quota Anchor              │
  │   LM Studio / OpenVINO NPU (localhost:1234/v1)         │
  │   Qwen 2.5 0.5B / 3B • Infinite RPM • $0.00 Cost       │
  └────────────────────────────────────────────────────────┘
```

---

## 3. Phased Implementation Roadmap

### Phase 1: Current Situ Muscle Bridge & Quota Defense
*Objective:* Wire the active 27 Copilot accounts (5,117 credits) into Azmuth, eliminate the 429 Gemini rate-limit stall, and throttle mutator thrashing.
- [x] Connect `CopilotHeadlessAdapter` and `tools/credit_ledger.py` into `tools/ultimatrix_autonomous_solver.py`.
- [x] Add Multi-Model Gemini fallback (`gemini-3.8-flash` → `gemini-2.5-flash` → `gemini-2.5-flash-lite`) with cached `circuit_breaker_until` timestamps.
- [x] Refine heuristic keyword matching in `synthesize_python_solution()` to prevent false-positive synthesis on complex tasks (e.g. eliminate naive `"sum" in slug` trap).
- [x] Throttle mutator in `tools/ultimatrix_mutator.py` to `PRIMARY` and `ALTERNATIVE` alleles only (max 2 base alleles per gene).
- [x] Clean `"mock-repairable-task"` from `orchestrator-state/ultimatrix_solver_ledger.json` and isolate test fixtures in `tests/test_ultimatrix_phase8.py`.
- [x] Run full test suite (`pytest tests/ -k "azmuth or ultimatrix" -v`).
- [x] Sync via `.\sync.bat` and verify remote CI.

### Phase 2: Fleet Configuration Expansion (27 → 31 Accounts)
*Objective:* Formally expand configuration, ledgers, and sandboxes from 27 to 31 nodes ([Issue #26](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/26) / RFC-001).
- [x] Add `COPILOT_ACCOUNT_28` through `COPILOT_ACCOUNT_31` to `.env.fleet.copilot`, `.env.fleet`, `.env.fleet.copilot.example`, and `.env.fleet.example`.
- [x] Expand `.env.fleet.gemini` and `.env.fleet.gemini.example` to support `GEMINI_API_KEY_1` through `GEMINI_API_KEY_32` across independent GCP projects (30 healthy project keys active).
- [x] Provision 31 isolated `~/.agy-workers/worker_N` profile sandboxes in `.env.fleet.agy` and `.env.fleet.agy.example`.
- [x] Update `tools/fleet_env.py` and `tools/copilot_fleet.py` to discover and validate all 31 accounts.
- [x] Audit pool status via `python tools/unified_fleet_cli.py status` (verified 6,200 pooled credit capacity across 31 accounts and 450 RPM / 45,000 RPD across 30 Gemini keys).



### Phase 3: Autonomous CPM DAG Planner & SKU Expansion Engine
*Objective:* Implement dependency-ordered Critical Path Method (CPM) DAG scheduling ([Issues #28](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/28)–[#31](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/31), [#34](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/34)).
- [ ] Implement `tools/dag_planner.py` supporting linear, fan-out, and diamond topologies.
- [ ] Integrate `DeterministicCPMSolver` to calculate Earliest/Latest start times, Total Float, and the Critical Path.
- [ ] Enforce dependency gating and cascade-blocking in `tools/copilot_queue_worker.py`.
- [ ] Add `submit-dag`, `dag-status`, and `dag-cancel` subcommands to `fleet.bat`.
- [ ] Create unit test suite `tests/test_dag_planner.py`.

### Phase 4: Autonomous GitHub Sentinel Loop
*Objective:* Enable the fleet to autonomously pick up GitHub issues and submit verified PRs ([Issues #35](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/35)–[#39](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/39)).
- [ ] Implement `tools/github_issue_sentinel.py` to poll issues labeled `sentinel-ready` via `gh issue list`.
- [ ] Route issue intent through `tools/fast_intent_router.py` to determine tier, timeout floor, and adapter.
- [ ] Dispatch execution inside isolated `.worktrees/task_gh_<repo>_<number>`.
- [ ] Enforce local test gates (`pytest` + `ruff`).
- [ ] Dispatch automated PRs (`sync.bat -PR` / `gh pr create`) with `Closes #<id>` and test manifests.
- [ ] Add unit test suite `tests/test_github_issue_sentinel.py`.

### Phase 5: Unified Desktop Control Center GUI v2.1
*Objective:* Real-time high-DPI desktop visualization of the entire swarm.
- [ ] Add Tab 6: `🧬 Azmuth & Ultimatrix` to `tools/fleet_gui.py` (daemon status, gear switcher, codon stream genome browser, DNA splicer).
- [ ] Enhance Tab 2 (`Pipeline Tasks`) with interactive CPM DAG visualization badges.

---

## 4. Execution History & Provenance Log

| Phase | Commit SHA | CI Run ID | CI Verdict | Verified Deliverables | Date |
|:---|:---|:---|:---|:---|:---|
| **Phase 7** | `0bfe208` | `38902470555` | **SUCCESS** (9/9 jobs) | Closed-Loop Evolutionary Scheduler, Anti-Starvation Filter, Auto-Solution Sequencing | 2026-10-16 |
| **Phase 8** | `cd9e4a0` | `38903713511` | **SUCCESS** (9/9 jobs) | Spliced-DNA Fallback Synthesis, Self-Healing Repair, Empirical Judge Sandbox | 2026-10-16 |
| **Phase 1 (Exp)** | `1dfc4a2` | `38918736819` | **SUCCESS** (9/9 jobs) | Copilot Muscle Bridge, Multi-Model Gemini Fallback, Mutator Throttle | 2026-10-16 |
