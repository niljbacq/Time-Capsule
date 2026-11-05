from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from session_snapshot.models.results import Reason


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
