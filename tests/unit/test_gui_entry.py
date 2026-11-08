"""Offscreen tests for the GUI entry point and the sessionctl gui subcommand."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6.QtSvg")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_entry_main_builds_window_without_loop(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from session_snapshot.gui.entry import main as gui_main

    assert gui_main([], run=False) == 0
    assert QApplication.instance() is not None


def test_gui_package_has_main_module():
    from pathlib import Path

    import session_snapshot.gui as gui_pkg

    main_path = Path(gui_pkg.__file__).parent / "__main__.py"
    assert main_path.is_file()


def test_cli_has_gui_subcommand():
    from session_snapshot.cli.main import _build_parser

    ns = _build_parser().parse_args(["gui"])
    assert ns.command == "gui"
    assert callable(ns.handler)


def test_cli_gui_handler_dispatches_to_entry(monkeypatch):
    from session_snapshot.cli import main as cli_main

    calls = []

    def fake_gui_main(argv):
        calls.append(argv)
        return 0

    monkeypatch.setattr("session_snapshot.gui.entry.main", fake_gui_main)
    assert cli_main._cmd_gui(None) == 0
    assert calls == [[]]
