from datetime import datetime, timedelta, timezone

from session_snapshot.cli.format_oplog import format_oplog_entry, format_oplog_list
from session_snapshot.core.oplog import OperationEntry

START = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
FULL_ID = "abcdef0123456789abcdef0123456789"


def entry(kind="save", counts=None, warnings=None, eid=FULL_ID):
    return OperationEntry(
        id=eid,
        kind=kind,
        session_id="study",
        started_at=START,
        finished_at=START + timedelta(seconds=2.5),
        counts=counts or {},
        warnings=warnings or [],
        summary="Saved session 'study' (2 apps)",
    )


def test_list_empty():
    assert "No operations" in format_oplog_list([])


def test_list_rows_show_short_id_kind_and_counts():
    text = format_oplog_list(
        [
            entry(counts={"captured": 2, "failed": 0}),
            entry(kind="restore", eid="1111111122222222" * 2),
        ]
    )
    assert "KIND" in text
    assert "abcdef01" in text
    assert FULL_ID not in text
    assert "restore" in text
    assert "captured=2" in text
    assert "failed=0" in text


def test_entry_detail_shows_everything():
    text = format_oplog_entry(entry(counts={"captured": 2}, warnings=["w one"]))
    assert FULL_ID in text
    assert "study" in text
    assert "2.50s" in text
    assert "captured=2" in text
    assert "Warnings:" in text
    assert "  - w one" in text


def test_entry_without_warnings_or_counts():
    text = format_oplog_entry(entry())
    assert "Warnings:" not in text
    assert "Counts    : -" in text