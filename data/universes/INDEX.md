# Azmuth Cortical Cartridge Index (`CorticalCartridgeV1`)

This directory houses the 6 modular **Cortical Cartridge Lobes** (`U0` through `U5`) powering the Azmuth Neuromorphic, Temporal-Triad & 6-Universe Foresight Engine.

Each universe is defined by a strictly typed schema containing:
1. `metadata`: Universe identifier, name, version, and natural frequency timescale $\tau_{\text{universe}}$.
2. `nodes`: Graph vertices representing entities, models, queues, hardware parameters, or market tickers, each parameterized with homeostatic baselines ($\mu, \sigma$).
3. `edges`: Directed, weighted, typed causal or structural pathways with latency $\Delta t$ and decay $\lambda$.
4. `macro_engrams`: Historical shock templates and crisis signatures for singularity-free hybrid matching.

---

## 🌌 Universe Directory

| Cartridge ID | Universe Name | Focus Domain | Key Nodes & Invariants |
| :--- | :--- | :--- | :--- |
| **`u0_ecosystem_mesh`** | Ecosystem & Swarm Mesh | 28 internal ecosystem modules, skill execution DAGs, worker quotas | `FLEET_COPILOT_POOL`, `GEMINI_ROUTER`, `BRAINSTORM_CORE`, `NOTEBOOKLM_SUPER_NLM`, `NEUROMORPHIC_DAEMON` |
| **`u1_research_arbitrage`** | Research & Publication Arbitrage | Academic lab pipelines, SOTA model benchmarks, publication timelines | `SPARK_TINYML_ACCURACY`, `BIAS_APERTURE_AUDIT`, `FUSEMACHINES_FELLOWSHIP`, `BRL_LAB_ARXIV`, `SOTA_DIFFUSION_GAP` |
| **`u2_ai_compute_frontier`** | AI Compute Frontier & Silicon | Local hardware constraints (16GB RAM, Arc iGPU, NPU), Colab GPU runtimes, SLM latency budgets | `LOCAL_16GB_RAM_PRESSURE`, `INTEL_ARC_IGPU_VRAM`, `NPU_TENSOR_LOAD`, `COLAB_T4_L4_GPU_FLEET`, `UNSLOTH_SLM_VRAM_FOOTPRINT` |
| **`u3_career_opportunity_alpha`** | Career & Opportunity Alpha | Kathmandu University faculty networks, AI fellowship admissions, international grants, core maintainer status | `KU_ACADEMIC_FACULTY_SPONSOR`, `FUSEMACHINES_AI_FELLOWSHIP`, `KAUST_AI_RESEARCH_GRANT`, `COMMUNITY_MAINTAINER_AUTHORITY`, `INDUSTRY_AI_RESIDENCY` |
| **`u4_macro_capital_markets`** | Macro Capital & Silicon Geopolitics | Global semiconductor supply chain (TSMC, ASML, NVDA), central banks, crude energy, Nepal NEPSE liquidity | `ASML_LITHOGRAPHY`, `TSMC_ADVANCED_FOUNDRY`, `NVDA_GPU_DEMAND`, `FED_FUNDS_RATE`, `BRENT_CRUDE_BARREL`, `NEPSE_INDEX` |
| **`u5_hardware_physics_bom`** | Embedded Hardware & Physics BOM | Edge AI microcontrollers (ESP32-S3), IMU sensor calibration, TFLite Micro tensor arenas, battery discharge profiles | `ESP32_S3_PSRAM_8MB`, `MPU6050_IMU_DRIFT`, `TFLITE_MICRO_TENSOR_ARENA`, `LIPO_3S_DISCHARGE_CURVE`, `BLE_TELEMETRY_DUTY_CYCLE` |

---

## 🛠️ CLI Operations & Inspection

The master CLI tool `tools/azmuth_macro_graph.py` provides high-level commands to mount, simulate, and project across any universe:

### 1. Universal Cartridge Mount & 3rd-Person Macro View (3PV)
```bash
python tools/azmuth_macro_graph.py --mount u0_ecosystem_mesh --view 3pv
python tools/azmuth_macro_graph.py --mount u4_macro_capital_markets --view 3pv
```

### 2. First-Person Objective View (FPV)
Compute directed upstream risk propagation and downstream opportunities toward a specific node:
```bash
python tools/azmuth_macro_graph.py --mount u1_research_arbitrage --view fpv --target SPARK_TINYML_ACCURACY
python tools/azmuth_macro_graph.py --mount u4_macro_capital_markets --view fpv --target NEPSE_INDEX
```

### 3. Shock Propagation & Leaky Integrate-and-Fire (LIF) Simulation
Inject synthetic or empirical shocks and watch spiking waves ripple across the topological network:
```bash
# Inject -40% shock into ASML lithography equipment
python tools/azmuth_macro_graph.py --mount u4_macro_capital_markets --shock ASML_LITHOGRAPHY --magnitude -0.40

# Inject -50% shock into Local RAM capacity
python tools/azmuth_macro_graph.py --mount u2_ai_compute_frontier --shock LOCAL_16GB_RAM_PRESSURE --magnitude -0.50
```

### 4. Graph Centrality & Chokepoint Identification
Calculate topological betweenness centrality to isolate systemic single-points-of-failure:
```bash
python tools/azmuth_macro_graph.py --mount u4_macro_capital_markets --chokepoints
python tools/azmuth_macro_graph.py --mount u0_ecosystem_mesh --chokepoints
```

### 5. Multi-Universe Foresight Scan & Brief Synthesis
Scan all 6 universe lobes in parallel, evaluate unpriced ripples, and compile `orchestrator-state/macro_foresight_brief.json` and `.md`:
```bash
python tools/azmuth_macro_graph.py --foresight
```
