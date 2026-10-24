"""Unit tests for CopilotTokenPool (Issue #27)."""

import time
from pathlib import Path
from client.copilot_token_pool import CopilotTokenPool


def test_token_pool_init_and_filtering():
    dummy_tok_1 = "mock_" + "pat_alpha_12345"
    dummy_tok_2 = "mock_" + "pat_beta_67890"

    accounts = [
        {"token": dummy_tok_1, "name": "acc_1", "worker_id": "copilot-w1"},
        {"token": "github_pat_REPLACE_ME_XYZ", "name": "placeholder_acc"},
        {"token": "", "name": "empty_acc"},
        {"token": "short", "name": "too_short_acc"},
        {"token": dummy_tok_2, "name": "acc_2", "worker_id": "copilot-w2"},
    ]

    pool = CopilotTokenPool(accounts)
    assert len(pool) == 2
    assert pool.accounts[0]["name"] == "acc_1"
    assert pool.accounts[1]["name"] == "acc_2"


def test_token_pool_round_robin_cycling():
    tok1 = "mock_" + "pat_one_12345"
    tok2 = "mock_" + "pat_two_12345"
    tok3 = "mock_" + "pat_three_12345"

    pool = CopilotTokenPool()
    pool.add_account(token=tok1, name="acc1", worker_id="w1")
    pool.add_account(token=tok2, name="acc2", worker_id="w2")
    pool.add_account(token=tok3, name="acc3", worker_id="w3")

    assert len(pool) == 3

    # Consecutive get_next calls cycle in round-robin order
    a1 = pool.get_next()
    a2 = pool.get_next()
    a3 = pool.get_next()
    a4 = pool.get_next()

    assert a1["name"] == "acc1"
    assert a2["name"] == "acc2"
    assert a3["name"] == "acc3"
    assert a4["name"] == "acc1"  # Wraps around


def test_token_pool_cooldown_governance():
    tok1 = "mock_" + "pat_active1_1234"
    tok2 = "mock_" + "pat_active2_5678"

    pool = CopilotTokenPool()
    pool.add_account(token=tok1, name="acc1", worker_id="w1")
    pool.add_account(token=tok2, name="acc2", worker_id="w2")

    # Mark acc1 as rate-limited
    pool.mark_rate_limited(1, cooldown_seconds=120.0)

    summary = pool.get_summary()
    assert summary["total_accounts"] == 2
    assert summary["active_accounts"] == 1
    assert summary["cooldown_accounts"] == 1

    # get_next skips acc1 and returns acc2
    next_acc = pool.get_next(skip_in_cooldown=True)
    assert next_acc["name"] == "acc2"


def test_token_pool_mark_quota_and_auth():
    tok = "mock_" + "pat_sample_0000"
    pool = CopilotTokenPool([{"token": tok, "name": "sample"}])

    pool.mark_quota_exhausted(1, cooldown_seconds=300.0)
    acc = pool.accounts[0]
    assert acc["cooldown_until"] > time.time()
    assert acc["fail_count"] == 1
    assert "QUOTA_EXHAUSTED" in acc["last_error"]

    pool.mark_success(1)
    acc = pool.accounts[0]
    assert acc["success_count"] == 1
    assert acc["last_error"] is None


def test_token_pool_from_env_vars():
    mock_env = {
        "COPILOT_ACCOUNT_1_TOKEN": "mock_" + "env_pat_1_12345",
        "COPILOT_ACCOUNT_1_NAME": "AaradhyaDT",
        "COPILOT_ACCOUNT_2_TOKEN": "mock_" + "env_pat_2_67890",
        "COPILOT_ACCOUNT_2_NAME": "Worker0",
        "COPILOT_ACCOUNT_3_TOKEN": "github_pat_REPLACE_ME",
    }

    pool = CopilotTokenPool.from_env_fleet(env_vars=mock_env)
    assert len(pool) >= 2
    # Verify AaradhyaDT and Worker0 exist in pool
    names = [a["name"] for a in pool.accounts]
    assert "AaradhyaDT" in names
    assert "Worker0" in names


def test_token_pool_masking():
    tok = "mock_" + "secret_token_val_9999"
    masked = CopilotTokenPool.mask_token(tok)
    assert masked.startswith("mock")
    assert masked.endswith("9999")
    assert "..." in masked
