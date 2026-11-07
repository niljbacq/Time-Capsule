import json
from datetime import datetime, timedelta, timezone

from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.cli.main import main
from session_snapshot.core.oplog import OperationEntry
from session_snapshot.services.session_service import SessionService
from session_snapshot.store.manifests import ManifestStore
from tests.fakes.fake_process_source import FakeProcessSource

START = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
ID_A = "aaaa" + "0" * 28
ID_B = "aaaa" + "1" * 28
ID_C = "bbbb" + "2" * 28


def entry(eid, minutes, kind="save"):
    return OperationEntry(
        id=eid,
        kind=kind,
        session_id="study",
        started_at=START + timedelta(minutes=minutes),
        finished_at=START + timedelta(minutes=minutes, seconds=2),
        counts={"captured": 1},
        summary=f"summary {eid[:4]}",
    )


def install(monkeypatch, tmp_path, entries=()):
    service = SessionService(
        AdapterRegistry(), ManifestStore(tmp_path), FakeProcessSource(())
    )
    for e in entries:
        service._oplog.append(e)
    monkeypatch.setattr(
        "session_snapshot.cli.main.SERVICE_FACTORY", lambda *a, **kw: service
    )


def three(monkeypatch, tmp_path):
    install(
        monkeypatch,
        tmp_path,
        [entry(ID_A, 0), entry(ID_B, 1, "restore"), entry(ID_C, 2)],
    )


def test_list_empty(monkeypatch, tmp_path, capsys):
    install(monkeypatch, tmp_path)
    assert main(["report", "list"]) == 0
    assert "No operations" in capsys.readouterr().out


def test_list_shows_newest_first(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report", "list"]) == 0
    out = capsys.readouterr().out
    assert out.index("bbbb2222") < out.index("aaaa1111") < out.index("aaaa0000")


def test_latest_shows_newest_in_detail(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report", "latest"]) == 0
    out = capsys.readouterr().out
    assert ID_C in out
    assert ID_A not in out


def test_default_target_is_latest(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report"]) == 0
    assert ID_C in capsys.readouterr().out


def test_full_id(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report", ID_B]) == 0
    out = capsys.readouterr().out
    assert ID_B in out
    assert "restore" in out


def test_unique_prefix(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report", "bbbb"]) == 0
    assert ID_C in capsys.readouterr().out


def test_unknown_id_returns_2(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report", "zzzz"]) == 2
    assert "no operation matches" in capsys.readouterr().err


def test_ambiguous_prefix_returns_2(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report", "aaaa"]) == 2
    assert "ambiguous" in capsys.readouterr().err


def test_list_json(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report", "list", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["id"] for d in data] == [ID_C, ID_B, ID_A]


def test_latest_json_and_empty_json(monkeypatch, tmp_path, capsys):
    three(monkeypatch, tmp_path)
    assert main(["report", "latest", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == ID_C
    install(monkeypatch, tmp_path / "empty")
    assert main(["report", "latest", "--json"]) == 0
    assert capsys.readouterr().out.strip() == "null"