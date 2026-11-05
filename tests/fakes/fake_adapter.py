import time

from session_snapshot.adapters.base import SessionAdapter
from session_snapshot.models.adapter_types import (
    ActionKind,
    AppInstance,
    CaptureContext,
    DiscoveryContext,
    RestoreContext,
    RestoreHandle,
    RestorePlan,
)
from session_snapshot.models.manifest import AppEntry
from session_snapshot.models.results import Capability, OpResult


class FakeAdapter(SessionAdapter):
    """A harmless adapter for tests. Finds processes named 'fakeapp'."""

    adapter_id = "fake"
    version = 1
    compatibility_class = 2

    def __init__(
        self,
        adapter_id: str = "fake",
        fail_with: Exception | None = None,
        restore_error: Exception | None = None,
        restore_delay: float = 0.0,
        plan: RestorePlan | None = None,
        verify_result: OpResult | None = None,
        verify_error: Exception | None = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.fail_with = fail_with  # raises in capture and restore
        self.restore_error = restore_error  # raises in restore only
        self.restore_delay = restore_delay
        self.plan = plan
        self.verify_result = verify_result
        self.verify_error = verify_error
        self.calls: list[str] = []
        self.last_ctx: RestoreContext | None = None

    def capabilities(self) -> list[Capability]:
        return [Capability(name="cwd", supported=True)]

    def detect(self, ctx: DiscoveryContext) -> list[AppInstance]:
        return [
            AppInstance(
                instance_id=f"{self.adapter_id}-{p.pid}",
                adapter_id=self.adapter_id,
                pid=p.pid,
                label=p.name,
            )
            for p in ctx.processes
            if p.name == "fakeapp"
        ]

    def capture(self, instance: AppInstance, ctx: CaptureContext) -> AppEntry:
        if self.fail_with:
            raise self.fail_with
        return AppEntry.model_validate(
            {
                "instance_id": instance.instance_id,
                "adapter": {"id": self.adapter_id, "version": self.version},
                "compatibility_class": self.compatibility_class,
                "launch": {"executable": "fakeapp"},
                "state": {"cwd": "/tmp"},
                "capture": {"status": "captured"},
            }
        )

    def plan_restore(self, snapshot: AppEntry, ctx: RestoreContext) -> RestorePlan:
        self.calls.append("plan")
        self.last_ctx = ctx
        return self.plan or RestorePlan(action=ActionKind.LAUNCH, message="would launch fakeapp")

    def restore(self, snapshot: AppEntry, plan: RestorePlan, ctx: RestoreContext) -> RestoreHandle:
        self.calls.append("restore")
        if self.fail_with:
            raise self.fail_with
        if self.restore_error:
            raise self.restore_error
        if self.restore_delay:
            time.sleep(self.restore_delay)
        return RestoreHandle(instance_id=snapshot.instance_id, pid=1234, launched_at=0.0)

    def verify(self, snapshot: AppEntry, handle: RestoreHandle, ctx: RestoreContext) -> OpResult:
        self.calls.append("verify")
        if self.verify_error:
            raise self.verify_error
        return self.verify_result or OpResult.restored("fake state verified")
