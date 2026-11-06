from session_snapshot.models.manifest import Geometry
from session_snapshot.windows.base import CommandResult
from session_snapshot.windows.x11 import X11Backend

WID = "0x04608456"
GEO = Geometry(x=100, y=100, width=500, height=300)
CLEAR_MAX = ["wmctrl", "-i", "-r", WID, "-b", "remove,maximized_vert,maximized_horz"]
CLEAR_FULL = ["wmctrl", "-i", "-r", WID, "-b", "remove,fullscreen"]


class Recorder:
    def __init__(self, fail_flag=None):
        self.calls = []
        self.fail_flag = fail_flag

    def __call__(self, argv):
        self.calls.append(list(argv))
        if self.fail_flag is not None and self.fail_flag in argv:
            return CommandResult(1, "")
        return CommandResult(0, "")


def test_normal_state_clears_then_sets_workspace_then_moves():
    rec = Recorder()
    warnings = X11Backend(rec).place_window(WID, 1, "normal", GEO)
    assert warnings == []
    assert rec.calls == [
        CLEAR_MAX,
        CLEAR_FULL,
        ["wmctrl", "-i", "-r", WID, "-t", "1"],
        ["wmctrl", "-i", "-r", WID, "-e", "10,100,100,500,300"],
    ]


def test_maximized_state_skips_geometry_and_maximizes():
    rec = Recorder()
    warnings = X11Backend(rec).place_window(WID, 0, "maximized", GEO)
    assert warnings == []
    assert rec.calls[-1] == [
        "wmctrl", "-i", "-r", WID, "-b", "add,maximized_vert,maximized_horz",
    ]
    assert not any("-e" in call for call in rec.calls)


def test_fullscreen_state_adds_fullscreen():
    rec = Recorder()
    warnings = X11Backend(rec).place_window(WID, None, "fullscreen", GEO)
    assert warnings == []
    assert rec.calls[-1] == ["wmctrl", "-i", "-r", WID, "-b", "add,fullscreen"]
    assert not any("-e" in call for call in rec.calls)


def test_failing_step_becomes_warning_and_later_steps_still_run():
    rec = Recorder(fail_flag="-t")
    warnings = X11Backend(rec).place_window(WID, 2, "normal", GEO)
    assert len(warnings) == 1
    assert "workspace failed" in warnings[0]
    assert WID in warnings[0]
    assert any("-e" in call for call in rec.calls)


def test_no_workspace_and_no_geometry_send_only_the_clear_steps():
    rec = Recorder()
    warnings = X11Backend(rec).place_window(WID, None, "normal", None)
    assert warnings == []
    assert rec.calls == [CLEAR_MAX, CLEAR_FULL]


def test_all_commands_are_argv_lists_of_strings():
    rec = Recorder()
    X11Backend(rec).place_window(WID, 1, "normal", GEO)
    assert rec.calls
    for argv in rec.calls:
        assert isinstance(argv, list)
        assert all(isinstance(part, str) for part in argv)