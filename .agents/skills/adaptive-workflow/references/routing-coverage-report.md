# Adaptive-Workflow Routing Coverage & Capability Gap Report

> **Generated**: 2026-10-15 · **Authoritative Registry**: `tools/skills_registry.json`
> **Total Distinct Skills**: 97 · **Directly Mapped**: 47 (48.5%) · **Unmapped Gaps**: 50

---

## 1. Executive Summary & Gap Triage

| Category | Count | Strategic Impact & Routing Policy |
| :--- | :---: | :--- |
| **Directly Covered** | **47** | Explicitly routed in `skill-matrix.md` across 9 core archetypes. |
| **Critical Gaps** | **9** | Active user tools (e.g. Gemini API, Classroom) lacking explicit matrix entries. |
| **Useful Gaps** | **8** | Specialized hardware/workflow tools that fall back to heuristic match. |
| **Deferred Gaps** | **33** | Azure enterprise (28 skills) and platform internal maintenance skills. |

### Critical Unmapped Skills Needing Matrix Integration:
- `antigravity-guide`: Domain `FRONTEND_PRODUCT`
- `automation`: Domain `FRONTEND_PRODUCT`
- `gemini-api-dev`: Domain `AI_ENGINEERING_ML`
- `gemini-live-api-dev`: Domain `AI_ENGINEERING_ML`
- `gemini-omni-flash-api`: Domain `AI_ENGINEERING_ML`
- `generative_ui`: Domain `FRONTEND_PRODUCT`
- `google-classroom`: Domain `RESEARCH_ACADEMIC`
- `imagegen`: Domain `FRONTEND_PRODUCT`
- `permissioned-github`: Domain `FRONTEND_PRODUCT`

---

## 2. Complete 97-Skill Routing Census

| Skill Name | Domain Archetype | Availability Tier | Coverage Status | SSOT Origin |
| :--- | :--- | :--- | :--- | :--- |
| `academic-notebook-architect` | `AI_ENGINEERING_ML` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `adaptive-workflow` | `SWARM_ORCHESTRATION` | `VERIFIED` | ⚠️ USEFUL | SSOT_USER |
| `agent-teams-orchestration` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `agy-customizations` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ✅ Covered | BUILTIN_IDE |
| `ai-engineering-fellowship` | `AI_ENGINEERING_ML` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `airunway-aks-setup` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `antigravity-guide` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ⚠️ CRITICAL | BUILTIN_IDE |
| `appinsights-instrumentation` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `automation` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ⚠️ CRITICAL | BUILTIN_IDE |
| `avionic-telecom-analyzer` | `DOMAIN_HARDWARE` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `azure-ai` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-aigateway` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-app-onboard` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-app-onboard-prereq` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-cloud-migrate` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-compliance` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-compute` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-deploy` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-diagnostics` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-enterprise-infra-planner` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-kubernetes` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-kusto` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-messaging` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-prepare` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-quotas` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-reliability` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-resource-lookup` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-resource-visualizer` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-storage` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-upgrade` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `azure-validate` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `bitwarden` | `SYSADMIN_SECURITY` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `chat-archiver` | `RESEARCH_ACADEMIC` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `chrome-extensions` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `colab-cloud-accelerator` | `AI_ENGINEERING_ML` | `VERIFIED` | ✅ Covered | SSOT_USER |
| `cold-storage-archiver` | `AI_ENGINEERING_ML` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `compliance-report-harmonizer` | `AI_ENGINEERING_ML` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `control-systems-sim` | `FRONTEND_PRODUCT` | `VERIFIED` | ✅ Covered | SSOT_USER |
| `cp-archive-harvester` | `ENGINEERING_DEV` | `INSTALLED` | ⚠️ USEFUL | SSOT_USER |
| `customization-state-sync` | `SWARM_ORCHESTRATION` | `VERIFIED` | ⚠️ USEFUL | SSOT_USER |
| `cyber-forensics` | `SYSADMIN_SECURITY` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `design-taste-frontend` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `discover-azure-skills` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `doc-archiver` | `RESEARCH_ACADEMIC` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `dsa-complexity-optimizer` | `ENGINEERING_DEV` | `VERIFIED` | ✅ Covered | SSOT_USER |
| `dsp-signal-engine` | `DOMAIN_HARDWARE` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `edge-ai-model-forge` | `DOMAIN_HARDWARE` | `INSTALLED` | ⚠️ USEFUL | SSOT_USER |
| `electronics-circuit-synth` | `DOMAIN_HARDWARE` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `embedded-firmware-scaffold` | `DOMAIN_HARDWARE` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `entra-agent-id` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `entra-app-registration` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `feature-dev` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `find-skills` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `fleet-orchestrator` | `SWARM_ORCHESTRATION` | `VERIFIED` | ✅ Covered | SSOT_USER |
| `fluid-wordmark-collapse` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `gemini-api-dev` | `AI_ENGINEERING_ML` | `INSTALLED` | ⚠️ CRITICAL | PLUGIN_EMBEDDED |
| `gemini-live-api-dev` | `AI_ENGINEERING_ML` | `INSTALLED` | ⚠️ CRITICAL | PLUGIN_EMBEDDED |
| `gemini-omni-flash-api` | `AI_ENGINEERING_ML` | `INSTALLED` | ⚠️ CRITICAL | PLUGIN_EMBEDDED |
| `generative_ui` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ⚠️ CRITICAL | BUILTIN_IDE |
| `github-issue-pr-workflow` | `ENGINEERING_DEV` | `INSTALLED` | ⚠️ USEFUL | UNIVERSAL_HUB |
| `github-workflow` | `ENGINEERING_DEV` | `VERIFIED` | ✅ Covered | SSOT_USER |
| `google-classroom` | `RESEARCH_ACADEMIC` | `ACCESSIBLE` | ⚠️ CRITICAL | SSOT_USER |
| `google-stitch-integration` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `graphify` | `RESEARCH_ACADEMIC` | `VERIFIED` | ✅ Covered | SSOT_USER |
| `graphify-code-search` | `RESEARCH_ACADEMIC` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `graphify-optimizer` | `RESEARCH_ACADEMIC` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `imagegen` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ⚠️ CRITICAL | CODEX_SYSTEM |
| `latex-thesis-architect` | `AI_ENGINEERING_ML` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `mcp-integration` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `microsoft-foundry` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `migrate-workflows` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ✅ Covered | BUILTIN_IDE |
| `modern-web-guidance` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `oose-architecture-modeler` | `ENGINEERING_DEV` | `INSTALLED` | ⚠️ USEFUL | SSOT_USER |
| `openai-docs` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ⚠️ DEFERRED | CODEX_SYSTEM |
| `permissioned-github` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ⚠️ CRITICAL | BUILTIN_IDE |
| `plugin` | `ENGINEERING_DEV` | `INSTALLED` | ⚠️ USEFUL | BUILTIN_IDE |
| `pm-workflow-orchestrator` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `portfolio-project-manager` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `pr-review-toolkit` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `problem-dissector` | `ENGINEERING_DEV` | `INSTALLED` | ⚠️ USEFUL | SSOT_USER |
| `python-appservice-deploy` | `CLOUD_ENTERPRISE` | `INSTALLED` | ⚠️ DEFERRED | UNIVERSAL_HUB |
| `review-agent` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ⚠️ DEFERRED | CODEX_SYSTEM |
| `rf-link-budget-calc` | `DOMAIN_HARDWARE` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `security-guidance` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `shadcn-context` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `skill-creator` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ⚠️ DEFERRED | CODEX_SYSTEM |
| `skill-development` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `skill-installer` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ⚠️ DEFERRED | CODEX_SYSTEM |
| `slm-router-forge` | `AI_ENGINEERING_ML` | `VERIFIED` | ✅ Covered | SSOT_USER |
| `split-to-prs` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `super-nlm` | `AI_ENGINEERING_ML` | `VERIFIED` | ✅ Covered | SSOT_USER |
| `super-nlm-downloads` | `AI_ENGINEERING_ML` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `systems-concurrency-harness` | `ENGINEERING_DEV` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `ui-plugin-navigation` | `PLATFORM_INTERNAL` | `ACCESSIBLE` | ⚠️ DEFERRED | BUILTIN_IDE |
| `win-vault` | `SYSADMIN_SECURITY` | `INSTALLED` | ✅ Covered | SSOT_USER |
| `winpilot` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |
| `writing-like-claude` | `FRONTEND_PRODUCT` | `ACCESSIBLE` | ✅ Covered | SSOT_USER |

---
## 3. Recommended Actions
1. **Map Critical Gaps**: Add explicit entries in `references/skill-matrix.md` for `gemini-api-*` under `AI_ENGINEERING_ML` and `google-classroom` under `RESEARCH_ACADEMIC`.
2. **Add `CLOUD_ENTERPRISE` Archetype**: Create a dedicated enterprise table in `skill-matrix.md` mapping the 28 Azure/Entra skills to `~/.agents/skills/` without bloating `SKILL.md`.
3. **Dynamic Registry Ingestion**: `fast_intent_router.py` already consumes `skills_registry.json`, ensuring all 97 skills have keyword triggers.
