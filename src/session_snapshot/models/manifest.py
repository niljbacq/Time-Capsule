import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SHELL_META_RE = re.compile(r"[;&|`$<>\n\r]")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Geometry(_Strict):
    x: int
    y: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class WindowHint(_Strict):
    wm_class: str | None = None
    title_pattern: str | None = None


class WindowEntry(_Strict):
    window_id: str
    hint: WindowHint = Field(default_factory=WindowHint)
    workspace: int | None = None
    monitor: str | None = None
    state: Literal["normal", "maximized", "fullscreen"] = "normal"
    geometry: Geometry | None = None


class Monitor(_Strict):
    id: str
    name: str
    x: int
    y: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    scale: float = Field(default=1.0, gt=0)


class SessionMeta(_Strict):
    id: str
    name: str
    description: str = ""
    saved_at: datetime
    tool_version: str

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not SESSION_ID_RE.match(v):
            raise ValueError("session id must match ^[a-z0-9][a-z0-9-]{0,63}$")
        return v

    @field_validator("saved_at")
    @classmethod
    def _has_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("saved_at must include a timezone")
        return v


class EnvironmentInfo(_Strict):
    desktop: str | None = None
    session_type: Literal["x11", "wayland", "unknown"] = "unknown"
    window_manager: str | None = None
    monitors: list[Monitor] = Field(default_factory=list)


class LaunchSpec(_Strict):
    type: Literal["argv"] = "argv"
    executable: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)

    @field_validator("executable")
    @classmethod
    def _no_shell_metacharacters(cls, v: str) -> str:
        if _SHELL_META_RE.search(v):
            raise ValueError("executable contains shell metacharacters")
        return v


class AdapterRef(_Strict):
    id: str
    version: int = Field(ge=1)


class CapabilityCapture(_Strict):
    name: str
    captured: bool


class CaptureInfo(_Strict):
    status: Literal["captured", "partial", "failed"]
    capabilities: list[CapabilityCapture] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AppEntry(_Strict):
    instance_id: str
    app_id: str | None = None
    adapter: AdapterRef
    compatibility_class: Literal[1, 2]
    included: bool = True
    launch: LaunchSpec
    state: dict[str, Any] = Field(default_factory=dict)
    windows: list[WindowEntry] = Field(default_factory=list)
    capture: CaptureInfo


class UnsupportedEntry(_Strict):
    app_name: str
    reason: str = "unsupported"
    message: str = ""


class RestorePreferences(_Strict):
    duplicate_policy: Literal["reuse_existing", "launch_new", "skip_if_running"] = "reuse_existing"


class Manifest(_Strict):
    schema_version: Literal[1]
    session: SessionMeta
    environment: EnvironmentInfo
    apps: list[AppEntry] = Field(default_factory=list)
    unsupported: list[UnsupportedEntry] = Field(default_factory=list)
    restore_preferences: RestorePreferences = Field(default_factory=RestorePreferences)

    @model_validator(mode="after")
    def _unique_instance_ids(self) -> "Manifest":
        ids = [a.instance_id for a in self.apps]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate instance_id in apps")
        return self
