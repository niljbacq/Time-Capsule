from session_snapshot.models.manifest import Geometry
from session_snapshot.windows.base import CommandResult
from session_snapshot.windows.x11 import X11Backend, run_command

WID = "0x04800003"
LIST_ARGV = ("wmctrl", "-lp")
PROPS_ARGV = ("xprop", "-id", WID, "_NET_WM_STATE", "WM_CLASS", "_NET_WM_WINDOW_TYPE")
INFO_ARGV = ("xwininfo", "-id", WID)

LISTING = "0x04800003  0 6592 nj Mozilla Firefox\n"
PROPS = (
    "_NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_HORZ, _NET_WM_STATE_MAXIMIZED_VERT\n"
    'WM_CLASS(STRING) = "Navigator", "firefox"\n'
    "_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_NORMAL\n"
)
INFO = (
    "  Absolute upper-left X:  0\n"
    "  Absolute upper-left Y:  36\n"
    "  Width: 1366\n"
    "  Height: 699\n"
)

ROOT_ARGV = ("xprop", "-root", "_NET_SUPPORTING_WM_CHECK")
NAME_ARGV = ("xprop", "-id", "0x800336", "_NET_WM_NAME")
ROOT_OUT = "_NET_SUPPORTING_WM_CHECK(WINDOW): window id # 0x800336\n"
NAME_OUT = '_NET_WM_NAME(UTF8_STRING) = "Xfwm4"\n'


class FakeRunner:
    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        return self.table.get(tuple(argv), CommandResult(127, ""))


def ok(text):
    return CommandResult(0, text)


def test_available_true():
    runner = FakeRunner({("wmctrl", "-m"): ok("Name: Xfwm4\n")})
    assert X11Backend(runner).available() is True


def test_available_false_when_tool_missing():
    assert X11Backend(FakeRunner({})).available() is False


def test_window_manager_name():
    runner = FakeRunner({ROOT_ARGV: ok(ROOT_OUT), NAME_ARGV: ok(NAME_OUT)})
    assert X11Backend(runner).window_manager() == "Xfwm4"


def test_window_manager_none_when_root_check_fails():
    assert X11Backend(FakeRunner({})).window_manager() is None


def test_window_manager_none_when_no_id_in_output():
    runner = FakeRunner({ROOT_ARGV: ok("_NET_SUPPORTING_WM_CHECK:  not found.\n")})
    assert X11Backend(runner).window_manager() is None


def test_window_manager_none_when_name_lookup_fails():
    runner = FakeRunner({ROOT_ARGV: ok(ROOT_OUT)})
    assert X11Backend(runner).window_manager() is None


def test_list_windows_full_row():
    runner = FakeRunner(
        {LIST_ARGV: ok(LISTING), PROPS_ARGV: ok(PROPS), INFO_ARGV: ok(INFO)}
    )
    windows = X11Backend(runner).list_windows()
    assert len(windows) == 1
    w = windows[0]
    assert w.window_id == WID
    assert w.pid == 6592
    assert w.title == "Mozilla Firefox"
    assert w.workspace == 0
    assert w.wm_class == "firefox"
    assert w.state == "maximized"
    assert w.window_type == "normal"
    assert w.geometry == Geometry(x=0, y=36, width=1366, height=699)


def test_list_windows_empty_when_wmctrl_fails():
    assert X11Backend(FakeRunner({})).list_windows() == []


def test_list_windows_survives_failed_xprop_and_xwininfo():
    runner = FakeRunner({LIST_ARGV: ok(LISTING)})
    windows = X11Backend(runner).list_windows()
    assert len(windows) == 1
    w = windows[0]
    assert w.wm_class is None
    assert w.state == "normal"
    assert w.window_type is None
    assert w.geometry is None
    assert w.title == "Mozilla Firefox"


def test_list_windows_sticky_workspace_is_none():
    runner = FakeRunner({LIST_ARGV: ok("0x00e00003 -1 1675 nj xfce4-panel\n")})
    windows = X11Backend(runner).list_windows()
    assert windows[0].workspace is None
    assert windows[0].pid == 1675


def test_run_command_missing_tool_is_failure_result():
    result = run_command(["definitely-not-a-real-tool-xyz"])
    assert result.returncode == 127
    assert result.stdout == ""


def test_all_commands_are_argv_lists():
    runner = FakeRunner(
        {LIST_ARGV: ok(LISTING), PROPS_ARGV: ok(PROPS), INFO_ARGV: ok(INFO)}
    )
    X11Backend(runner).list_windows()
    assert runner.calls
    for argv in runner.calls:
        assert isinstance(argv, list)
        assert all(isinstance(part, str) for part in argv)