import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6 import __version__ as pyside_version  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_pyside_version_is_at_least_6_6():
    major, minor = (int(part) for part in pyside_version.split(".")[:2])
    assert (major, minor) >= (6, 6)


def test_qt_runs_on_the_offscreen_platform(qapp):
    assert qapp.platformName() == "offscreen"


def test_a_widget_can_be_created_and_resized(qapp):
    label = QLabel("hello")
    label.resize(120, 30)
    assert label.text() == "hello"
    assert (label.width(), label.height()) == (120, 30)