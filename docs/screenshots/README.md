# Screenshot Evidence & Visual Artifacts Catalog: EXP-REA-002

This directory contains raw screenshot captures validating the end-to-end deployment, IDE client configuration, live Cloudflare tunnel routing, and runtime lifecycle governance for the **Qwen3.8-27B Uncensored (FastMTP) A100 Server**.

---

## Artifact Index

| File | Timestamp (NPT) | Dimensions | Resolution / Size | Primary Focus |
| :--- | :--- | :--- | :--- | :--- |
| [`01_continue_initial_config_yaml.png`](01_continue_initial_config_yaml.png) | 2026-10-24 19:12 | 1024 x 640 | 247.6 KB | Continue extension initial `config.yaml` showing local Ollama, LM Studio, and Gemini endpoints |
| [`02_continue_agent_mode_selected.png`](02_continue_agent_mode_selected.png) | 2026-10-24 19:14 | 1024 x 640 | 179.3 KB | Continue sidebar in VS Code configured in `Agent` mode targeting `A100 Qwen3.8-27B Uncensored` |
| [`03_continue_agent_plan_dropdown.png`](03_continue_agent_plan_dropdown.png) | 2026-10-24 19:46 | 577 x 189 | 17.4 KB | Experimental warning triage (`⚠️`) on Agent and Plan modes in Continue UI |
| [`04_cline_openai_compatible_config.png`](04_cline_openai_compatible_config.png) | 2026-10-24 19:57 | 1024 x 640 | 246.5 KB | Cline extension settings pane configured with OpenAI-compatible API Provider, Cloudflare tunnel URL, and High reasoning effort |
| [`05_colab_cell4_live_execution.png`](05_colab_cell4_live_execution.png) | 2026-10-24 19:59 | 1024 x 640 | 180.9 KB | Google Colab A100 notebook Cell 4 execution output displaying public tunnel URL and llama-server FastMTP initialization |
| [`06_colab_auto_unassign_failure.png`](06_colab_auto_unassign_failure.png) | 2026-10-24 20:05 | 1024 x 640 | 231.9 KB | Video transcode Colab failure evidence: conditional `if AUTO_UNASSIGN:` guard bypassed runtime destruction, burning billable CUs |

---

## Detailed Visual Evidence Breakdown

### 1. `01_continue_initial_config_yaml.png`
- **Context**: Initial user state in VS Code displaying `C:\Users\Aaradhya\.continue\config.yaml`.
- **Pre-existing Models**: `Llama 3.1 8B` (ollama), `Qwen2.5-Coder 1.5B` (ollama), `Nomic Embed` (ollama), `Fleet Master 7B` (lmstudio), `Fleet Gemini Pool` (openai).
- **Outcome**: Established base YAML configuration pattern to seamlessly insert `A100 Qwen3.8-27B Uncensored` with `contextLength: 65536`.

### 2. `02_continue_agent_mode_selected.png`
- **Context**: Continue UI sidebar opened to tutorial and mode selector.
- **Verification**: `Agent` mode explicitly active with `A100 Qwen3.8-27B Uncensored` selected in the model picker, ready for multi-turn autonomous tool execution.

### 3. `03_continue_agent_plan_dropdown.png`
- **Context**: User inquiry regarding the yellow warning badge next to Agent/Plan modes.
- **Analysis**: Explains Continue's internal safety heuristic flagging non-pre-certified models (outside Sonnet 3.5/GPT-4o) as experimental, despite Qwen3.8-27B's 8.5/10 agentic reasoning competence and FastMTP acceleration.

### 4. `04_cline_openai_compatible_config.png`
- **Context**: Cline extension settings modal in VS Code.
- **Configuration Captured**:
  - API Provider: `OpenAI Compatible`
  - Base URL: `https://domain-expansys-athletes-power.trycloudflare.com/v1`
  - API Key: `none`
  - Model ID: `./models/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q5_K_P.gguf`
  - Reasoning Effort: `High`

### 5. `05_colab_cell4_live_execution.png`
- **Context**: Google Colab runtime running on NVIDIA A100-SXM4 GPU.
- **Output Verified**:
  - Cloudflare tunnel established: `https://domain-expansys-athletes-power.trycloudflare.com`
  - Local server binding: `http://127.0.0.1:8088`
  - FastMTP draft model loaded: `FastMTP-32K.gguf` with `--spec-draft-ngl all`
  - FlashAttention-2 enabled: `-fa on`

### 6. `06_colab_auto_unassign_failure.png`
- **Context**: Post-mortem audit of user's batch video transcoding notebook (`Download from HubCloud`).
- **Defect Pinpointed**: The script contained `if AUTO_UNASSIGN:` which defaulted to `False` or unset, printing `[DONE] Finished! You can now download Drishyam-3_LG_TV.mp4...` while leaving the 8.31 CU/hr container running idle.
- **Resulting Invariant**: Formalization of `INV-COLAB-UNASSIGN-MANDATORY` across `AGENTS.md` and repo guardrails forbidding conditional teardown blocks.
