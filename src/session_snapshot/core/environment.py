import os
from collections.abc import Mapping

from session_snapshot.models.manifest import EnvironmentInfo


def detect_environment(env: Mapping[str, str] | None = None) -> EnvironmentInfo:
    """Read desktop and session type from environment variables.

    The window manager is not detected here; the window backend does that later.
    """
    env = os.environ if env is None else env
    desktop = env.get("XDG_CURRENT_DESKTOP") or None
    session_type = (env.get("XDG_SESSION_TYPE") or "").lower()
    if session_type not in ("x11", "wayland"):
        if env.get("WAYLAND_DISPLAY"):
            session_type = "wayland"
        elif env.get("DISPLAY"):
            session_type = "x11"
        else:
            session_type = "unknown"
    return EnvironmentInfo(desktop=desktop, session_type=session_type, window_manager=None)
