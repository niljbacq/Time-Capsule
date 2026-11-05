from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from session_snapshot.adapters.base import SessionAdapter
from session_snapshot.adapters.registry import AdapterRegistry
from session_snapshot.cli.main import main
from session_snapshot.models.adapter_types import (
    ActionKind,
    AppInstance,
    DiscoveryContext,
    ProcessInfo,
    RestoreContext,
    RestoreHandle,
    RestorePlan,
)
from session_snapshot.models.manifest import (
    AppEntry,
    EnvironmentInfo,
    Manifest,
    SessionMeta,
)
from session_snapshot.models.results import Capability, OpResult
from session_snapshot.services.session_service import SessionService
from session_snapshot.store.manifests import ManifestStore


def _proc(pid: int, ppid: int, name: str, cwd: str | None = None) -> ProcessInfo:
    return ProcessInfo(pid=pid, ppid=ppid, name=name, cwd=cwd)


class _FakeAdapter(SessionAdapter):
    adapter_id = "fake"
    version = 1
    compatibility_class = 2

    def capabilities(self) -> list[Capability]:
        return [Capability(name="cwd", supported=True)]

    def detect(self, ctx: DiscoveryContext) -> list[AppInstance]:
        return [
            AppInstance(
                instance_id=f"fake-{p.pid}",
                adapter_id="fake",
                pid=p.pid,
                app_id="fake.app",
            )
            for p in ctx.processes
            if p.name == "fakeapp"
        ]

    def capture(self, instance: AppInstance, ctx) -> AppEntry:
        return AppEntry.model_validate(
            {
                "instance_id": instance.instance_id,
                "app_id": instance.app_id,
                "adapter": {"id": "fake", "version": 1},
                "compatibility_class": 2,
                "launch": {"executable": "fakeapp"},
                "state": {"cwd": "/tmp"},
                "capture": {"status": "captured"},
            }
        )

    def plan_restore(
        self, snapshot: AppEntry, ctx: RestoreContext
    ) -> RestorePlan:
        return RestorePlan(action=ActionKind.LAUNCH, message="launch fake")

    def restore(
        self, snapshot: AppEntry, plan: RestorePlan, ctx: RestoreContext
    ) -> RestoreHandle:
        return RestoreHandle(instance_id=snapshot.instance_id, pid=1234)

    def verify(
        self, snapshot: AppEntry, handle: RestoreHandle, ctx: RestoreContext
    ) -> OpResult:
        return OpResult.restored("fake ok")


class _FakeProcessSource:
    def __init__(self, procs=()) -> None:
        self._procs = tuple(procs)

    def snapshot(self):
        return self._procs


def _service(tmp_path, procs=()) -> SessionService:
    registry = AdapterRegistry()
    registry.register(_FakeAdapter())
    return SessionService(
        registry, ManifestStore(tmp_path), _FakeProcessSource(procs)
    )


def _empty_service(tmp_path) -> SessionService:
    return SessionService(
        AdapterRegistry(), ManifestStore(tmp_path), _FakeProcessSource(())
    )


def _install_factory(monkeypatch, service) -> None:
    monkeypatch.setattr(
        "session_snapshot.cli.main.SERVICE_FACTORY",
        lambda *a, **kw: service,
    )


def _seed(tmp_path, session_id="study", name="Study") -> Manifest:
    manifest = Manifest(
        schema_version=1,
        session=SessionMeta(
            id=session_id,
            name=name,
            saved_at=datetime.now(timezone.utc),
            tool_version="0.1.0",
        ),
        environment=EnvironmentInfo(desktop="XFCE", session_type="x11"),
        apps=[
            AppEntry.model_validate(
                {
                    "instance_id": "fake-1",
                    "adapter": {"id": "fake", "version": 1},
                    "compatibility_class": 2,
                    "launch": {"executable": "fakeapp"},
                    "state": {"cwd": "/tmp"},
                    "capture": {"status": "captured"},
                }
            )
        ],
    )
    ManifestStore(tmp_path).save(manifest)
    return manifest


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "sessionctl" in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "usage: sessionctl" in capsys.readouterr().out


def test_list_empty(monkeypatch, tmp_path, capsys):
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["list"]) == 0
    assert "No saved sessions." in capsys.readouterr().out


def test_list_with_manifest(monkeypatch, tmp_path, capsys):
    _seed(tmp_path)
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "study" in out and "Study" in out


def test_list_json(monkeypatch, tmp_path, capsys):
    _seed(tmp_path)
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sessions"][0]["session_id"] == "study"


def test_show_manifest(monkeypatch, tmp_path, capsys):
    _seed(tmp_path)
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["show", "study"]) == 0
    out = capsys.readouterr().out
    assert "Study" in out and "fake-1" in out


def test_show_missing_returns_2(monkeypatch, tmp_path, capsys):
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["show", "nope"]) == 2
    assert "error" in capsys.readouterr().err


def test_adapters_shows_fake(monkeypatch, tmp_path, capsys):
    _install_factory(monkeypatch, _service(tmp_path))
    assert main(["adapters"]) == 0
    assert "fake" in capsys.readouterr().out


def test_doctor_prints_sections(monkeypatch, tmp_path, capsys):
    _install_factory(monkeypatch, _service(tmp_path))
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    for section in ("Environment", "Executables", "Adapters"):
        assert section in out


def test_report_returns_2(monkeypatch, tmp_path, capsys):
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["report", "latest"]) == 2
    assert "planned for a later phase" in capsys.readouterr().err

# ---- save / preview / restore --------------------------------------------


def test_save_with_fake_adapter(monkeypatch, tmp_path, capsys):
    service = _service(tmp_path, procs=(_proc(10, 1, "fakeapp", "/tmp"),))
    _install_factory(monkeypatch, service)
    rc = main(["save", "study", "--name", "Study"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Saved session 'study'" in out
    assert "fake-10" in out


def test_save_json_roundtrip(monkeypatch, tmp_path, capsys):
    service = _service(tmp_path, procs=(_proc(10, 1, "fakeapp", "/tmp"),))
    _install_factory(monkeypatch, service)
    assert main(["save", "study", "--name", "Study", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "study"
    assert payload["outcomes"][0]["instance_id"] == "fake-10"


def test_preview_shows_launch(monkeypatch, tmp_path, capsys):
    service = _service(tmp_path, procs=(_proc(10, 1, "fakeapp", "/tmp"),))
    service.save("study", "Study")
    _install_factory(monkeypatch, service)
    assert main(["preview", "study"]) == 0
    out = capsys.readouterr().out
    assert "Preview for 'Study'" in out
    assert "launch" in out


def test_restore_dry_run_does_not_call_restore(monkeypatch, tmp_path, capsys):
    service = _service(tmp_path, procs=(_proc(10, 1, "fakeapp", "/tmp"),))
    service.save("study", "Study")

    def _boom(*a, **kw):
        raise AssertionError("restore() must not run under --dry-run")

    monkeypatch.setattr(service, "restore", _boom)
    _install_factory(monkeypatch, service)
    assert main(["restore", "study", "--dry-run"]) == 0
    assert "Preview for 'Study'" in capsys.readouterr().out


def test_restore_executes_and_reports(monkeypatch, tmp_path, capsys):
    service = _service(tmp_path, procs=(_proc(10, 1, "fakeapp", "/tmp"),))
    service.save("study", "Study")
    _install_factory(monkeypatch, service)
    assert main(["restore", "study"]) == 0
    out = capsys.readouterr().out
    assert "Restored session 'study'" in out
    assert "restored" in out


def test_restore_missing_session_returns_2(monkeypatch, tmp_path, capsys):
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["restore", "nope"]) == 2
    assert "error" in capsys.readouterr().err

# ---- delete / rename / duplicate ----------------------------------------


def test_delete_with_yes(monkeypatch, tmp_path, capsys):
    _seed(tmp_path)
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["delete", "study", "-y"]) == 0
    assert "deleted study" in capsys.readouterr().out
    assert main(["show", "study"]) == 2


def test_delete_confirmation_aborts(monkeypatch, tmp_path, capsys):
    _seed(tmp_path)
    _install_factory(monkeypatch, _empty_service(tmp_path))
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    assert main(["delete", "study"]) == 1
    assert main(["show", "study"]) == 0


def test_rename(monkeypatch, tmp_path, capsys):
    _seed(tmp_path)
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["rename", "study", "New Name"]) == 0
    out = capsys.readouterr().out
    assert "renamed study" in out
    assert "New Name" in out


def test_duplicate(monkeypatch, tmp_path, capsys):
    _seed(tmp_path)
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["duplicate", "study", "copy", "--name", "Copy"]) == 0
    assert "duplicated study to copy" in capsys.readouterr().out


def test_duplicate_conflict_returns_2(monkeypatch, tmp_path, capsys):
    _seed(tmp_path)
    _install_factory(monkeypatch, _empty_service(tmp_path))
    assert main(["duplicate", "study", "study", "--name", "Same"]) == 2
    assert "error" in capsys.readouterr().err
