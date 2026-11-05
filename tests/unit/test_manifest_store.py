import os
import stat

import pytest

from session_snapshot.store.manifests import ManifestError, ManifestStore


def test_save_and_load_roundtrip(tmp_path, make_manifest):
    store = ManifestStore(tmp_path / "sessions")
    m = make_manifest()
    store.save(m)
    assert store.load("study-setup") == m


def test_file_and_directory_permissions(tmp_path, make_manifest):
    store = ManifestStore(tmp_path / "sessions")
    path = store.save(make_manifest())
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700


def test_no_temp_files_left_behind(tmp_path, make_manifest):
    store = ManifestStore(tmp_path / "sessions")
    store.save(make_manifest())
    assert sorted(os.listdir(store.root)) == ["study-setup.json"]


def test_overwrite_replaces_existing(tmp_path, make_manifest):
    store = ManifestStore(tmp_path / "sessions")
    store.save(make_manifest())
    m2 = make_manifest(
        session={
            "id": "study-setup",
            "name": "Renamed",
            "saved_at": "2026-11-06T10:00:00+00:00",
            "tool_version": "0.1.0",
        }
    )
    store.save(m2)
    assert store.load("study-setup").session.name == "Renamed"


def test_invalid_session_id_rejected(tmp_path):
    store = ManifestStore(tmp_path / "sessions")
    with pytest.raises(ManifestError):
        store.load("../evil")
    with pytest.raises(ManifestError):
        store.delete("../evil")


def test_corrupt_json_raises_manifest_error(tmp_path):
    store = ManifestStore(tmp_path / "sessions")
    store.root.mkdir(parents=True)
    (store.root / "broken.json").write_text("{not json")
    with pytest.raises(ManifestError):
        store.load("broken")


def test_schema_violation_raises_manifest_error(tmp_path):
    store = ManifestStore(tmp_path / "sessions")
    store.root.mkdir(parents=True)
    (store.root / "bad.json").write_text('{"schema_version": 1}')
    with pytest.raises(ManifestError):
        store.load("bad")


def test_list_and_delete(tmp_path, make_manifest):
    store = ManifestStore(tmp_path / "sessions")
    store.save(make_manifest("study-setup"))
    store.save(make_manifest("a-session"))
    assert store.list_ids() == ["a-session", "study-setup"]
    store.delete("a-session")
    assert store.list_ids() == ["study-setup"]
    with pytest.raises(ManifestError):
        store.delete("a-session")


def test_load_missing_raises(tmp_path):
    store = ManifestStore(tmp_path / "sessions")
    with pytest.raises(ManifestError):
        store.load("nope")
