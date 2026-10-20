"""DPI startup probes use isolated processes; native settings are never changed."""

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools.azmuth_gui_dpi import DisplayInfo, DpiController, WindowsDpi


class ClockRoot:
    def __init__(self):
        self.pending = {}
        self.counter = 0

    def after(self, delay, callback):
        self.counter += 1
        self.pending[self.counter] = callback
        return self.counter

    def after_cancel(self, identifier):
        self.pending.pop(identifier, None)


def test_locked_process_awareness_falls_back_to_gui_thread():
    native = WindowsDpi.__new__(WindowsDpi)
    native.is_v2 = lambda value: value == "v2"
    native.user = SimpleNamespace(
        GetThreadDpiAwarenessContext=Mock(side_effect=["unaware", "unaware", "v2"]),
        SetProcessDpiAwarenessContext=Mock(return_value=False),
        SetThreadDpiAwarenessContext=Mock(return_value=1),
    )
    assert native.prepare() == ""
    native.user.SetThreadDpiAwarenessContext.assert_called_once()


@pytest.mark.skipif(os.name != "nt", reason="Windows last-error reporting")
def test_failed_thread_awareness_is_reported():
    native = WindowsDpi.__new__(WindowsDpi)
    native.is_v2 = lambda value: False
    native.user = SimpleNamespace(
        GetThreadDpiAwarenessContext=Mock(return_value="unaware"),
        SetProcessDpiAwarenessContext=Mock(return_value=False),
        SetThreadDpiAwarenessContext=Mock(return_value=None),
    )
    assert "could not be disabled" in native.prepare()


def test_display_notifications_coalesce_and_polling_recovers():
    root = ClockRoot()
    initial = DisplayInfo(96)
    backend = SimpleNamespace(hwnd=lambda _: 1, install_hook=Mock(return_value="hook"),
                              remove_hook=Mock(), snapshot=Mock(return_value=initial), clamp_window=Mock())
    changed = []
    controller = DpiController(root, backend, initial, changed.append)
    for dpi in (144, 192, 96):
        controller.notify()
        controller.notify()
        backend.snapshot.return_value = DisplayInfo(dpi)
        controller.poll()
        controller.poll()
    assert [info.dpi for info in changed] == [144, 192, 96]
    backend.snapshot.side_effect = OSError("temporary monitor lookup failure")
    controller.poll()
    assert not controller.closed and controller.after_id is not None
    backend.snapshot.side_effect = None
    backend.snapshot.return_value = DisplayInfo(96, (0, 0, 1280, 720))
    controller.poll()
    assert changed[-1].work_area == (0, 0, 1280, 720)
    controller.close()
    controller.close()
    assert not root.pending
    backend.remove_hook.assert_called_once_with(1, "hook")
    count = backend.snapshot.call_count
    controller.poll()
    assert backend.snapshot.call_count == count


def test_hook_failure_keeps_fallback_polling():
    root = ClockRoot()
    backend = SimpleNamespace(hwnd=lambda _: 1, install_hook=Mock(side_effect=OSError("hook unavailable")),
                              snapshot=Mock(return_value=DisplayInfo(144)), clamp_window=Mock())
    changed = []
    controller = DpiController(root, backend, DisplayInfo(), changed.append)
    controller.poll()
    assert changed[0].dpi == 144
    controller.close()
    assert controller.after_id is None


def test_window_is_clamped_to_replacement_monitor():
    native = WindowsDpi.__new__(WindowsDpi)
    def read_rect(hwnd, pointer):
        rect = pointer._obj
        rect.left, rect.top, rect.right, rect.bottom = -2400, 40, -400, 1400
        return True
    native.user = SimpleNamespace(GetWindowRect=read_rect)
    native.set_rect = Mock()
    native.clamp_window(1, (0, 0, 1280, 720))
    native.set_rect.assert_called_once_with(1, (0, 0, 1280, 720))


PROBE = r'''
import json,sys,pathlib,traceback
destination=pathlib.Path(sys.argv[1])
try:
    from tools.azmuth_gui_dpi import create_gui_root
    root=create_gui_root()
    info=root._azmuth_display_info
    result={'dpi':info.dpi,'scale':info.scale,'v2':info.per_monitor_v2,'warning':info.warning,
            'tk_scaling':float(root.tk.call('tk','scaling')),'patchlevel':root.tk.call('package','provide','Tk')}
    if len(sys.argv)>2 and sys.argv[2]=='hook':
        import ctypes
        from ctypes import wintypes
        native=root._azmuth_dpi_backend
        notices=[];rectangles=[]
        native.set_rect=lambda hwnd,rect:rectangles.append(rect)
        hwnd=native.hwnd(root)
        hook=native.install_hook(hwnd,lambda:notices.append(True))
        send=native._declare(native.user,'SendMessageW',ctypes.c_ssize_t,wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
        rect=wintypes.RECT(20,30,820,630)
        send(hwnd,0x02E0,144|(144<<16),ctypes.addressof(rect))
        assert rectangles==[(20,30,820,630)] and notices==[True]
        send(hwnd,0,0,0)
        native.remove_hook(hwnd,hook)
        send(hwnd,0x02E0,144|(144<<16),ctypes.addressof(rect))
        assert len(notices)==1
        result['hook_verified']=True
        root.destroy()
    elif len(sys.argv)>2:
        from types import SimpleNamespace
        from tools import azmuth_gui as gui
        from tools.azmuth_gui_dpi import DisplayInfo
        state=destination.parent
        for name in ('GH_CACHE_FILE','CORPUS_LEDGER','ARENA_LEDGER','MUTATION_LEDGER','INGESTION_FEED','RUN_LOG_JSON','SWEEP_JSON','MACRO_BRIEF_JSON'):
            setattr(gui,name,state/name)
        gui.check_and_enforce_gear_safety=lambda:('whisper',{})
        gui.get_current_gear=lambda:'whisper'
        gui.is_paused=lambda:False
        gui.get_memory_status_gb=lambda:(16,8,50)
        gui.AzmuthGitHubSensor=lambda:SimpleNamespace(pool=SimpleNamespace(tokens=[]))
        gui.load_all_genes=lambda:{'LOCAL':{'gene_id':'LOCAL','tier':2,'category':'graph','description':'Isolated DPI test','alleles':[]}}
        app=gui.AzmuthCommandCenterGUI(root)
        root.deiconify()
        errors=[]
        def inspect():
            try:
                app.switch_view('genes')
                app.cam_x,app.cam_y,app.cam_zoom=640.0,380.0,0.9
                app.zoom_level=0.9
                camera=(app.cam_x,app.cam_y,app.cam_zoom)
                selected=app.selected_gene_id
                padding=float(app.bar.cget('highlightthickness'))/info.scale
                app._run_background_job('Local DPI regression',app.theme.accent_blue,managed_command=[sys.executable,'-c','import time;time.sleep(30)'])
                for dpi in (96,144,192,96):
                    app._on_display_change(DisplayInfo(dpi,info.work_area,True))
                    assert camera==(app.cam_x,app.cam_y,app.cam_zoom)
                    assert app.selected_gene_id==selected
                    assert app.is_job_running
                    assert str(app.btn_cancel_job.cget('state'))=='normal'
                    assert all(str(button.cget('state'))=='disabled' for button,_ in app.action_buttons)
                    app._redraw_active_canvas()
                    identifier='GENE_ROOT::LOCAL'
                    box=app.canvas_nodes[identifier]['bbox']
                    x,y=(box[0]+box[2])/2,(box[1]+box[3])/2
                    app.canvas.event_generate('<ButtonPress-1>',x=round(x*app.system_dpi),y=round(y*app.system_dpi))
                    app.canvas.event_generate('<ButtonRelease-1>',x=round(x*app.system_dpi),y=round(y*app.system_dpi))
                    assert app.selected_node_id==identifier
                # Native borders round to whole pixels (notably at 225%).
                assert abs(float(app.bar.cget('highlightthickness'))-padding)<=0.5
                app._on_display_change(info)
                app.switch_view('ingestion')
                app._fit_active_view()
                import itertools
                for (name,a),(other,b) in itertools.combinations(app.canvas_nodes.items(),2):
                    a,b=a['bbox'],b['bbox']
                    assert min(a[2],b[2])-max(a[0],b[0])<=4 or min(a[3],b[3])-max(a[1],b[1])<=4,(name,other,a,b)
                app._cancel_active_job()
                root.after(100,finish)
            except BaseException:
                errors.append(traceback.format_exc());app._cancel_active_job();root.after(100,finish)
        def finish():
            if app.active_job and not app.active_job.worker_done.is_set():
                root.after(50,finish);return
            app._poll_job_results()
            if app.active_job.outcome!='cancelled':errors.append('Managed child did not cancel cleanly')
            result['transitions']=[96,144,192,96]
            result['job_outcome']=app.active_job.outcome
            result['errors']=errors
            app._on_close()
        root.after(600,inspect)
        root.after(10000,lambda:(errors.append('DPI test timed out'),app._cancel_active_job(),root.after(100,finish)))
        root.mainloop()
    else:
        root.destroy()
    destination.write_text(json.dumps(result),encoding='utf-8')
except BaseException:
    destination.write_text(json.dumps({'error':traceback.format_exc()}),encoding='utf-8')
'''


@pytest.mark.skipif(os.name != "nt", reason="Native Windows DPI verification")
@pytest.mark.parametrize("executable_name", ["python.exe", "pythonw.exe"])
@pytest.mark.parametrize("compatibility", [False, True])
def test_native_startup_through_console_and_windowed_python(tmp_path, executable_name, compatibility):
    executable = Path(sys.executable).with_name(executable_name)
    if not executable.exists():
        pytest.skip(f"{executable_name} is not installed")
    result_path = tmp_path / "dpi.json"
    environment = dict(os.environ)
    if compatibility:
        environment["__COMPAT_LAYER"] = "PerProcessSystemDPIForceOff GdiDPIScaling DPIUnaware"
    result = subprocess.run([str(executable), "-c", PROBE, str(result_path)], cwd=Path(__file__).resolve().parents[1],
                            env=environment, capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr
    data = json.loads(result_path.read_text())
    assert "error" not in data, data
    assert data["v2"] and not data["warning"], data
    assert abs(data["tk_scaling"] - data["dpi"] / 72) < 0.02


@pytest.mark.skipif(os.name != "nt", reason="Native Windows DPI and GUI hit testing")
def test_dpi_transitions_preserve_gui_state_and_running_job(tmp_path):
    destination = tmp_path / "gui.json"
    result = subprocess.run([sys.executable, "-c", PROBE, str(destination), "gui"], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr
    data = json.loads(destination.read_text())
    assert "error" not in data, data
    assert data["errors"] == [], data
    assert data["job_outcome"] == "cancelled"


@pytest.mark.skipif(os.name != "nt", reason="Native Windows subclass callback")
def test_native_hook_forwards_and_unhooks_without_changing_display_settings(tmp_path):
    destination = tmp_path / "hook.json"
    result = subprocess.run([sys.executable, "-c", PROBE, str(destination), "hook"], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr
    data = json.loads(destination.read_text())
    assert "error" not in data, data
    assert data["hook_verified"]
