import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication  # noqa: E402

from session_snapshot.gui import navigation, styles, theme  # noqa: E402
from session_snapshot.gui.navigation import NavigationState  # noqa: E402
from session_snapshot.gui.sidebar import (  # noqa: E402
    COLLAPSED_WIDTH,
    EXPANDED_WIDTH,
    Sidebar,
)

IDS = navigation.page_ids()
LABELS = [item.label for item in navigation.NAV_ITEMS]


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def make(collapsed=False, palette=theme.LIGHT):
    state = NavigationState(collapsed=collapsed)
    return Sidebar(palette, state), state


def width_is(bar, expected):
    return bar.minimumWidth() == bar.maximumWidth() == expected


def active_ids(bar):
    return [i for i in IDS if bool(bar.button(i).property("active"))]


def test_starts_expanded(qt_app):
    bar, _ = make()
    assert width_is(bar, EXPANDED_WIDTH)
    assert [bar.button(i).text() for i in IDS] == LABELS
    assert all(bar.button(i).toolTip() == "" for i in IDS)
    assert not bar.title_label().isHidden()
    assert active_ids(bar) == ["dashboard"]


def test_collapsed_shows_icons_and_tooltips_only(qt_app):
    bar, _ = make()
    bar.set_collapsed(True)
    assert width_is(bar, COLLAPSED_WIDTH)
    assert all(bar.button(i).text() == "" for i in IDS)
    assert [bar.button(i).toolTip() for i in IDS] == LABELS
    assert bar.title_label().isHidden()
    bar.set_collapsed(False)
    assert width_is(bar, EXPANDED_WIDTH)
    assert [bar.button(i).text() for i in IDS] == LABELS


def test_can_start_collapsed(qt_app):
    bar, state = make(collapsed=True)
    assert state.collapsed is True
    assert width_is(bar, COLLAPSED_WIDTH)
    assert bar.title_label().isHidden()


def test_click_emits_and_marks_the_button_active(qt_app):
    bar, state = make()
    seen = []
    bar.page_selected.connect(seen.append)
    bar.button("sessions").click()
    assert seen == ["sessions"]
    assert state.active == "sessions"
    assert active_ids(bar) == ["sessions"]


def test_set_active_updates_without_emitting(qt_app):
    bar, state = make()
    seen = []
    bar.page_selected.connect(seen.append)
    assert bar.set_active("activity") is True
    assert seen == []
    assert state.active == "activity"
    assert active_ids(bar) == ["activity"]


def test_unknown_page_is_ignored(qt_app):
    bar, state = make()
    assert bar.set_active("nowhere") is False
    assert state.active == "dashboard"
    assert active_ids(bar) == ["dashboard"]


def test_collapse_button_toggles_and_emits(qt_app):
    bar, state = make()
    seen = []
    bar.collapsed_changed.connect(seen.append)
    bar.collapse_button().click()
    assert seen == [True]
    assert state.collapsed is True
    assert width_is(bar, COLLAPSED_WIDTH)
    bar.collapse_button().click()
    assert seen == [True, False]
    assert width_is(bar, EXPANDED_WIDTH)


def test_collapse_button_text_and_tooltip_follow_state(qt_app):
    bar, _ = make()
    assert bar.collapse_button().text() == "Collapse"
    assert bar.collapse_button().toolTip() == ""
    bar.set_collapsed(True)
    assert bar.collapse_button().text() == ""
    assert bar.collapse_button().toolTip() == "Expand sidebar"


def test_every_button_has_an_icon_in_every_mode(qt_app):
    for palette in (theme.LIGHT, theme.DARK):
        for collapsed in (False, True):
            bar, _ = make(collapsed=collapsed, palette=palette)
            assert all(not bar.button(i).icon().isNull() for i in IDS)
            assert not bar.collapse_button().icon().isNull()


def test_palette_can_be_switched(qt_app):
    bar, _ = make()
    bar.set_palette(theme.DARK)
    assert all(not bar.button(i).icon().isNull() for i in IDS)


def test_accessible_names_are_always_the_label(qt_app):
    bar, _ = make()
    for collapsed in (False, True):
        bar.set_collapsed(collapsed)
        assert [bar.button(i).accessibleName() for i in IDS] == LABELS


def test_object_names_match_the_stylesheet(qt_app):
    bar, _ = make()
    assert bar.objectName() == styles.SIDEBAR
    assert bar.title_label().objectName() == styles.APP_NAME
    assert all(bar.button(i).objectName() == styles.NAV_BUTTON for i in IDS)