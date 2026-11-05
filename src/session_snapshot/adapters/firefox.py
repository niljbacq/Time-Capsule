"""Firefox adapter (Class 1 — Native).

Coordinates Firefox's own session restoration. This adapter does NOT
manipulate Firefox's session store, cookies, logins, or form history. It
reads one preference (browser.startup.page) from prefs.js to decide
whether session restore is enabled, then launches Firefox with the saved
profile. Firefox itself does the tab restoration.

Verification limitation: this adapter can prove Firefox launched, but it
cannot prove tabs were restored. The skip_if_running duplicate policy is
the honest mitigation.
"""

from __future__ import annotations

import configparser
import re
import shutil
import subprocess
import time
from pathlib import Path

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

_FIREFOX_NAME = "firefox"
_FIREFOX_APP_ID = "firefox.desktop"
_STARTUP_PAGE_RESTORE = 3
_VERIFY_TIMEOUT_SECONDS = 5.0
_VERIFY_POLL_SECONDS = 0.15
_CLOCK_FUZZ_SECONDS = 2.0


_MAIN_NAMES = frozenset({"firefox", "firefox-bin"})


def _is_firefox_main(name: str, argv: list[str] | None) -> bool:
    if name not in _MAIN_NAMES:
        return False
    argv = argv or []
    # Firefox children are named variously ("Web Content", "RDD Process",
    # "forkserver", "Socket Process", etc.) but all of them carry
    # -parentPid in argv. The main process does not. This is more reliable
    # than looking for -contentproc alone, which misses socket/rdd helpers.
    if any(arg == "-parentPid" for arg in argv):
        return False
    if any("contentproc" in arg for arg in argv):
        return False
    return True


def _find_firefox_dir() -> Path | None:
    candidate = Path.home() / ".mozilla" / "firefox"
    return candidate if candidate.is_dir() else None


def _resolve_default_profile(firefox_dir: Path) -> Path | None:
    ini = firefox_dir / "profiles.ini"
    if not ini.is_file():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(ini)
    except configparser.Error:
        return None
    for section in parser.sections():
        if section.startswith("Install") and parser.has_option(
            section, "Default"
        ):
            candidate = firefox_dir / parser.get(section, "Default")
            if candidate.is_dir():
                return candidate
    for section in parser.sections():
        if not section.startswith("Profile"):
            continue
        if not parser.has_option(section, "Path"):
            continue
        if parser.get(section, "Default", fallback="0") != "1":
            continue
        path = parser.get(section, "Path")
        is_relative = parser.get(section, "IsRelative", fallback="1") == "1"
        return (firefox_dir / path) if is_relative else Path(path)
    return None


def _read_startup_page(profile_dir: Path) -> int | None:
    prefs = profile_dir / "prefs.js"
    if not prefs.is_file():
        return None
    try:
        text = prefs.read_text(errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if "browser.startup.page" not in line:
            continue
        m = re.search(r'"browser\.startup\.page"\s*,\s*(\d+)\s*\)', line)
        if m:
            return int(m.group(1))
    return None


def _live_firefox_pids() -> list[tuple[int, float]]:
    result: list[tuple[int, float]] = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            info = p.info
            if not _is_firefox_main(
                info.get("name", ""), info.get("cmdline") or []
            ):
                continue
            ctime = info.get("create_time")
            if ctime is None:
                ctime = p.create_time()
            result.append((info["pid"], ctime))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


class FirefoxAdapter(SessionAdapter):
    adapter_id = "browser_firefox"
    version = 1
    compatibility_class = 1

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                name="session_restore",
                supported=True,
                limitation=(
                    "requires browser.startup.page=3 (restore previous "
                    "session) in the target profile; verification confirms "
                    "Firefox launched, not that tabs were restored"
                ),
            ),
            Capability(
                name="tabs_content",
                supported=False,
                limitation=(
                    "tab contents are managed by Firefox and not captured"
                ),
            ),
            Capability(
                name="profile_secrets",
                supported=False,
                limitation=(
                    "cookies, logins, form history and places are never "
                    "captured or modified by this adapter"
                ),
            ),
            Capability(
                name="already_running_verification",
                supported=False,
                limitation=(
                    "if Firefox was already running, this adapter cannot "
                    "distinguish 'opened a window' from 'reused the "
                    "existing instance'"
                ),
            ),
        ]

    def detect(self, ctx: DiscoveryContext) -> list[AppInstance]:
        if shutil.which(_FIREFOX_NAME) is None:
            return []
        label = ""
        firefox_dir = _find_firefox_dir()
        if firefox_dir is not None:
            profile = _resolve_default_profile(firefox_dir)
            if profile is not None:
                label = profile.name
        result: list[AppInstance] = []
        for proc in ctx.processes:
            if not _is_firefox_main(proc.name, proc.argv):
                continue
            result.append(
                AppInstance(
                    instance_id=f"firefox-{proc.pid}",
                    adapter_id=self.adapter_id,
                    pid=proc.pid,
                    app_id=_FIREFOX_APP_ID,
                    label=label,
                )
            )
        return result

    def capture(
        self, instance: AppInstance, ctx: CaptureContext
    ) -> AppEntry:
        proc = next(
            (p for p in ctx.processes if p.pid == instance.pid), None
        )
        if proc is None:
            raise AdapterError(
                Reason.PATH_MISSING,
                f"firefox process {instance.pid} is no longer visible",
                pid=instance.pid,
            )
        executable = shutil.which(_FIREFOX_NAME)
        if executable is None:
            raise AdapterError(
                Reason.NOT_INSTALLED, "firefox is not on PATH"
            )

        profile_path: Path | None = None
        argv = proc.argv or []
        for i, arg in enumerate(argv):
            if arg == "--profile" and i + 1 < len(argv):
                profile_path = Path(argv[i + 1]).expanduser()
                break
            if arg.startswith("--profile="):
                profile_path = Path(arg.split("=", 1)[1]).expanduser()
                break
        if profile_path is None:
            firefox_dir = _find_firefox_dir()
            if firefox_dir is not None:
                profile_path = _resolve_default_profile(firefox_dir)
        if profile_path is None:
            raise AdapterError(
                Reason.PATH_MISSING,
                "could not resolve Firefox profile directory",
            )

        startup_page = _read_startup_page(profile_path)
        return AppEntry.model_validate(
            {
                "instance_id": instance.instance_id,
                "app_id": _FIREFOX_APP_ID,
                "adapter": {"id": self.adapter_id, "version": self.version},
                "compatibility_class": self.compatibility_class,
                "launch": {
                    "type": "argv",
                    "executable": executable,
                    "args": ["--profile", str(profile_path)],
                },
                "state": {
                    "profile_path": str(profile_path),
                    "browser_startup_page": startup_page,
                },
                "capture": {
                    "status": "captured",
                    "capabilities": [
                        {"name": "session_restore", "captured": True},
                    ],
                },
            }
        )

    def plan_restore(
        self, snapshot: AppEntry, ctx: RestoreContext
    ) -> RestorePlan:
        executable = shutil.which(_FIREFOX_NAME)
        if executable is None:
            return RestorePlan(
                action=ActionKind.SKIP,
                reason=Reason.NOT_INSTALLED,
                message="firefox is not on PATH",
                missing_dependencies=["firefox"],
            )
        profile_path = snapshot.state.get("profile_path")
        if not profile_path or not Path(profile_path).is_dir():
            return RestorePlan(
                action=ActionKind.SKIP,
                reason=Reason.PATH_MISSING,
                message=f"Firefox profile {profile_path!r} not found",
                unavailable_paths=[profile_path] if profile_path else [],
            )
        startup_page = snapshot.state.get("browser_startup_page")
        if startup_page != _STARTUP_PAGE_RESTORE:
            hint = (
                f"browser.startup.page={startup_page}"
                if startup_page is not None
                else "browser.startup.page is unset (defaults to 1)"
            )
            return RestorePlan(
                action=ActionKind.SKIP,
                reason=Reason.UNSUPPORTED,
                message=(
                    "Firefox session restore is not enabled "
                    f"({hint}). Set browser.startup.page=3 in "
                    "about:config to enable."
                ),
            )
        if ctx.duplicate_policy == "skip_if_running":
            for proc in ctx.processes:
                if _is_firefox_main(proc.name, proc.argv):
                    return RestorePlan(
                        action=ActionKind.SKIP,
                        reason=Reason.ALREADY_RUNNING,
                        message="Firefox is already running",
                    )
        return RestorePlan(
            action=ActionKind.LAUNCH,
            reason=Reason.OK,
            message=f"launch Firefox with profile {profile_path}",
        )

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

    def verify(
        self, snapshot: AppEntry, handle: RestoreHandle, ctx: RestoreContext
    ) -> OpResult:
        launched_at = handle.launched_at or 0.0
        threshold = launched_at - _CLOCK_FUZZ_SECONDS
        deadline = time.monotonic() + _VERIFY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            for pid, ctime in _live_firefox_pids():
                if ctime >= threshold:
                    return OpResult.restored(
                        f"Firefox process {pid} is running", pid=pid
                    )
            time.sleep(_VERIFY_POLL_SECONDS)
        return OpResult.partial(
            Reason.TIMEOUT,
            f"no Firefox process appeared within "
            f"{_VERIFY_TIMEOUT_SECONDS}s",
        )
