"""Pure helpers that match live windows to app instances. No X calls."""

from collections.abc import Collection, Mapping, Sequence

from session_snapshot.models.adapter_types import ProcessInfo
from session_snapshot.models.manifest import WindowEntry, WindowHint
from session_snapshot.windows.base import LiveWindow


def owner_pid_for(
    pid: int, parents: Mapping[int, int | None], owners: Collection[int]
) -> int | None:
    """Walk from pid up through its parents; return the first pid in owners."""
    seen: set[int] = set()
    current: int | None = pid
    while current is not None and current not in seen and len(seen) < 64:
        if current in owners:
            return current
        seen.add(current)
        current = parents.get(current)
    return None


def to_window_entry(window: LiveWindow) -> WindowEntry:
    return WindowEntry(
        window_id=window.window_id,
        hint=WindowHint(wm_class=window.wm_class),
        workspace=window.workspace,
        state=window.state,
        geometry=window.geometry,
    )


def match_windows(
    instances: Sequence[tuple[str, int | None]],
    processes: Sequence[ProcessInfo],
    windows: Sequence[LiveWindow],
) -> tuple[dict[str, list[WindowEntry]], list[str]]:
    """Match (instance_id, pid) pairs to normal windows by process ancestry.

    Returns (windows per instance_id, warnings). If several instances share one
    window-owning process, none of them gets windows and a warning is returned.
    """
    by_pid: dict[int, list[LiveWindow]] = {}
    for w in windows:
        if w.window_type == "normal" and w.pid is not None:
            by_pid.setdefault(w.pid, []).append(w)

    parents = {p.pid: p.ppid for p in processes}
    claimed: dict[int, list[str]] = {}
    for instance_id, pid in instances:
        if pid is None:
            continue
        owner = owner_pid_for(pid, parents, by_pid.keys())
        if owner is not None:
            claimed.setdefault(owner, []).append(instance_id)

    result: dict[str, list[WindowEntry]] = {}
    warnings: list[str] = []
    for owner, instance_ids in claimed.items():
        if len(instance_ids) == 1:
            result[instance_ids[0]] = [to_window_entry(w) for w in by_pid[owner]]
        else:
            warnings.append(
                f"{len(instance_ids)} instances share window owner pid {owner}; "
                f"window placement skipped for: {', '.join(sorted(instance_ids))}"
            )
    return result, warnings
