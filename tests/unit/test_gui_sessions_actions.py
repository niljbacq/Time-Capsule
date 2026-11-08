"""Offscreen tests for Sessions page actions (rename, delete)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication  # noqa: E402

from session_snapshot.gui.controllers.sessions_controller import SessionsController  # noqa: E402
from session_snapshot.gui.sessions_page import SessionsPage  # noqa: E402
from session_snapshot.models.summaries import SessionList, SessionSummary  # noqa: E402


def _summary(session_id="study-setup", name="Study Setup"):
    return SessionSummary(
        session_id=session_id,
        name=name,
        description="",
        saved_at=datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc),
        app_count=1,
        adapter_ids=["terminal"],
        desktop="XFCE",
        session_type="x11",
    )


class FakeService:
    def __init__(self, sessions=(), mutation_error=None):
        self.result = SessionList(sessions=list(sessions))
        self.mutation_error = mutation_error
        self.rename_calls = []
        self.delete_calls = []

    def list_sessions(self):
        return self.result

    def rename_session(self, session_id, new_name):
        if self.mutation_error is not None:
            raise self.mutation_error
        self.rename_calls.append((session_id, new_name))

    def delete_session(self, session_id):
        if self.mutation_error is not None:
            raise self.mutation_error
        self.delete_calls.append(session_id)


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_controller_rename_success():
    svc = FakeService(sessions=[_summary()])
    ctrl = SessionsController(svc)
    assert ctrl.rename_session("study-setup", "New Name") is True
    assert svc.rename_calls == [("study-setup", "New Name")]
    assert ctrl.last_error is None


def test_controller_rename_failure_records_error():
    svc = FakeService(sessions=[_summary()], mutation_error=OSError("disk full"))
    ctrl = SessionsController(svc)
    assert ctrl.rename_session("study-setup", "X") is False
    assert ctrl.last_error == "disk full"


def test_controller_delete_success():
    svc = FakeService(sessions=[_summary()])
    ctrl = SessionsController(svc)
    assert ctrl.delete_session("study-setup") is True
    assert svc.delete_calls == ["study-setup"]


def test_controller_delete_failure_records_error():
    svc = FakeService(sessions=[_summary()], mutation_error=OSError("permission denied"))
    ctrl = SessionsController(svc)
    assert ctrl.delete_session("study-setup") is False
    assert ctrl.last_error == "permission denied"


def test_page_rename_session_delegates_and_refreshes(qt_app):
    svc = FakeService(sessions=[_summary()])
    page = SessionsPage(SessionsController(svc))
    assert page.rename_session("study-setup", "New") is True
    assert svc.rename_calls == [("study-setup", "New")]


def test_page_delete_session_delegates_and_refreshes(qt_app):
    svc = FakeService(sessions=[_summary(), _summary("b", "B")])
    page = SessionsPage(SessionsController(svc))
    assert page.delete_session("study-setup") is True
    assert svc.delete_calls == ["study-setup"]


def test_action_buttons_disabled_without_selection(qt_app):
    page = SessionsPage(SessionsController(FakeService(sessions=[_summary()])))
    assert page.rename_button.isEnabled() is False
    assert page.delete_button.isEnabled() is False


def test_action_buttons_enable_on_selection(qt_app):
    page = SessionsPage(SessionsController(FakeService(sessions=[_summary()])))
    page.table.selectRow(0)
    qt_app.processEvents()
    assert page.rename_button.isEnabled() is True
    assert page.delete_button.isEnabled() is True