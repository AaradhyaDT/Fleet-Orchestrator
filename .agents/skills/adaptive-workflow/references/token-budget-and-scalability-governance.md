# Token Budget & Scalability Governance (`adaptive-workflow`)

This reference formalizes the mathematical token budget ceilings, progressive disclosure hierarchy, and real-time grounding protocols for the `adaptive-workflow` meta-orchestrator.

---

## 1. Mathematical $O(1)$ Context Scaling (`INV-SCALE-O1`)

In expanding ecosystems (growing from 28 to 200+ modules), naive prompt inclusion results in linear $O(N)$ context growth, quickly exhausting context windows and driving token costs.

`adaptive-workflow` guarantees $O(1)$ context consumption ($<2,000$ tokens overhead) through strict modular boundaries:
- **Lead Context Ceiling**: The primary chat context remains strictly under $5,000$ tokens.
- **Payload Bounding**: Task delegation specifications passed to subagents must not exceed $500$ tokens.
- **Manifest Compression**: Subagents must return an executive manifest of strictly $<300$ words ($<450$ tokens), leaving detailed stdout, test tracebacks, and worktree artifacts on disk.

```
Total Context = C_base + C_lead_triage (<= 200 tokens) + C_subagent_manifest (<= 450 tokens) = O(1)
```

---

## 2. Real-Time Internet Grounding Protocol (`INV-REALTIME-GROUNDING`)

To overcome model pre-training cutoff limitations and prevent trial-and-error CLI flapping:

### Gated Activation Trigger
Real-time web grounding via `tools/web_grounder.py` is strictly gated and triggers ONLY when:
1. An explicit `--ground` or `-g` flag is passed.
2. A task involves an external SDK marked with recent breaking changes (e.g. `google-genai`).
3. A local tool execution returns non-zero due to unrecognized arguments or import syntax errors.

### Discovery-to-Cache Flywheel
1. **Query**: `tools/web_grounder.py` queries upstream structured APIs (PyPI JSON API, authenticated `gh api`, host CLI `--version`) with a 5-second socket timeout.
2. **Atomic Persistence**: Discovered versions, headless flags, and syntax contracts are written atomically to `orchestrator-state/grounding_cache.json`.
3. **Decoupled Isolation**: Grounding discoveries are strictly separated from `orchestrator-state/exemplars.json` to prevent semantic degradation of intent classification similarity.
4. **Subsequent Invocations**: Subsequent executions read `grounding_cache.json` in $<0.5\text{ms}$ at 0 tokens and 0 network requests.

---

## 3. Zero-Help Loop Syntax Contract (`INV-ZERO-HELP-LOOP`)

Models that guess CLI flags frequently trigger command failures, prompting them to dump full `--help` walls (500–1,000 tokens) and retry, tripling token burn.

`tools/adaptive_engine.py` eliminates this flapping:
1. **Smart Argument Normalizer**: Automatically maps aliases before parsing:
   - `-f`, `--file` $\to$ `--files`
   - `-j` $\to$ `--json`
   - `-e` $\to$ `--execute`
   - `-g`, `--live` $\to$ `--ground`
   - `-d`, `--model` $\to$ `--decider`
   - Strips leading positional verbs (`triage`, `route`).
2. **Compact `--schema`**:
   `python tools/adaptive_engine.py --schema` outputs the machine-readable CLI schema in $<50$ tokens of JSON, bypassing multi-page help texts.
3. **Help Interception**:
   Passing `-h` or `--help` prints a concise, 10-line syntax table ($<60$ tokens).

---

## 4. 3-Tier Progressive Disclosure (`INV-PROG-DISCLOSURE`)

To prevent cognitive clutter, agents load documentation strictly on demand:
- **Tier 1 (Base Triage)**: Agents inspect `SKILL.md` only ($\le 8,192$ bytes / $\approx 2,000$ tokens).
- **Tier 2 (Domain Specialization)**: When delegating to specific domains (e.g., hardware DSP, fellowship ML), agents load at most 1 specialized reference document (e.g., `skill-matrix.md`).
- **Tier 3 (Error Diagnostics)**: Full diagnostic references (e.g., `transactional-recovery.md`, `dynamic-flight-envelope.md`) are loaded exclusively when an explicit runtime exception occurs.

---

## 5. Subagent Manifest Template (`INV-CTX-FIREBREAK`)

All child subagents (`TypeName: 'self'`, `Role: 'Fleet Commander'`) must structure final delivery manifests according to this template ($\le 300$ words):

```markdown
### Executive Task Manifest
- **Task ID**: <id>
- **Status**: SUCCESS | FAILURE
- **Execution Tier**: Tier 0 / Tier 1C (Fleet) / Tier 1E (Colab)
- **Artifacts Created / Modified**:
  - `path/to/file1`
  - `path/to/file2`
- **Verification Gates**:
  - Tests: N passed, 0 failed
  - Invariants: Verified
- **Delivery Commit**: sync.bat SHA / PR link
```
Raw command tracebacks and build logs remain strictly on disk under `orchestrator-state/tasks/<task_id>.json`.
