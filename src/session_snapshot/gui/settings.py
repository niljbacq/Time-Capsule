"""GUI settings stored as JSON under the XDG config directory. Pure Python, no Qt.

Loading never raises: a missing or damaged file, or a bad value in one field,
falls back to the default for that field. Saving is atomic (temp file, fsync,
rename) and the file is readable only by its owner; it raises OSError if the
disk write fails. Unknown keys are kept so settings written by a newer version
survive a round trip.
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from session_snapshot.gui.theme import (
    DEFAULT_PREFERENCE,
    ThemePreference,
    normalize_preference,
)

SessionsView = Literal["list", "grid"]
SESSIONS_VIEWS: tuple[SessionsView, ...] = ("list", "grid")

DEFAULT_WINDOW_SIZE = (1200, 800)
MIN_WINDOW_SIZE = (800, 500)
MAX_WINDOW_DIMENSION = 16384
MAX_WINDOW_OFFSET = 100000


@dataclass(frozen=True)
class GuiSettings:
    theme: ThemePreference = DEFAULT_PREFERENCE
    sidebar_collapsed: bool = False
    sessions_view: SessionsView = "list"
    window_width: int = DEFAULT_WINDOW_SIZE[0]
    window_height: int = DEFAULT_WINDOW_SIZE[1]
    window_x: int | None = None
    window_y: int | None = None
    window_maximized: bool = False
    extra: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


_KNOWN = (
    "theme",
    "sidebar_collapsed",
    "sessions_view",
    "window_width",
    "window_height",
    "window_x",
    "window_y",
    "window_maximized",
)


def _bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _size(value: object, default: int, low: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(low, min(MAX_WINDOW_DIMENSION, value))


def _offset(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if abs(value) <= MAX_WINDOW_OFFSET else None


def _view(value: object) -> SessionsView:
    for choice in SESSIONS_VIEWS:
        if value == choice:
            return choice
    return "list"


def settings_from_dict(raw: object) -> GuiSettings:
    """Build settings from parsed JSON, replacing any bad field with its default."""
    if not isinstance(raw, dict):
        return GuiSettings()
    return GuiSettings(
        theme=normalize_preference(raw.get("theme")),
        sidebar_collapsed=_bool(raw.get("sidebar_collapsed"), False),
        sessions_view=_view(raw.get("sessions_view")),
        window_width=_size(raw.get("window_width"), DEFAULT_WINDOW_SIZE[0], MIN_WINDOW_SIZE[0]),
        window_height=_size(raw.get("window_height"), DEFAULT_WINDOW_SIZE[1], MIN_WINDOW_SIZE[1]),
        window_x=_offset(raw.get("window_x")),
        window_y=_offset(raw.get("window_y")),
        window_maximized=_bool(raw.get("window_maximized"), False),
        extra={k: v for k, v in raw.items() if k not in _KNOWN},
    )


def settings_to_dict(settings: GuiSettings) -> dict[str, Any]:
    data: dict[str, Any] = dict(settings.extra)
    for name in _KNOWN:
        data[name] = getattr(settings, name)
    return data


def default_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "linux-session-snapshot"


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_config_dir() / "gui.json"

    def load(self) -> GuiSettings:
        try:
            text = self.path.read_text(encoding="utf-8")
            return settings_from_dict(json.loads(text))
        except (OSError, ValueError):
            return GuiSettings()

    def save(self, settings: GuiSettings) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        text = json.dumps(settings_to_dict(settings), indent=2, sort_keys=True) + "\n"
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".gui-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise