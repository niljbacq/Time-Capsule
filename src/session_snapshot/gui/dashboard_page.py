"""Dashboard page: primary Save action for the current desktop."""

from __future__ import annotations

import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from session_snapshot.gui import styles
from session_snapshot.gui.controllers.sessions_controller import SessionsController
from session_snapshot.report.models import SaveReport

PAGE_TITLE = "Dashboard"
PURPOSE_TEXT = "Save and restore the arrangement of your desktop applications."


def session_id_from_name(name: str) -> str:
    """Turn a human name into a session id: lowercase letters, digits, hyphens."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "session"


class DashboardPage(QWidget):
    """Dashboard with the primary Save action."""

    session_saved = Signal(str)

    def __init__(
        self, controller: SessionsController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setObjectName(styles.CONTENT)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.title_label = QLabel(PAGE_TITLE, self)
        self.title_label.setObjectName(styles.PAGE_TITLE)
        layout.addWidget(self.title_label)

        self.purpose_label = QLabel(PURPOSE_TEXT, self)
        self.purpose_label.setObjectName(styles.MUTED)
        self.purpose_label.setWordWrap(True)
        layout.addWidget(self.purpose_label)

        action_bar = QHBoxLayout()
        self.save_button = QPushButton("Save current desktop\u2026", self)
        self.save_button.setObjectName(styles.PRIMARY_BUTTON)
        self.save_button.clicked.connect(self._on_save_clicked)
        action_bar.addWidget(self.save_button)
        action_bar.addStretch(1)
        layout.addLayout(action_bar)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName(styles.MUTED)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName(styles.STATUS_ERROR)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        layout.addStretch(1)

    def _on_save_clicked(self) -> None:
        name, ok = QInputDialog.getText(self, "Save session", "Session name:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        session_id = session_id_from_name(name)
        self._controller.refresh()
        if any(s.session_id == session_id for s in self._controller.sessions):
            reply = QMessageBox.question(
                self,
                "Overwrite session",
                f"A session with id '{session_id}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        self.save_session(name)

    def save_session(self, name: str) -> SaveReport | None:
        """Save the current desktop under the given name. No prompt."""
        session_id = session_id_from_name(name)
        report = self._controller.save_session(session_id, name)
        if report is None:
            error = self._controller.last_error or "unknown error"
            self.error_label.setText(f"Could not save: {error}")
            self.status_label.setText("")
            return None
        self._show_success(name, report)
        self.session_saved.emit(session_id)
        return report

    def _show_success(self, name: str, report: SaveReport) -> None:
        counts = report.counts()
        parts = [f"{counts.get('captured', 0)} captured"]
        if counts.get("failed", 0):
            parts.append(f"{counts['failed']} failed")
        if counts.get("excluded", 0):
            parts.append(f"{counts['excluded']} excluded")
        self.status_label.setText(f"Saved '{name}' \u2014 {', '.join(parts)}.")
        self.error_label.setText("")
