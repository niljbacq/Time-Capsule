from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Status(str, Enum):
    RESTORED = "restored"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class Reason(str, Enum):
    OK = "ok"
    NOT_INSTALLED = "not_installed"
    PATH_MISSING = "path_missing"
    TIMEOUT = "timeout"
    VERIFY_MISMATCH = "verify_mismatch"
    UNSUPPORTED = "unsupported"
    EXCLUDED_BY_USER = "excluded_by_user"
    ALREADY_RUNNING = "already_running"
    ADAPTER_ERROR = "adapter_error"


class OpResult(BaseModel):
    """Outcome of one operation. Never a bare True/False."""

    status: Status
    reason: Reason
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def restored(cls, message: str, **details: Any) -> "OpResult":
        return cls(status=Status.RESTORED, reason=Reason.OK,
                   message=message, details=details)

    @classmethod
    def partial(cls, reason: Reason, message: str, **details: Any) -> "OpResult":
        return cls(status=Status.PARTIAL, reason=reason,
                   message=message, details=details)

    @classmethod
    def failed(cls, reason: Reason, message: str, **details: Any) -> "OpResult":
        return cls(status=Status.FAILED, reason=reason,
                   message=message, details=details)

    @classmethod
    def skipped(cls, reason: Reason, message: str, **details: Any) -> "OpResult":
        return cls(status=Status.SKIPPED, reason=reason,
                   message=message, details=details)


class Capability(BaseModel):
    name: str
    supported: bool
    limitation: str | None = None