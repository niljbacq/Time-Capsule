"""Tests for the Sessions library controller. No Qt, no real service."""

from datetime import datetime, timezone

from session_snapshot.gui.controllers.sessions_controller import SessionsController
from session_snapshot.models.summaries import (
    SessionList,
    SessionProblem,
    SessionSummary,
)


def _summary(session_id="study-setup", name="Study Setup", apps=2):
    return SessionSummary(
        session_id=session_id,
        name=name,
        description="",
        saved_at=datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
        app_count=apps,
        adapter_ids=["terminal", "firefox"],
        desktop="XFCE",
        session_type="x11",
    )


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else SessionList()
        self.error = error
        self.calls = 0

    def list_sessions(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class FlakyService:
    def __init__(self):
        self.calls = 0

    def list_sessions(self):
        self.calls += 1
        if self.calls == 1:
            return SessionList(sessions=[_summary()])
        raise OSError("permission denied")


def test_refresh_returns_service_result():
    summary = _summary()
    service = FakeService(SessionList(sessions=[summary]))
    controller = SessionsController(service)

    result = controller.refresh()

    assert [s.session_id for s in result.sessions] == ["study-setup"]
    assert service.calls == 1


def test_refresh_caches_sessions_and_problems():
    problem = SessionProblem(session_id="bad", message="manifest invalid")
    service = FakeService(SessionList(sessions=[_summary()], problems=[problem]))
    controller = SessionsController(service)

    controller.refresh()

    assert len(controller.sessions) == 1
    assert controller.problems[0].session_id == "bad"


def test_before_refresh_controller_is_unloaded():
    controller = SessionsController(FakeService())
    assert controller.loaded is False
    assert controller.is_empty is False


def test_empty_list_after_refresh_marks_is_empty():
    controller = SessionsController(FakeService(SessionList()))
    controller.refresh()
    assert controller.loaded is True
    assert controller.is_empty is True


def test_nonempty_list_is_not_empty():
    controller = SessionsController(FakeService(SessionList(sessions=[_summary()])))
    controller.refresh()
    assert controller.is_empty is False


def test_service_exception_is_captured_not_raised():
    controller = SessionsController(FakeService(error=RuntimeError("disk gone")))
    result = controller.refresh()
    assert result.sessions == []
    assert controller.last_error == "disk gone"
    assert controller.loaded is True


def test_second_failing_refresh_clears_previous_sessions():
    controller = SessionsController(FlakyService())
    controller.refresh()
    assert controller.sessions

    controller.refresh()
    assert controller.sessions == []
    assert controller.last_error == "permission denied"


def test_successful_refresh_clears_previous_error():
    service = FakeService(error=RuntimeError("boom"))
    controller = SessionsController(service)
    controller.refresh()
    assert controller.last_error == "boom"

    service.error = None
    service.result = SessionList(sessions=[_summary()])
    controller.refresh()
    assert controller.last_error is None


def test_returned_lists_are_copies():
    controller = SessionsController(FakeService(SessionList(sessions=[_summary()])))
    controller.refresh()
    copy = controller.sessions
    copy.clear()
    assert len(controller.sessions) == 1


def test_service_returning_none_is_treated_as_failure():
    class NoneService:
        def list_sessions(self):
            return None

    controller = SessionsController(NoneService())
    result = controller.refresh()
    assert result.sessions == []
    assert controller.last_error is not None
