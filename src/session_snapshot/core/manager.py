from collections.abc import Callable, Collection
from datetime import datetime

from session_snapshot import __version__
from session_snapshot.adapters.isolation import guarded
from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.discovery import ProcessSource
from session_snapshot.core.environment import detect_environment
from session_snapshot.core.events import EventBus, EventKind
from session_snapshot.models.adapter_types import CaptureContext, DiscoveryContext
from session_snapshot.models.manifest import (
    SESSION_ID_RE,
    AppEntry,
    EnvironmentInfo,
    Manifest,
    SessionMeta,
)
from session_snapshot.models.results import OpResult, Reason
from session_snapshot.report.models import AppSaveOutcome, SaveReport, SaveStatus
from session_snapshot.store.manifests import ManifestError, ManifestStore


def _failed_outcome(instance_id: str, adapter_id: str, err: OpResult) -> AppSaveOutcome:
    return AppSaveOutcome(
        instance_id=instance_id,
        adapter_id=adapter_id,
        status=SaveStatus.FAILED,
        reason=err.reason,
        message=err.message,
        details=err.details,
    )


def _check_entry(entry: object, adapter_id: str, instance_id: str) -> str | None:
    """Return a problem description if the adapter returned something inconsistent."""
    if not isinstance(entry, AppEntry):
        return f"adapter returned {type(entry).__name__}, expected AppEntry"
    if entry.adapter.id != adapter_id:
        return f"entry claims adapter {entry.adapter.id!r}, expected {adapter_id!r}"
    if entry.instance_id != instance_id:
        return f"entry instance_id {entry.instance_id!r} does not match {instance_id!r}"
    return None


class SessionManager:
    def __init__(
        self,
        registry: AdapterRegistry,
        store: ManifestStore,
        process_source: ProcessSource,
        bus: EventBus | None = None,
        env_provider: Callable[[], EnvironmentInfo] | None = None,
    ) -> None:
        self.registry = registry
        self.store = store
        self.process_source = process_source
        self.bus = bus or EventBus()
        self._env_provider = env_provider or detect_environment

    def save(
        self,
        session_id: str,
        name: str,
        description: str = "",
        exclude: Collection[str] = frozenset(),
    ) -> SaveReport:
        if not SESSION_ID_RE.match(session_id):
            raise ManifestError(f"invalid session id: {session_id!r}")
        if not name.strip():
            raise ManifestError("session name must not be empty")

        started = datetime.now().astimezone()
        self.bus.emit(EventKind.SAVE_STARTED, f"Saving session '{name}'", session_id=session_id)

        processes = self.process_source.snapshot()
        outcomes: list[AppSaveOutcome] = []
        entries: list[AppEntry] = []
        seen: set[str] = set()

        for adapter in self.registry.all():
            aid = adapter.adapter_id
            instances, err = guarded(
                aid, "detect", adapter.detect, DiscoveryContext(processes=processes)
            )
            if err is not None:
                outcomes.append(_failed_outcome(f"{aid}:detect", aid, err))
                self.bus.emit(EventKind.APP_CAPTURE_FAILED, err.message, app=aid)
                continue

            for instance in instances or []:
                iid = instance.instance_id
                self.bus.emit(
                    EventKind.APP_DETECTED,
                    f"Detected {instance.label or iid}",
                    app=iid,
                    adapter_id=aid,
                )

                if iid in exclude:
                    outcomes.append(
                        AppSaveOutcome(
                            instance_id=iid,
                            adapter_id=aid,
                            status=SaveStatus.EXCLUDED,
                            reason=Reason.EXCLUDED_BY_USER,
                            message="Excluded by user",
                        )
                    )
                    self.bus.emit(EventKind.APP_EXCLUDED, f"Excluded {iid}", app=iid)
                    continue

                if iid in seen:
                    err = OpResult.failed(
                        Reason.ADAPTER_ERROR,
                        f"duplicate instance_id {iid!r} reported by more than one adapter",
                        adapter_id=aid,
                        operation="detect",
                    )
                    outcomes.append(_failed_outcome(iid, aid, err))
                    self.bus.emit(EventKind.APP_CAPTURE_FAILED, err.message, app=iid)
                    continue
                seen.add(iid)

                entry, err = guarded(
                    aid, "capture", adapter.capture, instance, CaptureContext(processes=processes)
                )
                if err is None:
                    problem = _check_entry(entry, aid, iid)
                    if problem is not None:
                        err = OpResult.failed(
                            Reason.ADAPTER_ERROR, problem, adapter_id=aid, operation="capture"
                        )
                if err is not None:
                    outcomes.append(_failed_outcome(iid, aid, err))
                    self.bus.emit(EventKind.APP_CAPTURE_FAILED, err.message, app=iid)
                    continue

                entries.append(entry)
                outcomes.append(
                    AppSaveOutcome(
                        instance_id=iid,
                        adapter_id=aid,
                        status=SaveStatus.CAPTURED,
                        reason=Reason.OK,
                        message="Captured",
                        details={"warnings": list(entry.capture.warnings)},
                    )
                )
                self.bus.emit(EventKind.APP_CAPTURED, f"Captured {iid}", app=iid)

        warnings: list[str] = []
        if not entries:
            warnings.append("No applications were captured.")

        manifest = Manifest(
            schema_version=1,
            session=SessionMeta(
                id=session_id,
                name=name,
                description=description,
                saved_at=started,
                tool_version=__version__,
            ),
            environment=self._env_provider(),
            apps=entries,
        )
        try:
            path = self.store.save(manifest)
        except OSError as exc:
            raise ManifestError(f"cannot write session {session_id}: {exc}") from exc

        finished = datetime.now().astimezone()
        self.bus.emit(
            EventKind.SAVE_FINISHED,
            f"Saved session '{name}'",
            session_id=session_id,
            captured=len(entries),
        )
        return SaveReport(
            session_id=session_id,
            started_at=started,
            finished_at=finished,
            outcomes=outcomes,
            warnings=warnings,
            manifest_path=str(path),
        )
