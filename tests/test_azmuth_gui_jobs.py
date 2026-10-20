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
    root.maxsize(10000, 10000)
    root.geometry(f"{round(size[0] * instance.system_dpi)}x{round(size[1] * instance.system_dpi)}+0+0")
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


@pytest.mark.parametrize("scale,size", [(scale, size) for scale in (1.0, 1.5, 2.0) for size in ((980, 620), (1366, 768), (1920, 1080))])
def test_default_panels_and_complete_drawing_bounds(isolated_gui, monkeypatch, scale, size):
    """Untouched panels, first-open views, and Reset, with real Tk text metrics."""
    import itertools
    from tools.azmuth_gui_dpi import DisplayInfo
    instance = isolated_gui
    root = instance.root
    gene = {"gene_id": "ALGORITHM_WITH_A_LONG_IDENTIFIER_AND_ROLLBACK_SUPPORT", "tier": 2,
            "description": "Maintain connected components and compare implementation variants.", "category": "graph", "alleles": [
                {"allele_id": f"long_implementation_variant_{i}", "dominance": "PRIMARY" if i == 0 else "ALTERNATIVE",
                 "complexity_time": "O(N * alpha(N))", "complexity_space": "O(N)",
                 "empirical_fitness": {"runtime_ms": 40 + i, "ram_kb": 2048}, "invariants": []} for i in range(4)]}
    catalog = {f"ALGORITHM_{i:04d}": {**gene, "gene_id": f"ALGORITHM_{i:04d}", "tier": i % 6} for i in range(471)}
    del catalog["ALGORITHM_0000"]
    catalog[gene["gene_id"]] = {**gene, "tier": 0}
    monkeypatch.setattr(gui, "load_all_genes", lambda: catalog)
    instance.genes_catalog = catalog
    gui.SWEEP_JSON.write_text(json.dumps({"universes": {
        domain["stem"]: {"name": domain["cortical_lobe"], "spikes_count": 0, "top_chokepoint": "Long synthetic chokepoint identifier"}
        for domain in instance.cartridges
    }}), encoding="utf-8")
    target = tuple(round(value * scale) for value in size)
    root.maxsize(10000, 10000)
    instance._on_display_change(DisplayInfo(round(scale * 96), (0, 0, target[0] + 100, target[1] + 150)))
    root.geometry(f"{target[0]}x{target[1]}+0+0")
    root.deiconify()
    failures = []

    def verify():
        try:
            assert abs(root.winfo_width() - target[0]) <= 2
            assert abs(root.winfo_height() - target[1]) <= 2
            assert not instance.left_panel_collapsed and not instance.right_panel_collapsed
            for view in ("pipeline", "dag", "genes", "ingestion"):
                instance.switch_view(view)
                root.update_idletasks()
                # Test first-open geometry, then the explicit reset path.
                for reset in (False, True):
                    if reset:
                        instance.reset_layout()
                        root.update_idletasks()
                    width, height = instance._canvas_size()
                    bounds = instance.canvas.bbox("diagram")
                    if bounds:
                        assert bounds[0] >= -2 and bounds[1] >= instance._diagram_top - 3, (view, reset, bounds, instance._diagram_top, instance.cam_zoom, instance._fit_pending, instance._canvas_size())
                        assert bounds[2] <= width + 2 and bounds[3] <= height + 2, (view, reset, bounds, width, height)
                    for (a, x), (b, y) in itertools.combinations(instance.canvas_nodes.items(), 2):
                        x, y = x["bbox"], y["bbox"]
                        assert not (x[0] < y[2] - 1 and x[2] > y[0] + 1 and x[1] < y[3] - 1 and x[3] > y[1] + 1), (view, a, b, x, y)
                controls = [instance.btn_cancel_job, instance.btn_job_details, instance.btn_technical_details,
                            instance.btn_view_help, instance.spin_z, *instance.tier_pill_btns.values(), *instance.view_buttons.values()]
                controls += [b for b, _ in instance.action_buttons if b.winfo_ismapped()]
                for control in controls:
                    parent = control.master
                    assert control.winfo_ismapped(), (view, control)
                    assert control.winfo_x() >= 0 and control.winfo_y() >= 0, (view, control)
                    assert control.winfo_x() + control.winfo_width() <= parent.winfo_width() + 2, (view, control, control.cget("text"))
                    assert control.winfo_y() + control.winfo_height() <= parent.winfo_height() + 2, (view, control)
        except BaseException as exc:
            failures.append(exc)
        finally:
            root.quit()
    watchdog = root.after(8000, lambda: (failures.append(AssertionError("Default layout check timed out")), root.quit()))
    root.after(450, verify)
    try:
        root.mainloop()
    finally:
        root.after_cancel(watchdog)
    if failures:
        raise failures[0]


def test_layered_explanations_preserve_details_and_reset(isolated_gui):
    instance = isolated_gui
    instance._inspect_pipeline_stage("STAGE_PAT_RING")
    text = instance.inspector_text.get("1.0", tk.END)
    assert all(title in text for title in ("Purpose", "Current state", "Available action", "Technical details"))
    assert "capacity unknown" in text and "30-PAT" not in text and "req/hr" not in text
    assert instance.inspector_text.tag_cget("technical", "elide") in (1, "1")
    instance._toggle_technical_details()
    instance._inspect_pipeline_stage("STAGE_PAT_RING")
    assert instance._details_expanded
    assert instance.inspector_text.tag_cget("technical", "elide") in (0, "0")
    camera = instance.cam_x, instance.cam_y, instance.cam_zoom
    instance._schedule_telemetry_poll()
    assert camera == (instance.cam_x, instance.cam_y, instance.cam_zoom)
    instance.switch_view("ingestion")
    assert not instance._details_expanded
    assert "capacity unknown" not in instance.inspector_text.get("1.0", tk.END)
    instance._inspect_ingestion_event({"title": "Long event " * 100, "source": "Local fixture"})
    assert "Recorded outcome: unknown" in instance.inspector_text.get("1.0", tk.END)
    assert "Status:      UNKNOWN" in instance.inspector_text.get("1.0", tk.END)
    instance._inspect_ingestion_event({"id": "stable-event", "title": "Recorded event", "status": "RUNNING"})
    instance._toggle_technical_details()
    instance._inspect_ingestion_event({"id": "stable-event", "title": "Recorded event", "status": "FAILED", "details": {"error": "Updated externally"}})
    assert instance._details_expanded
    assert "FAILED" in instance.inspector_text.get("1.0", tk.END)
    instance._show_view_help()
    assert "apply generated repairs" in instance.inspector_text.get("1.0", tk.END)
    assert str(instance.btn_technical_details.cget("state")) == "disabled"


def test_edge_label_cleanup_and_long_badges_do_not_overlap(isolated_gui):
    instance = isolated_gui
    instance.switch_view("pipeline")
    for zoom in (0.35, 0.8, 1.0):
        instance.cam_zoom = zoom
        instance._redraw_active_canvas()
        for edge in instance.active_canvas_edges:
            box = instance.canvas_nodes[edge["target_id"]]["bbox"]
            x, y = edge["x2"], edge["y2"]
            assert box[0] - 1 <= x <= box[2] + 1 and box[1] - 1 <= y <= box[3] + 1
            assert min(abs(x - box[0]), abs(x - box[2]), abs(y - box[1]), abs(y - box[3])) < 1
    instance.canvas.delete("all")
    instance.canvas_nodes = {"obstacle": {"bbox": (-10000, -10000, 10000, 10000)}}
    instance.cam_zoom = 1
    instance.active_canvas_edges = []
    instance._draw_directed_edge(100, 100, 400, 400, label="An unusually long secondary edge label")
    instance._hide_colliding_edge_labels()
    assert not instance.canvas.find_withtag("edge_label")


def test_large_counts_keep_full_values_in_help_and_funnel_selection(isolated_gui):
    instance = isolated_gui
    count = 98765432109876543210
    instance.arena_ledger_data = {"tournaments_run": count}
    instance.mutation_ledger_data = {"mutations_applied": count}
    instance._refresh_header_indicators()
    assert len(instance.kpi_labels["arena"].cget("text")) <= 10
    instance._show_view_help()
    assert str(count) in instance.inspector_text.get("1.0", tk.END)
    instance._inspect_ingestion_funnel({"title": "BENCHMARKS", "value": str(count)})
    assert str(count) in instance.inspector_text.get("1.0", tk.END)
    instance._inspect_universe_status({"universe_id": "u0_ecosystem_mesh", "title": "U0: Ecosystem Mesh", "meta": {}})
    assert "unavailable" in instance.inspector_text.get("1.0", tk.END)


def assert_gene_edge_borders(instance):
    # Labels remain readable when edges are lowered behind the cards.
    stacking = list(instance.canvas.find_all())
    for item in instance.canvas.find_withtag("edge_label"):
        if instance.canvas.type(item) != "rectangle":
            continue
        group = next(t for t in instance.canvas.gettags(item) if t.startswith("edge_label_"))
        text = next(i for i in instance.canvas.find_withtag(group) if instance.canvas.type(i) == "text")
        assert stacking.index(item) < stacking.index(text)
    for edge in instance.active_canvas_edges:
        for role, xkey, ykey in (("source_id", "x1", "y1"), ("target_id", "x2", "y2")):
            node = instance.canvas_nodes[edge[role]]
            x1, y1, x2, y2 = node["bbox"]
            x, y = edge[xkey], edge[ykey]
            assert x1 - 1 <= x <= x2 + 1 and y1 - 1 <= y <= y2 + 1
            assert min(abs(x - x1), abs(x - x2), abs(y - y1), abs(y - y2)) < 1


@pytest.mark.parametrize("tier", range(6))
def test_gene_tiers_drag_root_base_nested_mutants_and_cta(isolated_gui, tier):
    instance = isolated_gui
    gene_id = f"TIER_{tier}"
    instance.genes_catalog = {gene_id: {
        "gene_id": gene_id, "tier": tier,
        "alleles": [{"allele_id": aid, "empirical_fitness": {"runtime_ms": rt}}
                    for aid, rt in (("base", 12), ("base_mut_fast", 10), ("base_mut_fast_mut_tuned", 8))],
    }}
    instance.selected_gene_id = gene_id
    instance.switch_view("genes")
    for page in (0, 1):
        instance._gene_pages[gene_id] = page
        instance._redraw_active_canvas()
        if page == 0:
            assert any(e["source_id"] == f"GENE_ROOT::{gene_id}" and e["target_id"].endswith("::base")
                       for e in instance.active_canvas_edges)
        else:
            nested = next(e for e in instance.active_canvas_edges if e["target_id"].endswith("base_mut_fast_mut_tuned"))
            assert nested["source_id"].endswith("::base_mut_fast")
        for nid in list(instance.canvas_nodes):
            x, y = instance.canvas_nodes[nid]["center"]
            instance._on_canvas_press(SimpleNamespace(x=x, y=y))
            instance._on_canvas_motion(SimpleNamespace(x=x + 41, y=y + 23))
            instance._on_canvas_release(SimpleNamespace(x=x + 41, y=y + 23))
            assert_gene_edge_borders(instance)
    # A base-only gene exposes a real connected action card, also draggable.
    instance.genes_catalog[gene_id]["alleles"] = [{"allele_id": "base"}]
    instance._gene_pages[gene_id] = 0
    instance._redraw_active_canvas()
    cta = f"MUTATE_CTA::{gene_id}"
    instance.custom_node_positions[cta] = (1100, 500)
    instance._redraw_active_canvas()
    assert any(e["target_id"] == cta for e in instance.active_canvas_edges)
    assert_gene_edge_borders(instance)
    instance.reset_layout()
    assert not instance.custom_node_positions


@pytest.mark.parametrize("tier", range(6))
def test_dense_gene_pages_cover_every_variant_and_keep_parent_context(isolated_gui, tier):
    instance = isolated_gui
    bases = [{"allele_id": f"base_{i}"} for i in range(20)]
    variants = [{"allele_id": f"base_{i}_mut_fast"} for i in range(20)]
    variants += [{"allele_id": f"base_{i}_mut_fast_mut_tuned"} for i in range(19)]
    gid = f"DENSE_T{tier}"
    instance.genes_catalog = {gid: {"gene_id": gid, "tier": tier, "alleles": bases + variants}}
    instance.selected_gene_id = gid
    instance.switch_view("genes")
    seen = set()
    for page in range(30):
        instance._gene_pages[gid] = page
        instance._redraw_active_canvas()
        shown = [n["payload"]["allele_id"] for n in instance.canvas_nodes.values() if n["payload"].get("type") == "allele"]
        seen.update(shown)
        assert len(shown) <= 4
        assert_gene_edge_borders(instance)
        assert instance._gene_pages[gid] == page
        before = (instance.cam_x, instance.cam_y, instance.cam_zoom)
        instance._redraw_active_canvas()
        assert before == (instance.cam_x, instance.cam_y, instance.cam_zoom)
    assert seen == {a["allele_id"] for a in bases + variants}
    # Navigation uses the fixed HUD hit test, independent of camera/zoom.
    bounds, direction = instance._gene_page_controls[0]
    instance._handle_node_click((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
    assert instance._gene_pages[gid] == 29 + direction
    # Identical allele names from another gene must not inherit its drag offset.
    instance.custom_node_positions[f"ALLELE::{gid}::base_0"] = (999, 999)
    other = f"{gid}_OTHER"
    instance.genes_catalog[other] = {"gene_id": other, "tier": tier, "alleles": bases[:1]}
    instance.selected_gene_id = other
    instance._redraw_active_canvas()
    assert instance.canvas_nodes[f"ALLELE::{other}::base_0"]["world_pos"] != (999, 999)


@pytest.mark.parametrize("scale,size", [(scale, size) for scale in (1.0, 1.5, 2.0) for size in ((980, 620), (1366, 768), (1920, 1080))])
def test_dense_gene_default_bounds_at_supported_sizes(isolated_gui, monkeypatch, scale, size):
    """Untouched panels, first-open views, and Reset, with real Tk text metrics."""
    import itertools
    from tools.azmuth_gui_dpi import DisplayInfo
    instance = isolated_gui
    root = instance.root
    gene = {"gene_id": "ALGORITHM_WITH_A_LONG_IDENTIFIER_AND_ROLLBACK_SUPPORT", "tier": 2,
            "description": "Maintain connected components and compare implementation variants.", "category": "graph", "alleles": [
                {"allele_id": f"long_implementation_variant_{i}", "dominance": "PRIMARY" if i == 0 else "ALTERNATIVE",
                 "complexity_time": "O(N * alpha(N))", "complexity_space": "O(N)",
                 "empirical_fitness": {"runtime_ms": 40 + i, "ram_kb": 2048}, "invariants": []} for i in range(4)]}
    catalog = {f"ALGORITHM_{i:04d}": {**gene, "gene_id": f"ALGORITHM_{i:04d}", "tier": i % 6} for i in range(471)}
    del catalog["ALGORITHM_0000"]
    catalog[gene["gene_id"]] = {**gene, "tier": 0}
    monkeypatch.setattr(gui, "load_all_genes", lambda: catalog)
    instance.genes_catalog = catalog
    gene["alleles"] = [{"allele_id": f"long_implementation_variant_{i}"} for i in range(20)]
    gene["alleles"] += [{"allele_id": f"long_implementation_variant_{i}_mut_fast"} for i in range(20)]
    gene["alleles"] += [{"allele_id": f"long_implementation_variant_{i}_mut_fast_mut_tuned"} for i in range(19)]
    catalog[gene["gene_id"]] = gene
    instance.selected_gene_id = gene["gene_id"]
    target = tuple(round(value * scale) for value in size)
    root.maxsize(10000, 10000)
    instance._on_display_change(DisplayInfo(round(scale * 96), (0, 0, target[0] + 100, target[1] + 150)))
    root.geometry(f"{target[0]}x{target[1]}+0+0")
    root.deiconify()
    failures = []

    def verify():
        try:
            assert abs(root.winfo_width() - target[0]) <= 2
            assert abs(root.winfo_height() - target[1]) <= 2
            assert not instance.left_panel_collapsed and not instance.right_panel_collapsed
            for tier in range(6):
                gene["tier"] = tier
                view = "genes"
                instance.switch_view(view)
                root.update_idletasks()
                # Test first-open geometry, then the explicit reset path.
                for reset in (False, True):
                    if reset:
                        instance.reset_layout()
                        root.update_idletasks()
                    width, height = instance._canvas_size()
                    bounds = instance.canvas.bbox("diagram")
                    if bounds:
                        assert bounds[0] >= -2 and bounds[1] >= instance._diagram_top - 3, (view, reset, bounds, instance._diagram_top, instance.cam_zoom, instance._fit_pending, instance._canvas_size())
                        assert bounds[2] <= width + 2 and bounds[3] <= height + 2, (view, reset, bounds, width, height)
                    for (a, x), (b, y) in itertools.combinations(instance.canvas_nodes.items(), 2):
                        x, y = x["bbox"], y["bbox"]
                        assert not (x[0] < y[2] - 1 and x[2] > y[0] + 1 and x[1] < y[3] - 1 and x[3] > y[1] + 1), (view, a, b, x, y)
                instance._gene_pages[gene["gene_id"]] = 21
                instance.zoom_reset()
                root.update_idletasks()
                assert_gene_edge_borders(instance)
                bounds = instance.canvas.bbox("diagram")
                assert bounds[0] >= -2 and bounds[1] >= instance._diagram_top - 3
                assert bounds[2] <= width + 2 and bounds[3] <= height + 2
                controls = [instance.btn_cancel_job, instance.btn_job_details, instance.btn_technical_details,
                            instance.btn_view_help, instance.spin_z, *instance.tier_pill_btns.values(), *instance.view_buttons.values()]
                controls += [b for b, _ in instance.action_buttons if b.winfo_ismapped()]
                for control in controls:
                    parent = control.master
                    assert control.winfo_ismapped(), (view, control)
                    assert control.winfo_x() >= 0 and control.winfo_y() >= 0, (view, control)
                    assert control.winfo_x() + control.winfo_width() <= parent.winfo_width() + 2, (view, control, control.cget("text"))
                    assert control.winfo_y() + control.winfo_height() <= parent.winfo_height() + 2, (view, control)
        except BaseException as exc:
            failures.append(exc)
        finally:
            root.quit()
    watchdog = root.after(8000, lambda: (failures.append(AssertionError("Default layout check timed out")), root.quit()))
    root.after(450, verify)
    try:
        root.mainloop()
    finally:
        root.after_cancel(watchdog)
    if failures:
        raise failures[0]
