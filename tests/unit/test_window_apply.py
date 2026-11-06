from session_snapshot.models.adapter_types import ProcessInfo
from session_snapshot.models.manifest import Geometry, WindowEntry
from session_snapshot.windows.apply import apply_saved_windows
from session_snapshot.windows.base import LiveWindow, WindowBackend

GEO = Geometry(x=10, y=36, width=800, height=600)


def live(wid, pid):
    return LiveWindow(
        window_id=wid,
        pid=pid,
        title="t",
        workspace=0,
        wm_class="x",
        state="normal",
        geometry=None,
        window_type="normal",
    )


def saved(wid="0x1"):
    return WindowEntry(window_id=wid, workspace=1, state="normal", geometry=GEO)


class FakeBackend(WindowBackend):
    def __init__(self, batches, error=None):
        self.batches = list(batches)
        self.error = error
        self.placed = []
        self.place_warnings = []

    def available(self):
        return True

    def window_manager(self):
        return "Xfwm4"

    def list_windows(self):
        if self.error:
            raise self.error
        return self.batches.pop(0) if len(self.batches) > 1 else self.batches[0]

    def place_window(self, window_id, workspace, state, geometry):
        self.placed.append((window_id, workspace, state, geometry))
        return list(self.place_warnings)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def run(backend, saved_windows, clock=None):
    clock = clock or Clock()
    return apply_saved_windows(
        backend,
        lambda: [ProcessInfo(pid=5, ppid=1, name="x")],
        5,
        saved_windows,
        wait_seconds=1.0,
        poll_seconds=0.5,
        sleep=clock.sleep,
        clock=clock,
    )


def test_places_windows_that_are_already_there():
    backend = FakeBackend([[live("0x20", 5)]])
    assert run(backend, [saved()]) == (1, [])
    assert backend.placed == [("0x20", 1, "normal", GEO)]


def test_waits_for_window_to_appear():
    backend = FakeBackend([[], [live("0x20", 5)]])
    assert run(backend, [saved()]) == (1, [])
    assert len(backend.placed) == 1


def test_gives_up_after_wait_and_warns():
    clock = Clock()
    backend = FakeBackend([[]])
    placed, warnings = run(backend, [saved()], clock)
    assert placed == 0
    assert "found 0" in warnings[0]
    assert clock.t >= 1.0
    assert backend.placed == []


def test_count_mismatch_places_nothing():
    backend = FakeBackend([[live("0x20", 5), live("0x21", 5)]])
    placed, warnings = run(backend, [saved()])
    assert placed == 0
    assert "expected 1" in warnings[0]
    assert "found 2" in warnings[0]
    assert backend.placed == []


def test_nothing_saved_never_touches_backend():
    backend = FakeBackend([[]], error=RuntimeError("must not be called"))
    assert run(backend, []) == (0, [])


def test_backend_error_becomes_warning():
    backend = FakeBackend([[]], error=RuntimeError("boom"))
    placed, warnings = run(backend, [saved()])
    assert placed == 0
    assert warnings == ["window placement failed: RuntimeError: boom"]


def test_place_window_warnings_are_returned():
    backend = FakeBackend([[live("0x20", 5)]])
    backend.place_warnings = ["0x20: workspace failed"]
    placed, warnings = run(backend, [saved()])
    assert placed == 1
    assert warnings == ["0x20: workspace failed"]