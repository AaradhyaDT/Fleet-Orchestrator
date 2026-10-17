# RFC-008: The Azmuth Gene Lab & Distributed Codon Stream Architecture

**Status:** APPROVED / PHASE 2 GRADUATED (162/100 GENES) — PHASE 3 ACTIVE  
**Author:** Aaradhya Dev Tamrakar  
**Date:** 2026-10-16 (Updated: 2026-10-17)  
**Repositories:**
- Engine Machinery: `F:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator`
- Genetic Vault (Codon Stream): `F:\Aaradhya-Dev-Tamrakar\Competitive-Programming`

---

## 1. Executive Summary & Vision

Traditional algorithms and systems documentation repositories suffer from monolithic stagnation: thousands of redundant files where each file duplicates boilerplate, and none can adapt to hybrid real-world production constraints.

The **Azmuth Gene Lab** re-architects algorithmic knowledge into a **Genomic Code Architecture (The Codon Stream)**:
1. **Genes & Competing Alleles**: Computational tasks are broken down into composable, typed **Genes** (e.g. `GRAPH_STORAGE`, `CUBIC_TRANSITIVE_CLOSURE`, `RANGE_QUERY`).
2. **Allele Evolution & Optimization**: For each gene, multiple implementations (**Alleles**) compete based on hardware memory layouts, asymptotic efficiency, and empirical cycle counts.
3. **The $O(N^3)$ Barrier**: Crossing the cubic complexity barrier is modeled as **Allele Substitution**—swapping a recessive naive loop for a dominant SIMD bit-parallel, cache-blocked, or mathematical reduction allele.
4. **Autonomous Proof-of-Fitness Mining**: Idle CPU cycles across devices are harvested in auto mode (akin to computational mining) to sequence code, race alleles, and discover new edge-case failure modes without human friction.

---

## 2. Multi-Tiered Genomic Hierarchy

The Codon Stream is partitioned into six distinct structural tiers spanning from physical silicon to real-world super-domains:

```text
The Codon Stream (codon_stream/)
├── tier0_hardware/       # Base Pairs: Cache lines (64B), SIMD/AVX2, branchless bitwise intrinsics
├── tier1_language/       # Core Semantics: C++20 (RAII, constexpr, custom allocators) | Python (CPython C-extensions)
├── tier2_primitives/     # Workhorse Genes: Static Forward-Star, Segment/Fenwick Trees, SplitMix64
├── tier3_cubic_breakers/ # High-Skill Invariants: O(N³) → O(N² / N log N), Bitset 64x, Knuth/CHT DP, Loop Tiling
├── tier4_symbolic/       # Frontier Frontiers: Fixed-Parameter Tractability (FPT), SMT Invariants, Wolfram/SymPy
└── tier5_super_domain/   # Super-Domain Foresight: Bio-Spiking LIF, Thalamic Normalizer, Gut Avoidance, CBF Inhibitory Safety, Lead-Lag Ripple, Historical Crisis Engrams, Chokepoint Alpha
```

---

## 3. Structural Gene & Allele Schema

Every gene in `codon_stream/` conforms to the canonical JSON schema:

```json
{
  "gene_id": "CUBIC_TRANSITIVE_CLOSURE",
  "tier": 3,
  "category": "dimensional_collapse",
  "description": "Computes reachability for all pairs in directed graphs.",
  "alleles": [
    {
      "allele_id": "bitset_floyd_warshall_64",
      "dominance": "PRIMARY",
      "complexity_time": "O(N^3 / 64)",
      "complexity_space": "O(N^2 / 64)",
      "environmental_triggers": [
        "N <= 5000",
        "dense_graph",
        "c++20"
      ],
      "empirical_fitness": {
        "n_2000_ms": 48.2,
        "ram_kb": 512
      },
      "code_template": "for (int k = 0; k < n; ++k)\n  for (int i = 0; i < n; ++i)\n    if (reach[i].test(k)) reach[i] |= reach[k];"
    },
    {
      "allele_id": "naive_floyd_warshall",
      "dominance": "RECESSIVE",
      "complexity_time": "O(N^3)",
      "complexity_space": "O(N^2)",
      "environmental_triggers": [
        "N <= 400"
      ],
      "empirical_fitness": {
        "n_2000_ms": 7820.0,
        "ram_kb": 16384
      }
    }
  ]
}
```

---

## 4. Hardware Safety & Tactile Control (Azmuth Engine)

All background research, sequencing, and mining are governed by strict hardware guardrails in `Fleet-Orchestrator`:

1. **Tactile System Tray Controller (`tools/azmuth_tray.ps1`)**:
   - **🚀 Turbo Mode**: 45s idle trigger, 30s cooldown, 3-task parallel stream.
   - **⚡ Balanced Mode (Auto-Managed Default)**: 3m idle trigger, 5m cooldown, 1-task stream.
   - **🌱 Whisper Mode**: 5m idle trigger, 30m cooldown, minimal footprint ($<25\text{MB}$).
2. **Automatic RAM Circuit Breaker**:
   - Queries `kernel32!GlobalMemoryStatusEx`.
   - If available RAM drops below **3.0 GB** or load exceeds **80%**, the engine **automatically downshifts from Turbo/Balanced to Whisper Mode** and calls `gc.collect()`.
3. **Instant Preemption**:
   - Subprocesses run under Windows `IDLE_PRIORITY_CLASS` (`0x00000040`).
   - Polls `user32!GetLastInputInfo` with $<250\text{ms}$ backoff on mouse/keyboard activity.

---

## 5. Phased Rollout Governance

To prevent "genetic pollution" and maintain zero-drift reliability across the ecosystem:

* **Phase 1: Genesis Lab (Node 0 — This Machine) [COMPLETED 2026-10-16]**
  - Anchor schemas, build local sequencer (`tools/azmuth_corpus_harvester.py`).
  - Sequence initial baseline genes across Tiers 0 to 3 from `Competitive-Programming/platforms/csacademy`.
  - Validate local selection chamber and RAM circuit breakers.
* **Phase 2: Production Maturity Gate (The Promotion Threshold) [GRADUATED 2026-10-17]**
  - Reached **162 / 100 verified core genes** in `codon_stream/` (162% target completion).
  - Integrated 3-Tier Global Language Reference Harvester (`30` canonical modules across Ecosystem, AI Fellowship, and Strategic Runtimes).
  - Compiled and verified test harness (`556` automated unit tests) with zero false-positive verifications.
  - Splicing engine successfully generates verified contest solutions across 23 tasks with 100% sample pass rate.
* **Phase 3: Autonomous Polyglot Synthesis & Galvanic Mesh [ACTIVE — Target: 250 Genes]**
  - Implement dual C++20/Python cross-synthesis arena racing head-to-head in `ultimatrix_verifier.py`.
  - Deploy lightweight headless worker daemons across secondary laptops/devices to pull idle work units, run allele tournaments, and submit signed **Proof-of-Fitness** PRs back to the mothership.

---

## 6. Bird's-Eye Relational Intelligence & 6-Universe Swappable Cartridges

Crossing bounds from algorithmic coding into real-world master planning ([Issue #181](https://github.com/AaradhyaDT/Fleet-Orchestrator/issues/181)), the Azmuth engine mounts domain knowledge as **Cortical Cartridges (`runtimes/universes/u0..u5`)** over a lean mathematical core (`tools/azmuth_macro_graph.py`):

1. **The 6 Swappable Cortical Cartridges (0 MB RAM / 0% CPU on disk when unmounted)**:
   - `U0`: Ecosystem Autonomic Mesh (28 modules, skills, MCPs, worker pool homeostasis)
   - `U1`: Research & Publication Arbitrage (`SPARK`, `BiasAperture`, `BRL`, `Nepali-OCR`, SOTA gaps)
   - `U2`: AI Compute Frontier (16GB RAM, Arc iGPU, NPU, Colab, SLMs/LLMs, RPM/RPD ceilings)
   - `U3`: Career Opportunity Alpha (Labs, fellowships, grants, 2nd-hop maintainer bottlenecks)
   - `U4`: Macro Capital Markets (24-node global chip/macro chain + Nepal/NEPSE liquidity chain + 6 Crisis Engrams)
   - `U5`: Hardware Physics & BOM (Sensors, ESP32-S3, Jetson, RF/DSP/Shannon limits)
2. **8 Bio-Mimetic Optimization Laws ($20\text{-Watt}$ Reference)**:
   - Vasodilation (1 mounted lobe in RAM at $<15\text{MB}$), Dual-Perspective (`--view 3pv` vs. `--view fpv`), Thalamic Habituation ($|Z| < 0.8\sigma \to 0$ spikes), Top-$k$ Pre-Contact Gut Avoidance (`PRE_CONTACT_AVOID`), Control Barrier Function (CBF) Mid-Flight Braking (`CATCH_AND_ARREST`), and Near-Miss Core Memory Stamping (`core_memory_engrams.json`).
3. **The 3-Stream Live Sensory Poller (`tools/azmuth_market_sensor.py`)**:
   - Stream 1: Zero-key public Yahoo Finance / FRED / Stooq + local telemetry
   - Stream 2: RSS / event keyword scanner
   - Stream 3: Sub-10ms deterministic delta caching in `orchestrator-state/macro_sensor_cache.json`.

