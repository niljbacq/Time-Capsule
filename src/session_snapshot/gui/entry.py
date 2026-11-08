"""GUI entry point for sessiongui, sessionctl gui, or python -m session_snapshot.gui.

The event loop is only entered when run=True: that lets the tests build and
show the window offscreen without blocking.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from session_snapshot.gui.main_window import MainWindow
from session_snapshot.gui.settings import SettingsStore


def main(argv: Sequence[str] | None = None, *, run: bool = True) -> int:
    args = list(argv) if argv is not None else sys.argv
    app = QApplication.instance() or QApplication(args)
    app.setApplicationName("Session Snapshot")
    app.setOrganizationName("linux-session-snapshot")

    window = MainWindow(SettingsStore())
    window.show()

    if not run:
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
