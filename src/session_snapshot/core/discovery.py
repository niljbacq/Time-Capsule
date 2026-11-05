import os
from typing import Protocol

import psutil

from session_snapshot.models.adapter_types import ProcessInfo


class ProcessSource(Protocol):
    def snapshot(self) -> tuple[ProcessInfo, ...]: ...


class PsutilProcessSource:
    """Lists the current user's processes using psutil (which reads /proc)."""

    _ATTRS = ["pid", "ppid", "name", "exe", "cmdline", "cwd", "uids"]

    def snapshot(self) -> tuple[ProcessInfo, ...]:
        my_uid = os.getuid()
        found: list[ProcessInfo] = []
        for proc in psutil.process_iter(self._ATTRS):
            try:
                info = proc.info
                uids = info.get("uids")
                if uids is None or uids.real != my_uid:
                    continue
                if not info.get("name"):
                    continue
                found.append(
                    ProcessInfo(
                        pid=info["pid"],
                        ppid=info.get("ppid"),
                        name=info["name"],
                        exe=info.get("exe"),
                        argv=list(info.get("cmdline") or []),
                        cwd=info.get("cwd"),
                    )
                )
            except psutil.Error:
                continue
        return tuple(found)
