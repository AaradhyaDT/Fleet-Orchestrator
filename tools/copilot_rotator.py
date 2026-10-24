"""
Copilot CLI Rotator & PAT Pool Controller (brainstorm Issue #27).
Enables round-robin GitHub PAT rotation per prompt across .env.fleet,
individual COPILOT_HOME directory isolation, and standalone CLI execution outside agent chat windows.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.adapters.copilot_cli_adapter import CopilotCLIAdapter
from client.copilot_token_pool import CopilotTokenPool

logger = logging.getLogger("copilot_rotator")


def cmd_list(args: argparse.Namespace) -> int:
    """List registered Copilot PAT accounts from .env.fleet and their quota / cooldown status."""
    pool = CopilotTokenPool.from_env_fleet(PROJECT_ROOT)
    summary = pool.get_summary()

    print("===============================================================================")
    print(" COPILOT MULTI-ACCOUNT PAT POOL (.env.fleet)")
    print("===============================================================================")
    print(f" Total Accounts: {summary['total_accounts']} | Active: {summary['active_accounts']} | In Cooldown: {summary['cooldown_accounts']}")
    print(f" Current Round-Robin Pointer: Account #{summary['current_rotation_index'] + 1}")
    print("-------------------------------------------------------------------------------")
    print(f" {'#':<3} | {'Worker ID':<16} | {'Account Name':<22} | {'Token':<14} | {'Status':<10}")
    print("-------------------------------------------------------------------------------")

    for acc in summary["accounts"]:
        status = "COOLDOWN" if acc["in_cooldown"] else "READY"
        cd_info = f" ({acc['cooldown_remaining_s']}s)" if acc["in_cooldown"] else ""
        status_str = f"{status}{cd_info}"
        print(f" {acc['index']:<3} | {acc['worker_id']:<16} | {acc['name']:<22} | {acc['token_masked']:<14} | {status_str}")

    print("===============================================================================")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Print structured JSON or summary status of PAT pool."""
    pool = CopilotTokenPool.from_env_fleet(PROJECT_ROOT)
    summary = pool.get_summary()
    if getattr(args, "json", False):
        print(json.dumps(summary, indent=2))
    else:
        cmd_list(args)
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    """Execute a prompt via Copilot CLI with automatic round-robin PAT rotation."""
    pool = CopilotTokenPool.from_env_fleet(PROJECT_ROOT)
    if len(pool) == 0:
        print("[!] No valid GitHub PATs found in .env.fleet or .env.fleet.copilot.", file=sys.stderr)
        print("    Configure COPILOT_ACCOUNT_1_TOKEN or COPILOT_PAT_POOL to enable rotation.", file=sys.stderr)

    adapter = CopilotCLIAdapter(
        worker_id="copilot-rotator-exec",
        nickname="Copilot Rotator",
        model=args.model,
        auto_tier=args.auto_tier,
        worktree=args.worktree,
        timeout=args.timeout,
        token_pool=pool,
        rotate_pats=True,
    )

    result = asyncio.run(adapter.execute_prompt(args.prompt))

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2))
    else:
        status_tag = "[SUCCESS]" if result.get("success") else "[FAILED]"
        account_name = result.get("pat_account_name", "unknown")
        worker_id = result.get("pat_worker_id", "unknown")
        model = result.get("model_used", args.model or "auto")

        print(f"┌────────────────────────────────────────────────────────────────────────┐")
        print(f"│ {status_tag:<12} Account: {account_name:<20} Model: {model:<15} │")
        print(f"│ Worker: {worker_id:<20} Credits: {result.get('credits_used', 0):<6} Tokens: {result.get('tokens_used', 0):<10} │")
        print(f"├────────────────────────────────────────────────────────────────────────┤")

        out = result.get("result_text", "")
        if out:
            for line in out.splitlines():
                print(f"  {line}")
        elif not result.get("success"):
            print(f"  Error: {result.get('error')}")

        print(f"└────────────────────────────────────────────────────────────────────────┘")

    return 0 if result.get("success") else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copilot CLI Rotator & PAT Pool Controller (Issue #27)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List configured Copilot PAT accounts from .env.fleet")
    p_list.set_defaults(func=cmd_list)

    # status
    p_status = subparsers.add_parser("status", help="Show PAT pool status summary")
    p_status.add_argument("--json", action="store_true", help="Output status in JSON format")
    p_status.set_defaults(func=cmd_status)

    # exec
    p_exec = subparsers.add_parser("exec", help="Execute prompt across rotating PAT pool")
    p_exec.add_argument("-p", "--prompt", required=True, help="Prompt text to execute")
    p_exec.add_argument("--model", help="Target model (e.g. claude-3.7-sonnet, gpt-5.4, auto)")
    p_exec.add_argument("--auto-tier", choices=["speed", "quality"], help="Auto model selection tier")
    p_exec.add_argument("--worktree", help="Working directory / worktree path")
    p_exec.add_argument("--timeout", type=float, default=180.0, help="Execution timeout in seconds")
    p_exec.add_argument("--json", action="store_true", help="Output execution results as JSON")
    p_exec.set_defaults(func=cmd_exec)

    parsed = parser.parse_args()
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
