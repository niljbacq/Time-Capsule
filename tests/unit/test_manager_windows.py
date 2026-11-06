from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.manager import SessionManager
from session_snapshot.models.adapter_types import ProcessInfo
from session_snapshot.models.manifest import EnvironmentInfo, Geometry
from session_snapshot.report.models import SaveStatus
from session_snapshot.store.manifests import ManifestStore
from session_snapshot.windows.base import LiveWindow, WindowBackend
from tests.fakes.fake_adapter import FakeAdapter
from tests.fakes.fake_process_source import FakeProcessSource

PROC = ProcessInfo(pid=42, ppid=1, name="fakeapp")


def live(pid, wid="0xa"):
    return LiveWindow(
        window_id=wid,
        pid=pid,
        title="t",
        workspace=1,
        wm_class="fakeapp",
        state="maximized",
        geometry=Geometry(x=0, y=36, width=800, height=600),
        window_type="normal",
    )


class FakeBackend(WindowBackend):
    def __init__(self, windows=(), wm="Xfwm4", error=None):
        self._windows = list(windows)
        self._wm = wm
        self._error = error

    def available(self):
        return True

    def window_manager(self):
        return self._wm

    def list_windows(self):
        if self._error:
            raise self._error
        return self._windows


def make(tmp_path, backend, procs=(PROC,)):
    registry = AdapterRegistry()
    registry.register(FakeAdapter())
    store = ManifestStore(tmp_path / "sessions")
    manager = SessionManager(
        registry,
        store,
        FakeProcessSource(procs),
        env_provider=lambda: EnvironmentInfo(session_type="x11"),
        window_backend=backend,
    )
    return manager, store


def test_windows_attached_to_matching_entry(tmp_path):
    manager, store = make(tmp_path, FakeBackend([live(42)]))
    manager.save("s1", "S1")
    app = store.load("s1").apps[0]
    assert [w.window_id for w in app.windows] == ["0xa"]
    assert app.windows[0].hint.wm_class == "fakeapp"
    assert app.windows[0].state == "maximized"
    assert app.windows[0].workspace == 1


def test_window_manager_recorded(tmp_path):
    manager, store = make(tmp_path, FakeBackend([live(42)], wm="Xfwm4"))
    manager.save("s1", "S1")
    assert store.load("s1").environment.window_manager == "Xfwm4"


def test_backend_error_warns_but_save_succeeds(tmp_path):
    manager, store = make(tmp_path, FakeBackend(error=RuntimeError("boom")))
    report = manager.save("s1", "S1")
    assert [o.status for o in report.outcomes] == [SaveStatus.CAPTURED]
    assert any("window capture failed" in w for w in report.warnings)
    manifest = store.load("s1")
    assert manifest.apps[0].windows == []
    assert manifest.environment.window_manager is None


def test_no_backend_leaves_windows_empty(tmp_path):
    manager, store = make(tmp_path, None)
    report = manager.save("s1", "S1")
    manifest = store.load("s1")
    assert manifest.apps[0].windows == []
    assert manifest.environment.window_manager is None
    assert report.warnings == []


def test_shared_window_owner_warns_and_skips(tmp_path):
    procs = (
        ProcessInfo(pid=42, ppid=7, name="fakeapp"),
        ProcessInfo(pid=43, ppid=7, name="fakeapp"),
    )
    manager, store = make(tmp_path, FakeBackend([live(7)]), procs=procs)
    report = manager.save("s1", "S1")
    assert any("share window owner pid 7" in w for w in report.warnings)
    assert all(a.windows == [] for a in store.load("s1").apps)