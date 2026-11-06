from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.manager import SessionManager
from session_snapshot.core.restore import RestoreEngine
from session_snapshot.models.adapter_types import ActionKind, ProcessInfo, RestorePlan
from session_snapshot.models.manifest import EnvironmentInfo, Geometry
from session_snapshot.models.results import OpResult, Reason, Status
from session_snapshot.store.manifests import ManifestStore
from session_snapshot.windows.base import LiveWindow, WindowBackend
from tests.fakes.fake_adapter import FakeAdapter
from tests.fakes.fake_process_source import FakeProcessSource

PROC = ProcessInfo(pid=42, ppid=1, name="fakeapp")
GEO = Geometry(x=0, y=36, width=800, height=600)


def x11_env():
    return EnvironmentInfo(session_type="x11")


def live(pid, wid):
    return LiveWindow(
        window_id=wid,
        pid=pid,
        title="t",
        workspace=1,
        wm_class="fakeapp",
        state="maximized",
        geometry=GEO,
        window_type="normal",
    )


class FakeBackend(WindowBackend):
    def __init__(self, windows=()):
        self.windows = list(windows)
        self.placed = []
        self.place_warnings = []

    def available(self):
        return True

    def window_manager(self):
        return "Xfwm4"

    def list_windows(self):
        return self.windows

    def place_window(self, window_id, workspace, state, geometry):
        self.placed.append((window_id, workspace, state, geometry))
        return list(self.place_warnings)


def saved_store(tmp_path):
    registry = AdapterRegistry()
    registry.register(FakeAdapter())
    store = ManifestStore(tmp_path / "sessions")
    SessionManager(
        registry,
        store,
        FakeProcessSource([PROC]),
        env_provider=x11_env,
        window_backend=FakeBackend([live(42, "0xa")]),
    ).save("s1", "S1")
    return store


def restore(store, adapter, backend):
    registry = AdapterRegistry()
    registry.register(adapter)
    engine = RestoreEngine(
        registry,
        store,
        FakeProcessSource(()),
        env_provider=x11_env,
        window_backend=backend,
    )
    return engine.restore("s1").outcomes[0]


def test_launched_and_verified_app_gets_windows_placed(tmp_path):
    store = saved_store(tmp_path)
    backend = FakeBackend([live(1234, "0x20")])
    outcome = restore(store, FakeAdapter(), backend)
    assert outcome.status is Status.RESTORED
    assert backend.placed == [("0x20", 1, "maximized", None)]
    assert outcome.details["windows"] == {"placed": 1, "warnings": []}


def test_reused_app_is_never_moved(tmp_path):
    store = saved_store(tmp_path)
    backend = FakeBackend([live(1234, "0x20")])
    adapter = FakeAdapter(plan=RestorePlan(action=ActionKind.REUSE, message="reuse"))
    outcome = restore(store, adapter, backend)
    assert backend.placed == []
    assert "windows" not in outcome.details


def test_failed_app_is_never_moved(tmp_path):
    store = saved_store(tmp_path)
    backend = FakeBackend([live(1234, "0x20")])
    adapter = FakeAdapter(verify_result=OpResult.failed(Reason.VERIFY_MISMATCH, "no"))
    outcome = restore(store, adapter, backend)
    assert outcome.status is Status.FAILED
    assert backend.placed == []
    assert "windows" not in outcome.details


def test_placement_warning_keeps_status_restored(tmp_path):
    store = saved_store(tmp_path)
    backend = FakeBackend([live(1234, "0x20")])
    backend.place_warnings = ["0x20: workspace failed"]
    outcome = restore(store, FakeAdapter(), backend)
    assert outcome.status is Status.RESTORED
    assert outcome.details["windows"]["warnings"] == ["0x20: workspace failed"]


def test_no_backend_leaves_details_without_windows(tmp_path):
    store = saved_store(tmp_path)
    outcome = restore(store, FakeAdapter(), None)
    assert outcome.status is Status.RESTORED
    assert "windows" not in outcome.details