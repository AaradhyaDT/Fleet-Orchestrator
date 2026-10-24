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
```

---

## 1. Executive Summary

`EXP-REA-002` establishes a remote, high-performance, uncensored LLM inference engine on an **NVIDIA A100-SXM4** (with L4 Ada Lovelace compatibility) to serve as the reasoning backbone for:
1. **Autonomous Local Agent Workflows**: Interactive and batch code editing, refactoring, and agentic multi-turn loops via VS Code Continue (`Agent` mode), Aider CLI, or Antigravity subagents.
2. **Reverse Engineering Anything (REA)**: Decompiling, deobfuscating, and reconstructing complex native PE/ELF binaries, Node Single Executable Applications (SEA), Electron ASAR packages, and proprietary cryptographic algorithms without commercial LLM refusal roadblocks (0/465 benchmark refusal score).

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
            ▼ (Encrypted HTTPS Tunnel over Port 8080)
      https://<tunnel-id>.trycloudflare.com/v1
            │
            ├─────────────────────────────────────────────┐
            ▼                                             ▼
[ VS Code / Continue.dev (Laptop) ]           [ REA MCP Pipeline (Antigravity) ]
 - Mode: Agent                                 - Native Disassembly (Ghidra/Kuna)
 - Model: qwen3.8-27b                          - PE Resources (NODE_SEA_BLOB)
 - Context: 65,536 tokens                      - tools/a100_agent_bridge.py
```

---

## 3. Hardware Benchmarking & Memory Allocation

| Parameter | Measured Specification |
| :--- | :--- |
| **GPU Target** | NVIDIA A100-SXM4 (40GB / 80GB VRAM) or L4 (24GB VRAM) |
| **Memory Bandwidth** | 1,555 – 2,039 GB/s (A100) vs. 300 GB/s (L4) |
| **VRAM Footprint** | ~20.22 GB (Model) + ~0.90 GB (Draft) + ~4.2 GB (65K KV Cache @ Q8_0) $\approx$ 25.32 GB |
| **Speculative Decoding** | HauhauCS FastMTP (up to 3.02x document TG, 1.93x reasoning TG) |
| **Context Ceiling** | 65,536 tokens with FlashAttention-2 (`--flash-attn on`) |
| **Sampler Defaults** | `temp: 0.2`, `top-p: 0.95`, `repeat-penalty: 1.05` (tuned for deterministic code reconstruction) |

---

## 4. Operational Invariants & Verification

1. **Deterministic Bridge**: Provided `tools/a100_agent_bridge.py` supporting both `--test` connectivity ping and `--analyze <file>` automated disassembly streaming.
2. **Persistence & Manifest Sync**: Registered in `drive-manifest.json` with file ID `1x_x1B-a8XNHtEPi54XRAikQ4heR7rtaD` and uploaded to Google Drive.
3. **Continue.dev Integration**: Configured in `C:\Users\Aaradhya\.continue\config.yaml` with roles `[chat, edit, apply]` and 65K context window.
