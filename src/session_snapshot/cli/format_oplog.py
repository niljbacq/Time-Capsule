"""Formatting for operation-log entries (used by `sessionctl report`)."""

from __future__ import annotations

from datetime import datetime

from session_snapshot.core.oplog import OperationEntry


def _when(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "-"


def format_oplog_list(entries: list[OperationEntry]) -> str:
    if not entries:
        return "No operations recorded yet."
    lines = [f"{'ID':<10} {'KIND':<8} {'SESSION':<20} {'FINISHED':<19}  COUNTS"]
    for e in entries:
        lines.append(
            f"{e.id[:8]:<10} {e.kind:<8} {e.session_id:<20} "
            f"{_when(e.finished_at):<19}  {_counts(e.counts)}"
        )
    return "\n".join(lines)


def format_oplog_entry(entry: OperationEntry) -> str:
    seconds = (entry.finished_at - entry.started_at).total_seconds()
    lines = [
        f"Operation : {entry.id}",
        f"Kind      : {entry.kind}",
        f"Session   : {entry.session_id}",
        f"Started   : {_when(entry.started_at)}",
        f"Finished  : {_when(entry.finished_at)}",
        f"Duration  : {seconds:.2f}s",
        f"Summary   : {entry.summary or '-'}",
        f"Counts    : {_counts(entry.counts)}",
    ]
    if entry.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {w}" for w in entry.warnings)
    return "\n".join(lines)