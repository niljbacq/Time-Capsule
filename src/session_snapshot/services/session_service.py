from collections.abc import Callable, Collection

from session_snapshot.adapters.isolation import guarded
from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.discovery import ProcessSource
from session_snapshot.core.events import EventBus
from session_snapshot.core.manager import SessionManager
from session_snapshot.core.restore import RestoreEngine
from session_snapshot.models.manifest import SESSION_ID_RE, EnvironmentInfo, Manifest
from session_snapshot.models.summaries import (
    AdapterInfo,
    SessionList,
    SessionProblem,
    SessionSummary,
)
from session_snapshot.report.models import RestorePreview, RestoreReport, SaveReport
from datetime import datetime
from session_snapshot.core.oplog import OperationEntry, OperationLog
from session_snapshot.store.manifests import ManifestError, ManifestStore
from session_snapshot.windows.base import WindowBackend


class SessionService:
    """The single API that both the CLI and the GUI call."""

    def __init__(
        self,
        registry: AdapterRegistry,
        store: ManifestStore,
        process_source: ProcessSource,
        bus: EventBus | None = None,
        env_provider: Callable[[], EnvironmentInfo] | None = None,
        window_backend: WindowBackend | None = None,
        oplog: OperationLog | None = None,
    ) -> None:
        self.registry = registry
        self.store = store
        self.bus = bus or EventBus()
        self._manager = SessionManager(
            registry,
            store,
            process_source,
            bus=self.bus,
            env_provider=env_provider,
            window_backend=window_backend,
        )
        self._restorer = RestoreEngine(
            registry,
            store,
            process_source,
            bus=self.bus,
            env_provider=env_provider,
            window_backend=window_backend,
        )
        self._oplog = oplog or OperationLog(store.root)

    # ---- save / restore ---------------------------------------------

    def save(
        self,
        session_id: str,
        name: str,
        description: str = "",
        exclude: Collection[str] = frozenset(),
    ) -> SaveReport:
        report = self._manager.save(session_id, name, description, exclude)
        self._oplog.append(
            OperationEntry(
                kind="save",
                session_id=session_id,
                started_at=report.started_at,
                finished_at=report.finished_at,
                counts=report.counts(),
                warnings=report.warnings,
                summary=f"Saved session '{name}' ({len(report.outcomes)} apps)",
            )
        )
        return report

    def preview(
        self,
        session_id: str,
        exclude: Collection[str] = frozenset(),
        duplicate_policy: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> RestorePreview:
        return self._restorer.preview(session_id, exclude, duplicate_policy, timeout_seconds)

    def restore(
        self,
        session_id: str,
        exclude: Collection[str] = frozenset(),
        duplicate_policy: str | None = None,
        timeout_seconds: float = 30.0,
        concurrency: int = 4,
    ) -> RestoreReport:
        report = self._restorer.restore(
            session_id, exclude, duplicate_policy, timeout_seconds, concurrency
        )
        self._oplog.append(
            OperationEntry(
                kind="restore",
                session_id=session_id,
                started_at=report.started_at,
                finished_at=report.finished_at,
                counts=report.counts(),
                warnings=report.warnings,
                summary=f"Restored session '{session_id}' ({report.counts()})",
            )
        )
        return report

    # ---- session library --------------------------------------------

    def list_sessions(self) -> SessionList:
        sessions: list[SessionSummary] = []
        problems: list[SessionProblem] = []
        for session_id in self.store.list_ids():
            try:
                manifest = self.store.load(session_id)
            except ManifestError as exc:
                problems.append(SessionProblem(session_id=session_id, message=str(exc)))
                continue
            sessions.append(
                SessionSummary(
                    session_id=manifest.session.id,
                    name=manifest.session.name,
                    description=manifest.session.description,
                    saved_at=manifest.session.saved_at,
                    app_count=len(manifest.apps),
                    adapter_ids=sorted({app.adapter.id for app in manifest.apps}),
                    desktop=manifest.environment.desktop,
                    session_type=manifest.environment.session_type,
                )
            )
        sessions.sort(key=lambda s: s.saved_at, reverse=True)
        return SessionList(sessions=sessions, problems=problems)

    def get_session(self, session_id: str) -> Manifest:
        return self.store.load(session_id)

    def delete_session(self, session_id: str) -> None:
        self.store.delete(session_id)

    def rename_session(self, session_id: str, new_name: str) -> Manifest:
        if not new_name.strip():
            raise ManifestError("session name must not be empty")
        manifest = self.store.load(session_id)
        updated = manifest.model_copy(
            update={"session": manifest.session.model_copy(update={"name": new_name.strip()})}
        )
        self._write(updated)
        return updated

    def duplicate_session(self, session_id: str, new_id: str, new_name: str) -> Manifest:
        if not SESSION_ID_RE.match(new_id):
            raise ManifestError(f"invalid session id: {new_id!r}")
        if not new_name.strip():
            raise ManifestError("session name must not be empty")
        if new_id in self.store.list_ids():
            raise ManifestError(f"session already exists: {new_id}")
        manifest = self.store.load(session_id)
        copy = manifest.model_copy(
            update={
                "session": manifest.session.model_copy(
                    update={"id": new_id, "name": new_name.strip()}
                )
            }
        )
        self._write(copy)
        return copy

    # ---- adapters ---------------------------------------------------

    def adapters(self) -> list[AdapterInfo]:
        infos: list[AdapterInfo] = []
        for adapter in self.registry.all():
            capabilities, err = guarded(
                adapter.adapter_id, "capabilities", adapter.capabilities
            )
            infos.append(
                AdapterInfo(
                    adapter_id=adapter.adapter_id,
                    version=adapter.version,
                    compatibility_class=adapter.compatibility_class,
                    capabilities=list(capabilities or []),
                    error=err.message if err is not None else None,
                )
            )
        return infos

    # ---- helpers ----------------------------------------------------

    def _write(self, manifest: Manifest) -> None:
        try:
            self.store.save(manifest)
        except OSError as exc:
            raise ManifestError(f"cannot write session {manifest.session.id}: {exc}") from exc
