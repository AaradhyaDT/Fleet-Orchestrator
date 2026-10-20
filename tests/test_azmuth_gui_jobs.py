"""Regression coverage for local GUI job cancellation, deadlines, and state isolation."""

from __future__ import annotations

import json
import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import tkinter as tk

import pytest

from tools import azmuth_gui as gui
from tools.azmuth_gui_jobs import GUIJob, JobCancelled, ProcessCleanupError, run_managed_process, terminate_owned_process


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "Timed out waiting for the harmless local test worker"
        time.sleep(0.01)


class FakeWidget:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


class FakeRoot:
    def __init__(self):
        self.callbacks = []
        self.destroyed = False

    def after(self, delay, callback):
        self.callbacks.append((delay, callback))
        return str(len(self.callbacks))

    def after_cancel(self, _identifier):
        pass

    def destroy(self):
        self.destroyed = True


@pytest.fixture
def app():
    instance = object.__new__(gui.AzmuthCommandCenterGUI)
    instance.root = FakeRoot()
    instance.theme = SimpleNamespace(accent_amber="amber", accent_crimson="red", accent_emerald="green")
    instance.lbl_footer_job = FakeWidget()
    instance.btn_cancel_job = FakeWidget()
    instance._running = True
    instance._closing = False
    instance._close_after = None
    instance.is_job_running = False
    instance.active_job = None
    instance.pulses = []
    instance.action_buttons = [(FakeWidget(), "blue")]
    instance.job_results = queue.Queue()
    instance._on_background_job_complete = lambda: None
    return instance


def test_managed_output_and_nonzero_exit(tmp_path):
    job = GUIJob("output", "fake", managed=True)
    result = run_managed_process(job, [sys.executable, "-u", "-c", "import sys;print('stdout');print('stderr', file=sys.stderr);sys.exit(7)"], cwd=tmp_path)
    assert result.returncode == job.return_code == 7
    assert "stdout" in job.stdout and "stderr" in job.stderr
    assert job.output == job.stdout + job.stderr
    assert job.process.poll() == 7


def test_stalled_process_times_out_and_is_reaped(tmp_path):
    job = GUIJob("timeout", "fake", managed=True)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="timed out"):
        run_managed_process(job, [sys.executable, "-u", "-c", "import time;print('before stall');time.sleep(30)"], cwd=tmp_path, timeout_seconds=0.3)
    assert time.monotonic() - started < 6
    assert job.process.poll() is not None
    assert job.return_code is not None
    assert "before stall" in job.output


def test_cancel_before_start_never_spawns(monkeypatch, tmp_path):
    job = GUIJob("early", "fake", managed=True)
    job.cancel_event.set()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Cancelled job must not start a process"))
    with pytest.raises(JobCancelled, match="before"):
        run_managed_process(job, ["never"], cwd=tmp_path)
    assert job.process is None


def test_cancel_local_child_through_gui_is_nonblocking(app, tmp_path):
    ready = tmp_path / "ready"
    command = [sys.executable, "-u", "-c", f"import pathlib,time;pathlib.Path({str(ready)!r}).touch();print('started');time.sleep(30)"]
    app._run_background_job("fake managed", "blue", managed_command=command)
    wait_until(ready.exists)
    started = time.monotonic()
    app._cancel_active_job()
    assert time.monotonic() - started < 0.1
    wait_until(app.active_job.worker_done.is_set)
    app._poll_job_results()
    assert app.active_job.outcome == "cancelled"
    assert app.active_job.process.poll() is not None
    assert "Remote session cleanup is unconfirmed" in app.active_job.error
    assert not app.is_job_running


def test_timeout_reaches_gui_as_failed(app):
    def timeout():
        raise TimeoutError("simulated stalled job timeout")
    app._run_background_job("stalled fake", "blue", timeout)
    wait_until(app.active_job.worker_done.is_set)
    app._poll_job_results()
    assert app.active_job.outcome == "failed"
    assert "timeout" in app.active_job.error
    assert app.action_buttons[0][0].options["state"] == tk.NORMAL


def test_stop_waiting_retains_busy_guard_and_actual_result(app):
    release = threading.Event()
    app._run_background_job("fake in-process", "blue", lambda: release.wait(3))
    original = app.active_job
    app._cancel_active_job()
    assert original.stop_waiting and app.is_job_running
    app._run_background_job("conflicting work", "blue", lambda: pytest.fail("Must remain blocked"))
    assert app.active_job is original
    release.set()
    wait_until(original.worker_done.is_set)
    app._poll_job_results()
    assert original.outcome == "succeeded"
    assert "stopped waiting" in original.notice


def test_late_and_duplicate_results_are_ignored(app):
    app.active_job = GUIJob("current", "fake", outcome="failed", error="original error")
    app.job_results.put(("previous", None, None))
    app.job_results.put(("current", None, None))
    app._poll_job_results()
    assert app.active_job.outcome == "failed"
    assert app.active_job.error == "original error"


def test_close_waits_for_startup_race_without_blocking_tk(app, monkeypatch):
    release = threading.Event()
    def startup(job, *_args, **_kwargs):
        release.wait(3)
        if job.cancel_event.is_set():
            raise JobCancelled("Cancelled before startup")
        pytest.fail("Close must signal cancellation before process startup")
    monkeypatch.setattr(gui, "run_managed_process", startup)
    app._run_background_job("starting fake", "blue", managed_command=["never"])
    started = time.monotonic()
    app._on_close()
    assert time.monotonic() - started < 0.1
    assert not app.root.destroyed
    release.set()
    wait_until(app.active_job.worker_done.is_set)
    app._check_close()
    assert app.root.destroyed
    assert app.active_job.outcome == "cancelled"


def test_close_running_child_reaps_before_destroying_window(app, tmp_path):
    ready = tmp_path / "ready"
    command = [sys.executable, "-u", "-c", f"import pathlib,time;pathlib.Path({str(ready)!r}).touch();time.sleep(30)"]
    app._run_background_job("closing fake", "blue", managed_command=command)
    wait_until(ready.exists)
    app._on_close()
    wait_until(app.active_job.worker_done.is_set)
    app._check_close()
    assert app.active_job.process.poll() is not None
    assert app.root.destroyed


def test_cleanup_failure_is_not_silently_ignored(monkeypatch):
    fake = SimpleNamespace(pid=999999, poll=lambda: None)
    fake.kill = lambda: (_ for _ in ()).throw(OSError("simulated kill failure"))
    fake.wait = lambda **kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("fake", 0.01))
    fake.terminate = lambda: None
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("fake", 0.01)))
    with pytest.raises(ProcessCleanupError, match="not confirmed stopped"):
        terminate_owned_process(fake, timeout=0.01)


def process_alive(pid):
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def test_timeout_stops_owned_descendant_process(tmp_path):
    child_pid_file = tmp_path / "child.pid"
    code = f"import subprocess,sys,pathlib,time;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);pathlib.Path({str(child_pid_file)!r}).write_text(str(p.pid));print('child started',flush=True);time.sleep(30)"
    job = GUIJob("tree", "fake tree", managed=True)
    try:
        with pytest.raises(TimeoutError):
            run_managed_process(job, [sys.executable, "-u", "-c", code], cwd=tmp_path, timeout_seconds=0.5)
        child_pid = int(child_pid_file.read_text())
        wait_until(lambda: not process_alive(child_pid))
        assert job.process.poll() is not None
    finally:
        if child_pid_file.exists():
            child_pid = int(child_pid_file.read_text())
            if process_alive(child_pid):
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(child_pid), "/T", "/F"], capture_output=True, timeout=2)
                else:
                    import signal
                    os.kill(child_pid, signal.SIGKILL)


@pytest.mark.skipif(os.name != "nt", reason="Win32 per-job process containment")
@pytest.mark.parametrize("keep_pipes", [False, True])
def test_descendant_outliving_its_parent_is_still_cleaned_up(tmp_path, keep_pipes):
    child_pid_file = tmp_path / "orphan.pid"
    redirected = "" if keep_pipes else ",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL"
    code = f"import subprocess,sys,pathlib;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']{redirected});pathlib.Path({str(child_pid_file)!r}).write_text(str(p.pid));print('parent finished',flush=True)"
    job = GUIJob("orphan", "fake parent", managed=True)
    if keep_pipes:
        with pytest.raises(TimeoutError):
            run_managed_process(job, [sys.executable, "-u", "-c", code], cwd=tmp_path, timeout_seconds=0.5)
    else:
        result = run_managed_process(job, [sys.executable, "-u", "-c", code], cwd=tmp_path, timeout_seconds=0.5)
        assert result.returncode == 0
    child_pid = int(child_pid_file.read_text())
    wait_until(lambda: not process_alive(child_pid))


def test_close_does_not_hide_cleanup_failure(app, monkeypatch):
    fake_process = SimpleNamespace(poll=lambda: None)
    job = GUIJob("cleanup", "fake", outcome="failed", managed=True, process=fake_process)
    job.worker_done.set()
    app.active_job, app.is_job_running = job, True
    monkeypatch.setattr(gui, "terminate_owned_process", lambda *a, **kw: (_ for _ in ()).throw(ProcessCleanupError("simulated cleanup failure")))
    monkeypatch.setattr(app, "_abort_close", lambda: setattr(app, "_closing", False))
    app._on_close()
    wait_until(job.worker_done.is_set)
    app._check_close()
    assert not app.root.destroyed
    assert job.outcome == "failed"
    assert "Close blocked" in app.lbl_footer_job.options["text"]


@pytest.fixture
def isolated_gui(monkeypatch, tmp_path, request):
    for name in ("GH_CACHE_FILE", "CORPUS_LEDGER", "ARENA_LEDGER", "MUTATION_LEDGER", "INGESTION_FEED", "RUN_LOG_JSON", "SWEEP_JSON"):
        monkeypatch.setattr(gui, name, tmp_path / getattr(gui, name).name)
    monkeypatch.setattr(gui, "check_and_enforce_gear_safety", lambda: ("whisper", {}))
    monkeypatch.setattr(gui, "AzmuthGitHubSensor", lambda: SimpleNamespace(pool=SimpleNamespace(tokens=[])))
    monkeypatch.setattr(gui, "get_memory_status_gb", lambda: (16.0, 8.0, 50.0))
    monkeypatch.setattr(gui, "get_system_dpi_scale", lambda: getattr(request, "param", 1.0))
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available")
    instance = gui.AzmuthCommandCenterGUI(root)
    yield instance
    instance._on_close()


@pytest.mark.parametrize("text", ["", "garbage", "nan", "inf", "-1", "4"])
def test_invalid_z_input_never_changes_committed_threshold_or_stops_loops(isolated_gui, text):
    instance = isolated_gui
    committed = instance.thalamic_z_threshold.get()
    instance.z_input_var.set(text)
    instance._on_parameter_tuned()
    instance._schedule_animation_frame()
    instance._schedule_telemetry_poll()
    assert instance.thalamic_z_threshold.get() == committed
    assert instance._animation_after and instance._telemetry_after
    instance.z_input_var.set("1.2")
    instance._on_parameter_tuned()
    assert instance.thalamic_z_threshold.get() == 1.2


def test_external_ledger_change_and_poll_failure_recovery(isolated_gui):
    instance = isolated_gui
    gui.ARENA_LEDGER.write_text(json.dumps({"tournaments_run": 123}), encoding="utf-8")
    instance._schedule_telemetry_poll()
    assert instance.arena_ledger_data["tournaments_run"] == 123
    assert instance.kpi_labels["arena"].cget("text") == "123"
    last_success = instance.telemetry_last_updated
    gui.ARENA_LEDGER.write_text("{broken", encoding="utf-8")
    instance._schedule_telemetry_poll()
    assert instance.telemetry_last_updated == last_success
    assert "stale" in instance.lbl_footer_right.cget("text").lower()
    assert instance.arena_ledger_data["tournaments_run"] == 123
    gui.ARENA_LEDGER.write_text(json.dumps({"tournaments_run": 124}), encoding="utf-8")
    instance._schedule_telemetry_poll()
    assert instance.kpi_labels["arena"].cget("text") == "124"
    assert instance.telemetry_last_updated > last_success


def test_ingestion_action_uses_same_managed_burst_handler(isolated_gui, monkeypatch):
    calls = []
    monkeypatch.setattr(isolated_gui, "_run_background_job", lambda *args, **kwargs: calls.append((args, kwargs)))
    isolated_gui._trigger_colab_cloud_burst()
    isolated_gui.switch_view("ingestion")
    isolated_gui._on_contextual_inspector_action()
    assert calls[0] == calls[1]
    assert calls[0][1]["timeout_seconds"] == 600


def test_poll_keeps_selected_event_and_clears_removed_details(isolated_gui):
    instance = isolated_gui
    event = {"timestamp": "2026-10-19T00:00:00Z", "source": "test", "event_type": "TEST", "title": "first event"}
    gui.INGESTION_FEED.write_text(json.dumps(event) + "\n", encoding="utf-8")
    instance.switch_view("ingestion")
    index = next(i for i, meta in enumerate(instance.left_items_meta) if meta.get("type") == "ingestion_event")
    instance.left_listbox.selection_set(index)
    instance._on_left_list_select(None)
    instance._schedule_telemetry_poll()
    assert instance.left_listbox.curselection()
    assert "first event" in instance.inspector_text.get("1.0", tk.END)
    gui.INGESTION_FEED.write_text("", encoding="utf-8")
    instance._schedule_telemetry_poll()
    assert "first event" not in instance.inspector_text.get("1.0", tk.END)


@pytest.mark.parametrize("isolated_gui,size", [(scale, size) for scale in (1.0, 1.5, 2.0) for size in ((980, 620), (1366, 768), (1920, 1080))], indirect=["isolated_gui"])
def test_visible_views_and_key_controls_fit_supported_sizes(isolated_gui, size):
    """Exercise real Tk geometry asynchronously; scales emulate the app's DPI input."""
    instance = isolated_gui
    root = instance.root
    root.geometry(f"{size[0]}x{size[1]}+0+0")
    root.deiconify()
    failures = []
    views = ("pipeline", "dag", "genes", "ingestion")

    def verify(index):
        try:
            width, height = instance.canvas.winfo_width(), instance.canvas.winfo_height()
            assert width >= 100 and height >= 100
            assert height >= root.winfo_height() * 0.5, "Chrome must leave at least half the window for work"
            for identifier, node in instance.canvas_nodes.items():
                x0, y0, x1, y1 = node["bbox"]
                assert x0 >= -2 and y0 >= -2 and x1 <= width + 2 and y1 <= height + 2, (views[index], identifier, node["bbox"], width, height)
            controls = [instance.btn_cancel_job, instance.btn_job_details, instance.spin_z, instance.btn_theme_toggle, instance.btn_zoom_in, instance.btn_zoom_out, instance.btn_toggle_left, instance.btn_toggle_right, *instance.view_buttons.values()]
            controls.extend(button for button, _ in instance.action_buttons if button.winfo_ismapped())
            for control in controls:
                assert control.winfo_ismapped(), control
                x = control.winfo_rootx() - root.winfo_rootx()
                y = control.winfo_rooty() - root.winfo_rooty()
                assert x >= 0 and y >= 0 and x + control.winfo_width() <= root.winfo_width() + 1 and y + control.winfo_height() <= root.winfo_height() + 1, control
            if index + 1 < len(views):
                root.after(20, lambda: open_view(index + 1))
            else:
                root.quit()
        except BaseException as exc:
            failures.append(exc)
            root.quit()

    def open_view(index):
        try:
            instance.switch_view(views[index])
            root.after(120, lambda: verify(index))
        except BaseException as exc:
            failures.append(exc)
            root.quit()

    def deadline():
        failures.append(AssertionError("Tk geometry review exceeded its 8 second bound"))
        root.quit()

    watchdog = root.after(8000, deadline)
    root.after(400, lambda: open_view(0))
    try:
        root.mainloop()
    finally:
        root.after_cancel(watchdog)
        root.withdraw()
    if failures:
        raise failures[0]


def test_gene_filter_selection_and_empty_search_share_one_visible_object(isolated_gui, monkeypatch):
    instance = isolated_gui
    def gene(identifier, tier):
        alleles = []
        for index in range(2):
            for suffix, runtime in (("", 40.0), ("_mut_pragma_tuning", 28.0)):
                alleles.append({
                    "allele_id": f"branch_{index}{suffix}", "dominance": "PRIMARY" if suffix else "ALTERNATIVE",
                    "complexity_time": "O(N * alpha(N))", "complexity_space": "O(N)",
                    "empirical_fitness": {"runtime_ms": runtime, "ram_kb": 1536},
                    "invariants": ["Mutated by Azmuth Genetic Optimizer (pragma_tuning)"] if suffix else [],
                })
        return {"gene_id": identifier, "tier": tier, "category": "primitive_structure", "description": identifier, "alleles": alleles}
    catalog = {"TWO": gene("TWO", 2), "FIVE": gene("FIVE", 5)}
    monkeypatch.setattr(gui, "load_all_genes", lambda: catalog)
    instance.genes_catalog = catalog
    root = instance.root
    root.geometry("1366x768")
    root.deiconify()
    failures = []

    def verify():
        try:
            instance.switch_view("genes")
            instance.cam_x, instance.cam_zoom = -500.0, 1.5
            instance._set_tier_filter(5)
            assert instance.selected_gene_id == "FIVE"
            assert instance.left_listbox.curselection() == (0,)
            assert str(instance.btn_contextual_action.cget("state")) == tk.NORMAL
            assert "FIVE" in instance.inspector_text.get("1.0", tk.END)
            for node in instance.canvas_nodes.values():
                x0, y0, x1, y1 = node["bbox"]
                assert x0 >= -2 and y0 >= -2
                assert x1 <= instance.canvas.winfo_width() + 2 and y1 <= instance.canvas.winfo_height() + 2
            camera = instance.cam_x, instance.cam_y, instance.cam_zoom
            instance._populate_left_panel()
            assert camera == (instance.cam_x, instance.cam_y, instance.cam_zoom)
            instance.search_query_var.set("nothing matches")
            assert instance.selected_gene_id is None
            assert str(instance.btn_contextual_action.cget("state")) == tk.DISABLED
            assert not instance.canvas_nodes
            assert not instance.inspector_text.get("1.0", tk.END).strip()
        except BaseException as exc:
            failures.append(exc)
        finally:
            root.quit()

    root.after(400, verify)
    watchdog = root.after(5000, lambda: (failures.append(AssertionError("GUI regression test timed out")), root.quit()))
    try:
        root.mainloop()
    finally:
        root.after_cancel(watchdog)
    if failures:
        raise failures[0]


def test_theme_round_trip_preserves_readable_controls(isolated_gui):
    instance = isolated_gui
    for _ in range(4):
        instance.toggle_theme()
        for control in (instance.lbl_tune_z, instance.lbl_tune_ram, instance.left_listbox, instance.inspector_text):
            assert control.cget("foreground") == instance.theme.text_secondary
        assert instance.btn_theme_toggle.cget("foreground") == instance.theme.text_primary


def test_view_switch_and_poll_preserve_user_camera(isolated_gui):
    instance = isolated_gui
    instance._fit_pending = False
    instance.cam_x, instance.cam_y, instance.cam_zoom = 123.0, 456.0, 1.5
    instance.zoom_level = 1.5
    instance.switch_view("dag")
    instance.switch_view("pipeline")
    assert (instance.cam_x, instance.cam_y, instance.cam_zoom) == (123.0, 456.0, 1.5)
    instance._schedule_telemetry_poll()
    assert (instance.cam_x, instance.cam_y, instance.cam_zoom) == (123.0, 456.0, 1.5)
