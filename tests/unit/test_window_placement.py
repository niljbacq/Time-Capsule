from session_snapshot.models.adapter_types import ProcessInfo
from session_snapshot.models.manifest import Geometry, WindowEntry
from session_snapshot.windows.base import LiveWindow
from session_snapshot.windows.placement import (
    Placement,
    candidate_windows,
    plan_placements,
)

GEO = Geometry(x=10, y=36, width=800, height=600)


def live(wid, pid, wtype="normal"):
    return LiveWindow(
        window_id=wid,
        pid=pid,
        title="t",
        workspace=0,
        wm_class="x",
        state="normal",
        geometry=None,
        window_type=wtype,
    )


def saved(wid, ws=1, state="normal", geometry=GEO):
    return WindowEntry(window_id=wid, workspace=ws, state=state, geometry=geometry)


def proc(pid, ppid):
    return ProcessInfo(pid=pid, ppid=ppid, name="x")


def test_candidates_follow_ancestry():
    found = candidate_windows(
        300, [proc(200, 1), proc(300, 200)], [live("0xa", 200), live("0xb", 200)]
    )
    assert [w.window_id for w in found] == ["0xa", "0xb"]


def test_candidates_ignore_non_normal_windows():
    found = candidate_windows(5, [proc(5, 1)], [live("0xa", 5, wtype="dock")])
    assert found == []


def test_candidates_empty_when_no_owner():
    assert candidate_windows(5, [proc(5, 1)], [live("0xa", 999)]) == []


def test_single_window_keeps_geometry_workspace_and_state():
    placements, warnings = plan_placements([saved("0x1")], [live("0x20", 5)])
    assert placements == [
        Placement(window_id="0x20", workspace=1, state="normal", geometry=GEO)
    ]
    assert warnings == []


def test_maximized_window_drops_geometry():
    placements, _ = plan_placements(
        [saved("0x1", state="maximized")], [live("0x20", 5)]
    )
    assert placements[0].state == "maximized"
    assert placements[0].geometry is None


def test_pairs_in_window_id_order():
    placements, warnings = plan_placements(
        [saved("0xb", ws=2), saved("0xa", ws=1)],
        [live("0x20", 5), live("0x10", 5)],
    )
    assert [(p.window_id, p.workspace) for p in placements] == [
        ("0x10", 1),
        ("0x20", 2),
    ]
    assert warnings == []


def test_count_mismatch_places_nothing_and_warns():
    placements, warnings = plan_placements(
        [saved("0x1")], [live("0x20", 5), live("0x21", 5)]
    )
    assert placements == []
    assert len(warnings) == 1
    assert "expected 1" in warnings[0]
    assert "found 2" in warnings[0]


def test_no_live_windows_warns():
    placements, warnings = plan_placements([saved("0x1")], [])
    assert placements == []
    assert "found 0" in warnings[0]


def test_nothing_saved_is_silent():
    assert plan_placements([], [live("0x20", 5)]) == ([], [])