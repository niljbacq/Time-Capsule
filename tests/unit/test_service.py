import pytest

from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.events import EventBus, EventKind
from session_snapshot.models.adapter_types import ActionKind, ProcessInfo
from session_snapshot.models.manifest import EnvironmentInfo
from session_snapshot.models.results import Status
from session_snapshot.services.factory import create_default_service
from session_snapshot.services.session_service import SessionService
from session_snapshot.store.manifests import ManifestError, ManifestStore
from tests.fakes.fake_adapter import FakeAdapter
from tests.fakes.fake_process_source import FakeProcessSource

PROC = ProcessInfo(pid=42, name="fakeapp")


def make_service(tmp_path, adapters=None, bus=None):
    registry = AdapterRegistry()
    for adapter in adapters if adapters is not None else [FakeAdapter()]:
        registry.register(adapter)
    return SessionService(
        registry,
        ManifestStore(tmp_path / "sessions"),
        FakeProcessSource([PROC]),
        bus=bus,
        env_provider=lambda: EnvironmentInfo(session_type="x11"),
    )


def test_save_then_list(tmp_path):
    svc = make_service(tmp_path)
    svc.save("study-setup", "Study Setup", description="notes")
    listing = svc.list_sessions()
    assert [s.session_id for s in listing.sessions] == ["study-setup"]
    summary = listing.sessions[0]
    assert summary.app_count == 1
    assert summary.adapter_ids == ["fake"]
    assert summary.description == "notes"
    assert summary.session_type == "x11"
    assert listing.problems == []


def test_corrupt_manifest_is_a_problem_not_a_crash(tmp_path):
    svc = make_service(tmp_path)
    svc.save("study-setup", "Study Setup")
    (svc.store.root / "broken.json").write_text("{nope")
    listing = svc.list_sessions()
    assert [s.session_id for s in listing.sessions] == ["study-setup"]
    assert [p.session_id for p in listing.problems] == ["broken"]


def test_get_session(tmp_path):
    svc = make_service(tmp_path)
    svc.save("study-setup", "Study Setup")
    assert svc.get_session("study-setup").session.name == "Study Setup"


def test_delete_session(tmp_path):
    svc = make_service(tmp_path)
    svc.save("study-setup", "Study Setup")
    svc.delete_session("study-setup")
    assert svc.list_sessions().sessions == []
    with pytest.raises(ManifestError):
        svc.delete_session("study-setup")


def test_rename_changes_name_only(tmp_path):
    svc = make_service(tmp_path)
    svc.save("study-setup", "Study Setup")
    svc.rename_session("study-setup", "Renamed")
    manifest = svc.get_session("study-setup")
    assert manifest.session.name == "Renamed"
    assert manifest.session.id == "study-setup"
    with pytest.raises(ManifestError):
        svc.rename_session("study-setup", "   ")


def test_duplicate_session(tmp_path):
    svc = make_service(tmp_path)
    svc.save("study-setup", "Study Setup")
    svc.duplicate_session("study-setup", "copy-of-study", "Copy")
    original = svc.get_session("study-setup")
    copy = svc.get_session("copy-of-study")
    assert copy.session.name == "Copy"
    assert copy.apps == original.apps
    assert original.session.name == "Study Setup"
    with pytest.raises(ManifestError):
        svc.duplicate_session("study-setup", "copy-of-study", "Again")
    with pytest.raises(ManifestError):
        svc.duplicate_session("study-setup", "../evil", "Bad")


def test_restore_through_service(tmp_path):
    svc = make_service(tmp_path)
    svc.save("study-setup", "Study Setup")
    report = svc.restore("study-setup")
    assert report.outcomes[0].status is Status.RESTORED


def test_preview_through_service(tmp_path):
    svc = make_service(tmp_path)
    svc.save("study-setup", "Study Setup")
    preview = svc.preview("study-setup")
    assert preview.apps[0].action is ActionKind.LAUNCH


class BrokenCapsAdapter(FakeAdapter):
    def capabilities(self):
        raise RuntimeError("no caps")


def test_adapters_info_isolates_failures(tmp_path):
    svc = make_service(tmp_path, [FakeAdapter(adapter_id="good"), BrokenCapsAdapter(adapter_id="broken")])
    infos = {i.adapter_id: i for i in svc.adapters()}
    assert infos["good"].error is None
    assert [c.name for c in infos["good"].capabilities] == ["cwd"]
    assert infos["good"].compatibility_class == 2
    assert infos["broken"].error is not None
    assert infos["broken"].capabilities == []


def test_save_and_restore_share_one_event_bus(tmp_path):
    bus = EventBus()
    kinds = []
    bus.subscribe(lambda e: kinds.append(e.kind))
    svc = make_service(tmp_path, bus=bus)
    svc.save("study-setup", "Study Setup")
    svc.restore("study-setup")
    assert EventKind.SAVE_STARTED in kinds
    assert EventKind.RESTORE_STARTED in kinds


def test_default_factory_builds_a_working_service(tmp_path):
    svc = create_default_service(tmp_path / "sessions")
    assert "terminal_xfce4" in [a.adapter_id for a in svc.adapters()]
    assert svc.list_sessions().sessions == []
