from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from session_snapshot.models.adapter_types import ActionKind
from session_snapshot.models.results import Reason, Status


class SaveStatus(str, Enum):
    CAPTURED = "captured"
    FAILED = "failed"
    EXCLUDED = "excluded"


class AppSaveOutcome(BaseModel):
    instance_id: str
    adapter_id: str
    status: SaveStatus
    reason: Reason
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class SaveReport(BaseModel):
    session_id: str
    started_at: datetime
    finished_at: datetime
    outcomes: list[AppSaveOutcome] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    manifest_path: str

    def counts(self) -> dict[str, int]:
        result = {status.value: 0 for status in SaveStatus}
        for outcome in self.outcomes:
            result[outcome.status.value] += 1
        return result


class AppRestoreOutcome(BaseModel):
    instance_id: str
    adapter_id: str
    action: ActionKind | None = None
    status: Status
    reason: Reason
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: float | None = None


class RestoreReport(BaseModel):
    session_id: str
    started_at: datetime
    finished_at: datetime
    outcomes: list[AppRestoreOutcome] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def counts(self) -> dict[str, int]:
        result = {status.value: 0 for status in Status}
        for outcome in self.outcomes:
            result[outcome.status.value] += 1
        return result


class AppPreview(BaseModel):
    instance_id: str
    adapter_id: str
    action: ActionKind
    reason: Reason = Reason.OK
    message: str
    missing_dependencies: list[str] = Field(default_factory=list)
    unavailable_paths: list[str] = Field(default_factory=list)


class RestorePreview(BaseModel):
    session_id: str
    session_name: str
    apps: list[AppPreview] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
