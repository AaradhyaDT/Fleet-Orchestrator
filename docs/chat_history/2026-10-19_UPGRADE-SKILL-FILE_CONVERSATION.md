# Upgrade Skill File

- **Source URL:** [https://share.gemini.google/rfebgG4YXfNi](https://share.gemini.google/rfebgG4YXfNi)
- **Archived Date:** 2026-10-19
- **Total Turns:** 6

---

## Turn 1

### User

I want to upgrade my skill.md file, currently it imitates claude's writing. Dissect it and help me out what are the actual elements in it and that I need to improve

### Assistant

Your `SKILL.md` is architected less like a simple style prompt and more like a full **routing and governance engine** for technical writing. While the progressive context-loading architecture is strong, the writing instructions themselves suffer from **domain leakage**: they conflate *how great engineers write prose* with *what Anthropic's product marketing and frontier safety teams publish*. 

MD+ 1

## 1. Structural Dissection: The 5 Elements Currently in Your Skill

Your file currently combines five distinct functional layers: 

MD

1. **Epistemic Identity & Philosophy (Section 1)**: Establishes the "Whiteboard Test" persona, the Trust=Precision+Scope Boundaries+Empirical Proof\text{Trust} = \text{Precision} + \text{Scope Boundaries} + \text{Empirical Proof}Trust=Precision+Scope Boundaries+Empirical Proof formula, and three pillars (Functional Precision, Explicit Scope Boundaries, Empirical Proof & Dog-Fooding). 

   MD
2. **Progressive Context Router (Section 2)**: A 5-tier pre-flight gate (`L1` through `L5`) segmented by word count (100 to 30,000+ words) and surface type. It keeps `L1` as a zero-shot fast-path while lazy-loading specific `references/*.md` files for heavier tiers so you don't burn context tokens on small tasks. 

   MD+ 1
3. **Hard Style Constraints (Section 3)**: Ten "Universal Invariant Writing Rules" covering title grammar, opening thesis structure, banned marketing vocabulary, definition length (10–15 words), scope non-goals, benchmark table conventions, Pareto tradeoff curves, sentence/paragraph length limits, runnable code/JSON diffs, and non-summary conclusions. 

   MD
4. **Execution & Ecosystem Wiring (Sections 4 & 5)**: Hooks into your broader local agent stack—routing between solo execution, `/agent-teams-orchestration` (Scout →\rightarrow→ Reviewer →\rightarrow→ Writer), and `/fleet-orchestrator` (`model_report_pack.json`), alongside hard rules for `compliance-report-harmonizer` (n<30n < 30n<30 suppression), `portfolio-project-manager`, `github-workflow`, `super-nlm`, and `graphify`. 

   MD
5. **Deterministic Linter & Reference Tree (Sections 6 & 7)**: Calls `audit_calm_writing.py` by tier and indexes 9 modular reference files alongside 5 worked tier examples. 

   MD

## 2. What Needs Improvement: 5 Core Flaws Holding the Skill Back

### Flaw 1: "Anthropic Cosplay" Disguised as Universal Rules (Domain Leakage)

Look closely at Rules 6 and 7 in Section 3: 

MD

* Rule 6 mandates *"Pinned Benchmark Grids (Subject, Predecessor, Competitor, Frontier Reference) with explicit qualifiers (`offline subset`, `no tools`, `with tools`, `Xhigh`)"*. 

  MD
* Rule 7 mandates *"effort setting curves (Low/Medium/High/Max)"*. 

  MD
* Rule 9 mandates *"Reports must cite formal system cards"*. 

  MD

Those are not universal writing principles—they are specific artifacts of releasing a frontier LLM API at Anthropic (`thinking`/`effort` parameters and agentic tool-use evals). When you invoke this skill to write an embedded systems thesis, a fairness auditing report, a robotics paper, or a backend architecture doc, the model gets pulled toward **roleplaying an AI lab release** instead of applying rigorous engineering exposition to your actual domain. 

MD

### Flaw 2: Structural Checklists Without Actual Prose Mechanics

Your skill tells the agent *what artifacts to put on the page* (declarative title, 1-sentence thesis, benchmark table, non-goals section, JSON diffs, CLI links), but almost nothing about **how to move from sentence to sentence**. 

MD

* **Missing Causal Transitions**: Good technical writing connects ideas via mechanical cause and effect (*"Because the IMU FIFO buffer saturates at 1 kHz, polling on the main loop drops frames; moving acquisition to an ISR eliminates the contention"*). Without explicit transition rules, LLMs default to disconnected paragraphs stacked under subheadings.
* **Missing Pedagogical Arc (Concrete →\rightarrow→ Abstract)**: A real whiteboard explanation starts with the concrete friction or failure mode *before* introducing the abstraction or architecture. Rule 2 jumps straight to a "1-Sentence Empirical Thesis", which works for release announcements but makes deep engineering blog posts (`L2`) feel dry and top-heavy if not paired with problem-first anchoring. 

  MD
* **Missing Epistemic Calibration**: Section 1 demands "Empirical Proof" and "95% bootstrap confidence intervals", leaving no instructions for how to write about *hypotheses, debugging observations, or architectural hunches*. Calm authority also means knowing when to say *"We suspect this tail latency stems from..."* versus stating a measured fact. 

  MD

### Flaw 3: The "Robotic Staccato" Trap in Rules 4 and 8

Rule 4 locks definitions to *"10 to 15 concrete, mechanical words"* and Rule 8 enforces *"One idea per paragraph (1–4 sentences max). One action per sentence."*

MD

* When an LLM obeys "one action per sentence" and "1–4 sentences max" strictly, it generates **choppy, telegraphic prose** where every sentence has the exact same rhythm (`Subject -> Verb -> Object.`).
* Great technical prose relies on **cadence variance**: pairing a longer multi-clause sentence that maps out a system constraint with a short, punchy declarative sentence that lands the consequence.

### Flaw 4: Level-1 Buzzword Filtering vs. Structural "LLM-isms"

Rule 3 bans obvious marketing adjectives (*revolutionary, game-changing, unleash, supercharge, magic*). That catches cheap promotional copy, but it misses the **syntactic AI habits** that immediately give away LLM-generated technical writing: 

MD

* **Negation-Contrast Framing ("Not X, just Y")**: Ironically, your own prompt uses this exact LLM cliché in Section 1 (*"Not selling. Not performing. Just explaining."*). When an LLM sees that in the system prompt, it mirrors that cadence everywhere (*"This isn't a wrapper. It's not a prototype. It's a deterministic pipeline."*). 

  MD
* **Participial Tail Clauses**: Tacking hollow `-ing` phrases onto the end of sentences (*"...reducing latency by 40%, ensuring high reliability and enabling scalable deployment"*).
* **Nominalization Bloat**: Turning active verbs into heavy noun phrases (*"performs quantization of the weights"* instead of *"quantizes the weights"*).
* **Compulsive Tricolons**: Grouping every adjective list, architectural pillar, or takeaway into sets of three.

### Flaw 5: Reference Sprawl & Tier Mismatch (`L4` & `L5`)

You currently point to **14 external files** (9 in `references/` and 5 in `examples/`): 

MD

* `references/adaptive-depth-guide.md` duplicates the routing responsibility of Section 2. 

  MD
* `L4` (*Frontier model releases*) and `L5` (*144-page Haiku 5.5 System Cards / RSP catastrophic risk evaluations*) are framed around foundation-model lab deliverables. Re-anchoring `L4` to **Empirical Evaluation & Research Papers** (ablation studies, latency/accuracy trade-offs, hardware/dataset benchmarks) and `L5` to **Comprehensive System Audits & Compliance Dossiers** makes those tiers directly usable for your real engineering and research work. 

  MD

## 3. Concrete Upgrade Blueprint (`v1.0.0` →\rightarrow→ `v2.0.0`)

Here is how to refactor the core elements of `SKILL.md` so it enforces genuine engineering prose rather than brand mimicry:

| Element | Current `v1.0.0` Implementation | Upgraded `v2.0.0` Specification |
| --- | --- | --- |
| **Skill Framing & Trigger** | Framed as imitating Anthropic (`writing-like-claude`, `Haiku 5.5 System Card`, `[claude.com/blog](https://claude.com/blog)`).  MD | Keep the trigger alias `"write like claude"` for convenience, but reframe the internal system directive as **Calm Engineering Authority**: zero-hype, mechanism-first technical exposition adaptable to any hardware, software, or ML domain.  MD |
| **Section 1 Quote** | Uses staccato negation framing (*"Not selling. Not performing. Just explaining."*).  MD | Rewrite in clean declarative prose so the prompt itself models the exact sentence geometry you want the agent to produce. |
| **Rules 6 & 7 (Empirical & Tradeoffs)** | Hardcodes LLM eval qualifiers (`offline subset`, `no tools`, `Xhigh`) and API effort curves (`Low/Medium/High/Max`).  MD | Generalize into **Controlled Baselines & Ablations** (always state hardware/runtime environment, precision/quantization, dataset split, or baseline comparator) and **Multi-Objective Tradeoffs** (always pair capability gains with latency, memory, compute, or operational cost). |
| **Rule 8 (Prose Geometry)** | *"One idea per paragraph (1–4 sentences max). One action per sentence."*  MD | Replace with **Causal Flow & Cadence Variance**:   1. Every paragraph must open with a claim or constraint and close with its mechanical consequence.   2. Vary sentence length: follow complex analytical clauses with short declarative conclusions.   3. Connect paragraphs via cause-and-effect (*because, consequently, however*), never meta-signposting (*"In this section, we will look at..."*). |
| **New Rule: Syntactic Anti-AI Filter** | Only bans lexical marketing buzzwords (*revolutionary, magic, seamless*).  MD | Add a **Syntactic Blacklist** banning:   • Negation contrasts (*"It's not X—it's Y"*)   • Participial tails (*"...ensuring X and enabling Y"*)   • Verb nominalizations (*"conduct an investigation"* →\rightarrow→ *"investigate"*)   • Rhetorical questions as section hooks. |
| **Reference Tree Consolidation** | 9 `references/*.md` + 5 `examples/*.md` (14 files total).  MD | Consolidate `adaptive-depth-guide.md` directly into Section 2, merge `system-cards-and-safety.md` + `governance-and-threat-models.md` into a single `audits-governance-and-safety.md`, and generalize `model-reports-and-benchmarks.md` to cover software/hardware/ML benchmarks alike. |

### Recommended Addition: A "Whiteboard Rhetoric" Micro-Section

Between Section 2 and Section 3, add a compact **Narrative & Explanation Mechanics** block that teaches the agent *how* to explain complex systems: 

MD

1. **Constraint →\rightarrow→ Mechanism →\rightarrow→ Consequence**: Never introduce a component by listing its features. State the bottleneck that forced its existence, explain how the mechanism works under the hood, and show the measured result.
2. **Concrete Trace Before General Law**: Show a real payload, failure log, register state, or failure case before stating the architectural rule.
3. **Calibrated Epistemic Verbs**: Use deterministic verbs (*eliminates, bounds, guarantees, reduces*) for verified measurements, and explicit observational verbs (*indicates, suggests, correlates with*) for unverified hypotheses.

Would you like me to draft the complete v2.0 `SKILL.md` with these upgraded rules and refactored tier descriptions, and should we keep the filename/name as `writing-like-claude` so your existing CLI paths and `audit_calm_writing.py` script don't break?

---

## Turn 2

### User

https://github.com/Aaradhya-Dev-Tamrakar/SPARK/issues

https://github.com/AaradhyaDT/BiasAperture/

https://github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot These are my projects will this work as a reference to my current status and what curation is needed

### Assistant

These three repositories form a strong, authentic foundation for both your public engineering status and the ground-truth reference corpus inside your upgraded `SKILL.md`. Together, they represent your full lifecycle as a builder—spanning a **completed hardware-control thesis** (`Gesture-Controlled-Self-Balancing-Robot`), a **submission-ready ML governance pipeline** (`BiasAperture`), and an **active edge-AI system in development** (`SPARK`). 

MD

More importantly for your `writing-like-claude` skill upgrade, these three projects cover every writing tier (`L1` through `L5`), allowing you to completely replace the synthetic "Anthropic Haiku 5.5" examples with your own verifiable engineering work. 

MD+ 1

## 1. Why This Trio Works as Your Status Reference

Each repository anchors a distinct technical pillar and maturity state:

* **Gesture-Controlled Self-Balancing Robot (`Completed` — Control Systems & Hardware Reality)**: Anchors your completed foundational work (`C++`, PID balancing, MPU6050, MediaPipe, DRV8825, MATLAB-to-hardware transfer, rated 9.6/10). It proves you can take a control model out of simulation, debug physical mechanical instabilities, and document empirical fixes.
* **BiasAperture (`Submission-Ready` — Algorithmic Fairness & Regulatory Auditing)**: Anchors your applied ML and governance maturity (`AIF360`, `Fairlearn`, `SHAP`, `FairFace`, EU AI Act compliance). It provides statistical rigor, confidence intervals, and regulatory scope boundaries. 

  MD
* **SPARK (`Building` — Edge AI Firmware & Systems Architecture)**: Anchors your active capstone trajectory (`ESP32-S3`, `TFLite Micro` 1D CNN at 200 Hz, `SHAP`, `MQTT`, `IMU`). Linking to its issue tracker and architecture specs shows how you decompose an active hardware-software system in real time.

## 2. External Curation Needed: Repository & Profile Hygiene

Before locking these links into your skill files, portfolio metadata, or CV, clean up four inconsistencies across your public surfaces:

1. **Normalize Your GitHub Handle (`Aaradhya-Dev-Tamrakar` vs. `AaradhyaDT`)**:

   * Your `SPARK` URL uses `[github.com/Aaradhya-Dev-Tamrakar/SPARK/issues](https://github.com/Aaradhya-Dev-Tamrakar/SPARK/issues)`, while `BiasAperture`, `Gesture-Controlled-Self-Balancing-Robot`, your active GitHub profile (`[github.com/AaradhyaDT](https://github.com/AaradhyaDT)`), and your portfolio site (`aaradhyadt.github.io`) use **`AaradhyaDT`**.
   * Relying on GitHub's legacy username redirect splits canonical link authority and breaks deterministic path checks in scripts. Standardize all references to `[https://github.com/AaradhyaDT/SPARK](https://github.com/AaradhyaDT/SPARK)`.
2. **Curate `SPARK/issues` into Structured Engineering Artifacts**:

   * Pointing someone to `/issues` on an in-progress repo (`Building`) only works if the issue tracker reads like an engineering specification board rather than a scratchpad.
   * **Action**: Ensure you have 4 to 6 open/closed issues structured in **Tier L1 format** (declarative title, 1-sentence thesis, constraints, and non-goals) covering key architectural workstreams (e.g., *200 Hz MPU6050 sampling pipeline on ESP32-S3*, *INT8 TFLite Micro 1D-CNN quantization vs. float32 baseline*, *MQTT/BLE alert payload schema*). Also link `/issues` from a clean root `README.md` architecture overview so visitors don't hit an uncontextualized issue list. 

     MD
3. **Sync Project Status Badges Between GitHub and Your Portfolio**:

   * Your GitHub profile README lists `BiasAperture` as **`Submission-ready`**, whereas your portfolio site (`aaradhyadt.github.io`, updated Oct 3, 2026) still lists `BiasAperture` as **`In Progress`**. Align both surfaces to the exact same state.
4. **Update Your Pinned Repositories on `[github.com/AaradhyaDT](https://github.com/AaradhyaDT)`**:

   * Currently, your pinned repositories feature `Gesture-Controlled-Self-Balancing-Robot` alongside older fellowship weekly notebooks (`fuseAiF_wk5_telco_churn_ensembles`, `fuseAiF_wk3_text2sql`, `FuseAIF2026M1`) and `stability-ai-system`.
   * **Action**: Pin **`SPARK`**, **`BiasAperture`**, and **`Gesture-Controlled-Self-Balancing-Robot`** as your top three pinned repositories on `[github.com/AaradhyaDT](https://github.com/AaradhyaDT)` so anyone visiting your profile sees this exact triad first.

## 3. Internal Curation: Mapping Your 3 Projects into `SKILL.md` (`v2.0.0`)

Instead of using Anthropic's `Haiku 5.5` release reports and system cards as the worked examples in `SKILL.md`, curate real artifacts from these three repositories into your `examples/` directory: 

MD+ 1

| Skill Tier | Current `v1.0.0` Anchor | Curated `v2.0.0` Anchor (From Your 3 Repos) | What to Extract & Curate |
| --- | --- | --- | --- |
| **`L1` (Micro-Surface)**   100–300 words  MD | Generic PR & portfolio blurb (`examples/l1-portfolio-and-pr.md`)  MD | **`SPARK` Issue / PR Spec** + **3-Bullet Portfolio Manifest**  MD | Curate one real `SPARK` issue and one PR description (declarative title, 1-sentence thesis, verification proof, explicit non-goals) alongside the 3 zero-hype bullet points for `portfolio-project-manager`.  MD |
| **`L2` (Editorial Narrative)**   800–1,500 words  MD | Anthropic dog-fooding blog post (`examples/l2-blog-case-study.md`)  MD | **`GCSBR` Engineering Post-Mortem** (MATLAB →\rightarrow→ Real Hardware) | Curate the story of bridging the simulation-to-hardware gap on the MPU6050 + DRV8825 loop, using the **Constraint →\rightarrow→ Mechanism →\rightarrow→ Consequence** whiteboard arc to explain how you isolated and fixed turn-induced pitch instability. |
| **`L3` (Technical Spec)**   1,000–3,000 words  MD | API model migration guide (`examples/l3-migration-guide.md`)  MD | **`SPARK` Edge Pipeline & Telemetry Contract** | Curate the hardware-firmware interface spec: 200 Hz IMU buffer framing, float32-to-INT8 TFLite Micro conversion diffs, memory/latency budgets on the ESP32-S3, and explicit unsupported failure modes.  MD |
| **`L4` (Empirical Evaluation)**   2,000–5,000 words  MD | Haiku 5.5 launch report (`examples/l4-model-launch-report.md`)  MD | **`SPARK` vs. `GCSBR` Benchmark & Ablation Report** | Replace LLM effort curves with real engineering Pareto tables: 1D-CNN quantization accuracy vs. inference latency on ESP32-S3 (`SPARK`), or PID response curves under MediaPipe Bluetooth command latency (`GCSBR`).  MD |
| **`L5` (System Card & Audit)**   5,000+ words  MD | 144p Haiku 5.5 System Card (`examples/l5-system-card-excerpt.md`)  MD | **`BiasAperture` Fairness & EU AI Act Dossier** | Replace frontier LLM catastrophic risk evals with your actual demographic bias audit on `FairFace` using `AIF360`, `Fairlearn`, and `SHAP`—enforcing your n<30n < 30n<30 cohort suppression rules (`.badge-guard` / `<details class="insufficient-block">`) and EU AI Act compliance mapping.  MD+ 1 |

Would you like to start by generating the upgraded **`SKILL.md` v2.0.0** wired to these three repositories, or would you prefer to draft the curated **Tier L1 issue templates for `SPARK`** and **status blurbs** first?

---

## Turn 3

### User

upgrade first

### Assistant

The upgraded `SKILL.md` (`v2.0.0`) below preserves your existing skill name (`writing-like-claude`), execution modes, ecosystem hooks, and `audit_calm_writing.py` CLI entrypoint while replacing Anthropic-specific mimicry with domain-agnostic engineering exposition anchored to `SPARK`, `BiasAperture`, and `Gesture-Controlled-Self-Balancing-Robot`. 

MD

Markdown

```
---
name: writing-like-claude
description: This skill should be used when the user asks to "write like claude", "write an engineering blog post", "write a release report", "draft a system card", "create a technical announcement", "write a developer migration guide", "audit technical writing", "write a case study", or mentions drafting publications, benchmarks, hardware/ML specs, or safety/fairness dossiers in a calm-authority engineering voice.
version: 2.0.0
---

# Writing Like Claude — The Calm Authority Engineering Standard (v2.0)

This skill codifies a mechanism-first, zero-hype technical writing standard across the full spectrum of engineering communication: from issue specs, PR descriptions, and developer tutorials to hardware-software post-mortems, empirical benchmark evaluations, and regulatory compliance dossiers.

---

## 1. Core Philosophy: The Whiteboard Test & Empirical Proof

The foundation of high-trust technical communication is **calm authority**:
> **Write as though you are mapping a real system for a sharp colleague at a whiteboard, or submitting an unredacted technical disclosure to a rigorous auditor. State the physical or computational constraint, explain the mechanism that resolves it, and prove the outcome with verifiable data.**

Trust is governed by an immutable relationship:
$$\text{Trust} = \text{Precision} + \text{Scope Boundaries} + \text{Empirical Proof}$$

### The Three Pillars
1. **Functional Precision**: Define systems by their mechanical inputs, state transitions, and outputs rather than promotional abstractions.
2. **Explicit Scope Boundaries**: Proactively declare what the system *cannot* do. Stating non-goals, hardware/runtime bottlenecks, and unsupported failure modes is the strongest signal of engineering credibility.
3. **Calibrated Empirical Proof**: Replace adjectives with verifiable operational metrics, controlled ablation tables, latency/memory budgets, or 95% confidence intervals. Distinguish measured facts from working hypotheses.

---

## 2. Fast-Path Pre-Flight Decision Gate (Zero-Thinking Route)

Before drafting, classify the target surface and load only the required reference file:

| Tier | Surface & Intent | Word Count | Canonical Project Anchor | Action & Loaded Reference |
| :--- | :--- | :--- | :--- | :--- |
| **`L1`** | **Micro-Surface**: Issue specs, PR descriptions, README intros, portfolio project blurbs, commit notes. | 100–300 | `SPARK` Issue Tracker & PR Specs (`github.com/AaradhyaDT/SPARK`) | **Fast-Path**: Execute directly using Sections 3 & 4 below. **Load 0 reference files**. |
| **`L2`** | **Editorial Narrative**: Engineering blog posts, sim-to-real post-mortems, architecture case studies, launches. | 800–1,500 | `GCSBR` Sim-to-Real Stabilization (`github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot`) | Load `references/narrative-and-case-studies.md`. |
| **`L3`** | **Technical Spec**: Firmware/SDK architecture, telemetry schemas, migration guides, API/hardware contracts. | 1,000–3,000 | `SPARK` 200 Hz IMU & Edge Inference Pipeline (`github.com/AaradhyaDT/SPARK`) | Load `references/migration-and-developer-specs.md`. |
| **`L4`** | **Empirical Evaluation**: Benchmark reports, quantization/ablation studies, latency vs. accuracy Pareto analyses. | 2,000–5,000 | `SPARK` INT8 1D-CNN & `GCSBR` Control Loop Benchmarks | Load `references/benchmarks-and-ablations.md`. |
| **`L5`** | **System Audit & Dossier**: Formal system cards, algorithmic fairness audits, regulatory compliance dossiers. | 5,000–30,000+ | `BiasAperture` Fairness & EU AI Act Audit (`github.com/AaradhyaDT/BiasAperture`) | Load `references/audits-governance-and-safety.md`. |

---

## 3. Whiteboard Rhetoric & Exposition Mechanics

Before applying sentence-level rules, structure every technical explanation using three rhetorical mechanics:

1. **Constraint $\rightarrow$ Mechanism $\rightarrow$ Consequence Arc**:
   - *Never* introduce a module by listing its features in isolation.
   - First state the physical, mathematical, or operational **constraint** (e.g., *"Polling the MPU6050 on the main loop introduces jitter above 200 Hz"*).
   - Next explain the **mechanism** that addresses it (e.g., *"Offloading sample acquisition to a hardware timer ISR decouples I2C reads from inference"*).
   - Close with the measured **consequence** (e.g., *"Frame drop variance falls to zero across a 10-minute stress window"*).
2. **Concrete Trace Before Abstract Law**:
   - Anchor the reader in a concrete failure log, register state, JSON payload, or physical oscillation before stating the general architectural principle.
3. **Epistemic Verb Calibration**:
   - **Verified Measurements**: Use deterministic verbs (*eliminates, bounds, reduces, guarantees, saturates at*).
   - **Hypotheses & Debugging Observations**: Use calibrated observational verbs (*indicates, correlates with, suggests, points toward*) and state the test required to confirm.

---

## 4. The 10 Universal Invariant Writing Rules

Every document drafted or audited under this skill must comply with these ten invariants:

1. **Title = Statement of Factual State**: Use a declarative sentence or precise noun phrase stating what exists or what changed (*"Isolating turn-induced pitch instability in two-wheeled PID balancing"* or *"INT8 quantization pipeline for 200 Hz fall detection on ESP32-S3"*). Never use clickbait, numbered listicles, or rhetorical questions.
2. **1-Sentence Empirical Thesis**: Open with a self-contained thesis stating the core mechanism and quantifiable outcome. In `L2` narratives, place this thesis immediately after the concrete problem setup.
3. **Dual Lexical & Syntactic Anti-AI Blacklist**:
   - **Lexical Ban**: Prohibit promotional superlatives (*revolutionary, game-changing, groundbreaking, unleash, supercharge, seamless, cutting-edge, magic, effortlessly, next-gen, robust, delve*). Consult `references/vocabulary_cheatsheet.md`.
   - **Syntactic Ban**: Prohibit negation-contrast clichés (*"It's not X—it's Y"*, *"Not selling. Just explaining."*), hollow participial tail clauses (*"...ensuring high reliability and enabling seamless scaling"*), verb nominalizations (*"performs quantization of"* $\rightarrow$ *"quantizes"*), and compulsive three-item adjective lists.
4. **Functional Precision in Definition**: Define any mechanism, component, or pipeline stage in 10 to 20 concrete words stating its input, transformation, and output (*"The feature extractor windows 200 Hz triaxial IMU streams into 256-sample frames for INT8 1D-CNN inference"*).
5. **Explicit Scope Boundaries & Non-Goals**: Dedicate explicit prose to what the system *does not* do. Declare unsupported hardware configurations, out-of-distribution failure modes, and deliberate non-goals prominently.
6. **Controlled Baselines & Environmental Pinning**: Back empirical claims with reproducible context. Always pin the execution environment (MCU clock/SRAM, GPU/CPU model, precision format `FP32` vs. `INT8`, dataset split, sample size $N$, and baseline comparator).
7. **Multi-Objective Tradeoff & Pareto Transparency**: Never report an improvement in one metric without stating its cost in another. Pair accuracy or throughput gains against SRAM footprint, inference latency (ms), power draw, or false-positive rate.
8. **Causal Flow & Cadence Variance**:
   - Keep one primary claim per paragraph (2 to 5 sentences).
   - Connect sentences via explicit cause-and-effect transitions (*because, consequently, when, whereas*) rather than meta-signposting (*"In this section, we will discuss..."*).
   - Vary sentence length: follow a longer multi-clause mechanical explanation with a short declarative consequence.
9. **Deterministic, Verifiable Artifacts**: Code blocks, firmware snippets, and CLI invocations must be copy-pasteable and runnable. Architecture and migration specs must include concrete before/after configuration or JSON schema diffs.
10. **Actionable Next Steps over Redundant Summaries**: Never restate the introduction in the conclusion. Conclude with reproducible CLI commands, commit/issue pointers, hardware BOM constraints, or open empirical questions.

---

## 5. Canonical Status & Ground-Truth Project Corpus

When referencing the author's active engineering portfolio, status, or worked examples, ground all claims in these three canonical repositories under the **`AaradhyaDT`** GitHub namespace:

1. **`SPARK` (`Building` — Edge AI & Embedded Systems)**:
   - **Canonical URL**: `https://github.com/AaradhyaDT/SPARK` (Issue board: `https://github.com/AaradhyaDT/SPARK/issues`)
   - **System Scope**: Two-layer wearable fall-detection system running an INT8 quantized TFLite Micro 1D-CNN on an ESP32-S3 with 200 Hz MPU6050 IMU sampling, BLE/MQTT telemetry, two-zone TPU 95A enclosure constraints, and SHAP explainability.
2. **`BiasAperture` (`Submission-Ready` — ML Fairness & Regulatory Auditing)**:
   - **Canonical URL**: `https://github.com/AaradhyaDT/BiasAperture`
   - **System Scope**: Five-module fairness and bias auditing pipeline for vision classifiers (`FairFace`, `UTKFace`) using `AIF360`, `Fairlearn`, and `SHAP`, mapped to EU AI Act and NIST AI RMF compliance gates with $n < 30$ cohort suppression.
3. **`Gesture-Controlled-Self-Balancing-Robot` (`Completed` — Control Systems & Robotics)**:
   - **Canonical URL**: `https://github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot`
   - **System Scope**: Two-wheeled self-balancing robot utilizing C++ PID control, MPU6050 sensor fusion, DRV8825 stepper actuation, and MediaPipe gesture command routing, featuring empirical corrections for turn-induced pitch instability.

---

## 6. Adaptive Execution Postures (Capability, Not Overhead)

Orchestration is an opt-in execution capability, never mandatory overhead:
```

[Task Scope]
├── Default (90% of tasks) ──> Solo Direct Execution (Immediate, zero subagents)
├── Explicit /agent-teams ───> Multi-Agent Team (Scout -> Reviewer -> Writer -> Lead)
└── Explicit /fleet-orch ───> Headless Batch Swarm (SKU DAG -> Pooled Workers -> Drive Sync)

```
1. **Mode 1: Solo Direct Execution (Default)**:
   - For all `L1` micro-tasks, `L2` engineering blog posts, `L3` specs, and standard `L4` drafts.
   - Executed directly by the primary agent with zero multi-agent coordination latency.
2. **Mode 2: Multi-Agent Team Capability (`/agent-teams-orchestration`)**:
   - For high-stakes `L4`/`L5` research dossiers and compliance audits requiring independent adversarial verification.
   - Dispatches **Scout** (`research`, `flash`) for raw metrics $\rightarrow$ **Reviewer** (`self`, `pro`) for adversarial scope/statistical checks $\rightarrow$ **Writer** for synthesis.
   - Consult `references/swarm-and-fleet-capabilities.md`.
3. **Mode 3: Fleet Swarm Capability (`/fleet-orchestrator`)**:
   - For high-throughput batch evaluation suites and multi-document pipelines.
   - Enqueues declarative SKU DAG `assets/sku-templates/model_report_pack.json` into `orchestrator-state/tasks/`.
   - Consult `references/swarm-and-fleet-capabilities.md`.

---

## 7. Ecosystem Compatibility Fast-Pointers

- **`compliance-report-harmonizer`**: When authoring Tier `L5` compliance dossiers (`BiasAperture`), adhere to the 5-section hierarchy and suppress cohorts with $n < 30$ using `.badge-guard` and `<details class="insufficient-block">`.
- **`portfolio-project-manager`**: When onboarding tools via `scripts/add_project.py`, generate 3 active-verb, zero-hype bullet points matching Tier `L1` format and ensure status badges (`Building`, `Submission-Ready`, `Completed`) match between GitHub and `aaradhyadt.github.io`.
- **`github-workflow`**: Use Tier `L1` format for `SPARK` issues and PR descriptions (declarative title, 1-sentence thesis, empirical verification proof, explicit non-goals) with authentic commit SHAs.
- **`super-nlm`**: Include `schema.org` JSON-LD and LaTeX math blocks (with spaces before all physical units, e.g., `200 Hz`, `0.5 mm`) to ensure clean ingestion into Google NotebookLM fleets.
- **`graphify`**: Ground research findings into the local Obsidian graph using `[[wikilinks]]`.
- Consult `references/ecosystem-compatibility.md` for complete cross-tool SOPs.

---

## 8. Deterministic Style Verification & Reference Tree

Audit any document against v2.0 calm authority standards (lexical hype + syntactic LLM-isms) using the local Python CLI:
```powershell
python "C:\Users\Aaradhya\.gemini\config\skills\writing-like-claude\scripts\audit_calm_writing.py" --tier L1 <path-to-file.md>
```

### Consolidated Reference Guides (`references/`)

* **`references/vocabulary_cheatsheet.md`** — Banned lexical hype list, banned syntactic AI patterns, and mechanical replacements.
* **`references/narrative-and-case-studies.md`** — `L2` structural formulas for engineering post-mortems and sim-to-real narratives.
* **`references/migration-and-developer-specs.md`** — `L3` hardware/software interface specs, schema diffs, and migration checklists.
* **`references/benchmarks-and-ablations.md`** — `L4` pinned baseline tables, quantization/latency Pareto frontiers, and ablation reporting.
* **`references/audits-governance-and-safety.md`** — `L5` fairness auditing, EU AI Act / NIST AI RMF mapping, and n<30n < 30n<30 suppression protocols.
* **`references/swarm-and-fleet-capabilities.md`** — Execution protocols for `/agent-teams` and `/fleet-orchestrator`.
* **`references/ecosystem-compatibility.md`** — Complete integration SOPs across the 8 interacting ecosystem skills.

### Ground-Truth Worked Examples (`examples/`)

* **`examples/l1-spark-issue-and-portfolio.md`** — Tier `L1`: `SPARK` architectural issue spec, PR template, and 3-bullet portfolio manifest.
* **`examples/l2-gcsbr-sim-to-real-postmortem.md`** — Tier `L2`: `GCSBR` engineering case study on resolving turn-induced pitch instability.
* **`examples/l3-spark-edge-telemetry-spec.md`** — Tier `L3`: `SPARK` 200 Hz MPU6050-to-TFLite Micro interface & payload contract.
* **`examples/l4-spark-quantization-benchmarks.md`** — Tier `L4`: `SPARK` FP32 vs. INT8 1D-CNN Pareto evaluation on ESP32-S3.
* **`examples/l5-biasaperture-eu-ai-act-audit.md`** — Tier `L5`: `BiasAperture` demographic fairness dossier with cohort suppression guards.

```
---

### Summary of Key Upgrades Applied

* **Eliminated Prompt Self-Contradiction**: Removed the `"Not selling. Not performing. Just explaining."` negation-contrast pattern from Section 1 so the skill prompt models clean, declarative cadence from line one[cite: 1].
* **Added Section 3 (Whiteboard Rhetoric)**: Introduced the **Constraint $\rightarrow$ Mechanism $\rightarrow$ Consequence** arc, concrete-first tracing, and calibrated epistemic verbs so the agent knows *how* to construct technical explanations rather than just checking off structural formatting rules[cite: 1].
* **Upgraded Rules 3, 6, 7, and 8**: Added a **Syntactic Ban** (blocking *"It's not X—it's Y"*, participial `-ing` tails, and nominalizations), replaced Anthropic-specific eval qualifiers (`Xhigh`, `offline subset`, `Low/Medium/High/Max` effort curves) with universal hardware/ML baseline pinning (`FP32` vs. `INT8`, MCU clock/SRAM, dataset split), and replaced the rigid `"One action per sentence"` rule with **Causal Flow & Cadence Variance**[cite: 1].
* **Wired Your Canonical Project Trio (Section 5)**: Standardized all repository references under `[https://github.com/AaradhyaDT/](https://github.com/AaradhyaDT/)...` and mapped `SPARK`, `BiasAperture`, and `Gesture-Controlled-Self-Balancing-Robot` directly into the `L1`–`L5` routing table and `examples/` directory[cite: 1].
* **Trimmed Reference Sprawl**: Consolidated `adaptive-depth-guide.md` into the Section 2 table and merged `system-cards-and-safety.md` + `governance-and-threat-models.md` into `audits-governance-and-safety.md`[cite: 1].

Would you like to update `audit_calm_writing.py` and `references/vocabulary_cheatsheet.md` next so your local CLI linter automatically flags those syntactic LLM-isms, or draft the `L1` `SPARK` issue templates and `examples/l1-spark-issue-and-portfolio.md` file?
```

---


---

# 📎 Appendix: Upgrade Skill File (Session Continuation)

> **Source URL:** [https://share.gemini.google/Kp9a7GKGcOYm](https://share.gemini.google/Kp9a7GKGcOYm)
> **Appended:** 2026-10-19
> **Total Turns:** 12

---

## Turn 1

### User

I want to upgrade my skill.md file, currently it imitates claude's writing. Dissect it and help me out what are the actual elements in it and that I need to improve

### Assistant

Your `SKILL.md` is architected less like a simple style prompt and more like a full **routing and governance engine** for technical writing. While the progressive context-loading architecture is strong, the writing instructions themselves suffer from **domain leakage**: they conflate *how great engineers write prose* with *what Anthropic's product marketing and frontier safety teams publish*. 

MD+ 1

## 1. Structural Dissection: The 5 Elements Currently in Your Skill

Your file currently combines five distinct functional layers: 

MD

1. **Epistemic Identity & Philosophy (Section 1)**: Establishes the "Whiteboard Test" persona, the Trust=Precision+Scope Boundaries+Empirical Proof\text{Trust} = \text{Precision} + \text{Scope Boundaries} + \text{Empirical Proof}Trust=Precision+Scope Boundaries+Empirical Proof formula, and three pillars (Functional Precision, Explicit Scope Boundaries, Empirical Proof & Dog-Fooding). 

   MD
2. **Progressive Context Router (Section 2)**: A 5-tier pre-flight gate (`L1` through `L5`) segmented by word count (100 to 30,000+ words) and surface type. It keeps `L1` as a zero-shot fast-path while lazy-loading specific `references/*.md` files for heavier tiers so you don't burn context tokens on small tasks. 

   MD+ 1
3. **Hard Style Constraints (Section 3)**: Ten "Universal Invariant Writing Rules" covering title grammar, opening thesis structure, banned marketing vocabulary, definition length (10–15 words), scope non-goals, benchmark table conventions, Pareto tradeoff curves, sentence/paragraph length limits, runnable code/JSON diffs, and non-summary conclusions. 

   MD
4. **Execution & Ecosystem Wiring (Sections 4 & 5)**: Hooks into your broader local agent stack—routing between solo execution, `/agent-teams-orchestration` (Scout →\rightarrow→ Reviewer →\rightarrow→ Writer), and `/fleet-orchestrator` (`model_report_pack.json`), alongside hard rules for `compliance-report-harmonizer` (n<30n < 30n<30 suppression), `portfolio-project-manager`, `github-workflow`, `super-nlm`, and `graphify`. 

   MD
5. **Deterministic Linter & Reference Tree (Sections 6 & 7)**: Calls `audit_calm_writing.py` by tier and indexes 9 modular reference files alongside 5 worked tier examples. 

   MD

## 2. What Needs Improvement: 5 Core Flaws Holding the Skill Back

### Flaw 1: "Anthropic Cosplay" Disguised as Universal Rules (Domain Leakage)

Look closely at Rules 6 and 7 in Section 3: 

MD

* Rule 6 mandates *"Pinned Benchmark Grids (Subject, Predecessor, Competitor, Frontier Reference) with explicit qualifiers (`offline subset`, `no tools`, `with tools`, `Xhigh`)"*. 

  MD
* Rule 7 mandates *"effort setting curves (Low/Medium/High/Max)"*. 

  MD
* Rule 9 mandates *"Reports must cite formal system cards"*. 

  MD

Those are not universal writing principles—they are specific artifacts of releasing a frontier LLM API at Anthropic (`thinking`/`effort` parameters and agentic tool-use evals). When you invoke this skill to write an embedded systems thesis, a fairness auditing report, a robotics paper, or a backend architecture doc, the model gets pulled toward **roleplaying an AI lab release** instead of applying rigorous engineering exposition to your actual domain. 

MD

### Flaw 2: Structural Checklists Without Actual Prose Mechanics

Your skill tells the agent *what artifacts to put on the page* (declarative title, 1-sentence thesis, benchmark table, non-goals section, JSON diffs, CLI links), but almost nothing about **how to move from sentence to sentence**. 

MD

* **Missing Causal Transitions**: Good technical writing connects ideas via mechanical cause and effect (*"Because the IMU FIFO buffer saturates at 1 kHz, polling on the main loop drops frames; moving acquisition to an ISR eliminates the contention"*). Without explicit transition rules, LLMs default to disconnected paragraphs stacked under subheadings.
* **Missing Pedagogical Arc (Concrete →\rightarrow→ Abstract)**: A real whiteboard explanation starts with the concrete friction or failure mode *before* introducing the abstraction or architecture. Rule 2 jumps straight to a "1-Sentence Empirical Thesis", which works for release announcements but makes deep engineering blog posts (`L2`) feel dry and top-heavy if not paired with problem-first anchoring. 

  MD
* **Missing Epistemic Calibration**: Section 1 demands "Empirical Proof" and "95% bootstrap confidence intervals", leaving no instructions for how to write about *hypotheses, debugging observations, or architectural hunches*. Calm authority also means knowing when to say *"We suspect this tail latency stems from..."* versus stating a measured fact. 

  MD

### Flaw 3: The "Robotic Staccato" Trap in Rules 4 and 8

Rule 4 locks definitions to *"10 to 15 concrete, mechanical words"* and Rule 8 enforces *"One idea per paragraph (1–4 sentences max). One action per sentence."*

MD

* When an LLM obeys "one action per sentence" and "1–4 sentences max" strictly, it generates **choppy, telegraphic prose** where every sentence has the exact same rhythm (`Subject -> Verb -> Object.`).
* Great technical prose relies on **cadence variance**: pairing a longer multi-clause sentence that maps out a system constraint with a short, punchy declarative sentence that lands the consequence.

### Flaw 4: Level-1 Buzzword Filtering vs. Structural "LLM-isms"

Rule 3 bans obvious marketing adjectives (*revolutionary, game-changing, unleash, supercharge, magic*). That catches cheap promotional copy, but it misses the **syntactic AI habits** that immediately give away LLM-generated technical writing: 

MD

* **Negation-Contrast Framing ("Not X, just Y")**: Ironically, your own prompt uses this exact LLM cliché in Section 1 (*"Not selling. Not performing. Just explaining."*). When an LLM sees that in the system prompt, it mirrors that cadence everywhere (*"This isn't a wrapper. It's not a prototype. It's a deterministic pipeline."*). 

  MD
* **Participial Tail Clauses**: Tacking hollow `-ing` phrases onto the end of sentences (*"...reducing latency by 40%, ensuring high reliability and enabling scalable deployment"*).
* **Nominalization Bloat**: Turning active verbs into heavy noun phrases (*"performs quantization of the weights"* instead of *"quantizes the weights"*).
* **Compulsive Tricolons**: Grouping every adjective list, architectural pillar, or takeaway into sets of three.

### Flaw 5: Reference Sprawl & Tier Mismatch (`L4` & `L5`)

You currently point to **14 external files** (9 in `references/` and 5 in `examples/`): 

MD

* `references/adaptive-depth-guide.md` duplicates the routing responsibility of Section 2. 

  MD
* `L4` (*Frontier model releases*) and `L5` (*144-page Haiku 5.5 System Cards / RSP catastrophic risk evaluations*) are framed around foundation-model lab deliverables. Re-anchoring `L4` to **Empirical Evaluation & Research Papers** (ablation studies, latency/accuracy trade-offs, hardware/dataset benchmarks) and `L5` to **Comprehensive System Audits & Compliance Dossiers** makes those tiers directly usable for your real engineering and research work. 

  MD

## 3. Concrete Upgrade Blueprint (`v1.0.0` →\rightarrow→ `v2.0.0`)

Here is how to refactor the core elements of `SKILL.md` so it enforces genuine engineering prose rather than brand mimicry:

| Element | Current `v1.0.0` Implementation | Upgraded `v2.0.0` Specification |
| --- | --- | --- |
| **Skill Framing & Trigger** | Framed as imitating Anthropic (`writing-like-claude`, `Haiku 5.5 System Card`, `[claude.com/blog](https://claude.com/blog)`).  MD | Keep the trigger alias `"write like claude"` for convenience, but reframe the internal system directive as **Calm Engineering Authority**: zero-hype, mechanism-first technical exposition adaptable to any hardware, software, or ML domain.  MD |
| **Section 1 Quote** | Uses staccato negation framing (*"Not selling. Not performing. Just explaining."*).  MD | Rewrite in clean declarative prose so the prompt itself models the exact sentence geometry you want the agent to produce. |
| **Rules 6 & 7 (Empirical & Tradeoffs)** | Hardcodes LLM eval qualifiers (`offline subset`, `no tools`, `Xhigh`) and API effort curves (`Low/Medium/High/Max`).  MD | Generalize into **Controlled Baselines & Ablations** (always state hardware/runtime environment, precision/quantization, dataset split, or baseline comparator) and **Multi-Objective Tradeoffs** (always pair capability gains with latency, memory, compute, or operational cost). |
| **Rule 8 (Prose Geometry)** | *"One idea per paragraph (1–4 sentences max). One action per sentence."*  MD | Replace with **Causal Flow & Cadence Variance**:   1. Every paragraph must open with a claim or constraint and close with its mechanical consequence.   2. Vary sentence length: follow complex analytical clauses with short declarative conclusions.   3. Connect paragraphs via cause-and-effect (*because, consequently, however*), never meta-signposting (*"In this section, we will look at..."*). |
| **New Rule: Syntactic Anti-AI Filter** | Only bans lexical marketing buzzwords (*revolutionary, magic, seamless*).  MD | Add a **Syntactic Blacklist** banning:   • Negation contrasts (*"It's not X—it's Y"*)   • Participial tails (*"...ensuring X and enabling Y"*)   • Verb nominalizations (*"conduct an investigation"* →\rightarrow→ *"investigate"*)   • Rhetorical questions as section hooks. |
| **Reference Tree Consolidation** | 9 `references/*.md` + 5 `examples/*.md` (14 files total).  MD | Consolidate `adaptive-depth-guide.md` directly into Section 2, merge `system-cards-and-safety.md` + `governance-and-threat-models.md` into a single `audits-governance-and-safety.md`, and generalize `model-reports-and-benchmarks.md` to cover software/hardware/ML benchmarks alike. |

### Recommended Addition: A "Whiteboard Rhetoric" Micro-Section

Between Section 2 and Section 3, add a compact **Narrative & Explanation Mechanics** block that teaches the agent *how* to explain complex systems: 

MD

1. **Constraint →\rightarrow→ Mechanism →\rightarrow→ Consequence**: Never introduce a component by listing its features. State the bottleneck that forced its existence, explain how the mechanism works under the hood, and show the measured result.
2. **Concrete Trace Before General Law**: Show a real payload, failure log, register state, or failure case before stating the architectural rule.
3. **Calibrated Epistemic Verbs**: Use deterministic verbs (*eliminates, bounds, guarantees, reduces*) for verified measurements, and explicit observational verbs (*indicates, suggests, correlates with*) for unverified hypotheses.

Would you like me to draft the complete v2.0 `SKILL.md` with these upgraded rules and refactored tier descriptions, and should we keep the filename/name as `writing-like-claude` so your existing CLI paths and `audit_calm_writing.py` script don't break?

---

## Turn 2

### User

https://github.com/Aaradhya-Dev-Tamrakar/SPARK/issues

https://github.com/AaradhyaDT/BiasAperture/

https://github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot These are my projects will this work as a reference to my current status and what curation is needed

### Assistant

These three repositories form a strong, authentic foundation for both your public engineering status and the ground-truth reference corpus inside your upgraded `SKILL.md`. Together, they represent your full lifecycle as a builder—spanning a **completed hardware-control thesis** (`Gesture-Controlled-Self-Balancing-Robot`), a **submission-ready ML governance pipeline** (`BiasAperture`), and an **active edge-AI system in development** (`SPARK`). 

MD

More importantly for your `writing-like-claude` skill upgrade, these three projects cover every writing tier (`L1` through `L5`), allowing you to completely replace the synthetic "Anthropic Haiku 5.5" examples with your own verifiable engineering work. 

MD+ 1

## 1. Why This Trio Works as Your Status Reference

Each repository anchors a distinct technical pillar and maturity state:

* **Gesture-Controlled Self-Balancing Robot (`Completed` — Control Systems & Hardware Reality)**: Anchors your completed foundational work (`C++`, PID balancing, MPU6050, MediaPipe, DRV8825, MATLAB-to-hardware transfer, rated 9.6/10). It proves you can take a control model out of simulation, debug physical mechanical instabilities, and document empirical fixes.
* **BiasAperture (`Submission-Ready` — Algorithmic Fairness & Regulatory Auditing)**: Anchors your applied ML and governance maturity (`AIF360`, `Fairlearn`, `SHAP`, `FairFace`, EU AI Act compliance). It provides statistical rigor, confidence intervals, and regulatory scope boundaries. 

  MD
* **SPARK (`Building` — Edge AI Firmware & Systems Architecture)**: Anchors your active capstone trajectory (`ESP32-S3`, `TFLite Micro` 1D CNN at 200 Hz, `SHAP`, `MQTT`, `IMU`). Linking to its issue tracker and architecture specs shows how you decompose an active hardware-software system in real time.

## 2. External Curation Needed: Repository & Profile Hygiene

Before locking these links into your skill files, portfolio metadata, or CV, clean up four inconsistencies across your public surfaces:

1. **Normalize Your GitHub Handle (`Aaradhya-Dev-Tamrakar` vs. `AaradhyaDT`)**:

   * Your `SPARK` URL uses `[github.com/Aaradhya-Dev-Tamrakar/SPARK/issues](https://github.com/Aaradhya-Dev-Tamrakar/SPARK/issues)`, while `BiasAperture`, `Gesture-Controlled-Self-Balancing-Robot`, your active GitHub profile (`[github.com/AaradhyaDT](https://github.com/AaradhyaDT)`), and your portfolio site (`aaradhyadt.github.io`) use **`AaradhyaDT`**.
   * Relying on GitHub's legacy username redirect splits canonical link authority and breaks deterministic path checks in scripts. Standardize all references to `[https://github.com/AaradhyaDT/SPARK](https://github.com/AaradhyaDT/SPARK)`.
2. **Curate `SPARK/issues` into Structured Engineering Artifacts**:

   * Pointing someone to `/issues` on an in-progress repo (`Building`) only works if the issue tracker reads like an engineering specification board rather than a scratchpad.
   * **Action**: Ensure you have 4 to 6 open/closed issues structured in **Tier L1 format** (declarative title, 1-sentence thesis, constraints, and non-goals) covering key architectural workstreams (e.g., *200 Hz MPU6050 sampling pipeline on ESP32-S3*, *INT8 TFLite Micro 1D-CNN quantization vs. float32 baseline*, *MQTT/BLE alert payload schema*). Also link `/issues` from a clean root `README.md` architecture overview so visitors don't hit an uncontextualized issue list. 

     MD
3. **Sync Project Status Badges Between GitHub and Your Portfolio**:

   * Your GitHub profile README lists `BiasAperture` as **`Submission-ready`**, whereas your portfolio site (`aaradhyadt.github.io`, updated Oct 3, 2026) still lists `BiasAperture` as **`In Progress`**. Align both surfaces to the exact same state.
4. **Update Your Pinned Repositories on `[github.com/AaradhyaDT](https://github.com/AaradhyaDT)`**:

   * Currently, your pinned repositories feature `Gesture-Controlled-Self-Balancing-Robot` alongside older fellowship weekly notebooks (`fuseAiF_wk5_telco_churn_ensembles`, `fuseAiF_wk3_text2sql`, `FuseAIF2026M1`) and `stability-ai-system`.
   * **Action**: Pin **`SPARK`**, **`BiasAperture`**, and **`Gesture-Controlled-Self-Balancing-Robot`** as your top three pinned repositories on `[github.com/AaradhyaDT](https://github.com/AaradhyaDT)` so anyone visiting your profile sees this exact triad first.

## 3. Internal Curation: Mapping Your 3 Projects into `SKILL.md` (`v2.0.0`)

Instead of using Anthropic's `Haiku 5.5` release reports and system cards as the worked examples in `SKILL.md`, curate real artifacts from these three repositories into your `examples/` directory: 

MD+ 1

| Skill Tier | Current `v1.0.0` Anchor | Curated `v2.0.0` Anchor (From Your 3 Repos) | What to Extract & Curate |
| --- | --- | --- | --- |
| **`L1` (Micro-Surface)**   100–300 words  MD | Generic PR & portfolio blurb (`examples/l1-portfolio-and-pr.md`)  MD | **`SPARK` Issue / PR Spec** + **3-Bullet Portfolio Manifest**  MD | Curate one real `SPARK` issue and one PR description (declarative title, 1-sentence thesis, verification proof, explicit non-goals) alongside the 3 zero-hype bullet points for `portfolio-project-manager`.  MD |
| **`L2` (Editorial Narrative)**   800–1,500 words  MD | Anthropic dog-fooding blog post (`examples/l2-blog-case-study.md`)  MD | **`GCSBR` Engineering Post-Mortem** (MATLAB →\rightarrow→ Real Hardware) | Curate the story of bridging the simulation-to-hardware gap on the MPU6050 + DRV8825 loop, using the **Constraint →\rightarrow→ Mechanism →\rightarrow→ Consequence** whiteboard arc to explain how you isolated and fixed turn-induced pitch instability. |
| **`L3` (Technical Spec)**   1,000–3,000 words  MD | API model migration guide (`examples/l3-migration-guide.md`)  MD | **`SPARK` Edge Pipeline & Telemetry Contract** | Curate the hardware-firmware interface spec: 200 Hz IMU buffer framing, float32-to-INT8 TFLite Micro conversion diffs, memory/latency budgets on the ESP32-S3, and explicit unsupported failure modes.  MD |
| **`L4` (Empirical Evaluation)**   2,000–5,000 words  MD | Haiku 5.5 launch report (`examples/l4-model-launch-report.md`)  MD | **`SPARK` vs. `GCSBR` Benchmark & Ablation Report** | Replace LLM effort curves with real engineering Pareto tables: 1D-CNN quantization accuracy vs. inference latency on ESP32-S3 (`SPARK`), or PID response curves under MediaPipe Bluetooth command latency (`GCSBR`).  MD |
| **`L5` (System Card & Audit)**   5,000+ words  MD | 144p Haiku 5.5 System Card (`examples/l5-system-card-excerpt.md`)  MD | **`BiasAperture` Fairness & EU AI Act Dossier** | Replace frontier LLM catastrophic risk evals with your actual demographic bias audit on `FairFace` using `AIF360`, `Fairlearn`, and `SHAP`—enforcing your n<30n < 30n<30 cohort suppression rules (`.badge-guard` / `<details class="insufficient-block">`) and EU AI Act compliance mapping.  MD+ 1 |

Would you like to start by generating the upgraded **`SKILL.md` v2.0.0** wired to these three repositories, or would you prefer to draft the curated **Tier L1 issue templates for `SPARK`** and **status blurbs** first?

---

## Turn 3

### User

upgrade first

### Assistant

The upgraded `SKILL.md` (`v2.0.0`) below preserves your existing skill name (`writing-like-claude`), execution modes, ecosystem hooks, and `audit_calm_writing.py` CLI entrypoint while replacing Anthropic-specific mimicry with domain-agnostic engineering exposition anchored to `SPARK`, `BiasAperture`, and `Gesture-Controlled-Self-Balancing-Robot`. 

MD

Markdown

```
---
name: writing-like-claude
description: This skill should be used when the user asks to "write like claude", "write an engineering blog post", "write a release report", "draft a system card", "create a technical announcement", "write a developer migration guide", "audit technical writing", "write a case study", or mentions drafting publications, benchmarks, hardware/ML specs, or safety/fairness dossiers in a calm-authority engineering voice.
version: 2.0.0
---

# Writing Like Claude — The Calm Authority Engineering Standard (v2.0)

This skill codifies a mechanism-first, zero-hype technical writing standard across the full spectrum of engineering communication: from issue specs, PR descriptions, and developer tutorials to hardware-software post-mortems, empirical benchmark evaluations, and regulatory compliance dossiers.

---

## 1. Core Philosophy: The Whiteboard Test & Empirical Proof

The foundation of high-trust technical communication is **calm authority**:
> **Write as though you are mapping a real system for a sharp colleague at a whiteboard, or submitting an unredacted technical disclosure to a rigorous auditor. State the physical or computational constraint, explain the mechanism that resolves it, and prove the outcome with verifiable data.**

Trust is governed by an immutable relationship:
$$\text{Trust} = \text{Precision} + \text{Scope Boundaries} + \text{Empirical Proof}$$

### The Three Pillars
1. **Functional Precision**: Define systems by their mechanical inputs, state transitions, and outputs rather than promotional abstractions.
2. **Explicit Scope Boundaries**: Proactively declare what the system *cannot* do. Stating non-goals, hardware/runtime bottlenecks, and unsupported failure modes is the strongest signal of engineering credibility.
3. **Calibrated Empirical Proof**: Replace adjectives with verifiable operational metrics, controlled ablation tables, latency/memory budgets, or 95% confidence intervals. Distinguish measured facts from working hypotheses.

---

## 2. Fast-Path Pre-Flight Decision Gate (Zero-Thinking Route)

Before drafting, classify the target surface and load only the required reference file:

| Tier | Surface & Intent | Word Count | Canonical Project Anchor | Action & Loaded Reference |
| :--- | :--- | :--- | :--- | :--- |
| **`L1`** | **Micro-Surface**: Issue specs, PR descriptions, README intros, portfolio project blurbs, commit notes. | 100–300 | `SPARK` Issue Tracker & PR Specs (`github.com/AaradhyaDT/SPARK`) | **Fast-Path**: Execute directly using Sections 3 & 4 below. **Load 0 reference files**. |
| **`L2`** | **Editorial Narrative**: Engineering blog posts, sim-to-real post-mortems, architecture case studies, launches. | 800–1,500 | `GCSBR` Sim-to-Real Stabilization (`github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot`) | Load `references/narrative-and-case-studies.md`. |
| **`L3`** | **Technical Spec**: Firmware/SDK architecture, telemetry schemas, migration guides, API/hardware contracts. | 1,000–3,000 | `SPARK` 200 Hz IMU & Edge Inference Pipeline (`github.com/AaradhyaDT/SPARK`) | Load `references/migration-and-developer-specs.md`. |
| **`L4`** | **Empirical Evaluation**: Benchmark reports, quantization/ablation studies, latency vs. accuracy Pareto analyses. | 2,000–5,000 | `SPARK` INT8 1D-CNN & `GCSBR` Control Loop Benchmarks | Load `references/benchmarks-and-ablations.md`. |
| **`L5`** | **System Audit & Dossier**: Formal system cards, algorithmic fairness audits, regulatory compliance dossiers. | 5,000–30,000+ | `BiasAperture` Fairness & EU AI Act Audit (`github.com/AaradhyaDT/BiasAperture`) | Load `references/audits-governance-and-safety.md`. |

---

## 3. Whiteboard Rhetoric & Exposition Mechanics

Before applying sentence-level rules, structure every technical explanation using three rhetorical mechanics:

1. **Constraint $\rightarrow$ Mechanism $\rightarrow$ Consequence Arc**:
   - *Never* introduce a module by listing its features in isolation.
   - First state the physical, mathematical, or operational **constraint** (e.g., *"Polling the MPU6050 on the main loop introduces jitter above 200 Hz"*).
   - Next explain the **mechanism** that addresses it (e.g., *"Offloading sample acquisition to a hardware timer ISR decouples I2C reads from inference"*).
   - Close with the measured **consequence** (e.g., *"Frame drop variance falls to zero across a 10-minute stress window"*).
2. **Concrete Trace Before Abstract Law**:
   - Anchor the reader in a concrete failure log, register state, JSON payload, or physical oscillation before stating the general architectural principle.
3. **Epistemic Verb Calibration**:
   - **Verified Measurements**: Use deterministic verbs (*eliminates, bounds, reduces, guarantees, saturates at*).
   - **Hypotheses & Debugging Observations**: Use calibrated observational verbs (*indicates, correlates with, suggests, points toward*) and state the test required to confirm.

---

## 4. The 10 Universal Invariant Writing Rules

Every document drafted or audited under this skill must comply with these ten invariants:

1. **Title = Statement of Factual State**: Use a declarative sentence or precise noun phrase stating what exists or what changed (*"Isolating turn-induced pitch instability in two-wheeled PID balancing"* or *"INT8 quantization pipeline for 200 Hz fall detection on ESP32-S3"*). Never use clickbait, numbered listicles, or rhetorical questions.
2. **1-Sentence Empirical Thesis**: Open with a self-contained thesis stating the core mechanism and quantifiable outcome. In `L2` narratives, place this thesis immediately after the concrete problem setup.
3. **Dual Lexical & Syntactic Anti-AI Blacklist**:
   - **Lexical Ban**: Prohibit promotional superlatives (*revolutionary, game-changing, groundbreaking, unleash, supercharge, seamless, cutting-edge, magic, effortlessly, next-gen, robust, delve*). Consult `references/vocabulary_cheatsheet.md`.
   - **Syntactic Ban**: Prohibit negation-contrast clichés (*"It's not X—it's Y"*, *"Not selling. Just explaining."*), hollow participial tail clauses (*"...ensuring high reliability and enabling seamless scaling"*), verb nominalizations (*"performs quantization of"* $\rightarrow$ *"quantizes"*), and compulsive three-item adjective lists.
4. **Functional Precision in Definition**: Define any mechanism, component, or pipeline stage in 10 to 20 concrete words stating its input, transformation, and output (*"The feature extractor windows 200 Hz triaxial IMU streams into 256-sample frames for INT8 1D-CNN inference"*).
5. **Explicit Scope Boundaries & Non-Goals**: Dedicate explicit prose to what the system *does not* do. Declare unsupported hardware configurations, out-of-distribution failure modes, and deliberate non-goals prominently.
6. **Controlled Baselines & Environmental Pinning**: Back empirical claims with reproducible context. Always pin the execution environment (MCU clock/SRAM, GPU/CPU model, precision format `FP32` vs. `INT8`, dataset split, sample size $N$, and baseline comparator).
7. **Multi-Objective Tradeoff & Pareto Transparency**: Never report an improvement in one metric without stating its cost in another. Pair accuracy or throughput gains against SRAM footprint, inference latency (ms), power draw, or false-positive rate.
8. **Causal Flow & Cadence Variance**:
   - Keep one primary claim per paragraph (2 to 5 sentences).
   - Connect sentences via explicit cause-and-effect transitions (*because, consequently, when, whereas*) rather than meta-signposting (*"In this section, we will discuss..."*).
   - Vary sentence length: follow a longer multi-clause mechanical explanation with a short declarative consequence.
9. **Deterministic, Verifiable Artifacts**: Code blocks, firmware snippets, and CLI invocations must be copy-pasteable and runnable. Architecture and migration specs must include concrete before/after configuration or JSON schema diffs.
10. **Actionable Next Steps over Redundant Summaries**: Never restate the introduction in the conclusion. Conclude with reproducible CLI commands, commit/issue pointers, hardware BOM constraints, or open empirical questions.

---

## 5. Canonical Status & Ground-Truth Project Corpus

When referencing the author's active engineering portfolio, status, or worked examples, ground all claims in these three canonical repositories under the **`AaradhyaDT`** GitHub namespace:

1. **`SPARK` (`Building` — Edge AI & Embedded Systems)**:
   - **Canonical URL**: `https://github.com/AaradhyaDT/SPARK` (Issue board: `https://github.com/AaradhyaDT/SPARK/issues`)
   - **System Scope**: Two-layer wearable fall-detection system running an INT8 quantized TFLite Micro 1D-CNN on an ESP32-S3 with 200 Hz MPU6050 IMU sampling, BLE/MQTT telemetry, two-zone TPU 95A enclosure constraints, and SHAP explainability.
2. **`BiasAperture` (`Submission-Ready` — ML Fairness & Regulatory Auditing)**:
   - **Canonical URL**: `https://github.com/AaradhyaDT/BiasAperture`
   - **System Scope**: Five-module fairness and bias auditing pipeline for vision classifiers (`FairFace`, `UTKFace`) using `AIF360`, `Fairlearn`, and `SHAP`, mapped to EU AI Act and NIST AI RMF compliance gates with $n < 30$ cohort suppression.
3. **`Gesture-Controlled-Self-Balancing-Robot` (`Completed` — Control Systems & Robotics)**:
   - **Canonical URL**: `https://github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot`
   - **System Scope**: Two-wheeled self-balancing robot utilizing C++ PID control, MPU6050 sensor fusion, DRV8825 stepper actuation, and MediaPipe gesture command routing, featuring empirical corrections for turn-induced pitch instability.

---

## 6. Adaptive Execution Postures (Capability, Not Overhead)

Orchestration is an opt-in execution capability, never mandatory overhead:
```

[Task Scope]
├── Default (90% of tasks) ──> Solo Direct Execution (Immediate, zero subagents)
├── Explicit /agent-teams ───> Multi-Agent Team (Scout -> Reviewer -> Writer -> Lead)
└── Explicit /fleet-orch ───> Headless Batch Swarm (SKU DAG -> Pooled Workers -> Drive Sync)

```
1. **Mode 1: Solo Direct Execution (Default)**:
   - For all `L1` micro-tasks, `L2` engineering blog posts, `L3` specs, and standard `L4` drafts.
   - Executed directly by the primary agent with zero multi-agent coordination latency.
2. **Mode 2: Multi-Agent Team Capability (`/agent-teams-orchestration`)**:
   - For high-stakes `L4`/`L5` research dossiers and compliance audits requiring independent adversarial verification.
   - Dispatches **Scout** (`research`, `flash`) for raw metrics $\rightarrow$ **Reviewer** (`self`, `pro`) for adversarial scope/statistical checks $\rightarrow$ **Writer** for synthesis.
   - Consult `references/swarm-and-fleet-capabilities.md`.
3. **Mode 3: Fleet Swarm Capability (`/fleet-orchestrator`)**:
   - For high-throughput batch evaluation suites and multi-document pipelines.
   - Enqueues declarative SKU DAG `assets/sku-templates/model_report_pack.json` into `orchestrator-state/tasks/`.
   - Consult `references/swarm-and-fleet-capabilities.md`.

---

## 7. Ecosystem Compatibility Fast-Pointers

- **`compliance-report-harmonizer`**: When authoring Tier `L5` compliance dossiers (`BiasAperture`), adhere to the 5-section hierarchy and suppress cohorts with $n < 30$ using `.badge-guard` and `<details class="insufficient-block">`.
- **`portfolio-project-manager`**: When onboarding tools via `scripts/add_project.py`, generate 3 active-verb, zero-hype bullet points matching Tier `L1` format and ensure status badges (`Building`, `Submission-Ready`, `Completed`) match between GitHub and `aaradhyadt.github.io`.
- **`github-workflow`**: Use Tier `L1` format for `SPARK` issues and PR descriptions (declarative title, 1-sentence thesis, empirical verification proof, explicit non-goals) with authentic commit SHAs.
- **`super-nlm`**: Include `schema.org` JSON-LD and LaTeX math blocks (with spaces before all physical units, e.g., `200 Hz`, `0.5 mm`) to ensure clean ingestion into Google NotebookLM fleets.
- **`graphify`**: Ground research findings into the local Obsidian graph using `[[wikilinks]]`.
- Consult `references/ecosystem-compatibility.md` for complete cross-tool SOPs.

---

## 8. Deterministic Style Verification & Reference Tree

Audit any document against v2.0 calm authority standards (lexical hype + syntactic LLM-isms) using the local Python CLI:
```powershell
python "C:\Users\Aaradhya\.gemini\config\skills\writing-like-claude\scripts\audit_calm_writing.py" --tier L1 <path-to-file.md>
```

### Consolidated Reference Guides (`references/`)

* **`references/vocabulary_cheatsheet.md`** — Banned lexical hype list, banned syntactic AI patterns, and mechanical replacements.
* **`references/narrative-and-case-studies.md`** — `L2` structural formulas for engineering post-mortems and sim-to-real narratives.
* **`references/migration-and-developer-specs.md`** — `L3` hardware/software interface specs, schema diffs, and migration checklists.
* **`references/benchmarks-and-ablations.md`** — `L4` pinned baseline tables, quantization/latency Pareto frontiers, and ablation reporting.
* **`references/audits-governance-and-safety.md`** — `L5` fairness auditing, EU AI Act / NIST AI RMF mapping, and n<30n < 30n<30 suppression protocols.
* **`references/swarm-and-fleet-capabilities.md`** — Execution protocols for `/agent-teams` and `/fleet-orchestrator`.
* **`references/ecosystem-compatibility.md`** — Complete integration SOPs across the 8 interacting ecosystem skills.

### Ground-Truth Worked Examples (`examples/`)

* **`examples/l1-spark-issue-and-portfolio.md`** — Tier `L1`: `SPARK` architectural issue spec, PR template, and 3-bullet portfolio manifest.
* **`examples/l2-gcsbr-sim-to-real-postmortem.md`** — Tier `L2`: `GCSBR` engineering case study on resolving turn-induced pitch instability.
* **`examples/l3-spark-edge-telemetry-spec.md`** — Tier `L3`: `SPARK` 200 Hz MPU6050-to-TFLite Micro interface & payload contract.
* **`examples/l4-spark-quantization-benchmarks.md`** — Tier `L4`: `SPARK` FP32 vs. INT8 1D-CNN Pareto evaluation on ESP32-S3.
* **`examples/l5-biasaperture-eu-ai-act-audit.md`** — Tier `L5`: `BiasAperture` demographic fairness dossier with cohort suppression guards.

```
---

### Summary of Key Upgrades Applied

* **Eliminated Prompt Self-Contradiction**: Removed the `"Not selling. Not performing. Just explaining."` negation-contrast pattern from Section 1 so the skill prompt models clean, declarative cadence from line one[cite: 1].
* **Added Section 3 (Whiteboard Rhetoric)**: Introduced the **Constraint $\rightarrow$ Mechanism $\rightarrow$ Consequence** arc, concrete-first tracing, and calibrated epistemic verbs so the agent knows *how* to construct technical explanations rather than just checking off structural formatting rules[cite: 1].
* **Upgraded Rules 3, 6, 7, and 8**: Added a **Syntactic Ban** (blocking *"It's not X—it's Y"*, participial `-ing` tails, and nominalizations), replaced Anthropic-specific eval qualifiers (`Xhigh`, `offline subset`, `Low/Medium/High/Max` effort curves) with universal hardware/ML baseline pinning (`FP32` vs. `INT8`, MCU clock/SRAM, dataset split), and replaced the rigid `"One action per sentence"` rule with **Causal Flow & Cadence Variance**[cite: 1].
* **Wired Your Canonical Project Trio (Section 5)**: Standardized all repository references under `[https://github.com/AaradhyaDT/](https://github.com/AaradhyaDT/)...` and mapped `SPARK`, `BiasAperture`, and `Gesture-Controlled-Self-Balancing-Robot` directly into the `L1`–`L5` routing table and `examples/` directory[cite: 1].
* **Trimmed Reference Sprawl**: Consolidated `adaptive-depth-guide.md` into the Section 2 table and merged `system-cards-and-safety.md` + `governance-and-threat-models.md` into `audits-governance-and-safety.md`[cite: 1].

Would you like to update `audit_calm_writing.py` and `references/vocabulary_cheatsheet.md` next so your local CLI linter automatically flags those syntactic LLM-isms, or draft the `L1` `SPARK` issue templates and `examples/l1-spark-issue-and-portfolio.md` file?
```

---

## Turn 4

### User

I think it even needs to adapt to use cases as well right?

here is my ecosystem for context https://github.com/Aaradhya-Dev-Tamrakar/brainstorm

### Assistant

A 1D length router (`L1` through `L5`) only tells the agent *how much* to write—it does not adapt *what counts as proof* across different engineering domains. When a single set of rules governs every task, the agent tries to force ML statistical conventions (like 95% bootstrap confidence intervals) onto deterministic firmware interrupt traces, or writes about a simulated architecture as if it were physical silicon.

*(Note: `[github.com/Aaradhya-Dev-Tamrakar/brainstorm](https://github.com/Aaradhya-Dev-Tamrakar/brainstorm)` is currently private or unindexed in public search—and still uses your legacy handle rather than `AaradhyaDT`—but mapping your 38-system public architecture on `aaradhyadt.github.io` alongside your shipped MCP servers reveals the exact use-case axes your `brainstorm` workspace orchestrates. If `brainstorm` has a custom internal directory tree you want mapped line-for-line, paste its `README.md` or `tree` output and we will wire the exact file paths.)*

## 1. Why Length Tiers (`L1`–`L5`) Are Only Half the Router

Across your ecosystem, a 1,500-word technical document (`L2`/`L3`) has completely different mechanical invariants depending on **which domain archetype** and **which epistemic maturity state** (`E3 Sim` vs. `E4`) it belongs to:

| Use-Case Code | Ecosystem Domain | Canonical Systems in Your Stack | What "Empirical Proof" Actually Means Here | What Fails Without Use-Case Adaptation |
| --- | --- | --- | --- | --- |
| **`U1`** | **Embedded, Robotics & Parametric CAD** | `SPARK` (E4), `GCSBR`, `Fusion 360 MCP`, `rhino-mcp` | SRAM/Flash budgets, ISR jitter (μs), sampling rates (`200 Hz`), step loss, FDM tolerances (`0.5 mm`, TPU 95A). | Agent asks for "dataset confidence intervals" on a deterministic I2C routine or CAD wall-thickness constraint. |
| **`U2`** | **Architecture & Network Simulation** | `STRANGLER-IPU` (E3 Sim), `epanet-mcp` | Line-rate throughput (`6G sub-THz`), CXL 3.0 pooled memory latency, queueing bounds, hydraulic/network solver convergence. | Agent conflates simulated projections (`E3 Sim`) with physical hardware measurements (`E4`). |
| **`U3`** | **Applied ML & Regulatory Auditing** | `BiasAperture` (E4), Fuse AI Fellowship | 95% bootstrap CIs, `AIF360` / `Fairlearn` parity metrics, `SHAP` attribution stability, EU AI Act gates, cohort n less than 30 suppression. | Statistical guardrails leak into non-ML docs, or cohort suppression tags are omitted in fairness audits. |
| **`U4`** | **AI Infra, DSP & MCP Servers** | `Claude Desktop DSP`, `typora-mcp`, `localsend-mcp`, `google-classroom-mcp` | JSON-RPC tool schemas, token-budget diffs, deterministic routing latency, idempotency, and zero-shot fallback paths. | Agent writes narrative prose where strict JSON schema contracts, I/O types, and error codes are required. |
| **`U5`** | **Knowledge Synthesis & Portfolio** | `super-nlm`, `graphify`, `portfolio-project-manager`, `aaradhyadt.github.io` | `schema.org` JSON-LD blocks, Obsidian `[[wikilinks]]`, unit-spaced LaTeX, and 3-bullet zero-hype impact manifests. | Formatting breaks downstream ingestion into NotebookLM fleets, Obsidian graphs, or portfolio build scripts. |

## 2. Two Missing Adaptation Mechanisms to Add in `v2.1.0`

### A. The 2D Routing Coordinate: `(Tier, UseCase)`

Instead of routing solely on `L1`–`L5`, the pre-flight gate should resolve a **2D coordinate** like `(L3, U1)` for a `SPARK` firmware telemetry contract or `(L4, U2)` for a `STRANGLER-IPU` CXL 3.0 memory-pooling benchmark:

* **Axis 1 (`L1`–`L5`)** controls **structural geometry, word budget, and orchestration depth** (Solo vs. `/agent-teams` vs. `/fleet-orchestrator`).
* **Axis 2 (`U1`–`U5`)** controls **domain proof standards, required telemetry units, and downstream tool hooks**.

### B. Epistemic Maturity Pinning (`E1`–`E4` Gate)

Your portfolio already tags systems by execution maturity—such as `STRANGLER-IPU (E3 Sim)` versus `SPARK Capstone (E4)` and `BiasAperture (E4)`. Adding an explicit **Epistemic Maturity Rule** inside `SKILL.md` prevents overclaiming:

* **`E1` (Conceptual / Brainstorm)**: Hypothesis-driven verbs (*proposes, models, bounds theoretically*). Must state what physical or empirical test will falsify the design.
* **`E2` (Prototype / Breadboard)**: Component-level bench validation. Must separate isolated module tests from end-to-end system claims.
* **`E3 Sim` (Cycle / Numerical Simulation)**: Mandatory qualifier on all metrics (*"In cycle-accurate simulation under CXL 3.0 pooled memory assumptions..."*). Never use hardware-verified verbs without the simulation qualifier.
* **`E4` (Physical Hardware / Production Verified)**: Unqualified deterministic verbs permitted (*eliminates, bounds, achieves*), backed by hardware traces, commit SHAs, or full dataset splits.

## 3. Upgraded `SKILL.md` (`v2.1.0`) Multi-Axis Router & Use-Case Overlay

Drop this upgraded routing architecture directly into **Section 2** and **Section 3** of the `v2.0.0` `SKILL.md` we drafted earlier:

Markdown

```
## 2. 2D Pre-Flight Decision Gate: Depth Tier (L1–L5) × Use Case (U1–U5)

Every writing task must be classified along two orthogonal axes before drafting:
1. **Surface Depth Tier (`L1`–`L5`)**: Determines structural template, word budget, and orchestration mode.
2. **Use-Case Archetype (`U1`–`U5`)**: Determines what constitutes valid empirical proof, required schema artifacts, and downstream ecosystem hooks.

### Axis 1: Surface Depth Tiers (`L1`–`L5`)
| Tier | Surface & Intent | Word Count | Default Execution Mode | Loaded Structural Reference |
| :--- | :--- | :--- | :--- | :--- |
| **`L1`** | **Micro-Surface**: Issue specs, PRs, commit notes, 3-bullet portfolio blurbs. | 100–300 | Solo Fast-Path (0 files) | Execute inline via Sections 3 & 4. |
| **`L2`** | **Editorial Narrative**: Sim-to-real post-mortems, engineering blog posts, build logs. | 800–1,500 | Solo Direct | `references/narrative-and-case-studies.md` |
| **`L3`** | **Technical Spec**: Firmware/hardware contracts, MCP tool schemas, migration guides. | 1,000–3,000 | Solo Direct | `references/migration-and-developer-specs.md` |
| **`L4`** | **Empirical Evaluation**: Quantization ablations, architecture simulation benchmarks. | 2,000–5,000 | Solo or `/agent-teams` | `references/benchmarks-and-ablations.md` |
| **`L5`** | **System Audit & Dossier**: Regulatory compliance dossiers, full thesis/capstone reports. | 5,000–30,000+ | `/agent-teams` or `/fleet-orch` | `references/audits-governance-and-safety.md` |

### Axis 2: Domain Use-Case Overlays (`U1`–`U5`)
Apply the proof standard and linter flag matching the target system's domain:

| Code | Use-Case Domain | Canonical Anchors (`AaradhyaDT`) | Mandatory Proof & Metric Standard | Required Ecosystem Hook & Linter Flag |
| :--- | :--- | :--- | :--- | :--- |
| **`U1`** | **Embedded, Robotics & CAD** | `SPARK` (E4), `GCSBR`, `Fusion 360 MCP`, `rhino-mcp` | Pin MCU/clock (`ESP32-S3`), SRAM/Flash bytes, sampling rate (`200 Hz`), ISR latency, and physical/FDM tolerances (`0.5 mm`, `TPU 95A`). | Enforce unit spacing for `super-nlm`; run `--domain embedded`. |
| **`U2`** | **Architecture & Network Sim** | `STRANGLER-IPU` (E3 Sim), `epanet-mcp` | Pin simulator assumptions, line-rate (`6G sub-THz`), interconnect spec (`CXL 3.0`), queue depth, and tail latency ($p99$). | Enforce `E3 Sim` epistemic qualifiers; run `--domain arch-sim`. |
| **`U3`** | **Applied ML & Fairness Audit** | `BiasAperture` (E4), Fuse AI Fellowship | Pin dataset split (`FairFace`), precision (`FP32` vs `INT8`), 95% bootstrap CIs, `SHAP`/`AIF360` parity metrics, and cohort size $N$. | Enforce `compliance-report-harmonizer` ($n < 30$ `.badge-guard`); run `--domain ml-audit`. |
| **`U4`** | **AI Infra, DSP & MCP Servers** | `Claude Desktop DSP`, `typora-mcp`, `localsend-mcp`, `google-classroom-mcp` | Provide deterministic JSON-RPC / MCP input-output schemas, token-cost deltas, idempotency guarantees, and failure codes. | Enforce copy-pasteable JSON schema diffs; run `--domain mcp-infra`. |
| **`U5`** | **Knowledge Graph & Portfolio** | `super-nlm`, `graphify`, `portfolio-project-manager`, `aaradhyadt.github.io` | Pair 3 active-verb impact bullets with `[[wikilinks]]`, `schema.org` JSON-LD, and synchronized maturity badges (`E3 Sim`, `E4`). | Sync status across GitHub & `aaradhyadt.github.io`; run `--domain knowledge`. |

---

## 3.4 Epistemic Maturity Calibration (`E1`–`E4` Hardware/Simulation Gate)

Never allow prose to overstate the physical readiness of a system. Match verb certainty to the project's maturity tag:
- **`E1` (Brainstorm / Architecture Proposal)**: Use *models, proposes, targets, bounds theoretically*. Explicitly list unverified physical assumptions.
- **`E2` (Bench Prototype / Isolated Module)**: State which subsystem is hardware-verified and which remains stubbed or mocked.
- **`E3 Sim` (Cycle / Numerical Simulation — e.g., `STRANGLER-IPU`)**: Prefix performance claims with explicit simulation scope (*"Under cycle-accurate CXL 3.0 simulation..."*). Ban unqualified hardware verbs.
- **`E4` (Physical / Production Verified — e.g., `SPARK`, `BiasAperture`, `GCSBR`)**: Use deterministic verbs (*eliminates, bounds, achieves*) backed by physical traces, commit SHAs, or full evaluation splits.
```

## 4. Interactive Use-Case & Tier Routing Explorer

Use the interactive matrix below to test how selecting a **Surface Depth Tier (`L1`–`L5`)** and **Use-Case Archetype (`U1`–`U5`)** dynamically reconfigures the required proof standard, epistemic maturity gate, loaded reference file, and `audit_calm_writing.py` CLI invocation across your ecosystem:

> **Key takeaway for `audit_calm_writing.py`**: By passing `--domain <embedded|arch-sim|ml-audit|mcp-infra|knowledge>` alongside `--tier <L1..L5>`, your Python linter won't falsely penalize a `Fusion 360 MCP` schema guide for lacking confidence intervals, and won't let an `E3 Sim` report on `STRANGLER-IPU` pass if it uses unqualified hardware-verification verbs.

Choose how you want to wire this 2D use-case adaptation into your local files:

Upgrade audit\_calm\_writing.py with --domain and E1-E4 checks

Generate references/ecosystem-compatibility.md for all U1-U5 tools

Map my brainstorm repo tree into SKILL.md

---

## Turn 5

### User

it is public

### Assistant

The "Danger Zone" in your settings confirms `[github.com/Aaradhya-Dev-Tamrakar/brainstorm](https://github.com/Aaradhya-Dev-Tamrakar/brainstorm)` is public ("This repository is currently public."). The reason it didn't surface earlier is search-engine indexing lag on the repository's internal file tree rather than your visibility settings. 

JPG+ 1

Your screenshot also reveals an important architectural detail across your open browser tabs: 

JPG

* **Dual-Namespace Split (`Aaradhya-Dev-Tamrakar` vs. `AaradhyaDT`)**: Your open tabs show `AaradhyaDT/BiasAp...` and `AaradhyaDT/Gestu...` hosted under **`AaradhyaDT`**, while `[github.com/Aaradhya-Dev-Tamrakar/brainstorm/settings](https://github.com/Aaradhya-Dev-Tamrakar/brainstorm/settings)` (along with `SPARK`) lives under **`Aaradhya-Dev-Tamrakar`**. 

  JPG
* **How We Should Handle This in `SKILL.md`**:

  1. **If this split is intentional** (e.g., `Aaradhya-Dev-Tamrakar` is your active R&D/workspace namespace for `brainstorm` and `SPARK`, while `AaradhyaDT` is your curated release namespace for `BiasAperture` and `Gesture-Controlled-Self-Balancing-Robot`), we must **revert the namespace overwrite** from `v2.0.0` so `SKILL.md` preserves `[github.com/Aaradhya-Dev-Tamrakar/SPARK](https://github.com/Aaradhya-Dev-Tamrakar/SPARK)` and `[github.com/Aaradhya-Dev-Tamrakar/brainstorm](https://github.com/Aaradhya-Dev-Tamrakar/brainstorm)` accurately. 

     JPG+ 1
  2. **If you want a single unified namespace**, you can use the **Transfer ownership** button visible right below "Disable branch protection rules" in your screenshot's Danger Zone to move `brainstorm` and `SPARK` to `AaradhyaDT` (or vice versa). 

     JPG

### How to Wire `brainstorm` Into `SKILL.md` Right Now

Because web search hasn't indexed the files inside `[github.com/Aaradhya-Dev-Tamrakar/brainstorm](https://github.com/Aaradhya-Dev-Tamrakar/brainstorm)` yet, paste your `README.md` or run this one-liner in PowerShell inside your local `brainstorm` directory and paste the output here: 

JPG

PowerShell

```
Get-ChildItem -Depth 2 -Exclude .git,node_modules,__pycache__ | Select-Object FullName
```

*(Or run `tree /F /A` if you want the full file tree).*

Once you drop the directory tree or `README.md` here—and let me know whether you want to keep both GitHub namespaces (`Aaradhya-Dev-Tamrakar` and `AaradhyaDT`) distinct—I will wire the exact `brainstorm` folders, workflows, and use-case rules directly into `SKILL.md`. 

JPG

---

## Turn 6

### User

it is intentional

### Assistant

Keeping the two GitHub namespaces separate turns what looked like a link inconsistency into a clean **lifecycle boundary** between active R&D and finalized releases:

* **`Aaradhya-Dev-Tamrakar` (Active R&D, Ideation & In-Flight Systems)**: Houses `brainstorm` (`[https://github.com/Aaradhya-Dev-Tamrakar/brainstorm](https://github.com/Aaradhya-Dev-Tamrakar/brainstorm)`) and `SPARK` (`[https://github.com/Aaradhya-Dev-Tamrakar/SPARK](https://github.com/Aaradhya-Dev-Tamrakar/SPARK)`). This namespace operates across early architectural exploration (`E1`–`E3`) and active hardware-firmware integration (`E4` in-flight), where issues automatically close as linked pull requests merge. 

  JPG+ 1
* **`AaradhyaDT` (Curated Production & Archival Showcase)**: Houses `BiasAperture` (`[https://github.com/AaradhyaDT/BiasAperture](https://github.com/AaradhyaDT/BiasAperture)`) and `Gesture-Controlled-Self-Balancing-Robot` (`[https://github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot](https://github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot)`). This namespace represents locked, submission-ready or completed `E4` deliverables backed by finalized empirical datasets and hardware benchmarks. 

  JPG+ 1

## Why `brainstorm` Unlocks the Missing Use Case (`U0`)

If `SKILL.md` demands finalized benchmarks or hardware traces on every document, the skill becomes unusable inside `[github.com/Aaradhya-Dev-Tamrakar/brainstorm](https://github.com/Aaradhya-Dev-Tamrakar/brainstorm)`. When you are brainstorming a new architecture or scoping an ecosystem tool, you do not have post-hoc experimental measurements yet. 

JPG

To adapt to `brainstorm` without losing "calm engineering authority," the skill needs a dedicated **`U0` (Systems Ideation & Architecture Exploration)** mode where proof shifts from *post-hoc measurements* to *first-principles bounding*:

1. **Back-of-the-Envelope (BotE) Feasibility Bounds**: Replace measured benchmarks with theoretical ceilings (e.g., I2C bus saturation limits at 400 kHz, SRAM tensor arena budgets on ESP32-S3, or token-context latency bounds).
2. **Explicit Falsification Criteria**: Instead of reporting a finished p-value or oscilloscope trace, state the exact bench test or simulation metric that would *kill* or validate the proposed design.
3. **Rejected Alternatives Matrix**: Document why competing architectures were ruled out before writing code.

## Complete Upgraded `SKILL.md` (`v2.2.0` — Multi-Use-Case & Dual-Namespace)

Drop this complete `v2.2.0` specification into your `SKILL.md`. It locks in both GitHub namespaces, adds the 2D `(Tier × UseCase)` router (`L1`–`L5` ×\times× `U0`–`U5`), and enforces the `E1`–`E4` epistemic maturity gate:

Markdown

```
---
name: writing-like-claude
description: This skill should be used when the user asks to "write like claude", "write an engineering blog post", "write a release report", "draft a system card", "create a technical announcement", "write a developer migration guide", "audit technical writing", "write a case study", "brainstorm an architecture spec", or mentions drafting publications, benchmarks, hardware/ML specs, or safety/fairness dossiers in a calm-authority engineering voice.
version: 2.2.0
---

# Writing Like Claude — The Calm Authority Engineering Standard (v2.2)

This skill codifies a mechanism-first, zero-hype technical writing standard that adapts dynamically across the full engineering lifecycle: from early-stage systems ideation (`brainstorm`) and active firmware issue specs (`SPARK`) to sim-to-real robotics post-mortems (`GCSBR`) and regulatory fairness dossiers (`BiasAperture`).

---

## 1. Core Philosophy: The Whiteboard Test & Empirical Proof

The foundation of high-trust technical communication is **calm authority**:
> **Write as though you are mapping a real system for a sharp colleague at a whiteboard, or submitting an unredacted technical disclosure to a rigorous auditor. State the physical or computational constraint, explain the mechanism that resolves it, and anchor the outcome in either verifiable data (`E3`/`E4`) or falsifiable first-principles bounds (`E1`/`E2`).**

Trust is governed by an immutable relationship:
$$\text{Trust} = \text{Precision} + \text{Scope Boundaries} + \text{Calibrated Proof}$$

### The Three Pillars
1. **Functional Precision**: Define systems by their mechanical inputs, state transitions, and outputs rather than promotional abstractions.
2. **Explicit Scope Boundaries**: Proactively declare what the system *cannot* do. Stating non-goals, hardware/runtime bottlenecks, and unsupported failure modes is the strongest signal of engineering credibility.
3. **Stage-Calibrated Proof**: Match the proof standard to the system's lifecycle state—using first-principles capacity envelopes and falsification criteria during ideation (`E1`–`E2`), cycle-accurate qualifiers in simulation (`E3 Sim`), and measured hardware/dataset traces in production (`E4`).

---

## 2. 2D Pre-Flight Router: Depth Tier (L1–L5) × Use-Case Domain (U0–U5)

Before drafting, resolve the task's **2D routing coordinate `(Tier, UseCase)`**:
- **Axis 1 (`L1`–`L5`)** governs document length, structural template, and execution posture.
- **Axis 2 (`U0`–`U5`)** governs domain-specific proof standards, required technical artifacts, and ecosystem hooks.

### Axis 1: Surface Depth Tiers (`L1`–`L5`)
| Tier | Surface & Intent | Word Count | Default Execution Mode | Loaded Structural Reference |
| :--- | :--- | :--- | :--- | :--- |
| **`L1`** | **Micro-Surface**: Issue specs, RFC stubs, PRs, commit notes, 3-bullet portfolio blurbs. | 100–300 | Solo Fast-Path (0 files) | Execute inline via Sections 3 & 4. |
| **`L2`** | **Editorial Narrative**: Sim-to-real post-mortems, engineering blog posts, build logs. | 800–1,500 | Solo Direct | `references/narrative-and-case-studies.md` |
| **`L3`** | **Technical Spec**: Architecture RFCs, firmware/hardware contracts, MCP tool schemas. | 1,000–3,000 | Solo Direct | `references/migration-and-developer-specs.md` |
| **`L4`** | **Empirical Evaluation**: Quantization ablations, control-loop & simulation benchmarks. | 2,000–5,000 | Solo or `/agent-teams` | `references/benchmarks-and-ablations.md` |
| **`L5`** | **System Audit & Dossier**: Regulatory compliance dossiers, full thesis/capstone reports. | 5,000–30,000+ | `/agent-teams` or `/fleet-orch` | `references/audits-governance-and-safety.md` |

### Axis 2: Domain Use-Case Overlays (`U0`–`U5`)
| Code | Use-Case Domain | Canonical Repository Anchor | Mandatory Proof & Artifact Standard | Linter Flag & Ecosystem Hook |
| :--- | :--- | :--- | :--- | :--- |
| **`U0`** | **Systems Ideation & Architecture RFCs** | `Aaradhya-Dev-Tamrakar/brainstorm` (`E1`–`E2`) | Back-of-the-envelope (BotE) resource bounds, rejected alternatives matrix, and explicit falsification test criteria. | `--domain brainstorm` (`graphify` `[[wikilinks]]`) |
| **`U1`** | **Embedded, Robotics & Parametric CAD** | `Aaradhya-Dev-Tamrakar/SPARK` (`E4` Building)<br>`AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot` (`E4` Completed) | Pin MCU/clock (`ESP32-S3`), SRAM/Flash bytes, sampling rate (`200 Hz`), ISR jitter, and FDM tolerances (`0.5 mm`, `TPU 95A`). | `--domain embedded` (`super-nlm` unit spacing) |
| **`U2`** | **Architecture & Network Simulation** | `STRANGLER-IPU` (`E3 Sim`), `epanet-mcp` | Pin simulator assumptions, line-rate (`6G sub-THz`), interconnect spec (`CXL 3.0`), queue depth, and $p99$ tail latency. | `--domain arch-sim` (Enforce `E3 Sim` qualifiers) |
| **`U3`** | **Applied ML & Fairness Auditing** | `AaradhyaDT/BiasAperture` (`E4` Submission-Ready) | Pin dataset split (`FairFace`), precision (`FP32` vs `INT8`), 95% bootstrap CIs, `AIF360`/`Fairlearn`/`SHAP` metrics, and sample size $N$. | `--domain ml-audit` ($n < 30$ `.badge-guard` suppression) |
| **`U4`** | **AI Infra, DSP & MCP Servers** | `Claude Desktop DSP`, `typora-mcp`, `localsend-mcp`, `Fusion 360 MCP` | Deterministic JSON-RPC / MCP input-output schemas, token-budget deltas, idempotency guarantees, and failure codes. | `--domain mcp-infra` (Runnable JSON schema diffs) |
| **`U5`** | **Knowledge Synthesis & Portfolio** | `aaradhyadt.github.io`, `super-nlm`, `graphify`, `portfolio-project-manager` | 3 active-verb impact bullets, `schema.org` JSON-LD blocks, Obsidian `[[wikilinks]]`, and synced lifecycle badges. | `--domain knowledge` (`scripts/add_project.py`) |

---

## 3. Whiteboard Rhetoric & Epistemic Calibration

### 3.1 The Constraint $\rightarrow$ Mechanism $\rightarrow$ Consequence Arc
Never introduce a module by listing its features in isolation:
1. **Constraint**: State the physical, mathematical, or operational bottleneck first (e.g., *"Polling the MPU6050 on the main loop introduces I2C jitter above 200 Hz"*).
2. **Mechanism**: Explain how the transformation works under the hood (e.g., *"Offloading sample acquisition to a hardware timer ISR decouples sensor reads from TFLite Micro inference"*).
3. **Consequence**: Close with the measured outcome or bounded envelope (e.g., *"Frame-drop variance falls to zero across a 10-minute stress window"*).

### 3.2 Concrete Trace Before Abstract Law
Anchor the reader in a concrete failure log, register state, JSON payload, or physical oscillation before stating the general architectural principle.

### 3.3 Epistemic Maturity Gate (`E1`–`E4` Verb Calibration)
Match verb certainty strictly to the project's maturity state:
- **`E1` (Conceptual / `brainstorm` RFC)**: Use *models, proposes, targets, bounds theoretically*. Must include a **Falsification Gate** stating what physical measurement or benchmark will invalidate the design.
- **`E2` (Bench Prototype / Isolated Module)**: State explicitly which subsystem is hardware-verified and which remains mocked or stubbed.
- **`E3 Sim` (Cycle / Numerical Simulation — e.g., `STRANGLER-IPU`)**: Prefix performance claims with explicit simulation scope (*"Under cycle-accurate CXL 3.0 simulation..."*). Never use unqualified hardware-completion verbs.
- **`E4` (Physical Hardware / Full Dataset Verified — e.g., `SPARK`, `BiasAperture`, `GCSBR`)**: Use deterministic verbs (*eliminates, bounds, guarantees, reduces*) backed by physical traces, commit SHAs, or full evaluation splits.

---

## 4. The 10 Universal Invariant Writing Rules

1. **Title = Statement of Factual State**: Use a declarative sentence or precise noun phrase stating what exists, what changed, or what trade-off is bounded. Never use clickbait, listicles, or rhetorical questions.
2. **1-Sentence Empirical or Bounding Thesis**: Open with a self-contained thesis stating the core mechanism and either its quantifiable outcome (`E3`–`E4`) or its theoretical capacity envelope (`E1`–`E2`).
3. **Dual Lexical & Syntactic Anti-AI Blacklist**:
   - **Lexical Ban**: Prohibit promotional superlatives (*revolutionary, game-changing, groundbreaking, unleash, supercharge, seamless, cutting-edge, magic, effortlessly, next-gen, robust, delve*). Consult `references/vocabulary_cheatsheet.md`.
   - **Syntactic Ban**: Prohibit negation-contrast clichés (*"It's not X—it's Y"*, *"Not selling. Just explaining."*), hollow participial tail clauses (*"...ensuring high reliability and enabling seamless scaling"*), verb nominalizations (*"performs quantization of"* $\rightarrow$ *"quantizes"*), and compulsive three-item adjective lists.
4. **Functional Precision in Definition**: Define any mechanism, component, or pipeline stage in 10 to 20 concrete words stating its input, transformation, and output.
5. **Explicit Scope Boundaries & Non-Goals**: Dedicate explicit prose to what the system *does not* do. Declare unsupported hardware configurations, rejected design alternatives (`U0`), and out-of-distribution failure modes prominently.
6. **Controlled Baselines & Environmental Pinning**: Always pin the execution or modeling environment (MCU clock/SRAM, simulator parameters, precision format `FP32` vs. `INT8`, dataset split, sample size $N$, and baseline comparator).
7. **Multi-Objective Tradeoff & Pareto Transparency**: Never report a gain in one metric without stating its cost in another (e.g., accuracy vs. INT8 SRAM footprint, balancing response vs. stepper resonance, or throughput vs. tail latency).
8. **Causal Flow & Cadence Variance**:
   - Keep one primary claim per paragraph (2 to 5 sentences).
   - Connect sentences via explicit cause-and-effect transitions (*because, consequently, when, whereas*) rather than meta-signposting (*"In this section, we will discuss..."*).
   - Vary sentence length: follow a complex multi-clause mechanical explanation with a short declarative consequence.
9. **Deterministic, Verifiable Artifacts**: Code blocks, firmware snippets, and CLI invocations must be copy-pasteable and runnable. Architecture and MCP specs (`U4`) must include concrete before/after configuration or JSON schema diffs.
10. **Actionable Next Steps over Redundant Summaries**: Never restate the introduction in the conclusion. Conclude with reproducible CLI commands, issue/PR pointers, falsification experiments (`U0`), or open engineering questions.

---

## 5. Intentional Dual-Namespace Governance (`Aaradhya-Dev-Tamrakar` vs. `AaradhyaDT`)

The author maintains an intentional two-namespace GitHub architecture separating active R&D workspaces from curated production releases. **Never rewrite or normalize URLs across namespaces:**

### Namespace A: `Aaradhya-Dev-Tamrakar` (Active R&D, Ideation & In-Flight Capstone)
1. **`brainstorm` (`E1`–`E2` — Ecosystem Ideation, RFCs & Architecture Exploration)**:
   - **Canonical URL**: `https://github.com/Aaradhya-Dev-Tamrakar/brainstorm`
   - **Default Routing**: `(L1–L3, U0)`
   - **Role**: Staging ground for multi-domain system designs, trade-off matrices, and tool orchestration workflows before promotion to standalone repositories.
2. **`SPARK` (`E4 Building` — Edge AI Wearable & Firmware Integration)**:
   - **Canonical URL**: `https://github.com/Aaradhya-Dev-Tamrakar/SPARK` (Issue Tracker: `https://github.com/Aaradhya-Dev-Tamrakar/SPARK/issues`)
   - **Default Routing**: `(L1/L3/L4, U1)`
   - **Role**: Active 8th-semester senior thesis developing a two-layer wearable fall-detection system (ESP32-S3, 200 Hz MPU6050 IMU, INT8 TFLite Micro 1D-CNN, MQTT/BLE telemetry, TPU 95A enclosure, SHAP explainability). Issues auto-close via merged linked PRs.

### Namespace B: `AaradhyaDT` (Curated Production, Release & Portfolio Namespace)
3. **`BiasAperture` (`E4 Submission-Ready` — Algorithmic Fairness & Regulatory Auditing)**:
   - **Canonical URL**: `https://github.com/AaradhyaDT/BiasAperture`
   - **Default Routing**: `(L4/L5, U3)`
   - **Role**: Five-module demographic fairness auditing pipeline for vision classifiers (`FairFace`, `UTKFace`) using `AIF360`, `Fairlearn`, and `SHAP`, mapped to EU AI Act and NIST AI RMF compliance gates with $n < 30$ cohort suppression.
4. **`Gesture-Controlled-Self-Balancing-Robot` (`E4 Completed` — Control Systems & Robotics)**:
   - **Canonical URL**: `https://github.com/AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot`
   - **Default Routing**: `(L2/L4, U1)`
   - **Role**: Completed hardware-verified two-wheeled self-balancing robot (C++ PID control, MPU6050 sensor fusion, DRV8825 stepper actuation, MediaPipe gesture routing) documenting the MATLAB-to-hardware transfer and turn-induced pitch stabilization.

---

## 6. Adaptive Execution Postures (Capability, Not Overhead)
```

[Task Scope]
├── Default (90% of tasks) ──> Solo Direct Execution (Immediate, zero subagents)
├── Explicit /agent-teams ───> Multi-Agent Team (Scout -> Reviewer -> Writer -> Lead)
└── Explicit /fleet-orch ───> Headless Batch Swarm (SKU DAG -> Pooled Workers -> Drive Sync)

```
1. **Mode 1: Solo Direct Execution (Default)**: Immediate execution for `L1`–`L3` tasks, `U0` brainstorming docs, and standard `L4` drafts.
2. **Mode 2: Multi-Agent Team Capability (`/agent-teams-orchestration`)**: For high-stakes `L4`/`L5` audits requiring adversarial verification (Scout $\rightarrow$ Reviewer $\rightarrow$ Writer). Consult `references/swarm-and-fleet-capabilities.md`.
3. **Mode 3: Fleet Swarm Capability (`/fleet-orchestrator`)**: Enqueues `assets/sku-templates/model_report_pack.json` into `orchestrator-state/tasks/`. Consult `references/swarm-and-fleet-capabilities.md`.

---

## 7. Ecosystem Compatibility Fast-Pointers

- **`compliance-report-harmonizer` (`U3`)**: Adhere to the 5-section hierarchy and suppress cohorts with $n < 30$ using `.badge-guard` and `<details class="insufficient-block">`.
- **`portfolio-project-manager` (`U5`)**: When onboarding tools via `scripts/add_project.py`, generate 3 active-verb, zero-hype bullet points matching Tier `L1` format and preserve exact namespace URLs (`Aaradhya-Dev-Tamrakar` vs. `AaradhyaDT`).
- **`github-workflow` (`U0`/`U1`)**: Use Tier `L1` format for `SPARK` and `brainstorm` issues and PR descriptions (declarative title, 1-sentence thesis, verification/falsification proof, explicit non-goals) so merged PRs cleanly close linked issues.
- **`super-nlm` (`U1`/`U5`)**: Include `schema.org` JSON-LD and LaTeX math blocks (with spaces before physical units, e.g., `200 Hz`, `0.5 mm`) for NotebookLM ingestion.
- **`graphify` (`U0`/`U5`)**: Connect `brainstorm` notes and research findings into the local Obsidian graph using `[[wikilinks]]`.

---

## 8. Deterministic Style Verification & Reference Tree

Audit any document against v2.2 standards (tier geometry, domain proof rules, syntactic anti-AI filters, and namespace preservation) via CLI:
```powershell
python "C:\Users\Aaradhya\.gemini\config\skills\writing-like-claude\scripts\audit_calm_writing.py" --tier L3 --domain embedded <path-to-file.md>
```

### Consolidated Reference Guides (`references/`)

* **`references/vocabulary_cheatsheet.md`** — Banned lexical hype list, banned syntactic AI patterns, and mechanical replacements.
* **`references/narrative-and-case-studies.md`** — `L2` structural formulas for engineering post-mortems (`GCSBR`) and architecture narratives.
* **`references/migration-and-developer-specs.md`** — `L3` RFCs (`brainstorm`), firmware contracts (`SPARK`), and MCP tool schemas (`U4`).
* **`references/benchmarks-and-ablations.md`** — `L4` pinned baseline tables, quantization/latency Pareto frontiers, and simulation bounds.
* **`references/audits-governance-and-safety.md`** — `L5` fairness auditing (`BiasAperture`), EU AI Act / NIST AI RMF mapping, and n<30n < 30n<30 suppression protocols.
* **`references/swarm-and-fleet-capabilities.md`** — Execution protocols for `/agent-teams` and `/fleet-orchestrator`.
* **`references/ecosystem-compatibility.md`** — Complete integration SOPs across the interacting ecosystem skills.

### Ground-Truth Worked Examples (`examples/`)

* **`examples/l1-spark-issue-and-portfolio.md`** — `(L1, U1/U5)`: `SPARK` issue spec (`Aaradhya-Dev-Tamrakar/SPARK`) & 3-bullet portfolio manifest.
* **`examples/l2-gcsbr-sim-to-real-postmortem.md`** — `(L2, U1)`: `GCSBR` case study (`AaradhyaDT/Gesture-Controlled-Self-Balancing-Robot`).
* **`examples/l3-spark-edge-telemetry-spec.md`** — `(L3, U0/U1)`: `brainstorm` RFC →\rightarrow→ `SPARK` 200 Hz IMU-to-TFLite Micro interface contract.
* **`examples/l4-spark-quantization-benchmarks.md`** — `(L4, U1)`: `SPARK` FP32 vs. INT8 1D-CNN Pareto evaluation on ESP32-S3.
* **`examples/l5-biasaperture-eu-ai-act-audit.md`** — `(L5, U3)`: `BiasAperture` demographic fairness dossier (`AaradhyaDT/BiasAperture`).

```
---

Would you like to upgrade `audit_calm_writing.py` next so it enforces `--domain` (`brainstorm`, `embedded`, `arch-sim`, `ml-audit`, `mcp-infra`, `knowledge`) and verifies that `Aaradhya-Dev-Tamrakar` and `AaradhyaDT` links aren't accidentally cross-rewritten, or would you like to paste your local `brainstorm` folder structure to map its internal subdirectories into `U0`?
```

---
