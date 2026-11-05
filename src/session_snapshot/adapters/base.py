from abc import ABC, abstractmethod
from typing import Any

from session_snapshot.models.adapter_types import (
    AppInstance,
    CaptureContext,
    DiscoveryContext,
    RestoreContext,
    RestoreHandle,
    RestorePlan,
)
from session_snapshot.models.manifest import AppEntry
from session_snapshot.models.results import Capability, OpResult, Reason


class AdapterError(Exception):
    """Raise from an adapter to report a specific, explained failure."""

    def __init__(self, reason: Reason, message: str, **details: Any) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details


class SessionAdapter(ABC):
    adapter_id: str
    version: int
    compatibility_class: int  # 1 = Native, 2 = Observable

    @abstractmethod
    def capabilities(self) -> list[Capability]: ...

    @abstractmethod
    def detect(self, ctx: DiscoveryContext) -> list[AppInstance]: ...

    @abstractmethod
    def capture(self, instance: AppInstance, ctx: CaptureContext) -> AppEntry: ...

    @abstractmethod
    def plan_restore(self, snapshot: AppEntry, ctx: RestoreContext) -> RestorePlan: ...

    @abstractmethod
    def restore(
        self, snapshot: AppEntry, plan: RestorePlan, ctx: RestoreContext
    ) -> RestoreHandle: ...

    @abstractmethod
    def verify(
        self, snapshot: AppEntry, handle: RestoreHandle, ctx: RestoreContext
    ) -> OpResult: ...
