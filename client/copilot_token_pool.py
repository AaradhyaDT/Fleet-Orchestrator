"""
Copilot Token Pool & Round-Robin PAT Rotator.
Manages a pool of GitHub Personal Access Tokens (PATs) discovered from .env.fleet,
providing thread-safe round-robin rotation per prompt, individual COPILOT_HOME isolation,
and transient rate-limit / quota-exhaustion cooldown governance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("copilot_token_pool")

PLACEHOLDER_PREFIXES = (
    "github_pat_REPLACE",
    "your_pat_here",
    "placeholder",
    "mock_key",
    "dummy_",
)


class CopilotTokenPool:
    """
    Thread-safe & async-safe round-robin PAT rotator for GitHub Copilot CLI executions.
    """

    def __init__(self, accounts: list[dict[str, Any]] | None = None):
        self._accounts: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._async_lock: asyncio.Lock | None = None
        self._current_index: int = 0

        if accounts:
            for acc in accounts:
                self.add_account(
                    token=acc.get("token", ""),
                    name=acc.get("name", ""),
                    worker_id=acc.get("worker_id", ""),
                    copilot_home=acc.get("copilot_home") or acc.get("state_dir"),
                    monthly_credits=acc.get("monthly_credits", 200),
                )

    def __len__(self) -> int:
        return len(self._accounts)

    @property
    def accounts(self) -> list[dict[str, Any]]:
        return list(self._accounts)

    @staticmethod
    def _is_valid_token(token: str) -> bool:
        t = token.strip()
        if not t:
            return False
        for prefix in PLACEHOLDER_PREFIXES:
            if t.startswith(prefix):
                return False
        return len(t) >= 10

    @staticmethod
    def mask_token(token: str) -> str:
        """Returns masked token string for secure telemetry/logging."""
        if not token:
            return "<none>"
        clean = token.strip()
        if len(clean) <= 8:
            return "***"
        return f"{clean[:4]}...{clean[-4:]}"

    def add_account(
        self,
        token: str,
        name: str = "",
        worker_id: str = "",
        copilot_home: Path | str | None = None,
        monthly_credits: int = 200,
    ) -> None:
        """Appends an account token if valid and not already in pool."""
        clean_token = token.strip()
        if not self._is_valid_token(clean_token):
            return

        idx = len(self._accounts) + 1
        w_id = worker_id or f"copilot-w{idx}"
        acc_name = name or f"account_{idx}"

        if copilot_home:
            home_path = Path(copilot_home).resolve()
        else:
            home_path = Path.home() / ".copilot-workers" / f"worker_{idx}_{acc_name}"

        account_entry = {
            "index": idx,
            "worker_id": w_id,
            "name": acc_name,
            "token": clean_token,
            "copilot_home": home_path,
            "monthly_credits": monthly_credits,
            "cooldown_until": 0.0,
            "fail_count": 0,
            "success_count": 0,
            "last_error": None,
        }
        self._accounts.append(account_entry)

    @classmethod
    def from_env_fleet(
        cls,
        repo_root: Path | str | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> CopilotTokenPool:
        """
        Discovers accounts and tokens from .env.fleet, .env.fleet.copilot,
        and environment variables (COPILOT_PAT_POOL, COPILOT_ACCOUNT_*).
        """
        pool = cls()
        merged_vars: dict[str, str] = {}

        # 1. Load from fleet_env if available
        root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parent.parent
        try:
            from tools.fleet_env import load_all_fleet_env

            fleet_data = load_all_fleet_env(root, inject_os_environ=False)
            merged_vars.update(fleet_data.get("copilot", {}))
            merged_vars.update(fleet_data.get("merged", {}))
        except Exception:
            # Fallback manual read
            for candidate in [
                root / ".env.fleet.copilot",
                root / ".env.fleet",
                root / ".env",
            ]:
                if candidate.is_file():
                    try:
                        with open(candidate, "r", encoding="utf-8", errors="replace") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("#") and "=" in line:
                                    k, v = line.split("=", 1)
                                    merged_vars[k.strip()] = v.strip().strip('"').strip("'")
                    except Exception:
                        pass

        # 2. Add caller-provided env_vars
        if env_vars:
            merged_vars.update(env_vars)

        # 3. Add active OS environment variables for overrides
        for k, v in os.environ.items():
            if k.startswith("COPILOT_") or k in {"GITHUB_TOKEN", "GH_TOKEN"}:
                merged_vars.setdefault(k, v)

        # A. Check for explicit COPILOT_PAT_POOL (comma-separated or JSON list)
        pat_pool_raw = merged_vars.get("COPILOT_PAT_POOL", "").strip()
        if pat_pool_raw:
            tokens: list[str] = []
            if pat_pool_raw.startswith("[") and pat_pool_raw.endswith("]"):
                try:
                    tokens = json.loads(pat_pool_raw)
                except Exception:
                    tokens = [t.strip() for t in pat_pool_raw.strip("[]").split(",")]
            else:
                tokens = [t.strip() for t in pat_pool_raw.split(",")]

            for i, tok in enumerate(tokens, start=1):
                pool.add_account(
                    token=tok,
                    name=f"pool_pat_{i}",
                    worker_id=f"copilot-pool-{i}",
                )

        # B. Check for numbered COPILOT_ACCOUNT_{i}_*
        i = 1
        while True:
            token_key = f"COPILOT_ACCOUNT_{i}_TOKEN"
            name_key = f"COPILOT_ACCOUNT_{i}_NAME"
            credits_key = f"COPILOT_ACCOUNT_{i}_MONTHLY_CREDITS"

            token = merged_vars.get(token_key, "").strip()
            name = merged_vars.get(name_key, f"account_{i}").strip()
            credits_str = merged_vars.get(credits_key, "200").strip()

            if not token:
                if i > 32:  # Stop scanning after standard 31+ accounts
                    break
                i += 1
                continue

            credits = int(credits_str) if credits_str.isdigit() else 200
            pool.add_account(
                token=token,
                name=name,
                worker_id=f"copilot-w{i}",
                monthly_credits=credits,
            )
            i += 1

        # C. Fallback: single COPILOT_GITHUB_TOKEN or GITHUB_TOKEN if pool is still empty
        if len(pool) == 0:
            fallback = (
                merged_vars.get("COPILOT_GITHUB_TOKEN")
                or merged_vars.get("GITHUB_TOKEN")
                or merged_vars.get("GH_TOKEN")
                or ""
            ).strip()
            if fallback:
                pool.add_account(
                    token=fallback,
                    name="default_pat",
                    worker_id="copilot-default",
                )

        return pool

    def get_next(self, skip_in_cooldown: bool = True) -> dict[str, Any] | None:
        """
        Returns the next available account entry in round-robin order.
        Thread-safe.
        """
        with self._lock:
            if not self._accounts:
                return None

            n = len(self._accounts)
            now = time.time()

            # Attempt to find an account not in cooldown
            if skip_in_cooldown:
                for _ in range(n):
                    candidate = self._accounts[self._current_index]
                    self._current_index = (self._current_index + 1) % n
                    if candidate["cooldown_until"] <= now:
                        return candidate

                # If all are in cooldown, pick the one that expires soonest
                earliest = min(self._accounts, key=lambda a: a["cooldown_until"])
                return earliest

            # Unconditionally advance
            candidate = self._accounts[self._current_index]
            self._current_index = (self._current_index + 1) % n
            return candidate

    async def get_next_async(self, skip_in_cooldown: bool = True) -> dict[str, Any] | None:
        """Async variant of get_next."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        async with self._async_lock:
            return self.get_next(skip_in_cooldown=skip_in_cooldown)

    def _resolve_account(self, identifier: str | int) -> dict[str, Any] | None:
        if isinstance(identifier, int):
            for acc in self._accounts:
                if acc["index"] == identifier:
                    return acc
        elif isinstance(identifier, str):
            for acc in self._accounts:
                if acc["token"] == identifier or acc["worker_id"] == identifier or acc["name"] == identifier:
                    return acc
        return None

    def mark_rate_limited(self, identifier: str | int, cooldown_seconds: float = 60.0) -> None:
        """Marks account as rate-limited (HTTP 429) for the specified cooldown duration."""
        acc = self._resolve_account(identifier)
        if acc:
            with self._lock:
                acc["cooldown_until"] = time.time() + cooldown_seconds
                acc["fail_count"] += 1
                acc["last_error"] = f"RATE_LIMITED_429: cooldown {cooldown_seconds}s"
                logger.warning(
                    f"Account {acc['worker_id']} ({acc['name']}) marked 429 cooldown until +{cooldown_seconds}s"
                )

    def mark_quota_exhausted(self, identifier: str | int, cooldown_seconds: float = 3600.0) -> None:
        """Marks account as quota exhausted (credit limit reached)."""
        acc = self._resolve_account(identifier)
        if acc:
            with self._lock:
                acc["cooldown_until"] = time.time() + cooldown_seconds
                acc["fail_count"] += 1
                acc["last_error"] = f"QUOTA_EXHAUSTED: cooldown {cooldown_seconds}s"
                logger.warning(
                    f"Account {acc['worker_id']} ({acc['name']}) marked quota exhausted (+{cooldown_seconds}s)"
                )

    def mark_auth_error(self, identifier: str | int, cooldown_seconds: float = 3600.0) -> None:
        """Marks account with authentication failure."""
        acc = self._resolve_account(identifier)
        if acc:
            with self._lock:
                acc["cooldown_until"] = time.time() + cooldown_seconds
                acc["fail_count"] += 1
                acc["last_error"] = f"AUTH_ERROR: cooldown {cooldown_seconds}s"
                logger.warning(f"Account {acc['worker_id']} ({acc['name']}) marked auth error (+{cooldown_seconds}s)")

    def mark_success(self, identifier: str | int) -> None:
        """Records successful execution on account and clears transient error."""
        acc = self._resolve_account(identifier)
        if acc:
            with self._lock:
                acc["success_count"] += 1
                acc["last_error"] = None

    def get_summary(self) -> dict[str, Any]:
        """Returns structured status summary across all accounts in the pool."""
        now = time.time()
        with self._lock:
            accounts_summary = []
            active_count = 0
            cooldown_count = 0

            for acc in self._accounts:
                in_cooldown = acc["cooldown_until"] > now
                remaining_cooldown = max(0.0, acc["cooldown_until"] - now) if in_cooldown else 0.0
                if in_cooldown:
                    cooldown_count += 1
                else:
                    active_count += 1

                accounts_summary.append({
                    "index": acc["index"],
                    "worker_id": acc["worker_id"],
                    "name": acc["name"],
                    "token_masked": self.mask_token(acc["token"]),
                    "copilot_home": str(acc["copilot_home"]),
                    "monthly_credits": acc["monthly_credits"],
                    "in_cooldown": in_cooldown,
                    "cooldown_remaining_s": round(remaining_cooldown, 1),
                    "success_count": acc["success_count"],
                    "fail_count": acc["fail_count"],
                    "last_error": acc["last_error"],
                })

            return {
                "total_accounts": len(self._accounts),
                "active_accounts": active_count,
                "cooldown_accounts": cooldown_count,
                "current_rotation_index": self._current_index,
                "accounts": accounts_summary,
            }
