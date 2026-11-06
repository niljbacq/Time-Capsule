"""Pure parsers for wmctrl, xprop and xwininfo output. No subprocess, no X calls."""

import re
from typing import Literal

from session_snapshot.models.manifest import Geometry

_WMCTRL_ROW = re.compile(r"^(0x[0-9a-fA-F]+)\s+(-?\d+)\s+(-?\d+)\s+(\S+)\s*(.*)$")
_QUOTED = re.compile(r'"([^"]*)"')
_TYPE = re.compile(r"_NET_WM_WINDOW_TYPE_([A-Z_]+)")

WmctrlRow = tuple[str, int | None, int | None, str]


def parse_wmctrl_list(text: str) -> list[WmctrlRow]:
    """Parse `wmctrl -lp` into (window_id, workspace, pid, title) rows.

    workspace is None for sticky windows (-1). pid is None when unknown (<= 0).
    Lines that do not look like window rows are skipped.
    """
    rows: list[WmctrlRow] = []
    for line in text.splitlines():
        m = _WMCTRL_ROW.match(line.strip())
        if not m:
            continue
        workspace = int(m.group(2))
        pid = int(m.group(3))
        rows.append(
            (
                m.group(1).lower(),
                workspace if workspace >= 0 else None,
                pid if pid > 0 else None,
                m.group(5),
            )
        )
    return rows


def parse_wm_state(text: str) -> Literal["normal", "maximized", "fullscreen"]:
    """Parse `xprop _NET_WM_STATE`. Fullscreen wins; maximized needs both axes."""
    if "_NET_WM_STATE_FULLSCREEN" in text:
        return "fullscreen"
    if "_NET_WM_STATE_MAXIMIZED_HORZ" in text and "_NET_WM_STATE_MAXIMIZED_VERT" in text:
        return "maximized"
    return "normal"


def parse_wm_class(text: str) -> str | None:
    """Parse `xprop WM_CLASS`; returns the class part (second value)."""
    values = _QUOTED.findall(text)
    if len(values) >= 2 and values[1]:
        return values[1]
    return None


def parse_quoted_name(text: str) -> str | None:
    """Parse a single quoted xprop string such as _NET_WM_NAME."""
    values = _QUOTED.findall(text)
    return values[0] if values and values[0] else None


def parse_window_type(text: str) -> str | None:
    """Parse `xprop _NET_WM_WINDOW_TYPE`; returns e.g. 'normal' or 'dock'."""
    m = _TYPE.search(text)
    return m.group(1).lower() if m else None


def _int_field(label: str, text: str) -> int | None:
    m = re.search(rf"^\s*{label}:\s*(-?\d+)", text, re.MULTILINE)
    return int(m.group(1)) if m else None


def parse_xwininfo_geometry(text: str) -> Geometry | None:
    """Parse `xwininfo -id` absolute client geometry, or None if incomplete."""
    x = _int_field("Absolute upper-left X", text)
    y = _int_field("Absolute upper-left Y", text)
    width = _int_field("Width", text)
    height = _int_field("Height", text)
    if x is None or y is None or width is None or height is None:
        return None
    if width <= 0 or height <= 0:
        return None
    return Geometry(x=x, y=y, width=width, height=height)