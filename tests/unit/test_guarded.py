from session_snapshot.adapters.base import AdapterError
from session_snapshot.adapters.isolation import guarded
from session_snapshot.models.adapter_types import CaptureContext, ProcessInfo
from session_snapshot.models.results import Reason, Status
from tests.fakes.fake_adapter import FakeAdapter


def test_success_returns_value():
    value, err = guarded("fake", "add", lambda a, b: a + b, 1, 2)
    assert value == 3
    assert err is None


def test_adapter_error_keeps_its_reason():
    def boom():
        raise AdapterError(Reason.PATH_MISSING, "project folder is gone", path="/x")

    value, err = guarded("fake", "restore", boom)
    assert value is None
    assert err.status is Status.FAILED
    assert err.reason is Reason.PATH_MISSING
    assert err.details["path"] == "/x"
    assert err.details["adapter_id"] == "fake"


def test_unexpected_exception_becomes_adapter_error():
    def boom():
        raise RuntimeError("kaput")

    value, err = guarded("fake", "capture", boom)
    assert value is None
    assert err.status is Status.FAILED
    assert err.reason is Reason.ADAPTER_ERROR
    assert "RuntimeError" in err.message


def test_one_failing_adapter_does_not_stop_the_others():
    good = FakeAdapter(adapter_id="good")
    bad = FakeAdapter(adapter_id="bad", fail_with=RuntimeError("kaput"))
    proc = ProcessInfo(pid=1, name="fakeapp")
    outcomes = {}
    for adapter in (bad, good):
        inst = adapter.detect(
            __import__("session_snapshot.models.adapter_types", fromlist=["x"]).DiscoveryContext(
                processes=(proc,)
            )
        )[0]
        value, err = guarded(
            adapter.adapter_id, "capture", adapter.capture, inst, CaptureContext()
        )
        outcomes[adapter.adapter_id] = (value, err)
    assert outcomes["bad"][1].reason is Reason.ADAPTER_ERROR
    assert outcomes["good"][0] is not None
    assert outcomes["good"][1] is None
