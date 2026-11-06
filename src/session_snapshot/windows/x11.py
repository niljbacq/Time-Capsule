"""X11 window backend built on wmctrl, xprop and xwininfo (argv only, no shell)."""

import re
import subprocess
from collections.abc import Sequence

from session_snapshot.windows.base import (
    CommandResult,
    CommandRunner,
    LiveWindow,
    WindowBackend,
)
from session_snapshot.windows.parsers import (
    parse_quoted_name,
    parse_window_type,
    parse_wm_class,
    parse_wm_state,
    parse_wmctrl_list,
    parse_xwininfo_geometry,
)

_TRAILING_ID = re.compile(r"(0x[0-9a-fA-F]+)\s*$")


def run_command(argv: Sequence[str]) -> CommandResult:
    """Run one command with a timeout. A missing tool or timeout is a failure result."""
    try:
        proc = subprocess.run(
            list(argv), capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return CommandResult(127, "")
    return CommandResult(proc.returncode, proc.stdout)


class X11Backend(WindowBackend):
    def __init__(self, runner: CommandRunner = run_command) -> None:
        self._run = runner

    def _out(self, argv: Sequence[str]) -> str | None:
        result = self._run(argv)
        return result.stdout if result.returncode == 0 else None

    def available(self) -> bool:
        return self._out(["wmctrl", "-m"]) is not None

    def window_manager(self) -> str | None:
        root = self._out(["xprop", "-root", "_NET_SUPPORTING_WM_CHECK"])
        if not root:
            return None
        m = _TRAILING_ID.search(root.strip())
        if not m:
            return None
        name = self._out(["xprop", "-id", m.group(1), "_NET_WM_NAME"])
        return parse_quoted_name(name) if name else None

    def list_windows(self) -> list[LiveWindow]:
        listing = self._out(["wmctrl", "-lp"])
        if listing is None:
            return []
        windows: list[LiveWindow] = []
        for wid, workspace, pid, title in parse_wmctrl_list(listing):
            props = self._out(
                ["xprop", "-id", wid, "_NET_WM_STATE", "WM_CLASS", "_NET_WM_WINDOW_TYPE"]
            ) or ""
            info = self._out(["xwininfo", "-id", wid]) or ""
            windows.append(
                LiveWindow(
                    window_id=wid,
                    pid=pid,
                    title=title,
                    workspace=workspace,
                    wm_class=parse_wm_class(props),
                    state=parse_wm_state(props),
                    geometry=parse_xwininfo_geometry(info),
                    window_type=parse_window_type(props),
                )
            )
        return windows
