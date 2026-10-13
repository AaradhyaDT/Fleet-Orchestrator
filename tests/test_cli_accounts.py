from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
from unittest.mock import AsyncMock

import pytest

from client.cli_accounts import AccountStore, classify_failure, profile_environment, save_failed_attempt
from client.adapters.account_pool_adapter import AccountPoolAdapter
from tools import fleet_accounts


@pytest.fixture
def store(tmp_path):
    return AccountStore(tmp_path / "private")


def ready(store, name, provider="codex_cli", pool="default", group=None):
    profile = store.add(name, provider, pool=pool, account_group=group)
    store.update(name, auth_state="ready")
    return profile


def test_profiles_do_not_share_auth_or_ambient_keys(store, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-leak")
    a = store.add("A", "codex_cli")
    b = store.add("b", "codex_cli")
    assert a["id"] == "a"
    assert profile_environment(a)["CODEX_HOME"] != profile_environment(b)["CODEX_HOME"]
    assert "OPENAI_API_KEY" not in profile_environment(a)
    assert 'cli_auth_credentials_store = "file"' in (Path(a["credential_dir"]) / "config.toml").read_text()
    with pytest.raises(Exception):
        store.add("a", "codex_cli")
    with pytest.raises(ValueError):
        store.add("CON", "codex_cli")
    c = store.add("c", "opencode_cli")
    env = profile_environment(c)
    for kind in ("DATA", "CONFIG", "CACHE", "STATE"):
        assert env[f"XDG_{kind}_HOME"].startswith(c["credential_dir"])
    assert "CODEX_HOME" not in env


def test_agy_isolation_is_not_assumed(store):
    profile = store.add("agy-a", "agy_cli")
    assert profile["auth_state"] == "isolation_unverified"
    with pytest.raises(ValueError, match="OS credential store"):
        profile_environment(profile)
    with pytest.raises(ValueError, match="OS credential store"):
        fleet_accounts.native_command(profile, "logout")
    assert store.acquire("agy_cli", "test", pool="default") is None


def test_round_robin_contention_and_shared_account_groups(store):
    ready(store, "a", group="plus-one")
    ready(store, "b")
    ready(store, "oc", provider="opencode_cli", group="plus-one")
    a, token = store.acquire("codex_cli", "worker", pool="default")
    assert a["id"] == "a"
    with pytest.raises(ValueError, match="leased"):
        store.update("a", enabled=False)
    with ThreadPoolExecutor(max_workers=4) as executor:
        claims = list(executor.map(lambda _: store.acquire("codex_cli", "worker", pool="default"), range(4)))
    assert sum(c is not None for c in claims) == 1
    assert store.acquire("opencode_cli", "other-cli", pool="default") is not None
    store.release("a", token)
    claim = next(c for c in claims if c)
    store.release(claim[0]["id"], claim[1])
    assert store.acquire("codex_cli", "worker", pool="default")[0]["id"] == "a"


def test_cooldown_auth_and_quota_failures_are_distinct(store):
    ready(store, "a")
    p, token = store.acquire("codex_cli", "worker", profile_id="a")
    start = time.time()
    store.release(p["id"], token, error_kind="rate_limit")
    assert start + 59 <= store.get("a")["cooldown_until"] <= time.time() + 60
    assert store.acquire("codex_cli", "worker", profile_id="a") is None
    store.update("a", cooldown_until=0)
    _, token = store.acquire("codex_cli", "worker", profile_id="a")
    store.release("a", token, error_kind="quota_exhausted")
    assert store.get("a")["auth_state"] == "quota_exhausted"
    store.update("a", auth_state="ready")
    _, token = store.acquire("codex_cli", "worker", profile_id="a")
    store.release("a", token, error_kind="authentication")
    assert store.get("a")["auth_state"] == "reauth_required"
    assert classify_failure({"error": "401 unauthorized"}) == "authentication"
    assert classify_failure({"error": "429 Too many requests"}) == "rate_limit"
    assert classify_failure({"error": "Usage limit reached"}) == "quota_exhausted"


def test_dead_process_lease_is_recovered_but_live_expired_lease_is_not(store):
    ready(store, "a")
    _, token = store.acquire("codex_cli", "worker", profile_id="a")
    with store.transaction() as db:
        db.execute("UPDATE leases SET expires=0")
    assert store.acquire("codex_cli", "another", profile_id="a") is None
    with store.transaction() as db:
        db.execute("UPDATE leases SET process_started=0")
    assert store.acquire("codex_cli", "another", profile_id="a") is not None


@pytest.mark.asyncio
async def test_pool_does_not_replay_failure_and_releases_on_cancellation(store):
    ready(store, "a")
    ready(store, "b")
    backend = AsyncMock()
    backend.execute_task.return_value = {"success": False, "error": "429 rate limit", "result_text": "partial"}
    wrapper = AccountPoolAdapter("w", "Worker", "codex_cli", lambda _: backend, pool="default", store=store)
    result = await wrapper.execute_task("t", "change file", "code", {})
    assert result["auth_profile"] == "a"
    assert result["execution_started"] is True
    backend.execute_task.assert_awaited_once()
    assert not any(p["lease_owner"] for p in store.list())
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def slow(*args):
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            stopped.set()

    backend.execute_task.side_effect = slow
    running = asyncio.create_task(wrapper.execute_task("t2", "change file", "code", {}))
    await started.wait()
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert stopped.is_set()
    assert not any(p["lease_owner"] for p in store.list())


def test_cancelled_login_does_not_mark_ready(store, monkeypatch):
    store.add("a", "codex_cli", binary="test-codex")
    monkeypatch.setattr(fleet_accounts.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert fleet_accounts.main(["--state-root", str(store.root), "login", "--id", "a"]) == 130
    assert store.get("a")["auth_state"] == "unverified"
    assert store.list()[0]["lease_owner"] is None


def test_failed_attempt_checkpoint_is_private_and_redacted(store, monkeypatch):
    monkeypatch.setenv("FLEET_ACCOUNTS_HOME", str(store.root))
    target = save_failed_attempt("w", "t", {"error": "Bearer sensitive-token", "result_text": "partial"})
    value = json.loads(target.read_text())
    assert "sensitive-token" not in target.read_text()
    assert value["result_text"] == "partial"


def test_factory_bindings_preserve_legacy_and_reject_conflicts(store, monkeypatch):
    from client.fleet_supervisor import create_adapter

    monkeypatch.setenv("FLEET_ACCOUNTS_HOME", str(store.root))
    ready(store, "a")
    adapter = create_adapter({"Account": "w", "Provider": "codex_cli", "AuthProfile": "a"})
    assert isinstance(adapter, AccountPoolAdapter)
    assert adapter.factory(store.get("a"))._prepare_environment()["CODEX_HOME"] == store.get("a")["credential_dir"]
    with pytest.raises(ValueError, match="mutually exclusive"):
        create_adapter({"Provider": "codex_cli", "AuthProfile": "a", "AccountPool": "default"})
    assert not isinstance(
        create_adapter({"Provider": "codex_cli", "CodexHome": str(store.root / "legacy")}), AccountPoolAdapter
    )


@pytest.mark.asyncio
async def test_factory_failure_returns_prestart_error_and_releases(store):
    ready(store, "a")

    def fail(profile):
        raise OSError("provider unavailable")

    wrapper = AccountPoolAdapter("w", "Worker", "codex_cli", fail, profile_id="a", store=store)
    result = await wrapper.execute_task("t", "prompt", "code", {})
    assert result["execution_started"] is False
    assert result["error_kind"] == "process"
    assert store.list()[0]["lease_owner"] is None


def test_cached_verification_does_not_clear_cooldown(store, monkeypatch):
    ready(store, "a")
    _, token = store.acquire("codex_cli", "worker", profile_id="a")
    store.release("a", token, error_kind="rate_limit")
    previous = store.get("a")["cooldown_until"]
    monkeypatch.setattr(fleet_accounts, "auth_state", lambda _: "ready")
    assert fleet_accounts.main(["--state-root", str(store.root), "verify", "--id", "a"]) == 0
    assert store.get("a")["cooldown_until"] == previous
