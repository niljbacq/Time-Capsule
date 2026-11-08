"""Sessions library, list view. Presentation only; no service or core import."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from session_snapshot.gui import styles
from session_snapshot.gui.controllers.sessions_controller import SessionsController

PAGE_TITLE = "Sessions"
COLUMNS = ("Name", "Saved", "Apps", "Environment")
COLUMN_WIDTHS = (300, 160, 60, 150)


def format_saved_at(value: datetime) -> str:
    """Format a tz-aware timestamp for the Saved column, in local time."""
    try:
        local = value.astimezone()
    except (ValueError, OSError):
        local = value
    return local.strftime("%Y-%m-%d %H:%M")


class SessionsPage(QWidget):
    """One table of saved sessions, plus empty / problems / error states."""

    def __init__(self, controller: SessionsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setObjectName(styles.CONTENT)
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.title_label = QLabel(PAGE_TITLE, self)
        self.title_label.setObjectName(styles.PAGE_TITLE)
        layout.addWidget(self.title_label)

        self.summary_label = QLabel("", self)
        self.summary_label.setObjectName(styles.MUTED)
        layout.addWidget(self.summary_label)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName(styles.STATUS_ERROR)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.problems_label = QLabel("", self)
        self.problems_label.setObjectName(styles.STATUS_WARNING)
        self.problems_label.setWordWrap(True)
        layout.addWidget(self.problems_label)

        self.empty_label = QLabel(
            "No saved sessions yet.\nUse Save on the Dashboard to create one.", self
        )
        self.empty_label.setObjectName(styles.MUTED)
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, len(COLUMNS), self)
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        for index, width in enumerate(COLUMN_WIDTHS):
            self.table.setColumnWidth(index, width)
        layout.addWidget(self.table, 1)

    # -- data flow --------------------------------------------------------

    def refresh(self) -> None:
        self._controller.refresh()
        self._render()

    def _render(self) -> None:
        sessions = self._controller.sessions
        self._render_rows(sessions)
        self._render_error()
        self._render_problems()
        self._render_visibility(sessions)

    def _render_rows(self, sessions) -> None:
        self.table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            name = QTableWidgetItem(s.name or s.session_id)
            name.setData(Qt.UserRole, s.session_id)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(format_saved_at(s.saved_at)))
            self.table.setItem(row, 2, QTableWidgetItem(str(s.app_count)))
            env = s.desktop or s.session_type or "unknown"
            self.table.setItem(row, 3, QTableWidgetItem(env))

    def _render_error(self) -> None:
        err = self._controller.last_error
        self.error_label.setText(f"Could not load sessions: {err}" if err else "")
        self.error_label.setVisible(bool(err))

    def _render_problems(self) -> None:
        problems = self._controller.problems
        if problems:
            lines = [f"{p.session_id}: {p.message}" for p in problems]
            self.problems_label.setText(
                "Some sessions could not be read:\n" + "\n".join(lines)
            )
            self.problems_label.setVisible(True)
        else:
            self.problems_label.setText("")
            self.problems_label.setVisible(False)

    def _render_visibility(self, sessions) -> None:
        self.empty_label.setVisible(self._controller.is_empty)
        self.table.setVisible(bool(sessions))
        count = len(sessions)
        if self._controller.last_error:
            self.summary_label.setText("")
        elif count == 1:
            self.summary_label.setText("1 saved session")
        elif count > 1:
            self.summary_label.setText(f"{count} saved sessions")
        else:
            self.summary_label.setText("")

    # -- accessors (used by controllers and tests) ------------------------

    def row_count(self) -> int:
        return self.table.rowCount()

    def session_id_at(self, row: int) -> str | None:
        item = self.table.item(row, 0)
        return None if item is None else item.data(Qt.UserRole)

    def selected_session_id(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.session_id_at(rows[0].row())