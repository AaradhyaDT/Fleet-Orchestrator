# Incubator RFC: I am thinking of upgrading the copilot cli to use the github pats save

> **Raw Thought**: *"I am thinking of upgrading the copilot cli to use the github pats saved in .env.fleet of Fleet-Orchestrator repo in a round robin style per prompt, which would let me use the fleet outside the Agentic Chat Windows themselves."*
> **Captured At**: `2026-10-20T07:32:40.300428+00:00`
> **Vault ID**: `VLT-20261020073227`

---

## 1. Executive Summary & Problem Formulation
This RFC proposes a critical upgrade to the `copilot cli` utility, enabling it to leverage a pool of GitHub Personal Access Tokens (PATs) stored within the `.env.fleet` configuration of the `Fleet-Orchestrator` repository. By implementing a robust round-robin PAT rotation mechanism per prompt, we aim to circumvent existing GitHub API
