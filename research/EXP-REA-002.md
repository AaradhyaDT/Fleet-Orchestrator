# EXP-REA-002: Qwen3.8-27B Uncensored (FastMTP) A100 Autonomous Agent & REA Server Provisioning

```text
Experiment ID:   EXP-REA-002
Evidence Tier:   EMPIRICALLY_VERIFIED (Google Colab A100-SXM4 / L4 Ada Lovelace)
Model ID:        HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF
Model Weights:   Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q5_K_P.gguf (20.22 GB)
Spec Draft:      Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf (903 MB)
Colab Notebook:  https://colab.research.google.com/drive/1x_x1B-a8XNHtEPi54XRAikQ4heR7rtaD
Local Notebook:  notebooks/qwen38_27b_uncensored_server.ipynb
Drive Folder:    Super-NLM > Fleet-Orchestrator (ID: 1wGq53okV7ZaFGSw2fWilEfxL4FEIVeIF)
Associated Tool: tools/a100_agent_bridge.py
Auto-Sync Tool:  tools/sync_endpoint.py (launcher: sync_endpoint.bat)
Evidence Media:  docs/screenshots/ (6 raw PNG captures)
```

---

## 1. Executive Summary

`EXP-REA-002` establishes a remote, high-performance, uncensored LLM inference engine on an **NVIDIA A100-SXM4** (with L4 Ada Lovelace compatibility) to serve as the reasoning backbone for:
1. **Autonomous Local Agent Workflows**: Interactive and batch code editing, refactoring, and agentic multi-turn loops via VS Code Continue (`Agent` mode), Cline (`Act/Agent` mode), Aider CLI, or Antigravity subagents.
2. **Reverse Engineering Anything (REA)**: Decompiling, deobfuscating, and reconstructing complex native PE/ELF binaries, Node Single Executable Applications (SEA), Electron ASAR packages, and proprietary cryptographic algorithms without commercial LLM refusal roadblocks (0/465 benchmark refusal score).
3. **Zero-Friction Option A Endpoint Auto-Sync**: Eliminates changing Cloudflare tunnel URLs across server reboots via automated Google Drive endpoint persistence, Windows clipboard auto-detection, and local configuration auto-patching (`sync_endpoint.bat`).

---

## 2. Infrastructure & Serving Architecture

```
[ Google Colab Cloud Accelerator (A100 SXM4 / 40-80GB) ]
 ├── llama-server (Compiled with CUDA + HauhauCS FastMTP patch)
 │    ├── Target Model: Qwen3.8-27B-Uncensored-Aggressive-Q5_K_P (65K context)
 │    ├── Speculative Draft: FastMTP 32K sidecar (depth: 3, ~3x TG speedup)
 │    └── Formatter: Jinja tool-calling & DeepSeek reasoning format
 └── Cloudflare Tunnel (cloudflared)
            │
            ▼ (Encrypted HTTPS Tunnel over Port 8088)
      https://<tunnel-id>.trycloudflare.com/v1
            │
            ├── Google Drive Sync (writes active_a100_endpoint.json)
            │
            ├── Laptop Auto-Sync: .\sync_endpoint.bat (Option A)
            │     ├── Patches ~/.continue/config.yaml (apiBase)
            │     ├── Updates .env.a100 (A100_API_BASE, CLINE_BASE_URL)
            │     └── Pings endpoint (/models) for health/latency confirmation
            │
            ├─────────────────────────────────────┬─────────────────────────────────────┐
            ▼                                     ▼                                     ▼
[ VS Code / Continue.dev (Laptop) ]     [ VS Code / Cline Extension ]         [ REA MCP Pipeline (Antigravity) ]
 - Mode: Agent                           - Mode: Act / Agent                   - Native Disassembly (Ghidra/R2)
 - Model: qwen3.8-27b                    - Provider: OpenAI Compatible         - PE Resources (NODE_SEA_BLOB)
 - Context: 65,536 tokens                - Reasoning Effort: High              - tools/a100_agent_bridge.py
```

---

## 3. Hardware Benchmarking & Memory Allocation

| Parameter | Measured Specification |
| :--- | :--- |
| **GPU Target** | NVIDIA A100-SXM4 (40GB / 80GB VRAM) or L4 (24GB VRAM) |
| **Memory Bandwidth** | 1,555 – 2,039 GB/s (A100) vs. 300 GB/s (L4) |
| **VRAM Footprint** | ~20.22 GB (Model) + ~0.90 GB (Draft) + ~4.2 GB (65K KV Cache @ Q8_0) $\approx$ 25.32 GB |
| **Speculative Decoding** | HauhauCS FastMTP (up to 3.02x document TG, 1.93x reasoning TG) |
| **Context Ceiling** | 65,536 tokens with FlashAttention-2 (`-fa on`) |
| **Sampler Defaults** | `temp: 0.2`, `top-p: 0.95`, `repeat-penalty: 1.05` (tuned for deterministic code reconstruction) |

---

## 4. Visual Evidence & Raw Screenshots

All 6 raw screenshot captures are indexed and verified under [`docs/screenshots/`](../docs/screenshots/):

1. **`01_continue_initial_config_yaml.png`**: Pre-existing Continue YAML configuration in VS Code with local Ollama, LM Studio, and Gemini endpoints.
2. **`02_continue_agent_mode_selected.png`**: Continue sidebar configured in `Agent` mode with `A100 Qwen3.8-27B Uncensored` selected.
3. **`03_continue_agent_plan_dropdown.png`**: Analysis of Continue UI warning badge (`⚠️`) for non-certified cloud models.
4. **`04_cline_openai_compatible_config.png`**: Cline settings pane configured with OpenAI-compatible API Provider, live tunnel URL, and High reasoning effort.
5. **`05_colab_cell4_live_execution.png`**: Live Colab A100 execution displaying Cloudflare URL (`https://domain-expansys-athletes-power.trycloudflare.com`) and FastMTP draft sidecar startup.
6. **`06_colab_auto_unassign_failure.png`**: Forensic evidence of the `if AUTO_UNASSIGN:` bypass bug in the user's video transcoding notebook, prompting `INV-COLAB-UNASSIGN-MANDATORY`.

---

## 5. Operational Invariants & Verification

1. **Deterministic Bridge**: Provided `tools/a100_agent_bridge.py` supporting both `--test` connectivity ping and `--analyze <file>` automated disassembly streaming.
2. **Option A Auto-Sync Tooling**: Created `tools/sync_endpoint.py` and `sync_endpoint.bat` supporting Drive sync, clipboard auto-detection, `--url` manual flag, and continuous `--watch` daemon mode.
3. **Persistence & Manifest Sync**: Registered in `drive-manifest.json` with file ID `1x_x1B-a8XNHtEPi54XRAikQ4heR7rtaD` and uploaded to Google Drive.
4. **Continue.dev Integration**: Configured in `C:\Users\Aaradhya\.continue\config.yaml` with roles `[chat, edit, apply]` and 65K context window; verified end-to-end in Agent mode.
5. **Cline Agent Integration**: Configured via OpenAI-compatible endpoint with model ID `./models/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q5_K_P.gguf`, high reasoning effort, and 65K–128K context window; confirmed operational in Act/Agent mode.
6. **Runtime Stability**: Port binding settled cleanly on `127.0.0.1:8088` with `-fa on` FlashAttention-2 flag handling and automated orphaned process cleanup (`pkill -9`). Cloudflare tunnel latency measured at ~1.16s for reasoning + response generation.
7. **Compute Teardown Governance (`INV-COLAB-UNASSIGN-MANDATORY`)**: All batch and training notebooks must unconditionally execute `runtime.unassign()` to destroy the cloud VM without conditional boolean guards.
