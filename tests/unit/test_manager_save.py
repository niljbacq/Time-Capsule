import pytest

from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.events import EventBus, EventKind
from session_snapshot.core.manager import SessionManager
from session_snapshot.models.adapter_types import AppInstance, ProcessInfo
from session_snapshot.models.manifest import AdapterRef, EnvironmentInfo
from session_snapshot.models.results import Reason
from session_snapshot.report.models import SaveStatus
from session_snapshot.store.manifests import ManifestError, ManifestStore
from tests.fakes.fake_adapter import FakeAdapter
from tests.fakes.fake_process_source import FakeProcessSource

PROC = ProcessInfo(pid=42, name="fakeapp")


def make_manager(tmp_path, adapters, procs=(PROC,), bus=None):
    registry = AdapterRegistry()
    for adapter in adapters:
        registry.register(adapter)
    store = ManifestStore(tmp_path / "sessions")
    manager = SessionManager(
        registry,
        store,
        FakeProcessSource(procs),
        bus=bus,
        env_provider=lambda: EnvironmentInfo(session_type="x11"),
    )
    return manager, store


def test_save_captures_and_writes_manifest(tmp_path):
    manager, store = make_manager(tmp_path, [FakeAdapter()])
    report = manager.save("study-setup", "Study Setup")
    assert [o.status for o in report.outcomes] == [SaveStatus.CAPTURED]
    assert report.warnings == []
    manifest = store.load("study-setup")
    assert [a.instance_id for a in manifest.apps] == ["fake-42"]
    assert manifest.session.name == "Study Setup"


def test_failing_adapter_is_recorded_and_others_still_saved(tmp_path):
    bad = FakeAdapter(adapter_id="bad", fail_with=RuntimeError("kaput"))
    good = FakeAdapter(adapter_id="good")
    manager, store = make_manager(tmp_path, [bad, good])
    report = manager.save("study-setup", "Study Setup")
    by_adapter = {o.adapter_id: o for o in report.outcomes}
    assert by_adapter["bad"].status is SaveStatus.FAILED
    assert by_adapter["bad"].reason is Reason.ADAPTER_ERROR
    assert by_adapter["good"].status is SaveStatus.CAPTURED
    assert [a.instance_id for a in store.load("study-setup").apps] == ["good-42"]


def test_excluded_instance_is_not_captured(tmp_path):
    manager, store = make_manager(tmp_path, [FakeAdapter()])
    report = manager.save("study-setup", "Study Setup", exclude={"fake-42"})
    assert [o.status for o in report.outcomes] == [SaveStatus.EXCLUDED]
    assert report.outcomes[0].reason is Reason.EXCLUDED_BY_USER
    assert store.load("study-setup").apps == []


def test_invalid_session_id_or_empty_name_rejected(tmp_path):
    manager, _ = make_manager(tmp_path, [FakeAdapter()])
    with pytest.raises(ManifestError):
        manager.save("../evil", "x")
    with pytest.raises(ManifestError):
        manager.save("study-setup", "   ")


def test_no_apps_still_saves_with_warning(tmp_path):
    manager, store = make_manager(tmp_path, [FakeAdapter()], procs=())
    report = manager.save("study-setup", "Study Setup")
    assert report.outcomes == []
    assert len(report.warnings) == 1
    assert store.list_ids() == ["study-setup"]


class SameIdAdapter(FakeAdapter):
    def detect(self, ctx):
        return [AppInstance(instance_id="same", adapter_id=self.adapter_id, pid=1)]


def test_duplicate_instance_ids_across_adapters(tmp_path):
    manager, store = make_manager(
        tmp_path, [SameIdAdapter(adapter_id="a"), SameIdAdapter(adapter_id="b")]
    )
    report = manager.save("study-setup", "Study Setup")
    assert [o.status for o in report.outcomes] == [SaveStatus.CAPTURED, SaveStatus.FAILED]
    assert report.outcomes[1].reason is Reason.ADAPTER_ERROR
    assert len(store.load("study-setup").apps) == 1


class LiarAdapter(FakeAdapter):
    def capture(self, instance, ctx):
        entry = super().capture(instance, ctx)
        return entry.model_copy(update={"adapter": AdapterRef(id="other", version=1)})


def test_entry_with_wrong_adapter_id_is_rejected(tmp_path):
    manager, store = make_manager(tmp_path, [LiarAdapter(adapter_id="liar")])
    report = manager.save("study-setup", "Study Setup")
    assert report.outcomes[0].status is SaveStatus.FAILED
    assert report.outcomes[0].reason is Reason.ADAPTER_ERROR
    assert store.load("study-setup").apps == []


def test_events_are_emitted_in_order(tmp_path):
    bus = EventBus()
    kinds = []
    bus.subscribe(lambda e: kinds.append(e.kind))
    manager, _ = make_manager(tmp_path, [FakeAdapter()], bus=bus)
    manager.save("study-setup", "Study Setup")
    assert kinds[0] is EventKind.SAVE_STARTED
    assert EventKind.APP_CAPTURED in kinds
    assert kinds[-1] is EventKind.SAVE_FINISHED
