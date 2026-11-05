import pytest
from pydantic import ValidationError

from session_snapshot.models.manifest import Manifest


def _dump(manifest):
    return manifest.model_dump(mode="json")


def test_naive_timestamp_rejected(make_manifest):
    data = _dump(make_manifest())
    data["session"]["saved_at"] = "2026-11-05T10:00:00"
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_unknown_schema_version_rejected(make_manifest):
    data = _dump(make_manifest())
    data["schema_version"] = 2
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_duplicate_instance_ids_rejected(make_manifest):
    data = _dump(make_manifest())
    data["apps"].append(dict(data["apps"][0]))
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_shell_metacharacters_in_executable_rejected(make_manifest):
    data = _dump(make_manifest())
    data["apps"][0]["launch"]["executable"] = "xfce4-terminal; rm -rf ~"
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_unknown_field_rejected(make_manifest):
    data = _dump(make_manifest())
    data["surprise"] = 1
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_bad_session_id_rejected(make_manifest):
    data = _dump(make_manifest())
    data["session"]["id"] = "../evil"
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)
