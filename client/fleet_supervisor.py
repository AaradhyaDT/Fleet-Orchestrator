from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter
from client.adapters.claude_desktop_cdp import ClaudeDesktopCDPAdapter
from client.adapters.copilot_headless import CopilotHeadlessAdapter
from client.adapters.winpilot_bridge import WinPilotBridge

_SHARED_WINPILOT_BRIDGE: WinPilotBridge | None = None


def get_winpilot_bridge() -> WinPilotBridge:
    """Return shared WinPilotBridge singleton to coordinate physical desktop input."""
    global _SHARED_WINPILOT_BRIDGE
    if _SHARED_WINPILOT_BRIDGE is None:
        _SHARED_WINPILOT_BRIDGE = WinPilotBridge()
    return _SHARED_WINPILOT_BRIDGE

REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000/api/v1")
NODE_ID = os.getenv("NODE_ID", "local-fleet-node")
POLL_INTERVAL_SECONDS = max(1.0, float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "5")))
LEASE_SECONDS = max(30, int(os.getenv("LEASE_SECONDS", "300")))
LEASE_RENEWAL_SECONDS = max(10, int(os.getenv("LEASE_RENEWAL_SECONDS", str(LEASE_SECONDS // 3))))
API_KEY = os.getenv("API_AUTH_KEY") or os.getenv("ORCHESTRATOR_API_KEY", "")

async def renew_task_lease_periodically(
    client: httpx.AsyncClient,
    worker_id: str,
    task_id: str,
    claim_token: str,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=LEASE_RENEWAL_SECONDS)
            break
        except asyncio.TimeoutError:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/tasks/{task_id}/renew-lease",
                json={
                    "worker_id": worker_id,
                    "claim_token": claim_token,
                    "lease_seconds": LEASE_SECONDS,
                },
            )
            if response.status_code != 200:
                print(f"[!] [{worker_id}] Lease renewal failed for {task_id}: HTTP {response.status_code}")
                break

ROLE_CAPABILITIES: dict[str, list[str]] = {
    "orchestrator": ["coordination", "review", "writing", "code"],
    "researcher": ["research", "fact_check", "web_search"],
    "writer": ["writing", "draft", "creative", "code"],
    "seo_optimizer": ["seo", "seo_optimize", "formatting", "writing"],
    "qa_reviewer": ["qa", "qa_review", "fact_check", "audit"],
    "formatter": ["formatting", "markdown", "schema"],
    "overflow_worker": ["writing", "research", "formatting"],
}

def get_system_telemetry() -> dict[str, Any]:
    """Measure empirical OS metrics (Invariant C). Does NOT include quota/usage fields."""
    if sys.platform not in ("win32", "linux", "darwin"):
        return {"cpu_percent": None, "memory_percent": None}
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        return {"cpu_percent": float(cpu), "memory_percent": float(mem)}
    except Exception:
        pass

    try:
        import ctypes
        import time
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            mem = float(stat.dwMemoryLoad)

            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

            idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
            if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                to_int = lambda ft: (ft.dwHighDateTime << 32) + ft.dwLowDateTime
                i1, k1, u1 = to_int(idle), to_int(kernel), to_int(user)
                time.sleep(0.01)
                ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
                i2, k2, u2 = to_int(idle), to_int(kernel), to_int(user)
                sys_time = (k2 - k1) + (u2 - u1)
                idle_time = (i2 - i1)
                cpu = float(round(100.0 * (sys_time - idle_time) / sys_time, 1)) if sys_time > 0 else 0.0
                return {"cpu_percent": cpu, "memory_percent": mem}
    except Exception:
        pass

    return {"cpu_percent": None, "memory_percent": None}

# ── Provider-based adapter factory ──────────────────────────────────
from client.adapters.copilot_cli_adapter import CopilotCLIAdapter
from client.adapters.agy_adapter import AGYCLIAdapter
from client.adapters.codex_cli_adapter import CodexCLIAdapter
from client.adapters.opencode_cli_adapter import OpenCodeCLIAdapter

_PROVIDER_REGISTRY: dict[str, type] = {
    "claude_desktop_cdp": ClaudeDesktopCDPAdapter,
    "copilot_headless": CopilotHeadlessAdapter,
    "copilot_cli": CopilotCLIAdapter,
    "agy_cli": AGYCLIAdapter,
    "agy": AGYCLIAdapter,
    "codex_cli": CodexCLIAdapter,
    "opencode_cli": OpenCodeCLIAdapter,
}


def create_adapter(inst: dict[str, Any]) -> BaseWorkerAdapter:
    """Instantiate the correct adapter from a fleet-entry dict.

    Supported providers:
      - claude_desktop_cdp  → ClaudeDesktopCDPAdapter (CDP/WebSocket)
      - copilot_headless    → CopilotHeadlessAdapter  (REST API, zero-GUI)
      - copilot_cli         → CopilotCLIAdapter       (Subprocess CLI, autopilot)
      - agy_cli / agy        → AGYCLIAdapter            (Antigravity headless CLI)
      - codex_cli           → CodexCLIAdapter          (Codex exec JSONL CLI)
      - opencode_cli        → OpenCodeCLIAdapter       (OpenCode run JSON events)
    """
    provider = inst.get("Provider", "claude_desktop_cdp")
    worker_id = inst.get("Account", "unknown")
    nickname = inst.get("Nickname", worker_id)
    profile_id, pool = inst.get("AuthProfile"), inst.get("AccountPool")
    if profile_id and pool:
        raise ValueError("AuthProfile and AccountPool are mutually exclusive")
    if profile_id or pool:
        from client.cli_accounts import AccountStore, profile_environment, valid_id
        from client.adapters.account_pool_adapter import AccountPoolAdapter
        if provider not in ("agy", "agy_cli", "codex_cli", "opencode_cli"):
            raise ValueError("AuthProfile/AccountPool require an AGY, Codex or OpenCode provider")
        provider = "agy_cli" if provider == "agy" else provider
        store = AccountStore()
        profile_id = valid_id(profile_id) if profile_id else None
        pool = valid_id(pool) if pool else None
        if profile_id and store.get(profile_id)["provider"] != provider:
            raise ValueError("AuthProfile provider does not match the worker provider")
        if any(inst.get(key) for key in ("AgyHome", "CodexHome")):
            raise ValueError("Use AuthProfile/AccountPool or legacy home settings, not both")

        def bind(profile: dict[str, Any]) -> BaseWorkerAdapter:
            from tools.fleet_accounts import binary_for
            entry = {k: v for k, v in inst.items() if k not in ("AuthProfile", "AccountPool")}
            entry["Provider"] = provider
            if provider == "codex_cli":
                entry["CodexHome"] = profile["credential_dir"]
                entry["CodexPath"] = binary_for(profile)
            elif provider == "opencode_cli":
                entry["OpenCodePath"] = binary_for(profile)
            adapter = create_adapter(entry)
            adapter.process_env = profile_environment(profile)
            return adapter

        return AccountPoolAdapter(worker_id, nickname, provider, bind, profile_id=profile_id, pool=pool, store=store)
    model = inst.get("PreferredModel", "claude-3-5-sonnet")
    budget = int(inst.get("ThinkingBudget", 0))

    if provider == "claude_desktop_cdp":
        cdp_port = int(inst.get("CdpPort", 9222))
        use_winpilot = inst.get("UseWinPilot", True)
        window_title = inst.get("WindowTitle", f"Claude - {nickname}" if nickname != worker_id else "Claude")
        bridge = get_winpilot_bridge() if use_winpilot else None
        return ClaudeDesktopCDPAdapter(
            worker_id=worker_id,
            nickname=nickname,
            cdp_port=cdp_port,
            preferred_model=model,
            thinking_budget=budget,
            winpilot_bridge=bridge,
            window_title=window_title,
        )

    if provider == "copilot_headless":
        env_token = inst.get("EnvToken", "GITHUB_TOKEN")
        return CopilotHeadlessAdapter(
            worker_id=worker_id,
            nickname=nickname,
            github_token=os.getenv(env_token, ""),
            model=model,
        )

    if provider == "copilot_cli":
        copilot_path = inst.get("CopilotPath")
        worktree = inst.get("Worktree")
        timeout = float(inst.get("Timeout", 180.0))
        max_continues = int(inst.get("MaxContinues", 5))
        github_tok = inst.get("GitHubToken") or (os.getenv(inst.get("EnvToken", "")) if inst.get("EnvToken") else None)
        max_credits = int(inst["MaxAiCredits"]) if "MaxAiCredits" in inst and inst["MaxAiCredits"] is not None else None
        return CopilotCLIAdapter(
            worker_id=worker_id,
            nickname=nickname,
            copilot_path=copilot_path,
            worktree=worktree,
            timeout=timeout,
            max_autopilot_continues=max_continues,
            model=model if model != "claude-3-5-sonnet" else None,
            github_token=github_tok,
            copilot_home=inst.get("CopilotHome"),
            max_ai_credits=max_credits,
        )

    if provider in ("agy_cli", "agy"):
        agy_model = inst.get("PreferredModel")
        if agy_model == "claude-3-5-sonnet":
            agy_model = None
        return AGYCLIAdapter(
            worker_id=worker_id,
            nickname=nickname,
            agy_path=inst.get("AgyPath"),
            worker_home=inst.get("AgyHome"),
            workspace_dir=inst.get("Workspace") or inst.get("Worktree"),
            model=agy_model or os.getenv("AGY_DEFAULT_MODEL", "gemini-3.8-flash"),
            effort=inst.get("Effort", os.getenv("AGY_DEFAULT_EFFORT", "high")),
            timeout=float(inst.get("Timeout", os.getenv("AGY_TASK_TIMEOUT_SECONDS", "300"))),
            dangerously_skip_permissions=bool(inst.get("DangerouslySkipPermissions", True)),
        )

    if provider == "codex_cli":
        codex_model = inst.get("PreferredModel")
        if codex_model == "claude-3-5-sonnet":
            codex_model = None
        return CodexCLIAdapter(
            worker_id=worker_id,
            nickname=nickname,
            codex_path=inst.get("CodexPath"),
            codex_home=inst.get("CodexHome"),
            workspace_dir=inst.get("Workspace") or inst.get("Worktree"),
            model=codex_model,
            reasoning_effort=inst.get("ReasoningEffort"),
            timeout=float(inst.get("Timeout", 600.0)),
            sandbox=inst.get("Sandbox", "workspace-write"),
            approval_policy=inst.get("ApprovalPolicy", "never"),
        )

    if provider == "opencode_cli":
        return OpenCodeCLIAdapter(
            worker_id=worker_id,
            nickname=nickname,
            opencode_path=inst.get("OpenCodePath"),
            workspace_dir=inst.get("Workspace") or inst.get("Worktree"),
            model=inst.get("OpenCodeModel"),
            variant=inst.get("OpenCodeVariant"),
            timeout=float(inst.get("Timeout", 600.0)),
            auto_approve=bool(inst.get("OpenCodeAuto", True)),
        )

    raise ValueError(f"Unknown provider '{provider}' for worker '{worker_id}'")


# ── Generic worker loop ─────────────────────────────────────────────
async def run_worker_loop(
    worker_id: str,
    nickname: str,
    role: str,
    provider: str,
    adapter: BaseWorkerAdapter,
    client: httpx.AsyncClient,
    stop_event: asyncio.Event,
) -> None:
    """Worker loop that drives any BaseWorkerAdapter through the orchestrator task lifecycle."""
    capabilities = ROLE_CAPABILITIES.get(role, ["writing", "research", "code", "qa", "formatting"])

    # Provider-specific readiness probe
    if provider == "claude_desktop_cdp" and hasattr(adapter, "wait_until_ready"):
        cdp_port = getattr(adapter, "cdp_port", "?")
        print(f"[*] [{worker_id}] Probing Claude Desktop CDP readiness on port {cdp_port}...")
        is_ready = await adapter.wait_until_ready(timeout=25.0)
        if not is_ready:
            print(f"[!] [{worker_id}] Warning: CDP port {cdp_port} did not report ready. Retrying in background...")
        else:
            print(f"[+] [{worker_id}] CDP on port {cdp_port} is READY.")
    elif provider in ("copilot_headless", "copilot_cli", "agy_cli", "agy", "codex_cli", "opencode_cli"):
        health = await adapter.check_health()
        is_ready = health if isinstance(health, bool) else bool(health.get("ok", False))
        tag = "READY" if is_ready else "DEGRADED"
        print(f"[+] [{worker_id}] {provider} adapter {tag}.")
    else:
        print(f"[*] [{worker_id}] Provider '{provider}' — skipping readiness probe.")

    # 1. Register worker with FastAPI orchestrator
    reg_payload = {
        "id": worker_id,
        "provider": provider,
        "node_id": NODE_ID,
        "nickname": f"{nickname} ({role})",
        "capabilities": capabilities,
        "quota_limit_per_window": 50 if provider == "claude_desktop_cdp" else 10,
        "cooldown_window_minutes": 300,
    }
    try:
        r = await client.post(f"{ORCHESTRATOR_URL}/workers/register", json=reg_payload)
        if r.status_code in (200, 201):
            print(f"[+] [{worker_id}] Registered with orchestrator (capabilities: {capabilities})")
    except Exception as e:
        print(f"[!] [{worker_id}] Failed to register with orchestrator: {e}")

    reconnect_delay = 1.0
    active_task_id: str | None = None
    while not stop_event.is_set():
        try:
            # Heartbeat with truthful telemetry (Invariant C)
            telemetry = get_system_telemetry()
            await client.post(
                f"{ORCHESTRATOR_URL}/workers/{worker_id}/heartbeat",
                json={
                    "cpu_percent": telemetry["cpu_percent"],
                    "memory_percent": telemetry["memory_percent"],
                    "active_leases": 1 if active_task_id else 0,
                    "current_task_id": active_task_id,
                },
            )

            # Acquire task via Closed-Loop Protocol (Invariant A)
            acq_payload = {
                "worker_id": worker_id,
                "capabilities": capabilities,
                "lease_seconds": LEASE_SECONDS,
            }
            acq_r = await client.post(f"{ORCHESTRATOR_URL}/tasks/acquire", json=acq_payload)
            if acq_r.status_code == 200 and acq_r.json():
                claim_data = acq_r.json()
                claim_token = claim_data.get("claim_token")
                task_info = claim_data.get("task", {})
                task_id = task_info.get("id")
                stage = task_info.get("stage")

                if task_id and claim_token:
                    print(f"[>] [{worker_id}] Acquired task {task_id} (stage: {stage}). Executing...")
                    active_task_id = task_id
                    await client.post(
                        f"{ORCHESTRATOR_URL}/workers/{worker_id}/heartbeat",
                        json={
                            "cpu_percent": telemetry["cpu_percent"],
                            "memory_percent": telemetry["memory_percent"],
                            "active_leases": 1,
                            "current_task_id": task_id,
                        },
                    )
                    lease_stop = asyncio.Event()
                    lease_task = asyncio.create_task(
                        renew_task_lease_periodically(client, worker_id, task_id, claim_token, lease_stop)
                    )
                    try:
                        exec_res = await adapter.execute_task(
                            task_id, task_info.get("spec", ""), stage, {}
                        )

                        if exec_res.get("success"):
                            result_text = exec_res.get("result_text", "")
                            
                            # If this is a QA stage, submit formal QA review
                            if stage in ("qa", "qa_review"):
                                verdict = "pass"
                                reason = None
                                if "fail" in result_text.lower() or "revision_needed" in result_text.lower():
                                    verdict = "revision_needed"
                                    reason = "QA checks requested revision"
                                
                                qa_payload = {
                                    "task_id": task_id,
                                    "reviewer_worker_id": worker_id,
                                    "claim_token": claim_token,
                                    "verdict": verdict,
                                    "rejection_reason": reason,
                                    "checks_passed": {"evaluated": True, "score": 90 if verdict == "pass" else 50},
                                    "summary": f"QA review: {verdict.upper()}" + (f" [AuthProfile: {exec_res['auth_profile']}]" if exec_res.get("auth_profile") else ""),
                                    "result_text": result_text,
                                }
                                await client.post(
                                    f"{ORCHESTRATOR_URL}/tasks/{task_id}/qa-review",
                                    json=qa_payload,
                                )
                                print(f"[+] [{worker_id}] Task {task_id} QA review submitted: {verdict.upper()}")
                            else:
                                # Normal stage: submit checkpoint
                                cp_payload = {
                                    "task_id": task_id,
                                    "kind": "text",
                                    "summary": exec_res.get("summary", ""),
                                    "result_text": result_text,
                                    "submitted_by": worker_id,
                                    "claim_token": claim_token,
                                }
                                await client.post(
                                    f"{ORCHESTRATOR_URL}/tasks/{task_id}/checkpoint",
                                    json=cp_payload,
                                )
                                print(f"[+] [{worker_id}] Task {task_id} checkpoint submitted.")

                        elif provider in ("agy", "agy_cli", "codex_cli", "opencode_cli"):
                            from client.cli_accounts import save_failed_attempt, classify_failure
                            kind = classify_failure(exec_res)
                            if exec_res.get("execution_started", True):
                                checkpoint = save_failed_attempt(worker_id, task_id, exec_res)
                                response = await client.post(
                                    f"{ORCHESTRATOR_URL}/tasks/{task_id}/block",
                                    json={"worker_id": worker_id, "claim_token": claim_token,
                                          "reason": f"CLI {kind}; recovery required. Attempt checkpoint: {checkpoint}"},
                                )
                                if response.status_code != 200:
                                    raise RuntimeError(f"Unable to block failed CLI task: HTTP {response.status_code}")
                                print(f"[!] [{worker_id}] Task blocked for recovery ({kind}); checkpoint: {checkpoint}")
                            else:
                                await client.post(
                                    f"{ORCHESTRATOR_URL}/tasks/{task_id}/release",
                                    json={"worker_id": worker_id, "claim_token": claim_token},
                                )
                        elif exec_res.get("error") == "RATE_LIMIT_429":
                            print(f"[!] [{worker_id}] Rate limit detected in Claude UI! Entering 5h cooldown.")
                            await client.post(
                                f"{ORCHESTRATOR_URL}/workers/{worker_id}/heartbeat",
                                json={"trigger_cooldown": True},
                            )
                            await client.post(
                                f"{ORCHESTRATOR_URL}/tasks/{task_id}/release",
                                json={"worker_id": worker_id, "claim_token": claim_token},
                            )
                            await asyncio.sleep(300)
                        else:
                            print(f"[!] [{worker_id}] Task execution failed: {exec_res.get('error')}")
                            await client.post(
                                f"{ORCHESTRATOR_URL}/tasks/{task_id}/release",
                                json={"worker_id": worker_id, "claim_token": claim_token},
                            )
                    except asyncio.CancelledError:
                        if provider in ("agy", "agy_cli", "codex_cli", "opencode_cli"):
                            from client.cli_accounts import save_failed_attempt
                            checkpoint = save_failed_attempt(worker_id, task_id, {
                                "error_kind": "cancelled", "error": "Worker interrupted; review workspace before resuming",
                                "auth_profile": getattr(adapter, "last_profile", None),
                                "workspace": str(getattr(adapter, "workspace_dir", "")),
                            })
                            await asyncio.shield(client.post(
                                f"{ORCHESTRATOR_URL}/tasks/{task_id}/block",
                                json={"worker_id": worker_id, "claim_token": claim_token,
                                      "reason": f"CLI interrupted; recovery required. Attempt checkpoint: {checkpoint}"},
                            ))
                        raise
                    finally:
                        lease_stop.set()
                        await lease_task
                        active_task_id = None

            reconnect_delay = 1.0
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[!] [{worker_id}] Loop error: {e}")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(30.0, reconnect_delay * 2)

async def main():
    parser = argparse.ArgumentParser(description="Autonomous Multi-Provider Fleet Supervisor")
    parser.add_argument(
        "--fleet-file",
        type=str,
        default=str(REPO_ROOT / "orchestrator-state" / "live-status" / "active_fleet.json"),
        help="Path to active fleet JSON metadata",
    )
    args = parser.parse_args()

    fleet_file = Path(args.fleet_file)
    if not fleet_file.exists():
        print(f"[!] Fleet metadata file not found at: {fleet_file}")
        sys.exit(1)

    try:
        fleet_data = json.loads(fleet_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] Failed to parse fleet metadata: {e}")
        sys.exit(1)

    # Normalise: accept a single dict or a list of dicts
    if isinstance(fleet_data, dict):
        fleet_data = [fleet_data]
    if not isinstance(fleet_data, list) or len(fleet_data) == 0:
        print("[!] Fleet metadata contains no active instances.")
        sys.exit(1)

    providers_used = sorted({inst.get("Provider", "claude_desktop_cdp") for inst in fleet_data})
    print("============================================================")
    print("  AUTONOMOUS MULTI-PROVIDER FLEET SUPERVISOR")
    print(f"  Managing {len(fleet_data)} workers  |  Providers: {', '.join(providers_used)}")
    print(f"  Connecting to Orchestrator: {ORCHESTRATOR_URL}")
    print("============================================================")

    stop_event = asyncio.Event()
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        tasks = []
        for inst in fleet_data:
            worker_id = inst.get("Account", "unknown")
            nickname = inst.get("Nickname", worker_id)
            role = inst.get("Role", "writer")
            provider = inst.get("Provider", "claude_desktop_cdp")

            try:
                adapter = create_adapter(inst)
            except ValueError as e:
                print(f"[!] Skipping worker '{worker_id}': {e}")
                continue

            t = asyncio.create_task(
                run_worker_loop(
                    worker_id=worker_id,
                    nickname=nickname,
                    role=role,
                    provider=provider,
                    adapter=adapter,
                    client=client,
                    stop_event=stop_event,
                )
            )
            tasks.append(t)

        if not tasks:
            print("[!] No workers could be initialised. Exiting.")
            sys.exit(1)

        try:
            await asyncio.gather(*tasks)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[*] Stopping fleet supervisor...")
            stop_event.set()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())

