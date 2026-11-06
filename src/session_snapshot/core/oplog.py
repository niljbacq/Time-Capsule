"""Persistent log of completed save and restore operations.

One JSON object per line (JSONL) under an app-data directory. The log is
written by SessionService after each operation completes. It is an
append-only file; existing entries are never modified in place.

The oplog exists so that the Reports screen (Phase 7) and `sessionctl
report` can display operation history without re-reading every manifest.
It is bounded by a max_entries retention policy applied on read.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OperationEntry(_Strict):
    """One completed save or restore operation."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    kind: Literal["save", "restore"]
    session_id: str
    started_at: datetime
    finished_at: datetime
    counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("started_at", "finished_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return v


class OperationLog:
    """Append-only JSONL store of OperationEntry records under a directory."""

    def __init__(self, root: Path, max_entries: int = 500) -> None:
        self.root = root
        self.path = root / "oplog.jsonl"
        self.max_entries = max_entries

    def _ensure_dir(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def append(self, entry: OperationEntry) -> None:
        """Append one entry. Creates the file with mode 0600 on first write.

        Raises OSError only for filesystem failures. The write is a single
        line (well under PIPE_BUF), so concurrent appends from separate
        processes do not interleave.
        """
        self._ensure_dir()
        line = entry.model_dump_json() + "\n"
        fd = os.open(
            self.path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,
        )
        with os.fdopen(fd, "a") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def list(self, limit: int = 50) -> list[OperationEntry]:
        """Return up to `limit` entries, newest first by finished_at.

        Malformed lines are skipped. If the file does not exist, returns [].
        """
        if not self.path.is_file():
            return []
        try:
            text = self.path.read_text(errors="replace")
        except OSError:
            return []
        entries: list[OperationEntry] = []
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                entries.append(OperationEntry.model_validate_json(raw))
            except Exception:  # noqa: BLE001 - corrupt line, skip
                continue
        entries.sort(key=lambda e: e.finished_at, reverse=True)
        return entries[:limit]

    def get(self, entry_id: str) -> OperationEntry | None:
        """Return the entry with the given id, or None."""
        for entry in self.list(limit=self.max_entries):
            if entry.id == entry_id:
                return entry
        return None