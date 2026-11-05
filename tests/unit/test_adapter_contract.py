import pytest

from session_snapshot.adapters.base import SessionAdapter
from session_snapshot.models.adapter_types import (
    ActionKind,
    CaptureContext,
    DiscoveryContext,
    ProcessInfo,
    RestoreContext,
)
from session_snapshot.models.results import Status
from tests.fakes.fake_adapter import FakeAdapter


def test_incomplete_adapter_cannot_be_instantiated():
    class Incomplete(SessionAdapter):
        adapter_id = "incomplete"
        version = 1
        compatibility_class = 2

    with pytest.raises(TypeError):
        Incomplete()


def test_full_lifecycle_with_fake_adapter():
    adapter = FakeAdapter()
    procs = (ProcessInfo(pid=42, name="fakeapp"), ProcessInfo(pid=43, name="other"))

    instances = adapter.detect(DiscoveryContext(processes=procs))
    assert [i.pid for i in instances] == [42]

    snapshot = adapter.capture(instances[0], CaptureContext(processes=procs))
    assert snapshot.state["cwd"] == "/tmp"

    ctx = RestoreContext()
    plan = adapter.plan_restore(snapshot, ctx)
    assert plan.action is ActionKind.LAUNCH

    handle = adapter.restore(snapshot, plan, ctx)
    result = adapter.verify(snapshot, handle, ctx)
    assert result.status is Status.RESTORED
