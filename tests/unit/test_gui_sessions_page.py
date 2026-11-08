"""Offscreen tests for the Sessions list view widget."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication  # noqa: E402

from session_snapshot.gui.controllers.sessions_controller import SessionsController  # noqa: E402
from session_snapshot.gui.sessions_page import SessionsPage, format_saved_at  # noqa: E402
from session_snapshot.models.summaries import (  # noqa: E402
    SessionList,
    SessionProblem,
    SessionSummary,
)


def _summary(session_id="study-setup", name="Study Setup", apps=2, desktop="XFCE"):
    return SessionSummary(
        session_id=session_id,
        name=name,
        description="",
        saved_at=datetime(2026, 11, 5, 10, 30, tzinfo=timezone.utc),
        app_count=apps,
        adapter_ids=["terminal"],
        desktop=desktop,
        session_type="x11",
    )


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else SessionList()
        self.error = error

    def list_sessions(self):
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def make_page(result=None, error=None):
    controller = SessionsController(FakeService(result, error))
    return SessionsPage(controller), controller


def test_title_label_reads_sessions(qt_app):
    page, _ = make_page()
    assert page.title_label.text() == "Sessions"


def test_table_headers_are_the_four_columns(qt_app):
    page, _ = make_page()
    headers = [page.table.horizontalHeaderItem(i).text() for i in range(4)]
    assert headers == ["Name", "Saved", "Apps", "Environment"]


def test_populates_rows_from_controller(qt_app):
    page, _ = make_page(SessionList(sessions=[_summary(), _summary("dev", "Dev", 5)]))
    assert page.row_count() == 2
    assert page.session_id_at(0) == "study-setup"
    assert page.session_id_at(1) == "dev"


def test_row_text_contains_expected_values(qt_app):
    page, _ = make_page(SessionList(sessions=[_summary(apps=3, desktop="XFCE")]))
    assert page.table.item(0, 0).text() == "Study Setup"
    assert page.table.item(0, 1).text() == format_saved_at(
        datetime(2026, 11, 5, 10, 30, tzinfo=timezone.utc)
    )
    assert page.table.item(0, 2).text() == "3"
    assert page.table.item(0, 3).text() == "XFCE"


def test_environment_falls_back_when_desktop_missing(qt_app):
    page, _ = make_page(
        SessionList(sessions=[_summary(desktop=None)])
    )
    assert page.table.item(0, 3).text() == "x11"


def test_empty_state_visible_and_table_hidden(qt_app):
    page, _ = make_page(SessionList())
    assert page.empty_label.isVisibleTo(page) is True
    assert page.table.isVisibleTo(page) is False
    assert page.row_count() == 0


def test_nonempty_hides_empty_state_and_shows_table(qt_app):
    page, _ = make_page(SessionList(sessions=[_summary()]))
    assert page.empty_label.isVisibleTo(page) is False
    assert page.table.isVisibleTo(page) is True


def test_summary_label_counts_sessions(qt_app):
    page, _ = make_page(SessionList(sessions=[_summary()]))
    assert page.summary_label.text() == "1 saved session"
    page2, _ = make_page(SessionList(sessions=[_summary(), _summary("b", "B")]))
    assert page2.summary_label.text() == "2 saved sessions"


def test_error_state_shows_label_and_hides_table(qt_app):
    page, _ = make_page(error=RuntimeError("disk gone"))
    assert page.error_label.isVisibleTo(page) is True
    assert "disk gone" in page.error_label.text()
    assert page.table.isVisibleTo(page) is False
    assert page.summary_label.text() == ""


def test_problems_label_lists_unreadable_sessions(qt_app):
    problem = SessionProblem(session_id="broken", message="bad manifest")
    page, _ = make_page(SessionList(sessions=[_summary()], problems=[problem]))
    assert page.problems_label.isVisibleTo(page) is True
    assert "broken" in page.problems_label.text()


def test_refresh_clears_error_after_recovery(qt_app):
    service = FakeService(error=RuntimeError("temporary"))
    page = SessionsPage(SessionsController(service))
    assert page.error_label.isVisibleTo(page) is True

    service.error = None
    service.result = SessionList(sessions=[_summary()])
    page.refresh()
    assert page.error_label.isVisibleTo(page) is False
    assert page.row_count() == 1


def test_no_selection_returns_none(qt_app):
    page, _ = make_page(SessionList(sessions=[_summary()]))
    assert page.selected_session_id() is None