from session_snapshot.models.results import OpResult, Reason, Status


def test_restored_result():
    r = OpResult.restored("cwd restored", cwd="/tmp")
    assert r.status is Status.RESTORED
    assert r.reason is Reason.OK
    assert r.details["cwd"] == "/tmp"


def test_failed_result_carries_reason():
    r = OpResult.failed(Reason.TIMEOUT, "window never appeared")
    assert r.status is Status.FAILED
    assert r.reason is Reason.TIMEOUT


def test_skipped_result():
    r = OpResult.skipped(Reason.UNSUPPORTED, "no adapter")
    assert r.status is Status.SKIPPED