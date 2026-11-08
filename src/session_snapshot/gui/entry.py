"""GUI entry point for sessionctl-gui / sessiongui."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from session_snapshot.gui.main_window import MainWindow
from session_snapshot.gui.settings import SettingsStore
from session_snapshot.services.factory import create_default_service

def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Session Snapshot")
    app.setOrganizationName("linux-session-snapshot")

    store = SettingsStore()
    # Create the service inside MainWindow's default behavior
    window = MainWindow(SettingsStore())
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
