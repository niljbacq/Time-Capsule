"""Pure planning for window placement after a restore. No X calls."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from session_snapshot.models.adapter_types import ProcessInfo
from session_snapshot.models.manifest import Geometry, WindowEntry
from session_snapshot.windows.base import LiveWindow
from session_snapshot.windows.matching import owner_pid_for


@dataclass(frozen=True)
class Placement:
    """What to do to one live window."""

    window_id: str
    workspace: int | None
    state: Literal["normal", "maximized", "fullscreen"]
    geometry: Geometry | None


def _id_key(window_id: str) -> int:
    try:
        return int(window_id, 16)
    except ValueError:
        return 0


def candidate_windows(
    pid: int, processes: Sequence[ProcessInfo], windows: Sequence[LiveWindow]
) -> list[LiveWindow]:
    """Normal windows owned by pid or by one of its ancestors."""
    by_pid: dict[int, list[LiveWindow]] = {}
    for w in windows:
        if w.window_type == "normal" and w.pid is not None:
            by_pid.setdefault(w.pid, []).append(w)
    parents = {p.pid: p.ppid for p in processes}
    owner = owner_pid_for(pid, parents, by_pid.keys())
    return list(by_pid[owner]) if owner is not None else []


def plan_placements(
    saved: Sequence[WindowEntry], candidates: Sequence[LiveWindow]
) -> tuple[list[Placement], list[str]]:
    """Pair saved windows with live ones in window-id order.

    Pairs only when the counts are equal. Otherwise nothing is placed and a
    warning explains why: a wrong placement is worse than none.
    """
    if not saved:
        return [], []
    if len(saved) != len(candidates):
        return [], [
            f"expected {len(saved)} window(s) but found {len(candidates)}; "
            "window placement skipped"
        ]
    pairs = zip(
        sorted(saved, key=lambda s: _id_key(s.window_id)),
        sorted(candidates, key=lambda c: _id_key(c.window_id)),
    )
    placements = [
        Placement(
            window_id=live.window_id,
            workspace=entry.workspace,
            state=entry.state,
            geometry=entry.geometry if entry.state == "normal" else None,
        )
        for entry, live in pairs
    ]
    return placements, []