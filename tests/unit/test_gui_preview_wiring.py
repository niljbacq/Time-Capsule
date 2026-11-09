"""Offscreen tests for Preview/Restore wiring (7.4b-1b)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timezone

import pytest

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication

from session_snapshot.gui import dashboard_page as dp_mod
from session_snapshot.gui import sessions_page as sp_mod
from session_snapshot.gui.controllers.sessions_controller import SessionsController
from session_snapshot.gui.dashboard_page import DashboardPage
from session_snapshot.gui.sessions_page import SessionsPage
from session_snapshot.models.adapter_types import ActionKind
from session_snapshot.models.results import Reason
from session_snapshot.models.summaries import SessionList, SessionSummary
from session_snapshot.report.models import AppPreview, RestorePreview


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


def _preview(session_id="study-setup", name="Study Setup"):
    return RestorePreview(
        session_id=session_id,
        session_name=name,
        apps=[
            AppPreview(
                instance_id="t1",
                adapter_id="terminal",
                action=ActionKind.LAUNCH,
                reason=Reason.OK,
                message="ok",
            )
        ],
        warnings=[],
    )


class FakeService:
    def __init__(self, sessions=(), preview=None, preview_error=None):
        self._sessions = list(sessions)
        self._preview = preview
        self._preview_error = preview_error

    def list_sessions(self):
        return SessionList(sessions=self._sessions)

    def preview(self, session_id):
        if self._preview_error is not None:
            raise self._preview_error
        return self._preview

    def rename_session(self, sid, name):
        return None

    def delete_session(self, sid):
        return None

    def save(self, sid, name, description=""):
        return None


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_sessions_preview_button_exists(qt_app):
    page = SessionsPage(SessionsController(FakeService()))
    assert hasattr(page, "preview_button")
    assert page.preview_button.text() == "Preview\u2026"


def test_sessions_preview_disabled_without_selection(qt_app):
    page = SessionsPage(SessionsController(FakeService(sessions=[_summary()])))
    assert page.preview_button.isEnabled() is False


def test_sessions_preview_enabled_on_selection(qt_app):
    page = SessionsPage(SessionsController(FakeService(sessions=[_summary()])))
    page.table.selectRow(0)
    qt_app.processEvents()
    assert page.preview_button.isEnabled() is True


def test_sessions_preview_opens_dialog(qt_app, monkeypatch):
    received = []

    class FakeDialog:
        def __init__(self, preview, parent=None):
            received.append(preview.session_id)

        def exec(self):
            return 0

    monkeypatch.setattr(sp_mod, "RestorePreviewDialog", FakeDialog)
    page = SessionsPage(
        SessionsController(FakeService(sessions=[_summary()], preview=_preview()))
    )
    page.table.selectRow(0)
    qt_app.processEvents()
    page.preview_button.click()
    assert received == ["study-setup"]


def test_sessions_preview_error_shows_label(qt_app):
    page = SessionsPage(
        SessionsController(
            FakeService(sessions=[_summary()], preview_error=OSError("manifest broken"))
        )
    )
    page.table.selectRow(0)
    qt_app.processEvents()
    page.preview_button.click()
    assert "manifest broken" in page.error_label.text()
    assert page.error_label.isVisibleTo(page) is True


def test_dashboard_restore_empty_shows_error(qt_app):
    page = DashboardPage(SessionsController(FakeService()))
    page._on_restore_clicked()
    assert "No saved sessions" in page.error_label.text()


def test_dashboard_restore_opens_picker_and_preview(qt_app, monkeypatch):
    received = []

    class FakeDialog:
        def __init__(self, preview, parent=None):
            received.append(preview.session_id)

        def exec(self):
            return 0

    monkeypatch.setattr(dp_mod, "RestorePreviewDialog", FakeDialog)
    monkeypatch.setattr(
        dp_mod.QInputDialog,
        "getItem",
        staticmethod(lambda *a, **kw: ("Study Setup (study-setup)", True)),
    )
    page = DashboardPage(
        SessionsController(FakeService(sessions=[_summary()], preview=_preview()))
    )
    page._on_restore_clicked()
    assert received == ["study-setup"]


def test_dashboard_restore_cancel_does_not_preview(qt_app, monkeypatch):
    received = []

    class FakeDialog:
        def __init__(self, preview, parent=None):
            received.append(preview.session_id)

        def exec(self):
            return 0

    monkeypatch.setattr(dp_mod, "RestorePreviewDialog", FakeDialog)
    monkeypatch.setattr(
        dp_mod.QInputDialog,
        "getItem",
        staticmethod(lambda *a, **kw: ("", False)),
    )
    page = DashboardPage(
        SessionsController(FakeService(sessions=[_summary()], preview=_preview()))
    )
    page._on_restore_clicked()
    assert received == []
