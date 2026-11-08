"""Offscreen tests for the GUI main window shell.

Every SettingsStore points at tmp_path: these tests must never read or write
the user's real GUI configuration.
"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication

from session_snapshot.gui import navigation, theme
from session_snapshot.gui.main_window import MainWindow, system_is_dark
from session_snapshot.gui.settings import GuiSettings, SettingsStore


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def store(tmp_path):
    return SettingsStore(tmp_path / "gui.json")


@pytest.fixture
def window(qt_app, store):
    win = MainWindow(store)
    yield win
    win.close()


def test_starts_on_dashboard_with_five_pages(window):
    assert window.current_page_id() == "dashboard"
    assert window.stack.count() == 5
    for page_id in navigation.page_ids():
        assert window.page(page_id) is not None


def test_show_page_switches_stack_and_sidebar(window):
    assert window.show_page("sessions") is True
    assert window.current_page_id() == "sessions"
    assert window.stack.currentIndex() == navigation.page_index("sessions")
    assert window.state.active == "sessions"


def test_unknown_page_is_ignored(window):
    assert window.show_page("nowhere") is False
    assert window.current_page_id() == "dashboard"
    assert window.stack.currentIndex() == 0


def test_nav_button_click_switches_page(window):
    window.sidebar.button("activity").click()
    assert window.current_page_id() == "activity"
    assert window.stack.currentIndex() == navigation.page_index("activity")


def test_collapse_button_syncs_state_and_settings(window):
    assert window.state.collapsed is False
    window.sidebar.collapse_button().click()
    assert window.state.collapsed is True
    assert window.current_settings().sidebar_collapsed is True
    window.sidebar.collapse_button().click()
    assert window.state.collapsed is False


def test_stored_collapsed_state_applied_on_start(qt_app, tmp_path):
    store = SettingsStore(tmp_path / "gui.json")
    store.save(GuiSettings(sidebar_collapsed=True))
    win = MainWindow(store)
    try:
        assert win.state.collapsed is True
    finally:
        win.close()


def test_theme_preference_applied_to_stylesheet(window):
    light_sheet = window.styleSheet()
    assert "EFF6FF" in light_sheet
    palette = window.apply_theme("dark")
    assert palette is theme.DARK
    assert window.current_settings().theme == "dark"
    assert window.styleSheet() != light_sheet
    assert "1E3A5F" in window.styleSheet()


def test_geometry_restored_from_settings(qt_app, tmp_path):
    store = SettingsStore(tmp_path / "gui.json")
    store.save(
        GuiSettings(
            window_width=1000,
            window_height=700,
            window_x=50,
            window_y=60,
            window_maximized=False,
        )
    )
    win = MainWindow(store)
    try:
        assert (win.width(), win.height()) == (1000, 700)
        assert (win.pos().x(), win.pos().y()) == (50, 60)
    finally:
        win.close()


def test_current_settings_reflects_live_geometry(window):
    window.resize(900, 600)
    window.move(10, 20)
    settings = window.current_settings()
    assert (settings.window_width, settings.window_height) == (900, 600)
    assert (settings.window_x, settings.window_y) == (10, 20)


def test_close_writes_settings_to_given_store(qt_app, tmp_path):
    path = tmp_path / "gui.json"
    win = MainWindow(SettingsStore(path))
    win.resize(880, 620)
    win.close()
    assert win.save_error is None
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["window_width"] == 880
    assert data["window_height"] == 620


def test_close_records_save_error_instead_of_raising(qt_app, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    win = MainWindow(SettingsStore(blocker / "gui.json"))
    try:
        assert isinstance(win.save_error, OSError) is False
        win.close()
        assert isinstance(win.save_error, OSError)
    finally:
        win.close()


def test_close_keeps_theme_preference(qt_app, tmp_path):
    path = tmp_path / "gui.json"
    win = MainWindow(SettingsStore(path))
    win.apply_theme("dark")
    win.close()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"


def test_system_is_dark_returns_bool(qt_app):
    from session_snapshot.gui.main_window import system_is_dark
    assert isinstance(system_is_dark(), bool)
