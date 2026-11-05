from session_snapshot.core.environment import detect_environment


def test_wayland_session_detected():
    env = detect_environment({"XDG_CURRENT_DESKTOP": "XFCE", "XDG_SESSION_TYPE": "wayland"})
    assert env.session_type == "wayland"
    assert env.desktop == "XFCE"


def test_x11_inferred_from_display():
    env = detect_environment({"DISPLAY": ":0"})
    assert env.session_type == "x11"
    assert env.desktop is None


def test_unknown_when_nothing_set():
    env = detect_environment({})
    assert env.session_type == "unknown"
    assert env.window_manager is None
