import time
from collections.abc import Callable, Collection
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, get_args

from session_snapshot.adapters.base import SessionAdapter
from session_snapshot.adapters.isolation import guarded
from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.core.discovery import ProcessSource
from session_snapshot.core.environment import detect_environment
from session_snapshot.core.events import EventBus, EventKind
from session_snapshot.models.adapter_types import (
    ActionKind,
    RestoreContext,
    RestoreHandle,
    RestorePlan,
)
from session_snapshot.models.manifest import AppEntry, EnvironmentInfo, Manifest
from session_snapshot.models.results import OpResult, Reason, Status
from session_snapshot.report.models import (
    AppPreview,
    AppRestoreOutcome,
    RestorePreview,
    RestoreReport,
)
from session_snapshot.store.manifests import ManifestStore

DuplicatePolicy = Literal["reuse_existing", "launch_new", "skip_if_running"]
_POLL_SECONDS = 0.02


@dataclass
class _Item:
    entry: AppEntry
    adapter: SessionAdapter | None = None
    plan: RestorePlan | None = None
    outcome: AppRestoreOutcome | None = None  # set when decided without running


def _outcome(
    entry: AppEntry,
    status: Status,
    reason: Reason,
    message: str,
    action: ActionKind | None = None,
    details: dict[str, Any] | None = None,
    duration: float | None = None,
) -> AppRestoreOutcome:
    return AppRestoreOutcome(
        instance_id=entry.instance_id,
        adapter_id=entry.adapter.id,
        action=action,
        status=status,
        reason=reason,
        message=message,
        details=details or {},
        duration_seconds=duration,
    )


class RestoreEngine:
    """Plans and runs restores. Only a verified result can be RESTORED."""

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

    # ---- public API -------------------------------------------------

    def preview(
        self,
        session_id: str,
        exclude: Collection[str] = frozenset(),
        duplicate_policy: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> RestorePreview:
        manifest = self.store.load(session_id)
        ctx = self._context(manifest, timeout_seconds, duplicate_policy)
        items = self._plan(manifest, ctx, exclude)
        return RestorePreview(
            session_id=manifest.session.id,
            session_name=manifest.session.name,
            apps=[self._to_preview(item) for item in items],
            warnings=self._warnings(manifest),
        )

    def restore(
        self,
        session_id: str,
        exclude: Collection[str] = frozenset(),
        duplicate_policy: str | None = None,
        timeout_seconds: float = 30.0,
        concurrency: int = 4,
    ) -> RestoreReport:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")

        manifest = self.store.load(session_id)
        started = datetime.now().astimezone()
        self.bus.emit(
            EventKind.RESTORE_STARTED,
            f"Restoring session '{manifest.session.name}'",
            session_id=session_id,
        )

        ctx = self._context(manifest, timeout_seconds, duplicate_policy)
        items = self._plan(manifest, ctx, exclude)

        results: dict[str, AppRestoreOutcome] = {}
        runnable: list[_Item] = []
        for item in items:
            iid = item.entry.instance_id
            if item.outcome is not None:
                results[iid] = item.outcome
                self._announce(item.outcome)
            else:
                self.bus.emit(
                    EventKind.APP_PLANNED,
                    f"Planned {iid}: {item.plan.action.value}",
                    app=iid,
                    action=item.plan.action.value,
                )
                runnable.append(item)

        results.update(self._execute(runnable, ctx, timeout_seconds, concurrency))

        report = RestoreReport(
            session_id=session_id,
            started_at=started,
            finished_at=datetime.now().astimezone(),
            outcomes=[results[entry.instance_id] for entry in manifest.apps],
            warnings=self._warnings(manifest),
        )
        self.bus.emit(
            EventKind.RESTORE_FINISHED,
            f"Finished restoring '{manifest.session.name}'",
            session_id=session_id,
            **report.counts(),
        )
        return report

    # ---- planning ---------------------------------------------------

    def _context(
        self, manifest: Manifest, timeout_seconds: float, policy: str | None
    ) -> RestoreContext:
        chosen = policy or manifest.restore_preferences.duplicate_policy
        if chosen not in get_args(DuplicatePolicy):
            raise ValueError(f"unknown duplicate policy: {chosen!r}")
        return RestoreContext(
            timeout_seconds=timeout_seconds,
            duplicate_policy=chosen,
            processes=self.process_source.snapshot(),
        )

    def _warnings(self, manifest: Manifest) -> list[str]:
        saved = manifest.environment
        current = self._env_provider()
        warnings: list[str] = []
        if (
            saved.session_type != "unknown"
            and current.session_type != "unknown"
            and saved.session_type != current.session_type
        ):
            warnings.append(
                f"Session was saved on {saved.session_type} but the current session is "
                f"{current.session_type}; window placement may not apply."
            )
        if saved.desktop and current.desktop and saved.desktop != current.desktop:
            warnings.append(
                f"Session was saved on {saved.desktop} but the current desktop is "
                f"{current.desktop}."
            )
        return warnings

    def _plan(
        self, manifest: Manifest, ctx: RestoreContext, exclude: Collection[str]
    ) -> list[_Item]:
        return [self._plan_one(entry, ctx, exclude) for entry in manifest.apps]

    def _plan_one(self, entry: AppEntry, ctx: RestoreContext, exclude: Collection[str]) -> _Item:
        iid = entry.instance_id
        aid = entry.adapter.id

        if not entry.included or iid in exclude:
            return _Item(
                entry,
                outcome=_outcome(
                    entry, Status.SKIPPED, Reason.EXCLUDED_BY_USER, "Excluded by user",
                    ActionKind.SKIP,
                ),
            )

        adapter = self.registry.get(aid)
        if adapter is None:
            return _Item(
                entry,
                outcome=_outcome(
                    entry, Status.SKIPPED, Reason.NOT_INSTALLED,
                    f"No adapter registered for {aid!r}", ActionKind.SKIP,
                ),
            )

        if entry.adapter.version > adapter.version:
            return _Item(
                entry,
                adapter,
                outcome=_outcome(
                    entry, Status.SKIPPED, Reason.UNSUPPORTED,
                    f"Saved with adapter version {entry.adapter.version}, "
                    f"installed version is {adapter.version}",
                    ActionKind.SKIP,
                ),
            )

        plan, err = guarded(aid, "plan_restore", adapter.plan_restore, entry, ctx)
        if err is None and not isinstance(plan, RestorePlan):
            err = OpResult.failed(
                Reason.ADAPTER_ERROR,
                f"plan_restore returned {type(plan).__name__}, expected RestorePlan",
                adapter_id=aid,
                operation="plan_restore",
            )
        if err is not None:
            return _Item(
                entry,
                adapter,
                outcome=_outcome(
                    entry, err.status, err.reason, err.message, ActionKind.SKIP, err.details
                ),
            )

        if plan.action is ActionKind.SKIP:
            return _Item(
                entry,
                adapter,
                plan,
                _outcome(
                    entry, Status.SKIPPED, plan.reason, plan.message, ActionKind.SKIP,
                    {
                        "missing_dependencies": list(plan.missing_dependencies),
                        "unavailable_paths": list(plan.unavailable_paths),
                    },
                ),
            )
        return _Item(entry, adapter, plan)

    @staticmethod
    def _to_preview(item: _Item) -> AppPreview:
        entry = item.entry
        if item.plan is not None:
            return AppPreview(
                instance_id=entry.instance_id,
                adapter_id=entry.adapter.id,
                action=item.plan.action,
                reason=item.plan.reason,
                message=item.plan.message,
                missing_dependencies=list(item.plan.missing_dependencies),
                unavailable_paths=list(item.plan.unavailable_paths),
            )
        outcome = item.outcome
        return AppPreview(
            instance_id=entry.instance_id,
            adapter_id=entry.adapter.id,
            action=ActionKind.SKIP,
            reason=outcome.reason,
            message=outcome.message,
        )

    # ---- execution --------------------------------------------------

    def _announce(self, outcome: AppRestoreOutcome) -> None:
        self.bus.emit(
            EventKind.APP_RESULT,
            f"{outcome.instance_id}: {outcome.status.value}",
            app=outcome.instance_id,
            status=outcome.status.value,
            reason=outcome.reason.value,
        )

    def _run_app(
        self, item: _Item, ctx: RestoreContext, started: dict[str, float]
    ) -> AppRestoreOutcome:
        entry, adapter, plan = item.entry, item.adapter, item.plan
        iid = entry.instance_id
        aid = adapter.adapter_id
        t0 = time.monotonic()
        started[iid] = t0
        try:
            self.bus.emit(
                EventKind.APP_RESTORING, f"Restoring {iid}", app=iid, action=plan.action.value
            )
            handle, err = guarded(aid, "restore", adapter.restore, entry, plan, ctx)
            if err is None and not isinstance(handle, RestoreHandle):
                err = OpResult.failed(
                    Reason.ADAPTER_ERROR,
                    f"restore returned {type(handle).__name__}, expected RestoreHandle",
                    adapter_id=aid,
                    operation="restore",
                )
            if err is not None:
                return _outcome(
                    entry, err.status, err.reason, err.message, plan.action, err.details,
                    time.monotonic() - t0,
                )

            result, err = guarded(aid, "verify", adapter.verify, entry, handle, ctx)
            if err is None and not isinstance(result, OpResult):
                err = OpResult.failed(
                    Reason.ADAPTER_ERROR,
                    f"verify returned {type(result).__name__}, expected OpResult",
                    adapter_id=aid,
                    operation="verify",
                )
            if err is not None:
                return _outcome(
                    entry, err.status, err.reason, err.message, plan.action, err.details,
                    time.monotonic() - t0,
                )

            return _outcome(
                entry, result.status, result.reason, result.message, plan.action,
                result.details, time.monotonic() - t0,
            )
        except Exception as exc:  # noqa: BLE001 - isolation boundary, by design
            return _outcome(
                entry, Status.FAILED, Reason.ADAPTER_ERROR,
                f"unexpected error while restoring {iid}: {type(exc).__name__}: {exc}",
                plan.action, None, time.monotonic() - t0,
            )

    def _execute(
        self,
        items: list[_Item],
        ctx: RestoreContext,
        timeout: float,
        concurrency: int,
    ) -> dict[str, AppRestoreOutcome]:
        results: dict[str, AppRestoreOutcome] = {}
        if not items:
            return results

        by_id = {item.entry.instance_id: item for item in items}
        started: dict[str, float] = {}
        timed_out: dict[str, Future] = {}
        pool = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="restore")
        pending: dict[str, Future] = {
            iid: pool.submit(self._run_app, item, ctx, started) for iid, item in by_id.items()
        }
        try:
            while pending:
                now = time.monotonic()
                for iid, future in list(pending.items()):
                    if future.done():
                        outcome = future.result()
                    elif iid in started and now - started[iid] > timeout:
                        outcome = _outcome(
                            by_id[iid].entry, Status.FAILED, Reason.TIMEOUT,
                            f"{iid} did not finish within {timeout}s",
                            by_id[iid].plan.action, {"timeout_seconds": timeout},
                        )
                        timed_out[iid] = future
                    else:
                        continue
                    del pending[iid]
                    results[iid] = outcome
                    self._announce(outcome)

                blocked = sum(1 for f in timed_out.values() if not f.done())
                if blocked >= concurrency:
                    for iid, future in list(pending.items()):
                        if iid not in started and future.cancel():
                            outcome = _outcome(
                                by_id[iid].entry, Status.FAILED, Reason.TIMEOUT,
                                f"{iid} was not started: all restore workers are blocked "
                                "by apps that timed out",
                                by_id[iid].plan.action, {"timeout_seconds": timeout},
                            )
                            del pending[iid]
                            results[iid] = outcome
                            self._announce(outcome)

                if pending:
                    time.sleep(_POLL_SECONDS)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return results
