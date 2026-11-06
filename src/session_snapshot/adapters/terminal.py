"""xfce4-terminal adapter (Class 2 — Observable).

Captures interactive shell working directories from a single xfce4-terminal
server process and restores them by asking the server (or a new instance)
to open a window with --working-directory.

Limitations (reported via capabilities(), not hidden):
  * Window/tab grouping is not captured; each saved cwd opens its own window.
  * Shell history, environment, running jobs and scrollback are not restored.
  * verify() checks that a shell with the expected cwd exists; it cannot prove
    the shell is the one we launched (the launching client exits immediately
    after handing off to the running D-Bus server).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterator

import psutil

from session_snapshot.adapters.base import AdapterError, SessionAdapter
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
from session_snapshot.models.results import Capability, OpResult, Reason

_TERMINAL_NAME = "xfce4-terminal"
_TERMINAL_APP_ID = "xfce4-terminal.desktop"
_INTERACTIVE_SHELLS = frozenset({"bash", "zsh", "sh", "dash", "ksh", "fish"})
_VERIFY_TIMEOUT_SECONDS = 3.0
_VERIFY_POLL_SECONDS = 0.15


def _iter_shell_cwds() -> Iterator[tuple[int, str]]:
    """Yield (pid, cwd) for interactive shells that are direct children of any
    xfce4-terminal server owned by the current user.

    Used at verification time, when a fresh view of the process tree is needed.
    Detection and planning use the snapshot in DiscoveryContext / RestoreContext
    instead; only verify needs this live scan because ctx.processes is captured
    at planning time and does not include shells launched by the restore.
    """
    uid = os.getuid()
    servers: set[int] = set()
    for proc in psutil.process_iter(["pid", "name", "uids"]):
        try:
            info = proc.info
            uids = info.get("uids")
            if uids is None or uids.real != uid:
                continue
            if info.get("name") == _TERMINAL_NAME:
                servers.add(info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not servers:
        return
    for proc in psutil.process_iter(["pid", "ppid", "name", "uids"]):
        try:
            info = proc.info
            uids = info.get("uids")
            if uids is None or uids.real != uid:
                continue
            if info.get("ppid") not in servers:
                continue
            if info.get("name") not in _INTERACTIVE_SHELLS:
                continue
            cwd = proc.cwd()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        yield proc.pid, cwd


class TerminalAdapter(SessionAdapter):
    adapter_id = "terminal_xfce4"
    version = 1
    compatibility_class = 2

    # ------------------------------------------------------------------ meta

    def capabilities(self) -> list[Capability]:
        return [
            Capability(name="shell_cwd", supported=True),
            Capability(
                name="window_grouping",
                supported=False,
                limitation="window/tab grouping is not captured; each saved cwd opens its own window",
            ),
            Capability(
                name="shell_state",
                supported=False,
                limitation="shell history, environment, jobs and scrollback are not restored",
            ),
        Capability(
            name="window_placement",
            supported=False,
            limitation=(
                "terminal windows are owned by a shared server process; "
                "placement works only when no server is already running, "
                "which cannot be guaranteed at restore time"
            ),
        ),
    ]

    # ---------------------------------------------------------------- detect

    def detect(self, ctx: DiscoveryContext) -> list[AppInstance]:
        if shutil.which(_TERMINAL_NAME) is None:
            return []
        server_pids = {p.pid for p in ctx.processes if p.name == _TERMINAL_NAME}
        if not server_pids:
            return []
        result: list[AppInstance] = []
        for proc in ctx.processes:
            if proc.ppid not in server_pids:
                continue
            if proc.name not in _INTERACTIVE_SHELLS:
                continue
            if not proc.cwd:
                continue
            result.append(
                AppInstance(
                    instance_id=f"terminal-{proc.pid}",
                    adapter_id=self.adapter_id,
                    pid=proc.pid,
                    app_id=_TERMINAL_APP_ID,
                    label=proc.cwd.rsplit("/", 1)[-1] or "/",
                )
            )
        return result

    # --------------------------------------------------------------- capture

    def capture(self, instance: AppInstance, ctx: CaptureContext) -> AppEntry:
        proc = next((p for p in ctx.processes if p.pid == instance.pid), None)
        if proc is None or not proc.cwd:
            raise AdapterError(
                Reason.PATH_MISSING,
                f"process {instance.pid} is no longer visible; cannot read cwd",
                pid=instance.pid,
            )
        executable = shutil.which(_TERMINAL_NAME)
        if executable is None:
            raise AdapterError(
                Reason.NOT_INSTALLED,
                f"{_TERMINAL_NAME} is not on PATH",
            )
        cwd = proc.cwd
        return AppEntry.model_validate(
            {
                "instance_id": instance.instance_id,
                "app_id": instance.app_id or _TERMINAL_APP_ID,
                "adapter": {"id": self.adapter_id, "version": self.version},
                "compatibility_class": self.compatibility_class,
                "launch": {
                    "type": "argv",
                    "executable": executable,
                    "args": ["--window", "--working-directory", cwd],
                },
                "state": {"cwd": cwd},
                "capture": {
                    "status": "captured",
                    "capabilities": [{"name": "shell_cwd", "captured": True}],
                },
            }
        )

    # ---------------------------------------------------------- plan_restore

    def plan_restore(self, snapshot: AppEntry, ctx: RestoreContext) -> RestorePlan:
        cwd = snapshot.state.get("cwd")
        if not cwd:
            return RestorePlan(
                action=ActionKind.SKIP,
                reason=Reason.VERIFY_MISMATCH,
                message="saved terminal has no cwd; nothing to restore",
            )
        if shutil.which(_TERMINAL_NAME) is None:
            return RestorePlan(
                action=ActionKind.SKIP,
                reason=Reason.NOT_INSTALLED,
                message=f"{_TERMINAL_NAME} is not on PATH",
                missing_dependencies=[_TERMINAL_NAME],
            )
        if not os.path.isdir(cwd):
            return RestorePlan(
                action=ActionKind.SKIP,
                reason=Reason.PATH_MISSING,
                message=f"directory {cwd!r} no longer exists",
                unavailable_paths=[cwd],
            )
        if ctx.duplicate_policy == "skip_if_running":
            for proc in ctx.processes:
                if proc.name in _INTERACTIVE_SHELLS and proc.cwd == cwd:
                    return RestorePlan(
                        action=ActionKind.SKIP,
                        reason=Reason.ALREADY_RUNNING,
                        message=f"a shell in {cwd} is already running",
                    )
        return RestorePlan(
            action=ActionKind.LAUNCH,
            reason=Reason.OK,
            message=f"open a terminal window in {cwd}",
        )

    # --------------------------------------------------------------- restore

    def restore(
        self, snapshot: AppEntry, plan: RestorePlan, ctx: RestoreContext
    ) -> RestoreHandle:
        launch = snapshot.launch
        try:
            proc = subprocess.Popen(
                [launch.executable, *launch.args],
                close_fds=True,
                start_new_session=True,
            )
        except OSError as exc:
            raise AdapterError(
                Reason.ADAPTER_ERROR,
                f"failed to launch {launch.executable}: {exc}",
            ) from exc
        return RestoreHandle(
            instance_id=snapshot.instance_id,
            pid=proc.pid,
            launched_at=time.time(),
        )

    # ---------------------------------------------------------------- verify

    def verify(
        self, snapshot: AppEntry, handle: RestoreHandle, ctx: RestoreContext
    ) -> OpResult:
        expected_cwd = snapshot.state.get("cwd")
        if not expected_cwd:
            return OpResult.failed(
                Reason.VERIFY_MISMATCH,
                "snapshot has no cwd to verify",
            )
        deadline = time.monotonic() + _VERIFY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            for _pid, cwd in _iter_shell_cwds():
                if cwd == expected_cwd:
                    return OpResult.restored(
                        f"shell with cwd {expected_cwd} is running",
                        cwd=expected_cwd,
                    )
            time.sleep(_VERIFY_POLL_SECONDS)
        return OpResult.partial(
            Reason.TIMEOUT,
            f"no shell with cwd {expected_cwd} appeared within "
            f"{_VERIFY_TIMEOUT_SECONDS}s",
            cwd=expected_cwd,
        )
