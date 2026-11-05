import pytest

from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.events import EventBus, EventKind
from session_snapshot.core.manager import SessionManager
from session_snapshot.core.restore import RestoreEngine
from session_snapshot.models.adapter_types import ActionKind, ProcessInfo, RestorePlan
from session_snapshot.models.manifest import EnvironmentInfo
from session_snapshot.models.results import OpResult, Reason, Status
from session_snapshot.store.manifests import ManifestError, ManifestStore
from tests.fakes.fake_adapter import FakeAdapter
from tests.fakes.fake_process_source import FakeProcessSource

PROC = ProcessInfo(pid=42, name="fakeapp")


def x11_env():
    return EnvironmentInfo(session_type="x11")


def save_session(tmp_path, adapters):
    registry = AdapterRegistry()
    for adapter in adapters:
        registry.register(adapter)
    store = ManifestStore(tmp_path / "sessions")
    SessionManager(registry, store, FakeProcessSource([PROC]), env_provider=x11_env).save(
        "study-setup", "Study Setup"
    )
    return store


def make_engine(store, adapters, bus=None, env=x11_env):
    registry = AdapterRegistry()
    for adapter in adapters:
        registry.register(adapter)
    return RestoreEngine(registry, store, FakeProcessSource(()), bus=bus, env_provider=env)


def by_id(report):
    return {o.instance_id: o for o in report.outcomes}


def test_verified_app_is_restored(tmp_path):
    adapters = [FakeAdapter()]
    store = save_session(tmp_path, adapters)
    report = make_engine(store, adapters).restore("study-setup")
    outcome = report.outcomes[0]
    assert outcome.status is Status.RESTORED
    assert outcome.action is ActionKind.LAUNCH
    assert report.counts() == {"restored": 1, "partial": 0, "failed": 0, "skipped": 0}
    assert adapters[0].calls == ["plan", "restore", "verify"]


def test_partial_verification_is_reported_as_partial(tmp_path):
    adapters = [FakeAdapter(verify_result=OpResult.partial(Reason.VERIFY_MISMATCH, "window not placed"))]
    store = save_session(tmp_path, adapters)
    report = make_engine(store, adapters).restore("study-setup")
    assert report.outcomes[0].status is Status.PARTIAL
    assert report.outcomes[0].reason is Reason.VERIFY_MISMATCH


def test_restore_error_is_failed_and_others_continue(tmp_path):
    bad = FakeAdapter(adapter_id="bad", restore_error=RuntimeError("kaput"))
    good = FakeAdapter(adapter_id="good")
    store = save_session(tmp_path, [bad, good])
    report = make_engine(store, [bad, good]).restore("study-setup")
    outcomes = by_id(report)
    assert outcomes["bad-42"].status is Status.FAILED
    assert outcomes["bad-42"].reason is Reason.ADAPTER_ERROR
    assert outcomes["good-42"].status is Status.RESTORED
    assert "verify" not in bad.calls


def test_failed_verification_is_never_reported_as_restored(tmp_path):
    adapters = [FakeAdapter(verify_result=OpResult.failed(Reason.VERIFY_MISMATCH, "state not found"))]
    store = save_session(tmp_path, adapters)
    report = make_engine(store, adapters).restore("study-setup")
    assert report.outcomes[0].status is Status.FAILED
    assert report.outcomes[0].reason is Reason.VERIFY_MISMATCH
    assert "verify" in adapters[0].calls


def test_verify_crash_is_failed(tmp_path):
    adapters = [FakeAdapter(verify_error=RuntimeError("boom"))]
    store = save_session(tmp_path, adapters)
    report = make_engine(store, adapters).restore("study-setup")
    assert report.outcomes[0].status is Status.FAILED
    assert report.outcomes[0].reason is Reason.ADAPTER_ERROR


def test_skip_plan_does_not_call_restore(tmp_path):
    plan = RestorePlan(
        action=ActionKind.SKIP, reason=Reason.ALREADY_RUNNING, message="already running"
    )
    adapters = [FakeAdapter(plan=plan)]
    store = save_session(tmp_path, adapters)
    report = make_engine(store, adapters).restore("study-setup")
    assert report.outcomes[0].status is Status.SKIPPED
    assert report.outcomes[0].reason is Reason.ALREADY_RUNNING
    assert adapters[0].calls == ["plan"]


def test_excluded_app_is_skipped_and_untouched(tmp_path):
    adapters = [FakeAdapter()]
    store = save_session(tmp_path, adapters)
    report = make_engine(store, adapters).restore("study-setup", exclude={"fake-42"})
    assert report.outcomes[0].status is Status.SKIPPED
    assert report.outcomes[0].reason is Reason.EXCLUDED_BY_USER
    assert adapters[0].calls == []


def test_missing_adapter_is_skipped(tmp_path):
    store = save_session(tmp_path, [FakeAdapter()])
    report = make_engine(store, []).restore("study-setup")
    assert report.outcomes[0].status is Status.SKIPPED
    assert report.outcomes[0].reason is Reason.NOT_INSTALLED


def test_manifest_from_newer_adapter_version_is_skipped(tmp_path):
    saved_with = FakeAdapter()
    saved_with.version = 2
    store = save_session(tmp_path, [saved_with])
    installed = FakeAdapter()
    report = make_engine(store, [installed]).restore("study-setup")
    assert report.outcomes[0].status is Status.SKIPPED
    assert report.outcomes[0].reason is Reason.UNSUPPORTED
    assert installed.calls == []


def test_timeout_is_reported(tmp_path):
    adapters = [FakeAdapter(restore_delay=0.5)]
    store = save_session(tmp_path, adapters)
    report = make_engine(store, adapters).restore("study-setup", timeout_seconds=0.1)
    assert report.outcomes[0].status is Status.FAILED
    assert report.outcomes[0].reason is Reason.TIMEOUT


def test_one_worker_blocked_by_timeout_fails_queued_app(tmp_path):
    slow = FakeAdapter(adapter_id="a", restore_delay=0.5)
    quick = FakeAdapter(adapter_id="b")
    store = save_session(tmp_path, [slow, quick])
    report = make_engine(store, [slow, quick]).restore(
        "study-setup", timeout_seconds=0.1, concurrency=1
    )
    outcomes = by_id(report)
    assert outcomes["a-42"].reason is Reason.TIMEOUT
    assert outcomes["b-42"].status is Status.FAILED
    assert outcomes["b-42"].reason is Reason.TIMEOUT
    assert "not started" in outcomes["b-42"].message
    assert "restore" not in quick.calls


def test_two_workers_let_other_app_finish_despite_timeout(tmp_path):
    slow = FakeAdapter(adapter_id="a", restore_delay=0.5)
    quick = FakeAdapter(adapter_id="b")
    store = save_session(tmp_path, [slow, quick])
    report = make_engine(store, [slow, quick]).restore(
        "study-setup", timeout_seconds=0.1, concurrency=2
    )
    outcomes = by_id(report)
    assert outcomes["a-42"].reason is Reason.TIMEOUT
    assert outcomes["b-42"].status is Status.RESTORED


def test_preview_plans_without_restoring(tmp_path):
    adapters = [FakeAdapter()]
    store = save_session(tmp_path, adapters)
    preview = make_engine(store, adapters).preview("study-setup")
    assert preview.session_name == "Study Setup"
    assert preview.apps[0].action is ActionKind.LAUNCH
    assert adapters[0].calls == ["plan"]


def test_duplicate_policy_reaches_the_adapter(tmp_path):
    adapters = [FakeAdapter()]
    store = save_session(tmp_path, adapters)
    engine = make_engine(store, adapters)
    engine.restore("study-setup", duplicate_policy="skip_if_running")
    assert adapters[0].last_ctx.duplicate_policy == "skip_if_running"
    engine.restore("study-setup")
    assert adapters[0].last_ctx.duplicate_policy == "reuse_existing"


def test_session_type_mismatch_adds_warning(tmp_path):
    adapters = [FakeAdapter()]
    store = save_session(tmp_path, adapters)
    engine = make_engine(store, adapters, env=lambda: EnvironmentInfo(session_type="wayland"))
    report = engine.restore("study-setup")
    assert any("wayland" in w for w in report.warnings)


def test_unknown_session_raises_manifest_error(tmp_path):
    engine = make_engine(ManifestStore(tmp_path / "sessions"), [])
    with pytest.raises(ManifestError):
        engine.restore("nope")


def test_invalid_arguments_rejected(tmp_path):
    adapters = [FakeAdapter()]
    store = save_session(tmp_path, adapters)
    engine = make_engine(store, adapters)
    with pytest.raises(ValueError):
        engine.restore("study-setup", concurrency=0)
    with pytest.raises(ValueError):
        engine.restore("study-setup", timeout_seconds=0)
    with pytest.raises(ValueError):
        engine.restore("study-setup", duplicate_policy="bogus")


def test_events_are_emitted_in_order(tmp_path):
    adapters = [FakeAdapter()]
    store = save_session(tmp_path, adapters)
    bus = EventBus()
    kinds = []
    bus.subscribe(lambda e: kinds.append(e.kind))
    make_engine(store, adapters, bus=bus).restore("study-setup")
    assert kinds[0] is EventKind.RESTORE_STARTED
    assert EventKind.APP_RESTORING in kinds
    assert EventKind.APP_RESULT in kinds
    assert kinds[-1] is EventKind.RESTORE_FINISHED


def test_outcomes_follow_manifest_order_and_counts(tmp_path):
    a = FakeAdapter(adapter_id="a")
    b = FakeAdapter(adapter_id="b")
    store = save_session(tmp_path, [a, b])
    report = make_engine(store, [a, b]).restore("study-setup")
    assert [o.instance_id for o in report.outcomes] == ["a-42", "b-42"]
    assert report.counts()["restored"] == 2
