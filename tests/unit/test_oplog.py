import os
import stat
from datetime import datetime, timezone

import pytest

from session_snapshot.core.oplog import OperationEntry, OperationLog


def _now(offset_seconds: float = 0.0):
    return datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + offset_seconds, tz=timezone.utc
    )


def _entry(kind="save", session_id="s1", offset=0.0, **kwargs):
    start = _now(offset)
    end = _now(offset + 0.1)
    return OperationEntry(
        kind=kind,
        session_id=session_id,
        started_at=start,
        finished_at=end,
        counts=kwargs.pop("counts", {"ok": 1}),
        warnings=kwargs.pop("warnings", []),
        summary=kwargs.pop("summary", "test"),
        **kwargs,
    )


def test_append_and_list_newest_first(tmp_path):
    log = OperationLog(tmp_path)
    log.append(_entry(session_id="older", offset=0.0))
    log.append(_entry(session_id="newer", offset=1.0))
    entries = log.list()
    assert [e.session_id for e in entries] == ["newer", "older"]


def test_get_returns_entry_by_id(tmp_path):
    log = OperationLog(tmp_path)
    entry = _entry()
    log.append(entry)
    fetched = log.get(entry.id)
    assert fetched is not None
    assert fetched.id == entry.id
    assert fetched.session_id == entry.session_id


def test_get_returns_none_for_missing_id(tmp_path):
    log = OperationLog(tmp_path)
    log.append(_entry())
    assert log.get("nonexistent") is None


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        OperationEntry(
            kind="save",
            session_id="s",
            started_at=datetime(2026, 1, 1),  # naive
            finished_at=datetime.now(timezone.utc),
        )


def test_file_and_directory_permissions(tmp_path):
    log = OperationLog(tmp_path / "opdata")
    log.append(_entry())
    file_mode = stat.S_IMODE(os.stat(log.path).st_mode)
    dir_mode = stat.S_IMODE(os.stat(tmp_path / "opdata").st_mode)
    assert file_mode == 0o600
    assert dir_mode == 0o700


def test_corrupt_lines_are_skipped(tmp_path):
    log = OperationLog(tmp_path)
    log.append(_entry(session_id="good"))
    with open(log.path, "a") as f:
        f.write("not json at all\n")
        f.write("{}\n")
        f.write("")
    entries = log.list()
    assert len(entries) == 1
    assert entries[0].session_id == "good"


def test_list_respects_limit(tmp_path):
    log = OperationLog(tmp_path)
    for i in range(5):
        log.append(_entry(session_id=f"s{i}", offset=float(i)))
    entries = log.list(limit=2)
    assert len(entries) == 2
    assert [e.session_id for e in entries] == ["s4", "s3"]


def test_list_empty_when_file_missing(tmp_path):
    log = OperationLog(tmp_path / "empty")
    assert log.list() == []