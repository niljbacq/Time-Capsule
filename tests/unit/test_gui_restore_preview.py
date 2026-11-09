"""Offscreen tests for the restore preview dialog and controller.preview()."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication

from session_snapshot.gui.controllers.sessions_controller import SessionsController
from session_snapshot.gui.restore_preview_dialog import RestorePreviewDialog
from session_snapshot.models.adapter_types import ActionKind
from session_snapshot.models.results import Reason
from session_snapshot.report.models import AppPreview, RestorePreview


def _preview(name="Study Setup", apps=None, warnings=None):
    return RestorePreview(
        session_id="study-setup",
        session_name=name,
        apps=apps or [],
        warnings=warnings or [],
    )


def _app(instance_id, action, message="", missing=None, unavailable=None):
    return AppPreview(
        instance_id=instance_id,
        adapter_id="terminal",
        action=action,
        reason=Reason.OK,
        message=message,
        missing_dependencies=missing or [],
        unavailable_paths=unavailable or [],
    )


class FakeService:
    def __init__(self, preview=None, error=None):
        self._preview = preview
        self._error = error

    def preview(self, session_id):
        if self._error is not None:
            raise self._error
        return self._preview


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_controller_preview_returns_data():
    expected = _preview()
    ctrl = SessionsController(FakeService(preview=expected))
    assert ctrl.preview("study-setup") is expected
    assert ctrl.last_error is None


def test_controller_preview_failure_records_error():
    ctrl = SessionsController(FakeService(error=OSError("manifest missing")))
    assert ctrl.preview("study-setup") is None
    assert ctrl.last_error == "manifest missing"


def test_dialog_title_contains_session_name(qt_app):
    dlg = RestorePreviewDialog(_preview(name="Evening Work"))
    assert "Evening Work" in dlg.title_label.text()


def test_dialog_shows_launch_and_skip_groups(qt_app):
    apps = [
        _app("t1", ActionKind.LAUNCH, "Launching terminal"),
        _app("f1", ActionKind.SKIP, "Firefox startup page unset"),
    ]
    dlg = RestorePreviewDialog(_preview(apps=apps))
    text = dlg.groups_text()
    assert "Will launch (1)" in text
    assert "Will be skipped (1)" in text
    assert "Launching terminal" in text


def test_dialog_hides_empty_groups(qt_app):
    apps = [_app("t1", ActionKind.LAUNCH, "ok")]
    dlg = RestorePreviewDialog(_preview(apps=apps))
    text = dlg.groups_text()
    assert "Will launch" in text
    assert "Will reconnect" not in text
    assert "Already running" not in text
    assert "Will be skipped" not in text


def test_dialog_shows_warnings_or_hides_label(qt_app):
    dlg = RestorePreviewDialog(_preview(warnings=["terminal shares owner pid"]))
    assert "shares owner pid" in dlg.warnings_text()
    dlg2 = RestorePreviewDialog(_preview())
    assert dlg2.warnings_text() == ""
    assert dlg2.warnings_label.isVisibleTo(dlg2) is False


def test_dialog_shows_missing_dependencies_and_paths(qt_app):
    apps = [
        _app(
            "t1",
            ActionKind.SKIP,
            "cannot reopen",
            missing=["tmux"],
            unavailable=["/home/x/foo"],
        )
    ]
    dlg = RestorePreviewDialog(_preview(apps=apps))
    text = dlg.groups_text()
    assert "missing: tmux" in text
    assert "unavailable: /home/x/foo" in text


def test_restore_button_is_disabled_with_tooltip(qt_app):
    dlg = RestorePreviewDialog(_preview())
    assert dlg.restore_button.isEnabled() is False
    assert "sessionctl" in dlg.restore_button.toolTip()
