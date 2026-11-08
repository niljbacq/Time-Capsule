import json
import os
import stat
from dataclasses import replace
from pathlib import Path

from session_snapshot.gui.settings import (
    GuiSettings,
    SettingsStore,
    default_config_dir,
)


def store_in(tmp_path):
    return SettingsStore(tmp_path / "gui.json")


def test_defaults_when_file_is_missing(tmp_path):
    s = store_in(tmp_path).load()
    assert s == GuiSettings()
    assert s.theme == "system"
    assert s.sidebar_collapsed is False
    assert s.sessions_view == "list"
    assert (s.window_width, s.window_height) == (1200, 800)
    assert s.window_x is None and s.window_y is None
    assert s.window_maximized is False


def test_round_trip(tmp_path):
    store = store_in(tmp_path)
    saved = GuiSettings(
        theme="dark",
        sidebar_collapsed=True,
        sessions_view="grid",
        window_width=1000,
        window_height=700,
        window_x=50,
        window_y=60,
        window_maximized=True,
    )
    store.save(saved)
    assert store.load() == saved


def test_corrupt_files_fall_back_to_defaults(tmp_path):
    store = store_in(tmp_path)
    store.path.write_text("{not json", encoding="utf-8")
    assert store.load() == GuiSettings()
    store.path.write_bytes(b"\xff\xfe\x00")
    assert store.load() == GuiSettings()


def test_non_object_json_falls_back_to_defaults(tmp_path):
    store = store_in(tmp_path)
    store.path.write_text("[1, 2, 3]", encoding="utf-8")
    assert store.load() == GuiSettings()


def test_one_bad_field_does_not_discard_the_others(tmp_path):
    store = store_in(tmp_path)
    store.path.write_text(
        json.dumps(
            {
                "theme": "dark",
                "sidebar_collapsed": "yes",
                "sessions_view": "cards",
                "window_width": "wide",
            }
        ),
        encoding="utf-8",
    )
    s = store.load()
    assert s.theme == "dark"
    assert s.sidebar_collapsed is False
    assert s.sessions_view == "list"
    assert s.window_width == 1200


def test_window_size_is_clamped(tmp_path):
    store = store_in(tmp_path)
    store.path.write_text(
        json.dumps({"window_width": 100, "window_height": 99999}), encoding="utf-8"
    )
    s = store.load()
    assert (s.window_width, s.window_height) == (800, 16384)


def test_window_position_must_be_an_integer(tmp_path):
    store = store_in(tmp_path)
    store.path.write_text(
        json.dumps({"window_x": "left", "window_y": 40}), encoding="utf-8"
    )
    s = store.load()
    assert s.window_x is None
    assert s.window_y == 40


def test_unknown_keys_survive_a_round_trip(tmp_path):
    store = store_in(tmp_path)
    store.path.write_text(
        json.dumps({"future_option": 7, "theme": "light"}), encoding="utf-8"
    )
    loaded = store.load()
    store.save(replace(loaded, theme="dark"))
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw["future_option"] == 7
    assert raw["theme"] == "dark"


def test_file_and_directory_are_private(tmp_path):
    store = SettingsStore(tmp_path / "cfg" / "gui.json")
    store.save(GuiSettings())
    assert stat.S_IMODE(os.stat(store.path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(store.path.parent).st_mode) == 0o700


def test_save_leaves_no_temporary_files(tmp_path):
    store = store_in(tmp_path)
    store.save(GuiSettings())
    store.save(GuiSettings(theme="light"))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["gui.json"]


def test_default_path_honors_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert default_config_dir() == tmp_path / "linux-session-snapshot"
    assert SettingsStore().path == tmp_path / "linux-session-snapshot" / "gui.json"


def test_default_path_falls_back_to_home_config(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_config_dir() == Path(tmp_path) / ".config" / "linux-session-snapshot"