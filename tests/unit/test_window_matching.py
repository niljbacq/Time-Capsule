from session_snapshot.models.adapter_types import ProcessInfo
from session_snapshot.models.manifest import Geometry
from session_snapshot.windows.base import LiveWindow
from session_snapshot.windows.matching import (
    match_windows,
    owner_pid_for,
    to_window_entry,
)


def win(wid, pid, wm_class="firefox", wtype="normal", ws=0, state="normal"):
    return LiveWindow(
        window_id=wid,
        pid=pid,
        title="t",
        workspace=ws,
        wm_class=wm_class,
        state=state,
        geometry=Geometry(x=0, y=36, width=800, height=600),
        window_type=wtype,
    )


def proc(pid, ppid, name="x"):
    return ProcessInfo(pid=pid, ppid=ppid, name=name)


def test_owner_walks_up_to_ancestor():
    assert owner_pid_for(300, {300: 200, 200: 1}, {200}) == 200


def test_owner_is_self_when_pid_owns_window():
    assert owner_pid_for(6592, {6592: 1}, {6592}) == 6592


def test_owner_none_when_no_ancestor_matches():
    assert owner_pid_for(300, {300: 200, 200: 1}, {999}) is None


def test_owner_survives_parent_cycle():
    assert owner_pid_for(1, {1: 2, 2: 1}, {9}) is None


def test_entry_fields():
    entry = to_window_entry(win("0x1", 5, wm_class="Foo", ws=2, state="maximized"))
    assert entry.window_id == "0x1"
    assert entry.hint.wm_class == "Foo"
    assert entry.hint.title_pattern is None
    assert entry.workspace == 2
    assert entry.state == "maximized"
    assert entry.geometry == Geometry(x=0, y=36, width=800, height=600)


def test_firefox_instance_gets_all_its_windows():
    result, warnings = match_windows(
        [("firefox-6592", 6592)],
        [proc(6592, 1, "firefox")],
        [win("0xa", 6592), win("0xb", 6592)],
    )
    assert [e.window_id for e in result["firefox-6592"]] == ["0xa", "0xb"]
    assert warnings == []


def test_single_terminal_shell_matches_via_parent():
    result, warnings = match_windows(
        [("terminal-300", 300)],
        [proc(200, 1, "xfce4-terminal"), proc(300, 200, "bash")],
        [win("0xc", 200, wm_class="Xfce4-terminal")],
    )
    assert [e.window_id for e in result["terminal-300"]] == ["0xc"]
    assert warnings == []


def test_two_shells_under_one_terminal_process_are_skipped_with_warning():
    result, warnings = match_windows(
        [("terminal-300", 300), ("terminal-301", 301)],
        [proc(200, 1), proc(300, 200), proc(301, 200)],
        [win("0xc", 200), win("0xd", 200)],
    )
    assert result == {}
    assert len(warnings) == 1
    assert "terminal-300" in warnings[0]
    assert "terminal-301" in warnings[0]


def test_non_normal_windows_and_unknown_pids_are_ignored():
    result, warnings = match_windows(
        [("firefox-1", 1), ("nopid", None)],
        [proc(1, None)],
        [win("0xe", 1, wtype="dock"), win("0xf", None)],
    )
    assert result == {}
    assert warnings == []
