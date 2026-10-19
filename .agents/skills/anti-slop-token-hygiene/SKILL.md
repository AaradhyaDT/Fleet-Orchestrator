---
name: anti-slop-token-hygiene
description: >-
  This skill should be used when the user asks to "audit context degradation", "strip AI slop",
  "sanitize prompt tokens", "clean thinking traces", "audit decorative emojis", "screen LLM output bloat",
  "calibrate reasoning budget", "optimize KV cache SNR", or mentions preventing token degradation across
  frontier models (Gemini 3.8 Flash, Claude Opus 5.5, GPT-6 Astra, Gemini 4 Argon, Muse Wonder, DeepSeek-R1).
version: 1.0.0
---

# Anti-Slop & Token Hygiene Skill

## Purpose & Scope
This skill provides deterministic workflows, mathematical checks, and automated screening to protect agent contexts, KV caches, and repository artifacts from **Token Degradation Factors** and **AI Slop**.

It is calibrated against contemporary frontier systems:
- **Google DeepMind**: `Gemini 3.8 Flash` (1M Context, tunable thinking levels), `Gemini 4 Argon` (1M Context enterprise)
- **Anthropic**: `Claude Opus 5.5`, `Claude Sonnet 5.5` (Hybrid thinking)
- **OpenAI**: `GPT-6 Astra`, `GPT-6.1 Sol / Luna` (Native computer-use)
- **Meta**: `Muse Wonder` / `Muse Wonder Full` (Active Focus / Active Memory)
- **Open-Weight / Pure RL**: `DeepSeek-R1` (671B MoE)

---

## 1. When to Activate This Skill
Trigger this skill whenever:
- Preparing high-context multi-turn agent prompts or system rules.
- Reviewing or cleaning transcripts, documentation, RFCs, or PR descriptions.
- Auditing prompt templates for decorative emoji fragmentation (`⚡`, `✨`, `🚀`).
- Configuring reasoning budgets (`LOW`, `MEDIUM`, `HIGH`) on Gemini 3.8 Flash or Claude hybrid models.
- Purging intermediate `<think>` traces or raw terminal stdout from agent memory.

---

## 2. The 6 Token Degradation Vectors & Mitigation Protocols

### Vector 1: Multi-Byte Tokenizer Splitting (Emojis & Glyphs)
- **Degradation**: Emojis like `⚡` (Unicode `U+26A1`), `✨` (`U+2728`), or composite emoji with variation selectors fragment into 1–4 distinct byte tokens, burning attention budget on non-semantic bytes.
- **Rule**: Strictly 0 decorative emojis in technical documentation, code comments, commit messages, and agent instructions. Use standard markdown, ASCII markers, or KaTeX math.

### Vector 2: Attention Smearing & Softmax Entropy Spike
- **Degradation**: High-frequency corporate buzzwords (*delve*, *testament to*, *beacon*, *evolving landscape*, *not only... but also*, *robust synergy*) create high-probability surface sinks in self-attention heads, diluting the attention weight on true needle keys ($k_{\text{target}}$).
- **Rule**: Enforce the canonical lexical blacklist. Replace with domain-specific nouns and active verbs.

### Vector 3: Reasoning Bloat & In-Context KV Cache Poisoning
- **Degradation**: Appending raw `<think>` traces from prior turns into conversation history causes models to attend to their own discarded hypotheses and false starts, increasing hallucination rates in Turn $N+1$.
- **Rule**: **Always strip `<think>...</think>` traces** before pushing assistant responses back into multi-turn agent history.

### Vector 4: Model-Specific Behavioral Quirks
- **Gemini 3.8 Flash**:
  - *Quirk*: Hierarchical satiation (unsolicited 5-part textbook breakdowns) and speed-over-depth premature halting in `LOW` thinking mode.
  - *Fix*: Pass `max_output_tokens: 2048` on atomic file edits; use `MEDIUM` thinking for complex refactoring; inject: `"Omit overview, prerequisites, and conclusion; emit only raw code."`
- **Claude Opus 5.5**:
  - *Quirk*: Tunnel-vision scope creep (refactoring 5 adjacent files and adding unwanted factory/adapter abstractions for a 2-line fix).
  - *Fix*: Inject strict boundaries: `"You are strictly restricted to editing lines X to Y of TargetFile. Do not introduce new abstractions."`
- **GPT-6 Astra**:
  - *Quirk*: Presumptuous UI automation and compulsive corporate callout boxes (`> [!NOTE]`).
  - *Fix*: Request `--diff-only` or raw JSON payloads.
- **Meta Muse Wonder**:
  - *Quirk*: Cross-session memory bleed and patch-on-patch death spirals.
  - *Fix*: Enforce clean-room branch isolation and reset session context per task.

### Vector 5: Stdout & Tool Output Bloat
- **Degradation**: Passing 300 lines of raw compiler or test runner stdout saturates context limits and buries error traces.
- **Rule**: Truncate tool output to a maximum of 30 lines (Top 10 lines + truncation ellipsis + Bottom 20 lines).

### Vector 6: In-Context Noise Mirroring
- **Degradation**: High-context models (Gemini 3.8 Flash, Gemini 4 Argon) mirror prompt slang and informal punctuation back at double frequency.
- **Rule**: Sanitize input prompts before dispatch.

---

## 3. Operational CLI Screening Workflow

Run the automated token degradation scanner in `Fleet-Orchestrator`:

```powershell
# Audit a single file
python f:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator\tools\screen_token_degradation.py --file path/to/doc.md

# Audit entire workspace
python f:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator\tools\screen_token_degradation.py --all

# Automatically sanitize emojis, thinking traces, and slop
python f:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator\tools\screen_token_degradation.py --all --fix
```

---

## 4. Anti-Slop System Prompt Template

Inject this snippet into agent system prompts when zero-degradation output is required:

```markdown
### Token Density & Anti-Degradation Constraints
1. Zero Decorative Emojis: Strictly ban ⚡, ✨, 🚀, 🧠, 💡, 🔥.
2. Lexical Blacklist: Never use 'delve', 'testament', 'beacon', 'tapestry', 'evolving landscape', 'not only... but also', 'robust synergy', 'holistic'.
3. Scope Invariant: Modify only the specified lines in the target file. Do not introduce unrequested abstractions or refactor adjacent files.
4. Output Discipline: Omit introductory conversational filler and summary bookends ("In conclusion", "Ultimately"). Terminate immediately when the code/proof is complete.
```
