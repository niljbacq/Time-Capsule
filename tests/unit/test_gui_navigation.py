import pytest

from session_snapshot.gui import navigation as nav


def test_five_pages_in_spec_order():
    assert [item.label for item in nav.NAV_ITEMS] == [
        "Dashboard",
        "Sessions",
        "Applications & Adapters",
        "Activity & Reports",
        "Settings",
    ]


def test_ids_and_icons_are_unique_and_not_empty():
    ids = [item.id for item in nav.NAV_ITEMS]
    icons = [item.icon for item in nav.NAV_ITEMS]
    assert len(set(ids)) == 5
    assert len(set(icons)) == 5
    assert all(ids) and all(icons)


def test_page_ids_match_the_items():
    assert nav.page_ids() == tuple(item.id for item in nav.NAV_ITEMS)


def test_default_state_is_dashboard_and_expanded():
    state = nav.NavigationState()
    assert state.active == "dashboard"
    assert state.collapsed is False


def test_select_known_page():
    state = nav.NavigationState()
    assert state.select("sessions") is True
    assert state.active == "sessions"


def test_select_unknown_page_changes_nothing():
    state = nav.NavigationState(active="sessions")
    assert state.select("nowhere") is False
    assert state.select(None) is False
    assert state.active == "sessions"


def test_toggle_flips_and_returns_the_new_value():
    state = nav.NavigationState()
    assert state.toggle_collapsed() is True
    assert state.collapsed is True
    assert state.toggle_collapsed() is False
    assert state.collapsed is False


def test_can_start_collapsed_and_set_directly():
    state = nav.NavigationState(collapsed=True)
    assert state.collapsed is True
    state.set_collapsed(False)
    assert state.collapsed is False


def test_nav_item_lookup():
    item = nav.nav_item("activity")
    assert item is not None
    assert item.label == "Activity & Reports"
    assert nav.nav_item("nowhere") is None


def test_page_index_follows_navigation_order():
    assert nav.page_index("dashboard") == 0
    assert nav.page_index("settings") == 4
    with pytest.raises(ValueError):
        nav.page_index("nowhere")


def test_normalize_page():
    assert nav.normalize_page("settings") == "settings"
    assert nav.normalize_page("nowhere") == "dashboard"
    assert nav.normalize_page(None) == "dashboard"