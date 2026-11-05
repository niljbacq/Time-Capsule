from unittest.mock import patch

import pytest

from session_snapshot.adapters.base import AdapterError
from session_snapshot.adapters.terminal import TerminalAdapter
from session_snapshot.models.adapter_types import (
    ActionKind,
    AppInstance,
    CaptureContext,
    DiscoveryContext,
    ProcessInfo,
    RestoreContext,
    RestoreHandle,
    RestorePlan,
)
from session_snapshot.models.manifest import AppEntry
from session_snapshot.models.results import Reason, Status


def _proc(pid: int, ppid: int | None, name: str, cwd: str | None = None) -> ProcessInfo:
    return ProcessInfo(pid=pid, ppid=ppid, name=name, cwd=cwd)


def _entry(cwd: str = "/home/neil") -> AppEntry:
    return AppEntry.model_validate(
        {
            "instance_id": "terminal-100",
            "app_id": "xfce4-terminal.desktop",
            "adapter": {"id": "terminal_xfce4", "version": 1},
            "compatibility_class": 2,
            "launch": {
                "type": "argv",
                "executable": "/usr/bin/xfce4-terminal",
                "args": ["--window", "--working-directory", cwd],
            },
            "state": {"cwd": cwd},
            "capture": {
                "status": "captured",
                "capabilities": [{"name": "shell_cwd", "captured": True}],
            },
        }
    )


def _discovery(*procs: ProcessInfo) -> DiscoveryContext:
    return DiscoveryContext(processes=tuple(procs))


def _capture_ctx(*procs: ProcessInfo) -> CaptureContext:
    return CaptureContext(processes=tuple(procs))


def _restore_ctx(*procs: ProcessInfo, policy: str = "reuse_existing") -> RestoreContext:
    return RestoreContext(processes=tuple(procs), duplicate_policy=policy)


# --- detect ----------------------------------------------------------------

def test_detect_finds_shells_under_single_server():
    procs = [
        _proc(10382, 1772, "xfce4-terminal"),
        _proc(10388, 10382, "bash", "/home/neil"),
        _proc(18899, 10382, "bash", "/home/neil/linux-session-snapshot"),
        _proc(19120, 10382, "bash", "/home/neil/Documents"),
    ]
    with patch(
        "session_snapshot.adapters.terminal.shutil.which",
        return_value="/usr/bin/xfce4-terminal",
    ):
        instances = TerminalAdapter().detect(_discovery(*procs))
    assert {i.instance_id for i in instances} == {
        "terminal-10388",
        "terminal-18899",
        "terminal-19120",
    }
    assert all(i.adapter_id == "terminal_xfce4" for i in instances)
    assert all(i.app_id == "xfce4-terminal.desktop" for i in instances)


def test_detect_skips_non_shell_children():
    procs = [
        _proc(10382, 1772, "xfce4-terminal"),
        _proc(10388, 10382, "bash", "/home/neil"),
        _proc(10599, 10388, "tmux: client", "/home/neil"),
        _proc(20000, 10382, "python3", "/tmp"),
    ]
    with patch(
        "session_snapshot.adapters.terminal.shutil.which",
        return_value="/usr/bin/xfce4-terminal",
    ):
        instances = TerminalAdapter().detect(_discovery(*procs))
    assert [i.instance_id for i in instances] == ["terminal-10388"]


def test_detect_returns_empty_when_terminal_not_installed():
    with patch("session_snapshot.adapters.terminal.shutil.which", return_value=None):
        instances = TerminalAdapter().detect(_discovery())
    assert instances == []


# --- capture ---------------------------------------------------------------

def test_capture_writes_launch_argv():
    inst = AppInstance(
        instance_id="terminal-100",
        adapter_id="terminal_xfce4",
        pid=100,
        app_id="xfce4-terminal.desktop",
        label="work",
    )
    ctx = _capture_ctx(_proc(100, 10382, "bash", "/home/neil/work"))
    with patch(
        "session_snapshot.adapters.terminal.shutil.which",
        return_value="/usr/bin/xfce4-terminal",
    ):
        entry = TerminalAdapter().capture(inst, ctx)
    assert entry.instance_id == "terminal-100"
    assert entry.adapter.id == "terminal_xfce4"
    assert entry.adapter.version == 1
    assert entry.compatibility_class == 2
    assert entry.launch.executable == "/usr/bin/xfce4-terminal"
    assert entry.launch.args == [
        "--window",
        "--working-directory",
        "/home/neil/work",
    ]
    assert entry.state["cwd"] == "/home/neil/work"
    assert entry.capture.status == "captured"


def test_capture_raises_when_process_is_gone():
    inst = AppInstance(instance_id="terminal-999", adapter_id="terminal_xfce4", pid=999)
    with pytest.raises(AdapterError) as exc_info:
        TerminalAdapter().capture(inst, _capture_ctx())
    assert exc_info.value.reason is Reason.PATH_MISSING


# --- plan_restore ----------------------------------------------------------

def test_plan_restore_launches_when_path_exists():
    with patch(
        "session_snapshot.adapters.terminal.shutil.which",
        return_value="/usr/bin/xfce4-terminal",
    ), patch("session_snapshot.adapters.terminal.os.path.isdir", return_value=True):
        plan = TerminalAdapter().plan_restore(_entry("/home/neil"), _restore_ctx())
    assert plan.action is ActionKind.LAUNCH
    assert plan.reason is Reason.OK


def test_plan_restore_skips_when_directory_is_gone():
    with patch(
        "session_snapshot.adapters.terminal.shutil.which",
        return_value="/usr/bin/xfce4-terminal",
    ), patch("session_snapshot.adapters.terminal.os.path.isdir", return_value=False):
        plan = TerminalAdapter().plan_restore(_entry("/home/neil/gone"), _restore_ctx())
    assert plan.action is ActionKind.SKIP
    assert plan.reason is Reason.PATH_MISSING
    assert plan.unavailable_paths == ["/home/neil/gone"]


def test_plan_restore_skips_when_already_running_and_policy_says_skip():
    entry = _entry("/home/neil/work")
    ctx = _restore_ctx(
        _proc(100, 10382, "bash", "/home/neil/work"),
        policy="skip_if_running",
    )
    with patch(
        "session_snapshot.adapters.terminal.shutil.which",
        return_value="/usr/bin/xfce4-terminal",
    ), patch("session_snapshot.adapters.terminal.os.path.isdir", return_value=True):
        plan = TerminalAdapter().plan_restore(entry, ctx)
    assert plan.action is ActionKind.SKIP
    assert plan.reason is Reason.ALREADY_RUNNING


def test_plan_restore_skips_when_terminal_not_installed():
    with patch("session_snapshot.adapters.terminal.shutil.which", return_value=None):
        plan = TerminalAdapter().plan_restore(_entry("/home/neil"), _restore_ctx())
    assert plan.action is ActionKind.SKIP
    assert plan.reason is Reason.NOT_INSTALLED
    assert "xfce4-terminal" in plan.missing_dependencies


# --- restore ---------------------------------------------------------------

def test_restore_launches_argv_without_shell():
    entry = _entry("/home/neil/work")
    plan = RestorePlan(action=ActionKind.LAUNCH, message="go")
    with patch("session_snapshot.adapters.terminal.subprocess.Popen") as popen:
        popen.return_value.pid = 4321
        handle = TerminalAdapter().restore(entry, plan, _restore_ctx())
    args, kwargs = popen.call_args
    assert args[0] == [
        "/usr/bin/xfce4-terminal",
        "--window",
        "--working-directory",
        "/home/neil/work",
    ]
    assert kwargs.get("shell") is not True
    assert handle.instance_id == "terminal-100"
    assert handle.pid == 4321


# --- verify ----------------------------------------------------------------

def test_verify_restored_when_shell_matches_cwd():
    entry = _entry("/home/neil/work")
    handle = RestoreHandle(instance_id="terminal-100", pid=4321)
    with patch(
        "session_snapshot.adapters.terminal._iter_shell_cwds",
        return_value=iter([(20000, "/home/neil/work")]),
    ):
        result = TerminalAdapter().verify(entry, handle, _restore_ctx())
    assert result.status is Status.RESTORED
    assert result.reason is Reason.OK


def test_verify_partial_on_timeout():
    entry = _entry("/home/neil/work")
    handle = RestoreHandle(instance_id="terminal-100", pid=4321)
    with patch(
        "session_snapshot.adapters.terminal._iter_shell_cwds",
        return_value=iter([]),
    ), patch(
        "session_snapshot.adapters.terminal.time.monotonic",
        side_effect=[0.0, 100.0],
    ), patch("time.sleep"):
        result = TerminalAdapter().verify(entry, handle, _restore_ctx())
    assert result.status is Status.PARTIAL
    assert result.reason is Reason.TIMEOUT


def test_verify_failed_when_snapshot_has_no_cwd():
    entry = AppEntry.model_validate(
        {
            "instance_id": "terminal-100",
            "adapter": {"id": "terminal_xfce4", "version": 1},
            "compatibility_class": 2,
            "launch": {"executable": "/usr/bin/xfce4-terminal"},
            "capture": {"status": "captured"},
        }
    )
    handle = RestoreHandle(instance_id="terminal-100")
    result = TerminalAdapter().verify(entry, handle, _restore_ctx())
    assert result.status is Status.FAILED
    assert result.reason is Reason.VERIFY_MISMATCH


# --- capabilities ----------------------------------------------------------

def test_capabilities_returns_list_with_supported_and_unsupported_entries():
    caps = TerminalAdapter().capabilities()
    assert isinstance(caps, list) and caps
    by_name = {c.name: c for c in caps}
    assert by_name["shell_cwd"].supported is True
    assert by_name["window_grouping"].supported is False
    assert by_name["window_grouping"].limitation
    assert by_name["shell_state"].supported is False


def test_adapter_has_required_class_attributes():
    assert TerminalAdapter.adapter_id == "terminal_xfce4"
    assert TerminalAdapter.version == 1
    assert TerminalAdapter.compatibility_class == 2
