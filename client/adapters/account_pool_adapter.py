"""Bind one account lease to an entire task; rotate only between executions."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from client.adapters.base_adapter import BaseWorkerAdapter
from client.cli_accounts import AccountStore, classify_failure, AGY_ISOLATION_NOTE, save_failed_attempt, redact_message
from client.process_runtime import launch_observer


class AccountPoolAdapter(BaseWorkerAdapter):
    def __init__(
        self,
        worker_id: str,
        nickname: str,
        provider: str,
        factory: Any,
        *,
        profile_id: str | None = None,
        pool: str | None = None,
        store: AccountStore | None = None,
    ):
        super().__init__(worker_id, nickname, ["code", "research", "writing", "qa_review", "formatting"])
        self.provider = provider
        self.factory = factory
        self.profile_id = profile_id
        self.pool = pool
        self.store = store or AccountStore()

    async def check_health(self) -> bool:
        # No model calls and no session/account mutation for readiness checks.
        available = [
            p
            for p in self.store.list()
            if p["provider"] == self.provider
            and p["enabled"]
            and p["auth_state"] == "ready"
            and p["cooldown_until"] <= time.time()
            and not p["lease_owner"]
            and (p["id"] == self.profile_id if self.profile_id else p["pool"] == self.pool)
        ]
        if not available:
            return False
        return await self.factory(available[0]).check_health()

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        self.last_profile = None
        if self.provider == "agy_cli":
            return {
                "success": False,
                "error": AGY_ISOLATION_NOTE,
                "error_kind": "isolation_unverified",
                "execution_started": False,
                "summary": "",
                "result_text": "",
            }
        acquired = self.store.acquire(
            self.provider, f"{self.worker_id}:{task_id}", profile_id=self.profile_id, pool=self.pool
        )
        if acquired is None:
            return {
                "success": False,
                "error": "No available authenticated account in this profile/pool",
                "error_kind": "account_unavailable",
                "execution_started": False,
                "summary": "",
                "result_text": "",
                "task_id": task_id,
            }
        profile, token = acquired
        self.last_profile = profile["id"]
        observer_token = launch_observer.set(
            lambda proc: self.store.record_child(profile["id"], token, getattr(proc, "pid", None))
        )
        done = asyncio.Event()

        async def renew() -> None:
            while not done.is_set():
                try:
                    await asyncio.wait_for(done.wait(), timeout=30)
                except asyncio.TimeoutError:
                    self.store.renew(profile["id"], token)

        renewal = asyncio.create_task(renew())
        result: dict[str, Any] = {}
        execution = None
        try:
            adapter = self.factory(profile)
            execution = asyncio.create_task(adapter.execute_task(task_id, spec, stage, context))
            completed, _ = await asyncio.wait((execution, renewal), return_when=asyncio.FIRST_COMPLETED)
            if renewal in completed and renewal.exception():
                execution.cancel()
                await asyncio.gather(execution, return_exceptions=True)
                raise renewal.exception()
            try:
                result = await execution
            except asyncio.CancelledError:
                execution.cancel()
                await asyncio.gather(execution, return_exceptions=True)
                raise
            result["auth_profile"] = profile["id"]
            result["summary"] = f"{result.get('summary', '')} [AuthProfile: {profile['id']}]"
            result["account_group"] = profile["account_group"]
            result["workspace"] = str(getattr(adapter, "workspace_dir", ""))
            result["error_kind"] = classify_failure(result)
            result.setdefault("execution_started", True)
            return result
        except asyncio.CancelledError:
            save_failed_attempt(
                self.worker_id,
                task_id,
                {
                    "auth_profile": profile["id"],
                    "error_kind": "cancelled",
                    "error": "CLI task interrupted; inspect retained workspace before retry",
                    "workspace": str(getattr(locals().get("adapter"), "workspace_dir", "")),
                    "execution_started": execution is not None,
                },
                root=self.store.root,
            )
            raise
        except Exception as exc:
            result = {
                "success": False,
                "error": redact_message(str(exc)),
                "error_kind": "process",
                "execution_started": execution is not None,
                "auth_profile": profile["id"],
                "account_group": profile["account_group"],
                "workspace": str(getattr(locals().get("adapter"), "workspace_dir", "")),
                "summary": "",
                "result_text": "",
            }
            return result
        finally:
            launch_observer.reset(observer_token)
            if execution is not None and not execution.done():
                execution.cancel()
                await asyncio.gather(execution, return_exceptions=True)
            done.set()
            await asyncio.gather(renewal, return_exceptions=True)
            self.store.release(
                profile["id"],
                token,
                error_kind=classify_failure(result) if result else "process",
                retry_after=result.get("retry_after_seconds"),
            )
