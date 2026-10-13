"""Native CLI sign-in and local account-pool management. No credentials in metadata."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.cli_accounts import (
    AccountStore,
    PROVIDERS,
    AGY_ISOLATION_NOTE,
    profile_environment,
    classify_failure,
    reported_retry_after,
)
from client.process_runtime import run_background


def binary_for(profile: dict) -> str:
    if profile.get("binary"):
        binary = str(profile["binary"])
    elif profile["provider"] == "codex_cli":
        from client.adapters.codex_cli_adapter import CodexCLIAdapter

        binary = CodexCLIAdapter._resolve_codex_binary()
    elif profile["provider"] == "opencode_cli":
        from client.adapters.opencode_cli_adapter import OpenCodeCLIAdapter

        binary = OpenCodeCLIAdapter._resolve_opencode_binary()
    else:
        from client.adapters.agy_adapter import AGYCLIAdapter

        binary = AGYCLIAdapter._resolve_agy_binary()
    if os.name == "nt" and Path(binary).suffix.lower() in {".ps1", ".cmd", ".bat"}:
        raise ValueError("Use a native CLI executable via --binary; shell shims are not supported")
    return binary


def native_command(profile: dict, operation: str, device_auth: bool = False) -> list[str]:
    if profile["provider"] == "agy_cli":
        raise ValueError(AGY_ISOLATION_NOTE)
    binary = binary_for(profile)
    if profile["provider"] == "codex_cli":
        prefix = [binary, "-c", 'cli_auth_credentials_store="file"', "-c", 'forced_login_method="chatgpt"']
        if operation == "login":
            return prefix + ["login"] + (["--device-auth"] if device_auth else [])
        if operation == "logout":
            return prefix + ["logout"]
        return prefix + ["login", "status"]
    if device_auth:
        raise ValueError("--device-auth is supported only for Codex")
    if operation == "login":
        return [binary, "auth", "login", "--provider", "openai"]
    if operation == "logout":
        return [binary, "auth", "logout", "openai"]
    return [binary, "auth", "list"]


def auth_state(profile: dict) -> str:
    if profile["provider"] == "agy_cli":
        return "isolation_unverified"
    response = run_background(
        native_command(profile, "status"),
        env=profile_environment(profile),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    if profile["provider"] == "codex_cli":
        return "ready" if response.returncode == 0 else "reauth_required"
    auth_file = Path(profile["credential_dir"]) / "data" / "opencode" / "auth.json"
    # Native list only establishes a stored OpenAI credential, not remote validity.
    return (
        "configured"
        if response.returncode == 0 and auth_file.is_file() and "openai" in response.stdout.lower()
        else "reauth_required"
    )


async def canary(profile: dict, model: str | None) -> dict:
    prompt = "Reply with FLEET_AUTH_OK only. Do not run tools, read files, or change files."
    env = profile_environment(profile)
    binary = binary_for(profile)
    with tempfile.TemporaryDirectory(prefix="fleet-auth-canary-") as workspace:
        if profile["provider"] == "codex_cli":
            from client.adapters.codex_cli_adapter import CodexCLIAdapter

            adapter = CodexCLIAdapter(
                profile["id"],
                "Auth verification",
                codex_path=binary,
                workspace_dir=workspace,
                process_env=env,
                sandbox="read-only",
                timeout=60,
                model=model,
            )
            # Canary is deliberately outside a Git repository; ordinary tasks retain the Git check.
            command = adapter.build_cli_command(prompt)
            command.insert(-1, "--skip-git-repo-check")
            parser = adapter._parse_jsonl_output
        else:
            from client.adapters.opencode_cli_adapter import OpenCodeCLIAdapter

            adapter = OpenCodeCLIAdapter(
                profile["id"],
                "Auth verification",
                opencode_path=binary,
                workspace_dir=workspace,
                process_env=env,
                auto_approve=False,
                timeout=60,
                model=model,
            )
            command = adapter.build_cli_command(prompt)
            command[-1:-1] = ["--agent", "plan"]
            parser = adapter._parse_jsonl_output
        from client.process_runtime import spawn_background, communicate_background

        proc = await spawn_background(
            *command,
            env=env,
            cwd=workspace,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, stderr = await communicate_background(proc, 60)
        text, error = parser(output.decode("utf-8", errors="replace"))
        success = proc.returncode == 0 and not error and "FLEET_AUTH_OK" in text
        result = {
            "success": success,
            "error": error or stderr.decode("utf-8", errors="replace") or "Canary response was not confirmed",
        }
        return {
            "success": success,
            "error_kind": classify_failure(result),
            "retry_after_seconds": reported_retry_after(output.decode("utf-8", errors="replace")),
        }


def manage(store: AccountStore, args: argparse.Namespace) -> int:
    profile = store.get(args.id)
    if profile["provider"] == "agy_cli":
        raise ValueError(AGY_ISOLATION_NOTE)
    acquired = store.acquire(profile["provider"], f"accounts:{args.command}", profile_id=profile["id"], management=True)
    if acquired is None:
        raise ValueError("Profile is already leased; wait for its task/login operation to finish")
    _, token = acquired
    state = "unverified"
    confirmed = bool(getattr(args, "identity_confirmed", False)) or bool(profile["identity_verified"])
    note = ""
    error_kind = None
    retry_after = None
    try:
        if args.command in ("login", "logout"):
            confirmed = False
            if args.command == "login" and profile["provider"] == "opencode_cli":
                print(
                    "Select the ChatGPT subscription login method in OpenCode. Complete authorization in your browser.",
                    flush=True,
                )
            # Intentional foreground command: native OAuth prompts and login errors stay visible.
            completed = subprocess.run(
                native_command(profile, args.command, getattr(args, "device_auth", False)),
                env=profile_environment(profile),
                cwd=profile["credential_dir"],
                check=False,
            )
            if completed.returncode:
                note = "Native login/logout did not complete; retry the explicit account command"
                return 1
            state = auth_state(profile) if args.command == "login" else "unverified"
        else:
            state = auth_state(profile)
            if args.canary:
                result = asyncio.run(canary(profile, args.model))
                error_kind = result["error_kind"]
                retry_after = result.get("retry_after_seconds")
                state = "ready" if result["success"] else "verification_failed"
                if error_kind == "authentication":
                    state = "reauth_required"
                elif error_kind == "quota_exhausted":
                    state = "ready" if retry_after is not None else "quota_exhausted"
                elif error_kind == "rate_limit":
                    state = profile["auth_state"]
                if not result["success"]:
                    note = f"Canary failed ({error_kind}); retry verification when available"
            elif state == "configured" and profile["auth_state"] == "ready":
                state = "ready"
            # A cached sign-in does not prove that an exhausted plan has reset.
            if profile["auth_state"] == "quota_exhausted" and not args.canary:
                state = "quota_exhausted"
                note = "Explicit --canary verification is required to restore quota-exhausted profiles"
        print(f"{profile['id']}: {state}")
        if state == "configured":
            note = "OpenCode credential configured; run verify --canary to prove execution access"
            print(note)
        return 0 if state in ("ready", "configured", "unverified") else 1
    except KeyboardInterrupt:
        note = "Login/verification cancelled; profile requires explicit verification"
        print(note, file=sys.stderr)
        return 130
    except Exception:
        state = "verification_failed"
        note = "Native operation failed; explicit verification is required"
        raise
    finally:
        store.finish_management(
            profile["id"],
            token,
            state=state,
            identity_verified=confirmed,
            note=note,
            error_kind=error_kind,
            retry_after=retry_after,
            reset_failure=bool(args.command == "verify" and args.canary and state == "ready" and error_kind is None),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fleet CLI account login and rotation")
    parser.add_argument("--state-root", help="Local private account store; must be outside this repository")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("--id", required=True)
    add.add_argument("--provider", choices=PROVIDERS, required=True)
    add.add_argument("--label")
    add.add_argument("--pool", default="default")
    add.add_argument("--account-group")
    add.add_argument("--binary")
    status = commands.add_parser("status")
    status.add_argument("--json", action="store_true")
    for name in ("login", "verify", "enable", "disable", "logout"):
        command = commands.add_parser(name)
        command.add_argument("--id", required=True)
        if name == "login":
            command.add_argument("--device-auth", action="store_true")
            command.add_argument(
                "--new-window", action="store_true", help="Open an intentional login console that stays open on errors"
            )
            command.add_argument("--pause", action="store_true", help=argparse.SUPPRESS)
        if name == "verify":
            command.add_argument(
                "--canary",
                action="store_true",
                help="Explicitly submit a small model prompt; consumes provider allowance",
            )
            command.add_argument("--model")
            command.add_argument(
                "--identity-confirmed",
                action="store_true",
                help="Confirm you selected the intended identity during native sign-in",
            )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "accounts":
        argv.pop(0)
    args = build_parser().parse_args(argv)
    code = 0
    try:
        store = AccountStore(args.state_root)
        if args.command == "add":
            profile = store.add(
                args.id,
                args.provider,
                label=args.label,
                pool=args.pool,
                account_group=args.account_group,
                binary=args.binary,
            )
            print(f"Added {profile['id']}: {profile['auth_state']}")
            if profile["note"]:
                print(profile["note"])
        elif args.command == "status":
            rows = store.list()
            for row in rows:
                row["quota_remaining"] = None
                try:
                    env = profile_environment(row) if row["provider"] != "agy_cli" else None
                    result = run_background(
                        [binary_for(row), "--version" if row["provider"] != "agy_cli" else "--help"],
                        env=env,
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        timeout=10,
                    )
                    row["installed"] = result.returncode == 0
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    row["installed"] = False
                row["available"] = bool(
                    row["installed"]
                    and row["enabled"]
                    and row["auth_state"] == "ready"
                    and row["cooldown_until"] <= time.time()
                    and not row["lease_owner"]
                )
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for row in rows:
                    print(
                        f"{row['id']}: {row['provider']} | installed={row['installed']} | auth={row['auth_state']} | identity_verified={bool(row['identity_verified'])} | available={row['available']}"
                    )
                    if row["note"]:
                        print(f"  {row['note']}")
        elif args.command in ("enable", "disable"):
            store.update(args.id, enabled=int(args.command == "enable"))
            print(f"{args.id}: {args.command}d")
        elif args.command == "login" and args.new_window:
            if os.name != "nt":
                raise ValueError("--new-window is Windows-only; run login in your terminal")
            profile = store.get(args.id)
            if profile["provider"] == "agy_cli":
                raise ValueError(AGY_ISOLATION_NOTE)
            command = [
                sys.executable,
                "-m",
                "tools.fleet_accounts",
                "--state-root",
                str(store.root),
                "login",
                "--id",
                args.id,
                "--pause",
            ]
            if args.device_auth:
                command.append("--device-auth")
            subprocess.Popen(command, cwd=PROJECT_ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            code = manage(store, args)
    except (ValueError, sqlite3.Error, OSError, subprocess.TimeoutExpired) as exc:
        # Provider stdout remains visible only in the explicit foreground login.
        print(f"Account operation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        if getattr(args, "id", None):
            try:
                profile = store.get(args.id)
                if profile["provider"] == "agy_cli":
                    print(AGY_ISOLATION_NOTE, file=sys.stderr)
            except (ValueError, UnboundLocalError):
                pass
        code = 1
    finally:
        if getattr(args, "pause", False):
            try:
                input("Press Enter to close this login terminal...")
            except EOFError:
                pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
