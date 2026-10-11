import subprocess
import json

# Backfill issues for M1 (Milestone #2) and M3 (Milestone #4)
issues_to_create = [
    # M1 Issue (Issue 21 is already created for Foundation Engine)
    {
        "milestone": 2,
        "title": "[Feature] Shared Job Scratchpad Manager & QA Verdict Parser",
        "body": """## Overview
Implement shared multi-worker job scratchpad manager with cross-process OS file locking, timeout detection, lost-update guards, and deterministic QA verdict evaluation.

## Commits & Evidence
- `dc0e112`: feat(fleet): add shared job scratchpad manager (WBS-1, task_2026-10-07_002)
- `f9d9e41`: test(fleet): add stale-lock, lock-timeout, lost-update and roundtrip tests for scratchpad manager
- `540d90d`: fix(fleet): repair test_scratchpad_manager.py corrupted by duplicated header append
- `cbc72a2`: feat(fleet): add QA verdict parser with explicit QA_VERDICT marker + legacy fallback

## Completed Tasks
- [x] Create `tools/scratchpad_manager.py` with file locking protocol
- [x] Author comprehensive concurrency test suite (`tests/test_scratchpad_manager.py`)
- [x] Implement robust regex/marker parser for worker QA verdicts""",
        "labels": ["enhancement"]
    },

    # M3 Issues
    {
        "milestone": 4,
        "title": "[Feature] Fleet Control Center v2.0 GUI & Live Worker Telemetry",
        "body": """## Overview
Overhaul the desktop Control Center UI into Fleet Control Center v2.0 with Tkinter High-DPI layout, authentic pooled AI credit telemetry, daemon log tailing, and live worker inspection.

## Commits & Evidence
- `b6d0327`: feat(gui): overhaul Fleet Control Center v2.0 and authentic AI credits tracking engine
- `4115733`: fix(gui): silence httpx request logs and handle dashboard CLI flags
- `6a61233`: feat(fleet): authentic copilot quota reconciliation and fleet commander
- `5d2ce8b`: feat(status): format pooled capacity display in copilot fleet
- `680171d`: feat(task_1791557502_add-daemon-log-tailing-to-fleet-gui): automated implementation
- `9855f98`: feat(gui): live telemetry, batch monitor, and worker inspector
- `ce4ae25`: fix(win32): suppress terminal window flashing for copilot and git subprocesses

## Completed Tasks
- [x] Design modern High-DPI Tkinter dashboard (`tools/fleet_gui.py`)
- [x] Integrate authentic Copilot credit pooling and quota reconciliation
- [x] Support real-time background log tailing and active worker inspection
- [x] Suppress Win32 console window flashing on Windows""",
        "labels": ["enhancement"]
    },
    {
        "milestone": 4,
        "title": "[Feature] Sub-50ms Local Intent Router & Antigravity Context Bridge",
        "body": """## Overview
Build high-speed local intent classification tool (`fast_intent_router.py`), transcript dataset harvester, and Antigravity workspace bridge projecting custom instructions to native Copilot workers.

## Commits & Evidence
- `4476946`: feat(bridge): implement antigravity context bridge and native copilot custom instructions projection
- `ad32a66`: feat(router): add fast_intent_router tool and ignore local model weights
- `c88fb1c`: docs(drive): register qwen intent router gguf in drive-manifest.json
- `a99938c`: docs(readme): document fast_intent_router tool and slm-router-forge skill in layout
- `b475b90`: feat(router): harvest transcript dataset and integrate task time allocation into slm router
- `5be97ce`: docs(skill): update slm-router-forge skill with task time allocation and empirical harvesting
- `8e2f1ef`: feat(router): update slm-router-forge skill with Colab forge notebook recipes

## Completed Tasks
- [x] Scaffold Antigravity IDE context bridge
- [x] Implement sub-50ms local intent classifier with LM Studio integration
- [x] Build transcript dataset harvester for task time duration allocation
- [x] Author `slm-router-forge` skill recipes""",
        "labels": ["enhancement"]
    },
    {
        "milestone": 4,
        "title": "[Feature] Google Colab Cloud Execution Adapter & Accelerator Skill",
        "body": """## Overview
Integrate `colab-mcp`, Windows Colab CLI runner, and `ColabCloudAdapter` with comprehensive test suite for offloading intensive GPU/TPU training runs.

## Commits & Evidence
- `074ddff`: feat(colab): integrate colab-mcp, windows colab cli runner, and cloud accelerator skill
- `f87de61`: feat(colab): add ColabCloudAdapter and comprehensive test suite
- `9b6486e`: fix(colab): replace deprecated tokenizer arg with processing_class for SFTTrainer
- `686dec5`: fix(colab): add compatibility bridge for trl < 0.9.0 and transformers >= 4.47

## Completed Tasks
- [x] Implement `ColabCloudAdapter` with remote dispatch API
- [x] Add `colab.bat` CLI entrypoint
- [x] Author comprehensive unit tests in `tests/test_colab_cloud_adapter.py`
- [x] Patch SFTTrainer and trl/transformers compatibility bridges""",
        "labels": ["enhancement"]
    }
]

created_numbers = [21]
for item in issues_to_create:
    cmd = [
        "gh", "issue", "create",
        "--title", item["title"],
        "--body", item["body"],
        "--assignee", "@me"
    ]
    for lbl in item["labels"]:
        cmd.extend(["--label", lbl])
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        url = res.stdout.strip()
        issue_num = url.split("/")[-1]
        print(f"Created Issue #{issue_num}: {item['title']}")
        # Attach milestone and close issue via API PATCH
        patch_cmd = [
            "gh", "api", f"repos/:owner/:repo/issues/{issue_num}",
            "--method", "PATCH",
            "-F", f"milestone={item['milestone']}",
            "-f", "state=closed"
        ]
        patch_res = subprocess.run(patch_cmd, capture_output=True, text=True)
        if patch_res.returncode == 0:
            print(f"Attached Milestone #{item['milestone']} & Closed Issue #{issue_num}")
        else:
            print(f"Error patching issue #{issue_num}: {patch_res.stderr}")
        created_numbers.append(issue_num)
    else:
        print(f"Failed to create issue {item['title']}: {res.stderr}")

print(f"Completed! All issues created and assigned: {created_numbers}")
