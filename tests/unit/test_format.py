from datetime import datetime, timezone

from session_snapshot.cli.format import (
    format_adapters,
    format_doctor,
    format_manifest,
    format_preview,
    format_restore_report,
    format_save_report,
    format_session_list,
)
from session_snapshot.models.adapter_types import ActionKind
from session_snapshot.models.manifest import (
    AppEntry,
    EnvironmentInfo,
    Manifest,
    SessionMeta,
)
from session_snapshot.models.results import Capability, Reason, Status
from session_snapshot.models.summaries import (
    AdapterInfo,
    SessionList,
    SessionProblem,
    SessionSummary,
)
from session_snapshot.report.models import (
    AppPreview,
    AppRestoreOutcome,
    AppSaveOutcome,
    RestorePreview,
    RestoreReport,
    SaveReport,
    SaveStatus,
)


def _manifest() -> Manifest:
    return Manifest(
        schema_version=1,
        session=SessionMeta(
            id="study",
            name="Study",
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


def _now():
    return datetime.now(timezone.utc)


# ---- existing session/formatter tests ---------------------------------


def test_format_session_list_empty():
    assert "No saved sessions" in format_session_list(SessionList())


def test_format_session_list_with_data():
    m = _manifest()
    sl = SessionList(
        sessions=[
            SessionSummary(
                session_id=m.session.id,
                name=m.session.name,
                description="",
                saved_at=m.session.saved_at,
                app_count=1,
                adapter_ids=["fake"],
                desktop="XFCE",
                session_type="x11",
            )
        ]
    )
    out = format_session_list(sl)
    assert "study" in out and "Study" in out and "XFCE" in out


def test_format_session_list_with_problem():
    sl = SessionList(
        problems=[SessionProblem(session_id="bad", message="corrupt")]
    )
    out = format_session_list(sl)
    assert "Problems:" in out and "bad: corrupt" in out


def test_format_manifest():
    out = format_manifest(_manifest())
    assert "Study" in out and "fake-1" in out and "cwd=/tmp" in out


def test_format_adapters_empty():
    assert "No adapters" in format_adapters([])


def test_format_adapters_with_capability():
    info = AdapterInfo(
        adapter_id="fake",
        version=1,
        compatibility_class=2,
        capabilities=[Capability(name="cwd", supported=True)],
        error=None,
    )
    out = format_adapters([info])
    assert "fake" in out and "cwd" in out


def test_format_adapters_with_error():
    info = AdapterInfo(
        adapter_id="broken",
        version=1,
        compatibility_class=2,
        capabilities=[],
        error="boom",
    )
    assert "ERROR: boom" in format_adapters([info])


def test_format_doctor_sections():
    class _Stub:
        store = None

        def adapters(self):
            return []

    out = format_doctor(_Stub())
    for section in ("Environment", "Executables", "Adapters"):
        assert section in out


# ---- new report formatters --------------------------------------------


def test_format_save_report():
    now = _now()
    r = SaveReport(
        session_id="study",
        started_at=now,
        finished_at=now,
        outcomes=[
            AppSaveOutcome(
                instance_id="fake-1",
                adapter_id="fake",
                status=SaveStatus.CAPTURED,
                reason=Reason.OK,
                message="captured",
            )
        ],
        warnings=["careful"],
        manifest_path="/tmp/study.json",
    )
    out = format_save_report(r)
    assert "Saved session 'study'" in out
    assert "/tmp/study.json" in out
    assert "fake-1" in out
    assert "captured" in out
    assert "careful" in out


def test_format_preview():
    p = RestorePreview(
        session_id="study",
        session_name="Study",
        apps=[
            AppPreview(
                instance_id="fake-1",
                adapter_id="fake",
                action=ActionKind.LAUNCH,
                reason=Reason.OK,
                message="will open",
            ),
            AppPreview(
                instance_id="fake-2",
                adapter_id="fake",
                action=ActionKind.SKIP,
                reason=Reason.PATH_MISSING,
                message="gone",
                unavailable_paths=["/gone"],
            ),
        ],
        warnings=["w1"],
    )
    out = format_preview(p)
    assert "Preview for 'Study'" in out
    assert "launch" in out and "skip" in out
    assert "will open" in out and "gone" in out
    assert "/gone" in out
    assert "w1" in out


def test_format_restore_report_counts():
    now = _now()
    r = RestoreReport(
        session_id="study",
        started_at=now,
        finished_at=now,
        outcomes=[
            AppRestoreOutcome(
                instance_id="a",
                adapter_id="fake",
                action=ActionKind.LAUNCH,
                status=Status.RESTORED,
                reason=Reason.OK,
                message="ok",
            ),
            AppRestoreOutcome(
                instance_id="b",
                adapter_id="fake",
                action=ActionKind.LAUNCH,
                status=Status.FAILED,
                reason=Reason.ADAPTER_ERROR,
                message="boom",
            ),
        ],
    )
    out = format_restore_report(r)
    assert "Restored session 'study'" in out
    assert "1 restored" in out
    assert "1 failed" in out
    assert "ok" in out and "boom" in out
