from datetime import datetime

from pydantic import BaseModel, Field

from session_snapshot.models.results import Capability


class SessionSummary(BaseModel):
    session_id: str
    name: str
    description: str = ""
    saved_at: datetime
    app_count: int
    adapter_ids: list[str] = Field(default_factory=list)
    desktop: str | None = None
    session_type: str = "unknown"


class SessionProblem(BaseModel):
    session_id: str
    message: str


class SessionList(BaseModel):
    sessions: list[SessionSummary] = Field(default_factory=list)
    problems: list[SessionProblem] = Field(default_factory=list)


class AdapterInfo(BaseModel):
    adapter_id: str
    version: int
    compatibility_class: int
    capabilities: list[Capability] = Field(default_factory=list)
    error: str | None = None
