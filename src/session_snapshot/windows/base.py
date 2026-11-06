"""Window backend interface. One ABC, one implementation per display system."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from session_snapshot.models.manifest import Geometry


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str


CommandRunner = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True)
class LiveWindow:
    """One window that exists right now, as reported by the display system."""

    window_id: str
    pid: int | None
    title: str
    workspace: int | None
    wm_class: str | None
    state: Literal["normal", "maximized", "fullscreen"]
    geometry: Geometry | None
    window_type: str | None = None


class WindowBackend(ABC):
    """Reads the live window list and moves windows."""

    @abstractmethod
    def available(self) -> bool:
        """True if this backend can talk to the display right now."""

    @abstractmethod
    def window_manager(self) -> str | None:
        """Name of the running window manager, or None if unknown."""

    @abstractmethod
    def list_windows(self) -> list[LiveWindow]:
        """All current windows. Returns [] if the display cannot be read."""

    def place_window(
        self,
        window_id: str,
        workspace: int | None,
        state: Literal["normal", "maximized", "fullscreen"],
        geometry: Geometry | None,
    ) -> list[str]:
        """Move a window. Returns warnings (empty on success). Default: unsupported."""
        return [f"{window_id}: window placement is not supported by this backend"]
