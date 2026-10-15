"""
Tests for Antigravity CLI Rotator & Profile Vault (Issue #26).
Verifies Windows Credential Manager snapshot/restore, profile lifecycle, and rotation.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch, MagicMock

import pytest

from client.windows_cred import (
    is_windows,
    read_generic_credential,
    write_generic_credential,
    snapshot_agy_credential,
    restore_agy_credential,
    AGY_CREDENTIAL_TARGET,
)
from client.cli_accounts import AccountStore
from tools.agy_rotator import (
    safe_get_profile,
    cmd_save,
    cmd_switch,
    cmd_list,
    cmd_exec,
)


@pytest.fixture
def temp_store(tmp_path):
    return AccountStore(tmp_path / "private_fleet")


def test_windows_cred_lifecycle(tmp_path):
    if not is_windows():
        pytest.skip("Windows Credential Manager is only testable on NT platforms")

    # Snapshot whatever is active
    snapshot_file = tmp_path / "active_cred.bin"
    did_snapshot = snapshot_agy_credential(snapshot_file)
    if not did_snapshot:
        pytest.skip("No active Antigravity session on this machine to snapshot")

    assert snapshot_file.exists()
    assert snapshot_file.stat().st_size > 100

    # Test restoring the same snapshot
    restored = restore_agy_credential(snapshot_file)
    assert restored is True

    # Read back to verify
    cred = read_generic_credential(AGY_CREDENTIAL_TARGET)
    assert cred is not None
    assert cred[0] == "antigravity"


def test_safe_get_profile(temp_store):
    assert safe_get_profile(temp_store, "nonexistent") is None
    temp_store.add("user1", "agy_cli")
    profile = safe_get_profile(temp_store, "user1")
    assert profile is not None
    assert profile["id"] == "user1"
    assert profile["provider"] == "agy_cli"


def test_cmd_save_and_list(temp_store, monkeypatch, capsys):
    monkeypatch.setattr("tools.agy_rotator.get_default_store", lambda: temp_store)
    
    with patch("tools.agy_rotator.snapshot_agy_credential") as mock_snap:
        mock_snap.return_value = True
        
        # Fake creating credential file
        def fake_snap(target_path):
            Path(target_path).parent.mkdir(parents=True, exist_ok=True)
            Path(target_path).write_bytes(b"dummy_cred_blob_content_12345")
            return True
        mock_snap.side_effect = fake_snap

        args = argparse.Namespace(id="user1", pool="default", label="Primary Account")
        res = cmd_save(args)
        assert res == 0

        profile = temp_store.get("user1")
        assert profile["auth_state"] == "ready"
        assert profile["identity_verified"] == 1

        # Test listing
        res_list = cmd_list(argparse.Namespace())
        assert res_list == 0
        captured = capsys.readouterr()
        assert "user1" in captured.out
        assert "ready" in captured.out


def test_cmd_switch(temp_store, monkeypatch):
    monkeypatch.setattr("tools.agy_rotator.get_default_store", lambda: temp_store)
    profile = temp_store.add("user1", "agy_cli")
    cred_file = Path(profile["credential_dir"]) / "credential.bin"
    cred_file.write_bytes(b"dummy_cred_content")

    with patch("tools.agy_rotator.restore_agy_credential") as mock_restore:
        mock_restore.return_value = True
        args = argparse.Namespace(id="user1")
        res = cmd_switch(args)
        assert res == 0
        mock_restore.assert_called_once_with(cred_file)


def test_cmd_exec_success(temp_store, monkeypatch, capsys):
    monkeypatch.setattr("tools.agy_rotator.get_default_store", lambda: temp_store)
    profile = temp_store.add("user1", "agy_cli")
    temp_store.update("user1", auth_state="ready", enabled=1)
    
    with patch("tools.agy_rotator.restore_agy_credential") as mock_restore, \
         patch("tools.agy_rotator.subprocess.run") as mock_run:
        
        mock_restore.return_value = True
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "response": "TEST_OK",
            "duration_seconds": 1.25,
            "usage": {"total_tokens": 150}
        })
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        args = argparse.Namespace(
            prompt="say hello",
            profile="user1",
            pool="default",
            model="gemini-3.8-flash",
            effort="high",
            timeout=60,
        )
        res = cmd_exec(args)
        assert res == 0
        captured = capsys.readouterr()
        assert "[user1 | 1.25s | 150 tokens]" in captured.out
        assert "TEST_OK" in captured.out
