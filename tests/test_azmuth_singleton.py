import os
import sys
import time
from pathlib import Path
import pytest

from tools.azmuth_daemon import AzmuthSingletonLock, LOCK_FILE

def test_azmuth_singleton_acquire_and_release(tmp_path):
    lock_file = tmp_path / "test_azmuth.pid.lock"
    lock1 = AzmuthSingletonLock(lock_file)
    assert lock1.acquire() is True
    assert lock_file.exists()
    assert lock1.get_locked_pid() == os.getpid()

    # Second lock acquisition while first is held should fail
    lock2 = AzmuthSingletonLock(lock_file)
    assert lock2.acquire() is False

    # Release first lock
    lock1.release()
    assert not lock_file.exists()

    # Now second lock can acquire
    assert lock2.acquire() is True
    assert lock2.get_locked_pid() == os.getpid()
    lock2.release()


def test_azmuth_singleton_stale_pid_cleanup(tmp_path):
    lock_file = tmp_path / "test_azmuth_stale.pid.lock"
    # Write an impossibly high/dead PID
    lock_file.write_text("9999999\n", encoding="utf-8")

    lock = AzmuthSingletonLock(lock_file)
    # Should detect stale dead PID and successfully acquire
    assert lock.acquire() is True
    assert lock.get_locked_pid() == os.getpid()
    lock.release()

