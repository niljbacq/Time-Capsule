import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from dataclasses import replace

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication  # noqa: E402

from session_snapshot.gui import navigation, theme  # noqa: E402
from session_snapshot.gui.main_window import MainWindow  # noqa: E402
from session_snapshot.gui.settings import SettingsStore, GuiSettings  # noqa: E402


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_window_created_with_five_pages(qt_app):
    w = MainWindow()
    assert w.current_page_id() == "dashboard"
    assert len(w._pages) == 5
    assert set(w._pages.keys()) == set(navigation.page_ids())


def test_show_page_switches_stack(qt_app):
    w = MainWindow()
    w.show_page("sessions")
    assert w.current_page_id() == "sessions"
    assert w._stack.currentIndex() == 1


def test_unknown_page_returns_false(qt_app):
    w = MainWindow()
    assert w.show_page("nowhere") is False


def test_sidebar_collapse_signal_syncs_state(qt_app):
    w = MainWindow()
    assert w._state.collapsed is False
    w._sidebar.collapse_button().click()
    assert w._state.collapsed is True


def test_theme_preference_is_stored_and_applied(qt_app):
    w = MainWindow()
    pal = w.apply_theme("dark")
    assert w._settings.theme == "dark"
    assert w._sidebar._palette is theme.DARK
    assert "1E3A5F" in w.styleSheet()


def test_window_geometry_is_restored_from_settings(qt_app):
    from session_snapshot.gui.settings import SettingsStore
    store = SettingsStore()
    store.save(
        GuiSettings(
            window_width=1000,
            window_height=700,
            window_x=50,
            window_y=60,
            window_maximized=False,
        )
    )
    w = MainWindow(store)
    assert w.width() == 1000
    assert w.height() == 700
    assert w.pos().x() == 50
    assert w.pos().y() == 60


def test_current_settings_includes_live_geometry(qt_app):
    w = MainWindow()
    w.resize(900, 600)
    w.move(10, 20)
    s = w.current_settings()
    assert (s.window_width, s.window_height) == (900, 600)
    assert (s.window_x, s.window_y) == (10, 20)


def test_close_event_saves_and_sets_error_flag(qt_app, tmp_path):
    from session_snapshot.gui.settings import SettingsStore
    store = SettingsStore(tmp_path / "gui.json")
    w = MainWindow(store)
    w.close()
    assert w.save_error is None


def test_close_event_sets_error_on_write_failure(qt_app):
    from session_snapshot.gui.settings import SettingsStore
    from pathlib import Path
    w = MainWindow()
    w._store = SettingsStore(Path("/no/such/path"))
    w.close()
    # save_error is set to OSError
    assert w.save_error is not None


def test_system_is_dark_never_raises(qt_app):
    # Should return a boolean without raising
    from session_snapshot.gui.main_window import system_is_dark
    assert system_is_dark() in (True, False)