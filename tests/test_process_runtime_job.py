import sys
import subprocess
import time
import pytest

from client.process_runtime import (
    bind_process_to_job,
    get_process_job_object,
    popen_background,
)

@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Objects require Windows")
def test_job_object_initialization():
    h_job = get_process_job_object()
    assert h_job is not None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Objects require Windows")
def test_bind_process_to_job():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(1)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        ok = bind_process_to_job(proc)
        assert ok is True
    finally:
        proc.kill()
        proc.wait()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Objects require Windows")
def test_popen_background_binds_to_job():
    proc = popen_background([sys.executable, "-c", "import time; time.sleep(0.5)"])
    try:
        assert proc.pid > 0
    finally:
        proc.wait()
