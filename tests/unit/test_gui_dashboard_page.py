"""Offscreen tests for the Dashboard page."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timezone

import pytest

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication

from session_snapshot.gui.controllers.sessions_controller import SessionsController
from session_snapshot.gui.dashboard_page import DashboardPage
from session_snapshot.models.summaries import SessionList, SessionSummary
from session_snapshot.report.models import SaveReport, SaveStatus, AppSaveOutcome
from session_snapshot.models.results import Reason
from datetime import datetime, timezone


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
    def __init__(self, sessions=()):
        self.result = SessionList(sessions=list(sessions))
        self.save_calls = []

    def list_sessions(self):
        return self.result

    def save(self, session_id, name, description=""):
        self.save_calls.append((session_id, name, description))
        return SaveReport(
            session_id=session_id,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            outcomes=[
                AppSaveOutcome(
                    instance_id="fake-1",
                    adapter_id="fake",
                    status=SaveStatus.CAPTURED,
                    reason=Reason.OK,
                    message="Captured",
                )
            ],
            warnings=[],
            manifest_path="/tmp/test.json",
        )


class BadService:
    def save(self, session_id, name, description=""):
        raise OSError("disk full")


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_dashboard_has_save_button(qt_app):
    from session_snapshot.gui.controllers.sessions_controller import SessionsController
    from session_snapshot.gui.dashboard_page import DashboardPage

    ctrl = SessionsController(FakeService())
    page = DashboardPage(ctrl)
    assert page.save_button.text() == "Save current desktop…"


def test_save_button_emits_signal(qt_app):
    from session_snapshot.gui.controllers.sessions_controller import SessionsController
    from session_snapshot.gui.dashboard_page import DashboardPage

    ctrl = SessionsController(FakeService())
    page = DashboardPage(ctrl)

    received = []
    page.session_saved.connect(received.append)

    page.save_session("Test Session")

    assert len(received) == 1
    assert received[0] == "test-session"


def test_save_session_uses_controller(qt_app):
    from session_snapshot.gui.controllers.sessions_controller import SessionsController
    from session_snapshot.gui.dashboard_page import DashboardPage

    ctrl = SessionsController(FakeService())
    page = DashboardPage(ctrl)

    report = page.save_session("Test")
    assert report is not None
    assert report.session_id == "test"
    assert "Test" in page.status_label.text()
    assert page.error_label.text() == ""


def test_save_session_records_controller_error(qt_app):
    from session_snapshot.gui.controllers.sessions_controller import SessionsController
    from session_snapshot.gui.dashboard_page import DashboardPage

    ctrl = SessionsController(BadService())
    page = DashboardPage(ctrl)

    report = page.save_session("Test")
    assert report is None
    assert "disk full" in page.error_label.text()
    assert page.status_label.text() == ""


def test_session_id_from_name_sanitizes():
    from session_snapshot.gui.dashboard_page import session_id_from_name

    assert session_id_from_name("Study Setup") == "study-setup"
    assert session_id_from_name("My Session 2") == "my-session-2"
    assert session_id_from_name("!!!") == "session"
    assert session_id_from_name("") == "session"
    assert session_id_from_name("  spaces  ") == "spaces"
