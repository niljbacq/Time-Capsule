"""Apply saved window placement to a freshly restored app."""

import time
from collections.abc import Callable, Sequence

from session_snapshot.models.adapter_types import ProcessInfo
from session_snapshot.models.manifest import WindowEntry
from session_snapshot.windows.base import WindowBackend
from session_snapshot.windows.placement import candidate_windows, plan_placements


def apply_saved_windows(
    backend: WindowBackend,
    snapshot: Callable[[], Sequence[ProcessInfo]],
    pid: int,
    saved: Sequence[WindowEntry],
    wait_seconds: float = 3.0,
    poll_seconds: float = 0.2,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[int, list[str]]:
    """Place a restored app's windows. Returns (windows placed, warnings).

    Waits up to wait_seconds for the app's windows to appear. Never raises:
    placement is cosmetic and must not break a restore.
    """
    if not saved:
        return 0, []
    try:
        deadline = clock() + wait_seconds
        while True:
            candidates = candidate_windows(pid, snapshot(), backend.list_windows())
            if len(candidates) >= len(saved) or clock() >= deadline:
                break
            sleep(poll_seconds)
        placements, warnings = plan_placements(saved, candidates)
        for p in placements:
            warnings.extend(
                backend.place_window(p.window_id, p.workspace, p.state, p.geometry)
            )
    except Exception as exc:  # noqa: BLE001 - placement must never break a restore
        return 0, [f"window placement failed: {type(exc).__name__}: {exc}"]
    return len(placements), warnings