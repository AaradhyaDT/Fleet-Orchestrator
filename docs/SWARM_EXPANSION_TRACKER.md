# Fleet-Orchestrator Swarm Expansion Tracker

> **Living Architectural Tracker & Ground Truth State**  
> *Initialized: 2026-10-16*  
> *Primary Specification:* [`docs/RFC-001-tri-modal-swarm-mesh.md`](RFC-001-tri-modal-swarm-mesh.md) | [GitHub Issue #26](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/26)  
> *Invariant:* `INV-EXT-STATE` — System state lives in the repository, immune to chat context truncation.

---

## 1. Executive Summary & Fleet Capacity Ledger

This tracker records the phase-by-phase evolution of Fleet-Orchestrator into a **decoupled asymmetric swarm mesh** (31 GitHub Copilot workers $\times$ 30 Google Gemini GCP project keys) operating in symbiosis with the **Azmuth Ultimatrix Genomic Engine** and the wider 28-tool ecosystem.

> [!NOTE]
> **Asymmetric Decoupled Pool Invariant (`INV-ASYM-FLEET`)**: GitHub PAT accounts and Google AI Studio accounts are **intentionally decoupled**. Because GitHub accounts were registered across diverse email providers (not strictly Gmail), the swarm does not enforce a synthetic 1:1 symmetric pairing. Copilot Workers (Code Muscle: 31 accounts) and Gemini Keys (Fast-Path Acceleration: 30 keys) rotate through independent circular allocators.

### Current vs. Target Swarm Capacity

| Resource / Modality | Current Situ (Live Verified) | Target Architecture (`INV-ASYM-FLEET`) | Status |
|:---|:---|:---|:---|
| **Active Copilot PATs** | **31 accounts** (`copilot-w1` ... `copilot-w31`) | **31 accounts** (all available GitHub PATs) | **100% Saturated (Online)** |
| **Pooled Copilot AI Credits** | **5,917.4 / 6,200 monthly credits** (95.4% intact) | **6,200 monthly credits** | **Fully Provisioned** |
| **Coding Tasks / Month** | **~2,000 – 3,100 tasks** | **~2,000 – 3,100 tasks** | **~70 – 100 tasks/day** |
| **Google AI Studio Keys** | **30 keys** (29 in `.env.fleet.gemini` + 1 in OS env across GCP projects) | **30 keys** (all available Gmail/GCP accounts) | **100% Saturated (450 RPM)** |
| **Gemini Burst Rate Limit** | **450 RPM** (7.5 requests/sec) | **450 RPM** (across 30 GCP project buckets) | **High-Throughput Pool** |
| **Gemini Daily Request Limit** | **45,000 RPD** | **45,000 RPD** | **Full Daily Quota** |
| **Gemini Multi-Model Fallback** | 3 models (`3.8-flash` → `2.5-flash` → `2.5-flash-lite`) | 3 models (`3.8-flash` → `2.5-flash` → `2.5-flash-lite`) | **90 quota buckets** |
| **Antigravity CLI Cortexes** | **31 isolated sandboxes** (`~/.agy-workers/worker_N`) | **31 isolated sandboxes** (`~/.agy-workers/worker_N`) | **31 parallel cortexes** |
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



### Phase 2.5: Azmuth 3-Tier Language Reference Harvester & Solver Escalation Ladder
*Objective:* Expand Codon Stream across 3 tiers (Ecosystem, AI Fellowship, Strategic Runtimes), eliminate solver plateau, and guard against in-memory daemon staleness.
- [x] Build and integrate `tools/azmuth_language_harvester.py` materializing 30 canonical language modules over live HTTP into `runtimes/global_references/` and `codon_stream/tier1_language/`.
- [x] Generate master ecosystem language index [`runtimes/global_references/INDEX.md`](../../Competitive-Programming/runtimes/global_references/INDEX.md) and fast zero-token query CLI (`--lookup`, `--tier`, `--list`).
- [x] Eliminate keyword hijacking bug and implement 4-stage Escalation Ladder in `tools/ultimatrix_autonomous_solver.py` (Archetype -> Spliced-DNA LLM -> Context-Grounded Self-Healing -> Sequencing).
- [x] Expand Python 3.12+ DNA translations from 5 to 19 algorithms in `tools/ultimatrix_splicer.py` and add structural mutators in `tools/ultimatrix_mutator.py`.
- [x] Implement dynamic module mtime hot-reload guard in `tools/azmuth_daemon.py` (`check_and_reload_tool_modules`).
- [x] Solve and sample-verify 23 competitive programming tasks (100% sample pass rate), expanding Codon Stream to 162 genes (162% of Phase 2 milestone target).

### Phase 3: Autonomous CPM DAG Planner & SKU Expansion Engine
*Objective:* Implement dependency-ordered Critical Path Method (CPM) DAG scheduling ([Issues #28](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/28)–[#31](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/31), [#34](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/34)).
- [x] Implement `tools/dag_planner.py` supporting linear, fan-out, and diamond topologies.
- [x] Integrate `DeterministicCPMSolver` to calculate Earliest/Latest start times, Total Float, and the Critical Path.
- [x] Enforce dependency gating and cascade-blocking in `tools/copilot_queue_worker.py`.
- [x] Add `submit-dag`, `dag-status`, and `dag-cancel` subcommands to `fleet.bat` and `tools/unified_fleet_cli.py`.
- [x] Create unit test suite `tests/test_dag_planner.py` (6/6 tests passing).

### Phase 4: Autonomous GitHub Sentinel Loop
*Objective:* Enable the fleet to autonomously pick up GitHub issues and submit verified PRs ([Issues #35](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/35)–[#39](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/39)).
- [x] Implement `tools/github_issue_sentinel.py` to poll issues labeled `sentinel-ready` via `gh issue list`.
- [x] Route issue intent through `tools/fast_intent_router.py` to determine tier, timeout floor, and adapter.
- [x] Dispatch execution inside isolated `.worktrees/task_gh_<repo>_<number>`.
- [x] Enforce local test gates (`pytest` + `ruff`).
- [x] Dispatch automated PRs (`sync.bat -PR` / `gh pr create`) with `Closes #<id>` and test manifests.
- [x] Add unit test suite `tests/test_github_issue_sentinel.py` (3/3 tests passing).

### Phase 5: Unified Desktop Control Center GUI v2.1
*Objective:* Real-time high-DPI desktop visualization of the entire swarm.
- [x] Add Tab 6: `🧬 Azmuth & Ultimatrix` to `tools/fleet_gui.py` (daemon status, gear switcher, codon stream genome browser, DNA splicer).
- [x] Enhance Tab 2 (`Pipeline Tasks`) with interactive CPM DAG visualization badges.

### Phase 6: Azmuth Neuromorphic, Temporal-Triad & Multi-Universe Foresight Engine
*Objective:* Build Bird's-Eye Relational Intelligence & Foresight Engine across 6 swappable cortical cartridges (`U0`–`U5`) with 8 bio-mimetic optimization laws ([Issue #181](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/181)).
- [x] Implement `tools/azmuth_macro_graph.py` with `HomeostaticBaselineNormalizer` (Layers 1-3), `ThalamicSignalFilter` (|Z| < 0.8σ), and `PreContactAvoidanceGate` (Top-5 path-attenuated D_gut).
- [x] Implement `InhibitorySafetyCatch` with closed-form Control Barrier Function (CBF) braking scalar alpha_brake (`CATCH_AND_ARREST`).
- [x] Implement `DualPerspectiveRenderer` supporting `--view 3pv` (allocentric bird's-eye map) and `--view fpv --target <NODE>` (egocentric node horizon).
- [x] Implement `ForesightAlphaEngine` with Signals 1-4, Hebbian synaptic consolidation, and plain-English actionable decision lines.
- [x] Sequence 6 canonical Tier-5 Super-Domain genes in `Competitive-Programming/codon_stream/tier5_super_domain/` (`bio_lif_spiking_shock_propagator`, `bio_thalamic_habituation_normalizer`, `bio_inhibitory_reflex_safety_catch`, `quant_lead_lag_unpriced_ripple`, `bio_hebbian_engram_pattern_matcher`, `quant_chokepoint_betweenness_alpha`).
- [x] Materialize Cortical Lobes `U0` (Ecosystem Mesh), `U1` (Research Arbitrage), and `U2` (AI Compute Frontier) in `Competitive-Programming/runtimes/universes/` and `data/universes/`.
- [x] Materialize Cortical Lobes `U3` (Career Alpha), `U4` (24-Node Chip Supply Chain + Nepal Macro Liquidity + 6 Crisis Engrams), and `U5` (Hardware Physics/BOM).
- [x] Build `tools/azmuth_market_sensor.py` (3-stream live poller: Yahoo Finance / FRED / Stooq, RSS scanner, <10ms delta cache).
- [x] Integrate into `tools/azmuth_daemon.py`, GUI Tab 6 radar button, and build `tests/test_azmuth_macro_graph.py` (8/8 tests passing; 573/573 full suite).

### Phase 9: REA Headless Runtime Hardening & SQLite Telemetry Governance
*Objective:* Harden `CopilotCLIAdapter` and worker daemon using findings empirically reverse-engineered from `copilot.EXE` and `@github/copilot` v1.0.65 via REA ([Issue #182](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/182) / [PR #183](https://github.com/AaradhyaDT/Fleet-Orchestrator/pull/183)).
- [x] Injected `--disallow-temp-dir` by default into `build_cli_command()` to prevent background worker pollution of OS temp dirs.
- [x] Injected process isolation flags and runtime environment variables: `COPILOT_ALLOW_ALL=true`, `COPILOT_FORCE_WINDOWS_HIDE=1`, and `COPILOT_DEBUG_SKIP_LAUNCH_CHECKS=1`.
- [x] Built `extract_sqlite_session_telemetry()` directly querying SQLite `session-store.db` (WAL mode) for authentic `assistant_usage_events` metrics (`total_nano_aiu`, `duration_ms`, `cache_read_tokens`, `reasoning_tokens`, `model="gpt-6-luna"`).
- [x] Added calibrated rate-limit categorization (`user_weekly_rate_limited`, `user_model_rate_limited`, `user_global_rate_limited`, `integration_rate_limited`).
- [x] Extended `tools/harvest_copilot_counter_dataset.py` with `harvest_from_session_stores()` to continuously mine usage patterns and failure traces from worker sessions.
- [x] Added 5 unit tests in `tests/test_copilot_cli_adapter.py` and validated full test suite (582/582 passed).

### Phase 10: Autonomous GitHub Sensory Radar & Zero-Friction Headless Subsystem Runtime
*Objective:* Continuous passive GitHub discovery stream across 4 universe channels rotating over 30 PATs, paired with Windows GUI subsystem (`pythonw.exe`) startup isolation eliminating terminal popups on boot.
- [x] Implement `tools/azmuth_github_sensor.py` with 4 sensory streams (`U3` Career/Lab Alpha, `U1/U2` SOTA AI Releases, Codon Stream CP Templates, `U0` Ecosystem Health).
- [x] Circular PAT rotation across 30 discovered Copilot tokens with Thalamic noise filtering (`|Z| < 0.8σ`), persistent caching (`orchestrator-state/github_sensor_cache.json`), and markdown briefing (`orchestrator-state/github_intelligence_brief.md`).
- [x] Wire Subtask 3 sensory scan into `execute_idle_burst()` in `tools/azmuth_daemon.py`.
- [x] Add `🛰️ GitHub Radar` action button to Tab 6 in `tools/fleet_gui.py`.
- [x] Enhance `tools/azmuth_tray.py` with live codon counts and manual radar scan action.
- [x] Solve Windows 11 ConPTY / Windows Terminal boot window bug by migrating `HKCU:\Software\Microsoft\Windows\CurrentVersion\Run\FleetAzmuthTray` and `launch_azmuth_tray.bat` to pure Windows GUI subsystem executable (`pythonw.exe`).
- [x] Create comprehensive unit test suite `tests/test_azmuth_github_sensor.py` (5/5 tests passing; 583/583 full suite).

### Phase 11: Azmuth Neuromorphic Command Center & Phylogenetic Gene Evolution GUI
*Objective:* Industry-grade standalone native desktop application (`tools/azmuth_gui.py`) featuring Win32 High-DPI 60FPS canvas animations, live event-driven telemetry pulses, and switchable interactive graph views:
- [x] **Unified Mission Control Layout**: Top telemetry bar with live Gear selector (`Whisper`/`Balanced`/`Turbo`), 60FPS RAM Oscilloscope Sparkline with tunable Circuit-Breaker line, 30-PAT Token Ring indicator, and live Thalamic $|Z|$-score threshold tuner.
- [x] **View [1] End-to-End Pipeline & PAT Flow**: Interactive 4-stream sensory schematic $\rightarrow$ 30-PAT orbital radar ring $\rightarrow$ Thalamic Sieve ($|Z| \ge \theta\sigma$) $\rightarrow$ U0–U5 Cortical Brain $\rightarrow$ Ultimatrix Gene Sequencer $\rightarrow$ Arena & SSOT Ledgers.
- [x] **View [2] U0–U5 Neuromorphic Causal DAG**: Dynamic 6-cartridge mounting (`U0`..`U5`), homeostatic Z-score node coloring, directed axonal synapses with weights & lag days, First-Person View (FPV) gut avoidance inspection, and interactive **Multi-Hop Shock Wave (+2.0σ)** simulation.
- [x] **View [3] Phylogenetic Gene Evolution Tree & Allele Arena**: Genomic taxonomy explorer across 349+ sequenced genes (Tiers 0–5); renders live branching phylogenetic trees (`Wild-Type` $\rightarrow$ `Mutator Operator Edge` $\rightarrow$ `Daughter Alleles` $\rightarrow$ `Ultimatrix Arena PRIMARY Champion`), with net speedup % and live **"⚡ Mutate & Race Selected Gene"** execution trigger.
- [x] **Interactive Capability & Code Diff Inspector**: Right-hand panel displaying Time & Space Big-O complexity bounds, Environmental Triggers (`N<=2e5`, `avx2`, `codeforces`), Mathematical Invariants, Empirical Fitness (`runtime_ms` & `ram_kb`) comparison bars, and syntax-styled Code Template / Mutation Diff viewer.
- [x] **Zero-Friction Subsystem Desktop Integration**: Added `"Open Azmuth Command Center"` to `tools/azmuth_tray.ps1` and `tools/azmuth_tray.py` (with double-click launch), standalone `launch_azmuth_gui.bat` (via `pythonw.exe`), and `tests/test_azmuth_gui.py` (4/4 tests passed; 587/587 full suite).

---

## 4. Execution History & Provenance Log

| Phase | Commit SHA | CI Run ID | CI Verdict | Verified Deliverables | Date |
|:---|:---|:---|:---|:---|:---|
| **Phase 7** | `0bfe208` | `38902470555` | **SUCCESS** (9/9 jobs) | Closed-Loop Evolutionary Scheduler, Anti-Starvation Filter, Auto-Solution Sequencing | 2026-10-16 |
| **Phase 8** | `cd9e4a0` | `38903713511` | **SUCCESS** (9/9 jobs) | Spliced-DNA Fallback Synthesis, Self-Healing Repair, Empirical Judge Sandbox | 2026-10-16 |
| **Phase 1 (Exp)** | `1dfc4a2` | `38918736819` | **SUCCESS** (9/9 jobs) | Copilot Muscle Bridge, Multi-Model Gemini Fallback, Mutator Throttle | 2026-10-16 |
| **Phase 2.5** | `663010e` | `38920412890` | **PASSED** (16/16 tests) | 3-Tier Language Reference Harvester (30 mods), Solver Escalation, 162 Codon Genes | 2026-10-17 |
| **Phase 3-5** | `52d83bd` | `38923489110` | **PASSED** (25/25 tests) | Tab 6 GUI, CPM DAG Planner (`dag_planner.py`), GitHub Sentinel (`github_issue_sentinel.py`) | 2026-10-17 |
| **Phase 6** | `ed69000` | `39023041427` | **SUCCESS** (9/9 jobs) | Azmuth Neuromorphic Foresight Engine, 6-Universe Cartridges (`U0`–`U5`), 3-Stream Live Sensor, 573/573 Tests ([#181](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/181)) | 2026-10-17 |
| **Phase 9** | `5fa7f78` | `39090074501` | **SUCCESS** (9/9 jobs) | REA Headless Runtime Hardening, SQLite Telemetry Governance, 582/582 Tests ([#182](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/182) / [#183](https://github.com/AaradhyaDT/Fleet-Orchestrator/pull/183)) | 2026-10-18 |
| **Phase 10** | `7258c9f` | `39145628102` | **PASSED** (583/583 tests) | Autonomous GitHub Sensory Radar, 4-Stream PAT Rotation, Thalamic Filter, Silent pythonw.exe Tray Subsystem | 2026-10-18 |
| **Phase 11** | `Pending` | Local | **PASSED** (587/587 tests) | Azmuth Neuromorphic Command Center GUI, 60FPS Canvas, U0-U5 Causal DAG, Phylogenetic Gene Evolution Tree & Capability Inspector | 2026-10-18 |



