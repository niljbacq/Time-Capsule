from datetime import datetime, timezone

from session_snapshot.cli.format import (
    format_adapters,
    format_doctor,
    format_manifest,
    format_session_list,
)
from session_snapshot.models.manifest import (
    AppEntry,
    EnvironmentInfo,
    Manifest,
    SessionMeta,
)
from session_snapshot.models.results import Capability
from session_snapshot.models.summaries import (
    AdapterInfo,
    SessionList,
    SessionProblem,
    SessionSummary,
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


def test_format_session_list_empty():
    out = format_session_list(SessionList())
    assert "No saved sessions" in out


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
    assert "study" in out
    assert "Study" in out
    assert "XFCE" in out


def test_format_session_list_with_problem():
    sl = SessionList(
        problems=[SessionProblem(session_id="bad", message="corrupt")]
    )
    out = format_session_list(sl)
    assert "Problems:" in out
    assert "bad: corrupt" in out


def test_format_manifest():
    out = format_manifest(_manifest())
    assert "Study" in out
    assert "fake-1" in out
    assert "cwd=/tmp" in out


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
    assert "fake" in out
    assert "cwd" in out


def test_format_adapters_with_error():
    info = AdapterInfo(
        adapter_id="broken",
        version=1,
        compatibility_class=2,
        capabilities=[],
        error="boom",
    )
    out = format_adapters([info])
    assert "ERROR: boom" in out


def test_format_doctor_sections():
    class _Stub:
        store = None

        def adapters(self):
            return []

    out = format_doctor(_Stub())
    for section in ("Environment", "Executables", "Adapters"):
        assert section in out
