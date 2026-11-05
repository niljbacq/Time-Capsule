from dataclasses import dataclass
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from session_snapshot.models.manifest import WindowHint
from session_snapshot.models.results import Reason


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProcessInfo(_Frozen):
    pid: int
    ppid: int | None = None
    name: str
    exe: str | None = None
    argv: list[str] = Field(default_factory=list)
    cwd: str | None = None


class AppInstance(_Frozen):
    """One running instance of an application, as found by an adapter."""

    instance_id: str
    adapter_id: str
    pid: int | None = None
    app_id: str | None = None
    label: str = ""


class ActionKind(str, Enum):
    LAUNCH = "launch"
    RECONNECT = "reconnect"
    REUSE = "reuse"
    SKIP = "skip"


class RestorePlan(_Frozen):
    """What would happen for one app. Computed before anything is launched."""

    action: ActionKind
    message: str
    reason: Reason = Reason.OK
    missing_dependencies: list[str] = Field(default_factory=list)
    unavailable_paths: list[str] = Field(default_factory=list)


class RestoreHandle(_Frozen):
    """What restore() hands to verify() and to the window backend."""

    instance_id: str
    pid: int | None = None
    launched_at: float | None = None
    window_hint: WindowHint | None = None


@dataclass(frozen=True)
class DiscoveryContext:
    processes: tuple[ProcessInfo, ...] = ()


@dataclass(frozen=True)
class CaptureContext:
    processes: tuple[ProcessInfo, ...] = ()


@dataclass(frozen=True)
class RestoreContext:
    timeout_seconds: float = 30.0
    duplicate_policy: Literal["reuse_existing", "launch_new", "skip_if_running"] = "reuse_existing"
    processes: tuple[ProcessInfo, ...] = ()
