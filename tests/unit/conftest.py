import pytest

from session_snapshot.models.manifest import Manifest


@pytest.fixture
def make_manifest():
    def _make(session_id: str = "study-setup", **overrides):
        data = {
            "schema_version": 1,
            "session": {
                "id": session_id,
                "name": "Study Setup",
                "saved_at": "2026-11-05T10:00:00+00:00",
                "tool_version": "0.1.0",
            },
            "environment": {
                "desktop": "XFCE",
                "session_type": "x11",
                "window_manager": "xfwm4",
            },
            "apps": [
                {
                    "instance_id": "terminal-1",
                    "app_id": "xfce4-terminal.desktop",
                    "adapter": {"id": "terminal", "version": 1},
                    "compatibility_class": 2,
                    "launch": {
                        "executable": "xfce4-terminal",
                        "args": ["--working-directory=/tmp"],
                    },
                    "state": {"cwd": "/tmp"},
                    "windows": [
                        {
                            "window_id": "w1",
                            "geometry": {"x": 0, "y": 0, "width": 800, "height": 600},
                        }
                    ],
                    "capture": {"status": "captured"},
                }
            ],
        }
        data.update(overrides)
        return Manifest.model_validate(data)

    return _make
