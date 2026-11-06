from session_snapshot.models.manifest import Geometry
from session_snapshot.windows.parsers import (
    parse_quoted_name,
    parse_window_type,
    parse_wm_class,
    parse_wm_state,
    parse_wmctrl_list,
    parse_xwininfo_geometry,
)

XWININFO = """
  Absolute upper-left X:  0
  Absolute upper-left Y:  36
  Relative upper-left X:  0
  Relative upper-left Y:  0
  Width: 1366
  Height: 699
  Border width: 0
"""


def test_wmctrl_basic_row():
    rows = parse_wmctrl_list("0x04800003  0 6592 nj Mozilla Firefox\n")
    assert rows == [("0x04800003", 0, 6592, "Mozilla Firefox")]


def test_wmctrl_sticky_and_zero_pid():
    text = "0x00e00003 -1 1675 nj xfce4-panel\n0x05000001  1 0 nj Some Window\n"
    rows = parse_wmctrl_list(text)
    assert rows[0] == ("0x00e00003", None, 1675, "xfce4-panel")
    assert rows[1] == ("0x05000001", 1, None, "Some Window")


def test_wmctrl_unicode_title():
    rows = parse_wmctrl_list("0x03000003  0 2387 nj Terminal - π - neil\n")
    assert rows[0][3] == "Terminal - π - neil"


def test_wmctrl_skips_garbage():
    assert parse_wmctrl_list("not a row\n\nCannot open display\n") == []


def test_state_maximized():
    text = "_NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_HORZ, _NET_WM_STATE_MAXIMIZED_VERT"
    assert parse_wm_state(text) == "maximized"


def test_state_fullscreen_wins():
    text = "_NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_HORZ, _NET_WM_STATE_FULLSCREEN"
    assert parse_wm_state(text) == "fullscreen"


def test_state_single_axis_is_normal():
    assert parse_wm_state("_NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_VERT") == "normal"


def test_state_not_found_is_normal():
    assert parse_wm_state("_NET_WM_STATE:  not found.") == "normal"


def test_wm_class_returns_class_part():
    assert parse_wm_class('WM_CLASS(STRING) = "Navigator", "firefox"') == "firefox"


def test_wm_class_missing():
    assert parse_wm_class("WM_CLASS:  not found.") is None


def test_quoted_name_and_window_type():
    assert parse_quoted_name('_NET_WM_NAME(UTF8_STRING) = "Xfwm4"') == "Xfwm4"
    assert parse_quoted_name("_NET_WM_NAME:  not found.") is None
    assert parse_window_type("_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_NORMAL") == "normal"
    assert parse_window_type("_NET_WM_WINDOW_TYPE:  not found.") is None


def test_xwininfo_geometry():
    assert parse_xwininfo_geometry(XWININFO) == Geometry(x=0, y=36, width=1366, height=699)


def test_xwininfo_incomplete_returns_none():
    assert parse_xwininfo_geometry("  Absolute upper-left X:  0\n") is None


def test_xwininfo_zero_size_returns_none():
    text = XWININFO.replace("Width: 1366", "Width: 0")
    assert parse_xwininfo_geometry(text) is None