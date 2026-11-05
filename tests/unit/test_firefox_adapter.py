import time
from unittest.mock import patch

import pytest

from session_snapshot.adapters.base import AdapterError
from session_snapshot.adapters.firefox import (
    FirefoxAdapter,
    _is_firefox_main,
    _read_startup_page,
    _resolve_default_profile,
)
from session_snapshot.models.adapter_types import (
    ActionKind,
    AppInstance,
    CaptureContext,
    DiscoveryContext,
    ProcessInfo,
    RestoreContext,
    RestoreHandle,
    RestorePlan,
)
from session_snapshot.models.manifest import AppEntry
from session_snapshot.models.results import Reason, Status


def _proc(pid, name, ppid=None, argv=None, cwd=None):
    return ProcessInfo(
        pid=pid, ppid=ppid, name=name, argv=argv or [], cwd=cwd
    )


def _entry(profile_path="/tmp/fake-profile", startup_page=3):
    return AppEntry.model_validate(
        {
            "instance_id": "firefox-100",
            "app_id": "firefox.desktop",
            "adapter": {"id": "browser_firefox", "version": 1},
            "compatibility_class": 1,
            "launch": {
                "type": "argv",
                "executable": "/usr/bin/firefox",
                "args": ["--profile", profile_path],
            },
            "state": {
                "profile_path": profile_path,
                "browser_startup_page": startup_page,
            },
            "capture": {"status": "captured"},
        }
    )


def _make_profile(tmp_path, startup_page_line=None):
    firefox_dir = tmp_path / ".mozilla" / "firefox"
    firefox_dir.mkdir(parents=True)
    profile_dir = firefox_dir / "abc.default"
    profile_dir.mkdir()
    (firefox_dir / "profiles.ini").write_text(
        "[Profile0]\n"
        "Name=default\n"
        "IsRelative=1\n"
        "Path=abc.default\n"
        "Default=1\n"
        "[General]\n"
        "StartWithLastProfile=1\n"
        "Version=2\n"
    )
    prefs = profile_dir / "prefs.js"
    if startup_page_line is not None:
        prefs.write_text(startup_page_line + "\n")
    else:
        prefs.write_text('user_pref("browser.somethingelse", true);\n')
    return firefox_dir, profile_dir


def test_is_firefox_main_excludes_contentproc():
    assert _is_firefox_main("firefox", ["/usr/lib/firefox/firefox"])
    assert not _is_firefox_main(
        "firefox", ["/usr/lib/firefox/firefox", "-contentproc", "x"]
    )
    assert not _is_firefox_main("chrome", ["/usr/lib/firefox/firefox"])


def test_read_startup_page_parses_three(tmp_path):
    _, profile_dir = _make_profile(
        tmp_path, 'user_pref("browser.startup.page", 3);'
    )
    assert _read_startup_page(profile_dir) == 3


def test_read_startup_page_returns_none_when_unset(tmp_path):
    _, profile_dir = _make_profile(tmp_path, None)
    assert _read_startup_page(profile_dir) is None


def test_resolve_default_profile_from_profiles_ini(tmp_path):
    firefox_dir, profile_dir = _make_profile(tmp_path, None)
    assert _resolve_default_profile(firefox_dir) == profile_dir


def test_detect_finds_firefox_main_only():
    procs = [
        _proc(100, "firefox", argv=["/usr/lib/firefox/firefox"]),
        _proc(
            101,
            "firefox",
            argv=["/usr/lib/firefox/firefox", "-contentproc", "x"],
        ),
        _proc(102, "bash", argv=["/bin/bash"]),
    ]
    with patch(
        "session_snapshot.adapters.firefox.shutil.which",
        return_value="/usr/bin/firefox",
    ), patch(
        "session_snapshot.adapters.firefox._find_firefox_dir",
        return_value=None,
    ):
        instances = FirefoxAdapter().detect(
            DiscoveryContext(processes=tuple(procs))
        )
    assert len(instances) == 1
    assert instances[0].pid == 100


def test_detect_returns_empty_when_not_installed():
    with patch(
        "session_snapshot.adapters.firefox.shutil.which", return_value=None
    ):
        assert FirefoxAdapter().detect(DiscoveryContext()) == []


def test_capture_with_profile_flag(tmp_path):
    _, profile_dir = _make_profile(
        tmp_path, 'user_pref("browser.startup.page", 3);'
    )
    proc = _proc(
        100,
        "firefox",
        argv=["/usr/lib/firefox/firefox", "--profile", str(profile_dir)],
    )
    instance = AppInstance(
        instance_id="firefox-100",
        adapter_id="browser_firefox",
        pid=100,
        app_id="firefox.desktop",
        label="abc.default",
    )
    with patch(
        "session_snapshot.adapters.firefox.shutil.which",
        return_value="/usr/bin/firefox",
    ):
        entry = FirefoxAdapter().capture(
            instance, CaptureContext(processes=(proc,))
        )
    assert entry.state["profile_path"] == str(profile_dir)
    assert entry.state["browser_startup_page"] == 3
    assert entry.launch.args == ["--profile", str(profile_dir)]


def test_capture_raises_when_process_gone():
    instance = AppInstance(
        instance_id="firefox-999", adapter_id="browser_firefox", pid=999
    )
    with pytest.raises(AdapterError) as exc:
        FirefoxAdapter().capture(instance, CaptureContext(processes=()))
    assert exc.value.reason is Reason.PATH_MISSING


def test_plan_restore_skips_when_not_installed():
    with patch(
        "session_snapshot.adapters.firefox.shutil.which", return_value=None
    ):
        plan = FirefoxAdapter().plan_restore(_entry(), RestoreContext())
    assert plan.action is ActionKind.SKIP
    assert plan.reason is Reason.NOT_INSTALLED


def test_plan_restore_skips_when_profile_missing(tmp_path):
    with patch(
        "session_snapshot.adapters.firefox.shutil.which",
        return_value="/usr/bin/firefox",
    ):
        plan = FirefoxAdapter().plan_restore(
            _entry(profile_path=str(tmp_path / "nope")), RestoreContext()
        )
    assert plan.action is ActionKind.SKIP
    assert plan.reason is Reason.PATH_MISSING


def test_plan_restore_skips_when_pref_unset(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    with patch(
        "session_snapshot.adapters.firefox.shutil.which",
        return_value="/usr/bin/firefox",
    ):
        plan = FirefoxAdapter().plan_restore(
            _entry(profile_path=str(profile), startup_page=None),
            RestoreContext(),
        )
    assert plan.action is ActionKind.SKIP
    assert plan.reason is Reason.UNSUPPORTED
    assert "browser.startup.page" in plan.message


def test_plan_restore_skips_when_pref_is_one(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    with patch(
        "session_snapshot.adapters.firefox.shutil.which",
        return_value="/usr/bin/firefox",
    ):
        plan = FirefoxAdapter().plan_restore(
            _entry(profile_path=str(profile), startup_page=1),
            RestoreContext(),
        )
    assert plan.action is ActionKind.SKIP
    assert "browser.startup.page=1" in plan.message


def test_plan_restore_launches_when_pref_is_three(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    with patch(
        "session_snapshot.adapters.firefox.shutil.which",
        return_value="/usr/bin/firefox",
    ):
        plan = FirefoxAdapter().plan_restore(
            _entry(profile_path=str(profile), startup_page=3),
            RestoreContext(),
        )
    assert plan.action is ActionKind.LAUNCH


def test_plan_restore_skips_when_already_running_with_policy(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    proc = _proc(100, "firefox", argv=["/usr/lib/firefox/firefox"])
    ctx = RestoreContext(
        processes=(proc,), duplicate_policy="skip_if_running"
    )
    with patch(
        "session_snapshot.adapters.firefox.shutil.which",
        return_value="/usr/bin/firefox",
    ):
        plan = FirefoxAdapter().plan_restore(
            _entry(profile_path=str(profile), startup_page=3), ctx
        )
    assert plan.action is ActionKind.SKIP
    assert plan.reason is Reason.ALREADY_RUNNING


def test_restore_launches_with_profile(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    entry = _entry(profile_path=str(profile), startup_page=3)
    plan = RestorePlan(action=ActionKind.LAUNCH, message="go")
    with patch(
        "session_snapshot.adapters.firefox.subprocess.Popen"
    ) as popen:
        popen.return_value.pid = 4321
        handle = FirefoxAdapter().restore(entry, plan, RestoreContext())
    args, kwargs = popen.call_args
    assert args[0] == ["/usr/bin/firefox", "--profile", str(profile)]
    assert kwargs.get("shell") is not True
    assert handle.pid == 4321


def test_verify_restored_when_process_appears():
    handle = RestoreHandle(
        instance_id="firefox-100", pid=4321, launched_at=time.time()
    )
    with patch(
        "session_snapshot.adapters.firefox._live_firefox_pids",
        return_value=[(5000, time.time())],
    ):
        result = FirefoxAdapter().verify(_entry(), handle, RestoreContext())
    assert result.status is Status.RESTORED
    assert result.reason is Reason.OK


def test_verify_partial_on_timeout():
    handle = RestoreHandle(
        instance_id="firefox-100", pid=4321, launched_at=time.time()
    )
    with patch(
        "session_snapshot.adapters.firefox._live_firefox_pids",
        return_value=[],
    ), patch(
        "session_snapshot.adapters.firefox.time.monotonic",
        side_effect=[0.0, 100.0],
    ), patch("time.sleep"):
        result = FirefoxAdapter().verify(_entry(), handle, RestoreContext())
    assert result.status is Status.PARTIAL
    assert result.reason is Reason.TIMEOUT


def test_capabilities_declare_limitations():
    caps = FirefoxAdapter().capabilities()
    by_name = {c.name: c for c in caps}
    assert by_name["session_restore"].supported is True
    assert "browser.startup.page" in by_name["session_restore"].limitation
    assert by_name["tabs_content"].supported is False
    assert by_name["profile_secrets"].supported is False
