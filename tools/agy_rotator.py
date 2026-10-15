"""
Antigravity CLI Rotator & Profile Vault (Issue #26 - RFC-001).
Enables double round-robin quota cycling and 1ms credential swapping across 1-31 AGY profiles.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.windows_cred import (
    read_generic_credential,
    write_generic_credential,
    delete_generic_credential,
    snapshot_agy_credential,
    restore_agy_credential,
    AGY_CREDENTIAL_TARGET,
    is_windows,
)
from client.cli_accounts import AccountStore, valid_id, profile_environment
from client.process_runtime import run_background, background_options
from client.adapters.agy_adapter import AGYCLIAdapter

logger = logging.getLogger(__name__)


def get_default_store() -> AccountStore:
    return AccountStore()


def resolve_profile_dir(store: AccountStore, profile_id: str) -> Path:
    profile_id = valid_id(profile_id)
    profile = store.get(profile_id)
    if profile:
        return Path(profile["credential_dir"])
    return store.root / "profiles" / "agy_cli" / profile_id


def safe_get_profile(store: AccountStore, profile_id: str) -> Optional[dict[str, Any]]:
    try:
        return store.get(valid_id(profile_id))
    except ValueError:
        return None


def cmd_save(args: argparse.Namespace) -> int:
    """Save current active gemini:antigravity credential into a profile."""
    store = get_default_store()
    profile_id = valid_id(args.id)
    profile = safe_get_profile(store, profile_id)
    if not profile:
        profile = store.add(profile_id, "agy_cli", pool=args.pool, label=args.label or profile_id)
    
    cred_dir = Path(profile["credential_dir"])
    cred_file = cred_dir / "credential.bin"
    
    if not snapshot_agy_credential(cred_file):
        print(f"[ERROR] No active '{AGY_CREDENTIAL_TARGET}' found in Windows Credential Manager.", file=sys.stderr)
        return 1

    size = cred_file.stat().st_size
    store.update(profile_id, auth_state="ready", identity_verified=True, last_verified=time.time(), note="Snapshotted from active Windows session")
    print(f"[OK] Profile '{profile_id}' saved successfully ({size} bytes). State: ready.")
    return 0


def cmd_switch(args: argparse.Namespace) -> int:
    """Switch active Windows gemini:antigravity credential to specified profile."""
    store = get_default_store()
    profile_id = valid_id(args.id)
    profile = safe_get_profile(store, profile_id)
    if not profile:
        print(f"[ERROR] Profile '{profile_id}' not found.", file=sys.stderr)
        return 1

    cred_file = Path(profile["credential_dir"]) / "credential.bin"
    if not cred_file.exists():
        print(f"[ERROR] Credential file not found for profile '{profile_id}': {cred_file}", file=sys.stderr)
        return 1

    if not restore_agy_credential(cred_file):
        print(f"[ERROR] Failed to restore credential into Windows Credential Manager.", file=sys.stderr)
        return 1

    print(f"[OK] Switched active Windows Antigravity credential to '{profile_id}'.")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    """Interactive login flow for an AGY profile."""
    store = get_default_store()
    profile_id = valid_id(args.id)
    profile = safe_get_profile(store, profile_id)
    if not profile:
        profile = store.add(profile_id, "agy_cli", pool=args.pool, label=args.label or profile_id)

    cred_dir = Path(profile["credential_dir"])
    cred_file = cred_dir / "credential.bin"

    # Temporary backup of existing credential if present
    backup_file = cred_dir / "pre_login_backup.bin"
    snapshot_agy_credential(backup_file)

    # Clear active credential so agy triggers interactive Google OAuth
    delete_generic_credential()

    binary = AGYCLIAdapter._resolve_agy_binary()
    print(f"============================================================")
    print(f" Launching interactive Antigravity CLI login for [{profile_id}]")
    print(f" Complete Google login in the browser window.")
    print(f" After login completes and agy is ready, exit the CLI.")
    print(f"============================================================")

    env = profile_environment(profile)
    subprocess.run(["cmd.exe", "/c", f'start "AGY Login - {profile_id}" "{binary}"'], env=env)

    input("\nPress ENTER after you have successfully logged in in the browser...")

    if snapshot_agy_credential(cred_file):
        store.update(profile_id, auth_state="ready", identity_verified=True, last_verified=time.time())
        print(f"[OK] Successfully captured credentials for '{profile_id}'.")
        return 0
    else:
        print(f"[ERROR] Could not find newly authorized credential. Restoring backup if available...", file=sys.stderr)
        if backup_file.exists():
            restore_agy_credential(backup_file)
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List all registered AGY profiles with quota and cooldown telemetry."""
    store = get_default_store()
    profiles = [p for p in store.list() if p["provider"] == "agy_cli"]
    
    if not profiles:
        print("No AGY profiles registered yet. Use 'agy-profile save --id <name>' to save current session.")
        return 0

    now = time.time()
    print(f"\n{'ID':<15} {'POOL':<12} {'STATE':<10} {'COOLDOWN':<15} {'SNAPSHOT':<10} {'NOTE'}")
    print("-" * 75)
    for p in sorted(profiles, key=lambda x: x["id"]):
        pid = p["id"]
        pool = p["pool"]
        state = p["auth_state"]
        cooldown = max(0.0, p["cooldown_until"] - now)
        cd_str = f"{int(cooldown)}s remaining" if cooldown > 0 else "Ready"
        cred_file = Path(p["credential_dir"]) / "credential.bin"
        snap_str = "Yes" if cred_file.exists() else "Missing"
        note = p.get("note", "")[:25]
        print(f"{pid:<15} {pool:<12} {state:<10} {cd_str:<15} {snap_str:<10} {note}")
    print()
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    """Execute a prompt using double round-robin quota cycling across AGY profiles."""
    store = get_default_store()
    pool = args.pool or "default"
    
    # Selection: explicit profile or next available in pool
    if args.profile:
        profile_id = valid_id(args.profile)
        profile = safe_get_profile(store, profile_id)
        if not profile:
            print(f"[ERROR] Profile '{profile_id}' not found.", file=sys.stderr)
            return 1
    else:
        acquired = store.acquire("agy_cli", f"cli-rotator:{int(time.time())}", pool=pool)
        if not acquired:
            print(f"[ERROR] No ready AGY profile available in pool '{pool}' (all in cooldown or unverified).", file=sys.stderr)
            return 1
        profile, token = acquired

    profile_id = profile["id"]
    cred_file = Path(profile["credential_dir"]) / "credential.bin"
    
    # Restore credential if snapshot exists
    if cred_file.exists():
        restore_agy_credential(cred_file)

    binary = AGYCLIAdapter._resolve_agy_binary()
    model = args.model or "gemini-3.8-flash"
    effort = args.effort or "high"

    cmd = [
        binary,
        "-p",
        args.prompt,
        "--dangerously-skip-permissions",
        "--output-format",
        "json",
        "--model",
        model,
        "--effort",
        effort,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=args.timeout or 300,
            **background_options(),
        )
        
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode != 0:
            print(f"[ERROR] AGY execution failed ({proc.returncode}):\n{stderr or stdout}", file=sys.stderr)
            is_rate = "429" in stderr or "RESOURCE_EXHAUSTED" in stderr
            if 'token' in locals():
                store.release(profile_id, token, error_kind="rate_limit" if is_rate else "process")
            return proc.returncode

        try:
            data = json.loads(stdout)
            response_text = data.get("response", "")
            duration = data.get("duration_seconds", 0.0)
            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)

            print(f"[{profile_id} | {duration:.2f}s | {tokens} tokens]")
            print(response_text)
            if 'token' in locals():
                store.release(profile_id, token, error_kind=None)
            return 0
        except json.JSONDecodeError:
            print(stdout)
            if 'token' in locals():
                store.release(profile_id, token, error_kind=None)
            return 0

    finally:
        pass


def cmd_chat(args: argparse.Namespace) -> int:
    """Launch interactive AGY shell using target profile."""
    if args.profile:
        store = get_default_store()
        profile_id = valid_id(args.profile)
        profile = safe_get_profile(store, profile_id)
        if profile:
            cred_file = Path(profile["credential_dir"]) / "credential.bin"
            if cred_file.exists():
                restore_agy_credential(cred_file)
                print(f"[OK] Mounted credentials for '{profile_id}'.")

    binary = AGYCLIAdapter._resolve_agy_binary()
    return subprocess.run([binary]).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity CLI Rotator & Profile Vault (Issue #26)")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # save
    p_save = subparsers.add_parser("save", help="Snapshot active Windows credential into profile")
    p_save.add_argument("--id", required=True, help="Profile ID (e.g. user1..user31)")
    p_save.add_argument("--pool", default="default", help="Pool group (default: default)")
    p_save.add_argument("--label", help="Descriptive label")
    p_save.set_defaults(func=cmd_save)

    # switch
    p_switch = subparsers.add_parser("switch", help="Switch active Windows credential to profile")
    p_switch.add_argument("--id", required=True, help="Profile ID")
    p_switch.set_defaults(func=cmd_switch)

    # login
    p_login = subparsers.add_parser("login", help="Interactive login flow for new profile")
    p_login.add_argument("--id", required=True, help="Profile ID")
    p_login.add_argument("--pool", default="default")
    p_login.add_argument("--label")
    p_login.set_defaults(func=cmd_login)

    # list
    p_list = subparsers.add_parser("list", help="List registered AGY profiles")
    p_list.set_defaults(func=cmd_list)

    # exec
    p_exec = subparsers.add_parser("exec", help="Execute prompt across rotating pool")
    p_exec.add_argument("-p", "--prompt", required=True, help="Prompt text")
    p_exec.add_argument("--profile", help="Force specific profile")
    p_exec.add_argument("--pool", default="default", help="Pool name")
    p_exec.add_argument("--model", default="gemini-3.8-flash")
    p_exec.add_argument("--effort", default="high")
    p_exec.add_argument("--timeout", type=int, default=300)
    p_exec.set_defaults(func=cmd_exec)

    # chat
    p_chat = subparsers.add_parser("chat", help="Launch interactive AGY shell")
    p_chat.add_argument("--profile", help="Profile to mount before launching")
    p_chat.set_defaults(func=cmd_chat)

    parsed = parser.parse_args()
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
