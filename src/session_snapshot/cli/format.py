"""Human-readable formatting for CLI output.

Kept separate from main.py so it can be unit-tested without argparse.
The mutation-command formatters (save report, preview, restore report)
land in a later round alongside the commands that use them.
"""

from __future__ import annotations

import os
import platform
import shutil
from datetime import datetime

from session_snapshot.models.manifest import Manifest
from session_snapshot.models.summaries import AdapterInfo, SessionList
from session_snapshot.services.session_service import SessionService


def _ts(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def format_session_list(sl: SessionList) -> str:
    lines: list[str] = []
    if not sl.sessions:
        lines.append("No saved sessions.")
    else:
        lines.append(
            f"{'ID':<24} {'NAME':<28} {'SAVED':<24} {'APPS':>4}  "
            f"{'DESKTOP':<8}  TYPE"
        )
        for s in sl.sessions:
            lines.append(
                f"{s.session_id:<24} {s.name[:27]:<28} {_ts(s.saved_at):<24} "
                f"{s.app_count:>4}  {(s.desktop or '-'):<8}  {s.session_type}"
            )
    if sl.problems:
        lines.append("")
        lines.append("Problems:")
        for p in sl.problems:
            lines.append(f"  {p.session_id}: {p.message}")
    return "\n".join(lines)


def format_manifest(m: Manifest) -> str:
    lines = [
        f"Session : {m.session.name}  ({m.session.id})",
        f"Saved   : {_ts(m.session.saved_at)}",
        f"Desktop : {m.environment.desktop or '-'} / "
        f"{m.environment.session_type}",
        f"Apps    : {len(m.apps)}",
    ]
    if m.session.description:
        lines.append(f"About   : {m.session.description}")
    if m.apps:
        lines.append("")
        for i, app in enumerate(m.apps, 1):
            state_bits = " ".join(f"{k}={v}" for k, v in app.state.items()) or "-"
            lines.append(
                f"  {i}. {app.instance_id:<24} adapter={app.adapter.id} "
                f"v{app.adapter.version}  {state_bits}"
            )
    if m.unsupported:
        lines.append("")
        lines.append(f"Unsupported: {len(m.unsupported)}")
        for u in m.unsupported:
            lines.append(f"  - {u.app_name}: {u.message or u.reason}")
    return "\n".join(lines)


def format_adapters(infos: list[AdapterInfo]) -> str:
    if not infos:
        return "No adapters registered."
    lines = [f"{'ID':<24} {'VER':>3} {'CLS':>3}  CAPABILITIES / ERROR"]
    for a in infos:
        if a.error:
            detail = f"ERROR: {a.error}"
        else:
            detail = (
                "; ".join(
                    f"{c.name}{'' if c.supported else ' (unsupported)'}"
                    for c in a.capabilities
                )
                or "-"
            )
        lines.append(
            f"{a.adapter_id:<24} {a.version:>3} "
            f"{a.compatibility_class:>3}  {detail}"
        )
    return "\n".join(lines)


def format_doctor(service: SessionService) -> str:
    env = (
        f"OS       : {platform.system()} {platform.release()}"
        f"\nPython   : {platform.python_version()}"
        f"\nDesktop  : {os.environ.get('XDG_CURRENT_DESKTOP', '-') or '-'}"
        f"\nSession  : {os.environ.get('XDG_SESSION_TYPE', '-') or '-'}"
        f"\nDisplay  : {os.environ.get('DISPLAY', '-') or '-'}"
        f"\nWayland  : {os.environ.get('WAYLAND_DISPLAY', '-') or '-'}"
    )
    store_root = getattr(getattr(service, "store", None), "root", None)
    store_bits = f"Store    : {store_root if store_root else '(default)'}"

    bin_lines: list[str] = []
    for exe in ("xfce4-terminal", "wmctrl", "xprop", "xdotool", "tmux"):
        path = shutil.which(exe)
        bin_lines.append(f"  {exe:<16} {path or 'NOT FOUND'}")

    ad_lines = [f"{'ID':<24} {'VER':>3} {'CLS':>3}  STATUS"]
    for a in service.adapters():
        status = f"error: {a.error}" if a.error else "ok"
        ad_lines.append(
            f"{a.adapter_id:<24} {a.version:>3} "
            f"{a.compatibility_class:>3}  {status}"
        )

    return "\n\n".join(
        [
            "Environment\n" + env,
            store_bits,
            "Executables\n" + "\n".join(bin_lines),
            "Adapters\n" + "\n".join(ad_lines),
        ]
    )
